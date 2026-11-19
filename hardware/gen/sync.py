#!/usr/bin/env python3
"""Bring the routed board in line with design.py without discarding the routing.

Usage: python3 sync.py

For every part, this swaps the footprint if design.py now names a different
one (keeping its position, side and rotation), updates the value and assigns
the pad nets. Where a pad has moved away or changed net, the tracks that ran
to or across it are removed, back to the nearest via, junction or other pad,
along with any via that is left with nothing attached. Everything
else is left alone. A part that is not on the board yet is added if layout.py
gives it a fixed position. Run route.py or finish.py afterwards to connect
what is new and reconnect what was removed.
"""
import os

import pcbnew

import board as board_builder
import build
import layout
import libs

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.normpath(os.path.join(HERE, ".."))
NEAR = pcbnew.FromMM(0.005)


def pad_layer(pad):
    if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
        return None
    return pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu


def snapshot(fp):
    return [(pad.GetBoundingBox(), pad_layer(pad), pad.GetNetname(), pad.GetPosition()) for pad in fp.Pads()]


def replace(board, old, lib, name, project_dir):
    new = pcbnew.FootprintLoad(board_builder.footprint_dir(lib, project_dir), name)
    if new is None:
        raise SystemExit(f"missing footprint {lib}:{name}")
    new.SetFPID(pcbnew.LIB_ID(lib, name))
    new.SetReference(old.GetReference())
    board.Add(new)
    new.SetPosition(old.GetPosition())
    if old.IsFlipped():
        new.Flip(new.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    new.SetOrientationDegrees(old.GetOrientationDegrees())
    new.Reference().SetVisible(False)
    new.Value().SetVisible(False)
    board.Remove(old)
    return new


def place(board, part, project_dir, origin=(100.0, 60.0)):
    """Add a part at its fixed position in layout.py, on the back face."""
    lib, name = part["footprint"].split(":")
    x, y, rot = layout.FIXED[part["ref"]]
    fp = pcbnew.FootprintLoad(board_builder.footprint_dir(lib, project_dir), name)
    if fp is None:
        raise SystemExit(f"missing footprint {lib}:{name}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(part["ref"])
    board.Add(fp)
    fp.SetPosition(board_builder.point(origin[0] + x, origin[1] + y))
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    return fp


def same(a, b):
    return abs(a.x - b.x) <= NEAR and abs(a.y - b.y) <= NEAR


def crosses(box, track):
    """True if any part of a track lies inside a box."""
    a, b = track.GetStart(), track.GetEnd()
    return any(box.Contains(pcbnew.VECTOR2I(a.x + (b.x - a.x) * i // 40, a.y + (b.y - a.y) * i // 40))
               for i in range(41))


class Ripper:
    """Works on lists taken once, up front: pcbnew's own iterators stop
    returning usable objects after items have been removed from the board."""

    def __init__(self, board):
        self.board = board
        self.removed = 0
        self.pads = [(pad.GetBoundingBox(), pad_layer(pad), pad.GetNetname())
                     for fp in board.GetFootprints() for pad in fp.Pads()]
        self.tracks = list(board.GetTracks())

    def drop(self, track):
        self.tracks.remove(track)
        self.board.Remove(track)
        self.removed += 1

    def anchored(self, point, layer, net):
        for box, pad_on, pad_net in self.pads:
            if pad_net == net and pad_on in (None, layer) and box.Contains(point):
                return True
        return any(t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == net and same(t.GetPosition(), point)
                   for t in self.tracks)

    def at(self, point, layer, net):
        return [t for t in self.tracks if t.Type() != pcbnew.PCB_VIA_T and t.GetNetname() == net
                and t.GetLayer() == layer and (same(t.GetStart(), point) or same(t.GetEnd(), point))]

    def orphan_via(self, point, net):
        """Remove a via that the run ended at if nothing else uses it."""
        for via in [t for t in self.tracks if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == net
                    and same(t.GetPosition(), point) and not t.IsLocked()]:
            if not any(t.Type() != pcbnew.PCB_VIA_T and t.GetNetname() == net
                       and (same(t.GetStart(), point) or same(t.GetEnd(), point)) for t in self.tracks):
                self.drop(via)

    def walk(self, point, layer, net):
        """Remove the dangling run of track that now ends at this point."""
        self._walk(point, layer, net)
        self.orphan_via(point, net)

    def _walk(self, point, layer, net):
        while not self.anchored(point, layer, net):
            found = self.at(point, layer, net)
            if len(found) != 1 or found[0].IsLocked():
                return
            track = found[0]
            end = track.GetEnd() if same(track.GetStart(), point) else track.GetStart()
            point.x, point.y = end.x, end.y
            self.drop(track)

    def clear_pad(self, box, layer, net):
        """Remove the tracks and vias of a net that end inside a pad it has left."""
        ends = []
        # Grown by a track's half-width and clearance, to catch tracks that
        # only brush the pad.
        box = pcbnew.BOX2I(box.GetOrigin(), box.GetSize())
        box.Inflate(pcbnew.FromMM(0.2))
        for t in list(self.tracks):
            if t.GetNetname() != net or t.IsLocked():
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                if box.Contains(t.GetPosition()):
                    pos = t.GetPosition()
                    ends += [(pcbnew.VECTOR2I(pos.x, pos.y), l) for l in (pcbnew.F_Cu, pcbnew.B_Cu)]
                    self.drop(t)
            elif layer in (None, t.GetLayer()) and crosses(box, t):
                ends += [(pcbnew.VECTOR2I(p.x, p.y), t.GetLayer()) for p in (t.GetStart(), t.GetEnd())
                         if not box.Contains(p)]
                self.drop(t)
        for point, track_layer in ends:
            self.walk(point, track_layer, net)


def main():
    import design
    parts = build.resolve(design.PARTS)
    libs.write(PROJECT_DIR, [libs.usb_c_midmount(), libs.battery_pads(), libs.module_footprint(), libs.battery_socket(),
                             libs.fpc_connector(), libs.inductor()], [libs.clock_symbol()])
    pcb = os.path.join(PROJECT_DIR, "inkotp.kicad_pcb")
    board = pcbnew.LoadBoard(pcb)
    stale = []
    for part in parts:
        if not part["footprint"]:
            continue
        ref = part["ref"]
        lib, name = part["footprint"].split(":")
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            if ref not in layout.FIXED:
                raise SystemExit(f"{ref} is not on the board and has no fixed position in layout.py")
            print(f"{ref}: added")
            fp = place(board, part, PROJECT_DIR)
        before = snapshot(fp)
        if str(fp.GetFPID().GetLibItemName()) != name:
            print(f"{ref}: footprint {fp.GetFPID().GetLibItemName()} -> {name}")
            fp = replace(board, fp, lib, name, PROJECT_DIR)
        fp.SetValue(part["value"])
        for pad in fp.Pads():
            wanted = part["pin_nets"].get(pad.GetNumber(), "")
            if pad.GetNetname() != wanted:
                net = board.FindNet(wanted)
                if net is None:
                    net = pcbnew.NETINFO_ITEM(board, wanted)
                    board.Add(net)
                pad.SetNet(net)
        after = snapshot(fp)
        for box, layer, net, centre in before:
            if net and not any(n == net and l == layer and b.Contains(centre) for b, l, n, _ in after):
                stale.append((ref, box, layer, net))
    ripper = Ripper(board)
    for ref, box, layer, net in stale:
        ripper.clear_pad(box, layer, net)
    print(f"{len(stale)} pads moved or changed net:", " ".join(sorted({f"{r}[{n}]" for r, _, _, n in stale})))
    print(f"{ripper.removed} tracks and vias removed")
    board_builder.fill_zones(board)
    pcbnew.SaveBoard(pcb, board)
    libs.project_file(PROJECT_DIR)


if __name__ == "__main__":
    main()
