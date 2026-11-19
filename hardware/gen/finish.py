#!/usr/bin/env python3
"""Finish connections the autorouter left open.

Usage: python3 finish.py REF.PAD[:REACH[:GRID]] [...]

Ground and 3.3 V each own an inner layer, so a pad on one of those nets only
needs a via. For each such pad named, this looks for the nearest spot where a
via fits with clearance to all other copper and joins it to the pad with a
straight track. A pad on any other net is routed on the outer layers to the
nearest copper of its own net, searching REACH millimetres around the pad
(default 5) on a grid of GRID millimetres (default 0.05). The pours are then
refilled and the board saved. Run KiCad's design rule check afterwards; this
script's own clearance test is conservative but approximate.
"""
import math
import os
import sys

import pcbnew

import board as board_builder
import libs

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.normpath(os.path.join(HERE, ".."))
VIA, DRILL, TRACK, CLEAR, EDGE = 0.45, 0.2, 0.2, 0.15, 0.35
PLANES = ("GND", "+3V3")


def seg_dist(p, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def rect_dist(p, r):
    dx = max(r[0] - p[0], 0, p[0] - r[2])
    dy = max(r[1] - p[1], 0, p[1] - r[3])
    return math.hypot(dx, dy)


class Obstacles:
    """Copper and edges, as distances a new via or track must keep."""

    def __init__(self, board, net):
        mm = pcbnew.ToMM
        self.tracks, self.vias, self.pads, self.edges, self.keepouts = [], [], [], [], []
        self.clearance = CLEAR
        for t in board.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                self.vias.append(((mm(t.GetPosition().x), mm(t.GetPosition().y)), mm(t.GetWidth(pcbnew.F_Cu)) / 2,
                                  t.GetNetname() == net))
            elif t.GetNetname() != net:
                self.tracks.append(((mm(t.GetStart().x), mm(t.GetStart().y)), (mm(t.GetEnd().x), mm(t.GetEnd().y)),
                                    mm(t.GetWidth()) / 2, t.GetLayer()))
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                box = pad.GetBoundingBox()
                rect = (mm(box.GetLeft()), mm(box.GetTop()), mm(box.GetRight()), mm(box.GetBottom()))
                through = pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
                layer = None if through else (pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
                self.pads.append((rect, layer, pad.GetNetname() == net and not through))
        for d in board.GetDrawings():
            if d.GetLayer() == pcbnew.Edge_Cuts:
                self.edges.append(((mm(d.GetStart().x), mm(d.GetStart().y)), (mm(d.GetEnd().x), mm(d.GetEnd().y))))
        for z in board.Zones():
            if z.GetIsRuleArea():
                box = z.GetBoundingBox()
                self.keepouts.append((mm(box.GetLeft()), mm(box.GetTop()), mm(box.GetRight()), mm(box.GetBottom())))

    def clear(self, p, radius, layer):
        """True if a round piece of copper of this radius fits at p. layer None
        means every layer (a via)."""
        for a, b in self.edges:
            if seg_dist(p, a, b) < radius + EDGE:
                return False
        for r in self.keepouts:
            if rect_dist(p, r) < radius:
                return False
        for centre, r, same in self.vias:
            gap = math.hypot(p[0] - centre[0], p[1] - centre[1]) - radius - r
            if same and layer is not None:
                continue  # a track may run into a via of its own net
            if gap < (0.3 if same else self.clearance):
                return False
        for a, b, half, tl in self.tracks:
            if (layer is None or tl == layer) and seg_dist(p, a, b) < radius + half + self.clearance:
                return False
        for rect, pl, same in self.pads:
            if same:
                continue
            if (layer is None or pl is None or pl == layer) and rect_dist(p, rect) < radius + self.clearance:
                return False
        return True


def finish(board, ref, number, pad=None):
    mm = pcbnew.ToMM
    if pad is None:
        pad = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == number)
    net = pad.GetNetname()
    layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
    start = (mm(pad.GetPosition().x), mm(pad.GetPosition().y))
    obstacles = Obstacles(board, net)
    for step in range(3, 40):
        radius = step * 0.1
        for k in range(48):
            angle = 2 * math.pi * k / 48
            via = (start[0] + radius * math.cos(angle), start[1] + radius * math.sin(angle))
            if not obstacles.clear(via, VIA / 2, None):
                continue
            n = max(2, int(radius / 0.04))
            line = [(start[0] + (via[0] - start[0]) * i / n, start[1] + (via[1] - start[1]) * i / n) for i in range(n + 1)]
            if not all(obstacles.clear(q, TRACK / 2, layer) for q in line):
                continue
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(board_builder.point(*start))
            track.SetEnd(board_builder.point(*via))
            track.SetLayer(layer)
            track.SetWidth(board_builder.mm(TRACK))
            track.SetNet(pad.GetNet())
            board.Add(track)
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(board_builder.point(*via))
            v.SetWidth(pcbnew.F_Cu, board_builder.mm(VIA))
            v.SetDrill(board_builder.mm(DRILL))
            v.SetNet(pad.GetNet())
            board.Add(v)
            print(f"{ref}.{number} [{net}]: via {radius:.1f} mm away at ({via[0] - 100:.2f}, {via[1] - 60:.2f})")
            return True
    print(f"{ref}.{number} [{net}]: no room for a via within 4 mm")
    return False


def connect(board, ref, number, reach=5.0, grid=0.05, pad=None):
    """Route a signal pad to the nearest copper of its own net on the outer
    layers: a shortest-path search over a fine grid around the pad, changing
    face through new vias where it has to."""
    import heapq
    mm = pcbnew.ToMM
    if pad is None:
        pad = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == number)
    net = pad.GetNetname()
    start = (mm(pad.GetPosition().x), mm(pad.GetPosition().y))
    start_layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
    width = 0.127
    obstacles = Obstacles(board, net)
    obstacles.clearance = 0.13  # the board's rule is 0.127; finish() and bridge() keep more
    near = lambda q, extra=0.0: abs(q[0] - start[0]) < reach + 1 + extra and abs(q[1] - start[1]) < reach + 1 + extra
    obstacles.tracks = [t for t in obstacles.tracks if near(t[0], 3) or near(t[1], 3)]
    obstacles.vias = [v for v in obstacles.vias if near(v[0])]
    obstacles.pads = [q for q in obstacles.pads if near(((q[0][0] + q[0][2]) / 2, (q[0][1] + q[0][3]) / 2), 8)]
    own = pad.GetBoundingBox()
    own = (mm(own.GetLeft()), mm(own.GetTop()), mm(own.GetRight()), mm(own.GetBottom()))

    # Places the route may end: this net's vias, tracks and other pads, except
    # copper the pad already reaches.
    P = lambda v: (mm(v.x), mm(v.y))
    items = []  # (points that touch other copper, layer or None for all, kind, object)
    for t in board.GetTracks():
        if t.GetNetname() != net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            items.append(([P(t.GetPosition())], None, "via", t))
        elif t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
            items.append(([P(t.GetStart()), P(t.GetEnd())], t.GetLayer(), "track", t))
    for fp in board.GetFootprints():
        for other in fp.Pads():
            if other.GetNetname() == net:
                layer = pcbnew.F_Cu if other.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
                items.append(([P(other.GetPosition())], layer, "pad", other))

    def touches(a, b):
        if a[1] is not None and b[1] is not None and a[1] != b[1]:
            return False
        for x, y in ((a, b), (b, a)):
            for q in x[0]:
                if y[2] == "pad":
                    box = y[3].GetBoundingBox()
                    if rect_dist(q, (mm(box.GetLeft()), mm(box.GetTop()), mm(box.GetRight()), mm(box.GetBottom()))) == 0:
                        return True
                elif y[2] == "via":
                    if math.hypot(q[0] - y[0][0][0], q[1] - y[0][0][1]) < VIA / 2:
                        return True
                elif seg_dist(q, y[0][0], y[0][1]) < 0.01:
                    return True
        return False

    reached = [next(i for i, item in enumerate(items) if item[2] == "pad" and item[3].GetPosition() == pad.GetPosition())]
    for i in reached:
        reached += [j for j, item in enumerate(items) if j not in reached and touches(items[i], item)]
    goals = {}

    def goal(q, layer):
        if near(q, -1):
            goals.setdefault((round((q[0] - start[0]) / grid), round((q[1] - start[1]) / grid), layer), q)

    for i, (points, layer, kind, _) in enumerate(items):
        if i in reached:
            continue
        if kind == "track":
            a, b = points
            n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / (grid / 2)))
            for k in range(n + 1):
                goal((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n), layer)
        else:
            for l in ((pcbnew.F_Cu, pcbnew.B_Cu) if layer is None else (layer,)):
                goal(points[0], l)
    if not goals:
        print(f"{ref}.{number} [{net}]: no unconnected copper of this net within {reach} mm")
        return False

    limit = int(reach / grid)
    free = {}

    def ok(ix, iy, layer):
        key = (ix, iy, layer)
        if key not in free:
            q = (start[0] + ix * grid, start[1] + iy * grid)
            free[key] = abs(ix) <= limit and abs(iy) <= limit and obstacles.clear(q, width / 2, layer)
        return free[key]

    first = (0, 0, start_layer)
    cost, came, queue, found = {first: 0.0}, {}, [(0.0, first)], None
    while queue:
        c, node = heapq.heappop(queue)
        if c > cost.get(node, 1e9):
            continue
        if node in goals:
            found = node
            break
        ix, iy, layer = node
        steps = [((ix + dx, iy + dy, layer), math.hypot(dx, dy)) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
        other = pcbnew.F_Cu if layer == pcbnew.B_Cu else pcbnew.B_Cu
        steps.append(((ix, iy, other), 30.0))
        for nxt, step in steps:
            if nxt[2] != layer:
                q = (start[0] + ix * grid, start[1] + iy * grid)
                if rect_dist(q, own) < 0.35 or not obstacles.clear(q, VIA / 2, None) or not ok(*nxt):
                    continue
            elif nxt not in goals and not ok(*nxt):
                continue
            if c + step < cost.get(nxt, 1e9):
                cost[nxt] = c + step
                came[nxt] = node
                heapq.heappush(queue, (c + step, nxt))
    if found is None:
        print(f"{ref}.{number} [{net}]: no route found within {reach} mm")
        return False

    path = [found]
    while path[-1] in came:
        path.append(came[path[-1]])
    path.reverse()
    points = [((start[0] + ix * grid, start[1] + iy * grid), layer) for ix, iy, layer in path]
    points[-1] = (goals[found], found[2])
    # Merge runs of grid steps in one direction into single tracks.
    merged = points[:1]
    for prev, cur, nxt in zip(points, points[1:], points[2:] + [None]):
        straight = (nxt is not None and prev[1] == cur[1] == nxt[1] and abs(
            (cur[0][0] - prev[0][0]) * (nxt[0][1] - cur[0][1]) - (cur[0][1] - prev[0][1]) * (nxt[0][0] - cur[0][0])) < 1e-9)
        if not straight:
            merged.append(cur)
    points = merged
    vias = 0
    for prev, cur in zip(points, points[1:]):
        if cur[1] != prev[1]:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(board_builder.point(*prev[0]))
            v.SetWidth(pcbnew.F_Cu, board_builder.mm(VIA))
            v.SetDrill(board_builder.mm(DRILL))
            v.SetNet(pad.GetNet())
            board.Add(v)
            vias += 1
        else:
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(board_builder.point(*prev[0]))
            track.SetEnd(board_builder.point(*cur[0]))
            track.SetLayer(cur[1])
            track.SetWidth(board_builder.mm(width))
            track.SetNet(pad.GetNet())
            board.Add(track)
    print(f"{ref}.{number} [{net}]: routed with {vias} vias, ending at ({goals[found][0] - 100:.2f}, {goals[found][1] - 60:.2f})")
    return True


def bridge(board, net_name, x_range, y_range):
    """Join two halves of a plane that an inner-layer track has cut apart: a via
    on each side of the cut, linked by a short track on an outer layer. The
    cut runs north-south between the two x values given."""
    obstacles = Obstacles(board, net_name)
    net = board.FindNet(net_name)
    y = y_range[0]
    while y <= y_range[1]:
        for xa in (x_range[0] - 0.1 * i for i in range(12)):
            if not obstacles.clear((xa, y), VIA / 2, None):
                continue
            for xb in (x_range[1] + 0.1 * i for i in range(12)):
                if not obstacles.clear((xb, y), VIA / 2, None):
                    continue
                n = int((xb - xa) / 0.04)
                line = [(xa + (xb - xa) * i / n, y) for i in range(n + 1)]
                for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                    if all(obstacles.clear(q, TRACK / 2, layer) for q in line):
                        track = pcbnew.PCB_TRACK(board)
                        track.SetStart(board_builder.point(xa, y))
                        track.SetEnd(board_builder.point(xb, y))
                        track.SetLayer(layer)
                        track.SetWidth(board_builder.mm(0.3))
                        track.SetNet(net)
                        board.Add(track)
                        for x in (xa, xb):
                            v = pcbnew.PCB_VIA(board)
                            v.SetPosition(board_builder.point(x, y))
                            v.SetWidth(pcbnew.F_Cu, board_builder.mm(VIA))
                            v.SetDrill(board_builder.mm(DRILL))
                            v.SetNet(net)
                            board.Add(v)
                        print(f"{net_name} bridge at y = {y - 60:.2f}, x = {xa - 100:.2f} to {xb - 100:.2f}, on {board.GetLayerName(layer)}")
                        return True
        y += 0.1
    print(f"{net_name}: no room for a bridge")
    return False


def main():
    pcb = os.path.join(PROJECT_DIR, "inkotp.kicad_pcb")
    board = pcbnew.LoadBoard(pcb)
    for name in sys.argv[1:]:
        name, *options = name.split(":")
        ref, number = name.split(".")
        # Several pads can share a number (mounting pads, switch terminals).
        for pad in [p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == number]:
            if pad.GetNetname() in PLANES:
                finish(board, ref, number, pad)
            else:
                connect(board, ref, number, *[float(v) for v in options], pad=pad)
    board_builder.fill_zones(board)
    pcbnew.SaveBoard(pcb, board)
    libs.project_file(PROJECT_DIR)


if __name__ == "__main__":
    main()
