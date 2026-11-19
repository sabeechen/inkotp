"""Build the board file from the design: footprints, nets, outline and planes."""
import os

import pcbnew

SYSTEM_FOOTPRINTS = "/usr/share/kicad/footprints"


def mm(v):
    return pcbnew.FromMM(float(v))


def point(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def footprint_dir(lib, project_dir):
    if lib == "inkotp":
        return os.path.join(project_dir, "inkotp.pretty")
    return os.path.join(SYSTEM_FOOTPRINTS, lib + ".pretty")


def _courtyard(fp, front=False):
    fp.BuildCourtyardCaches()
    box = fp.GetCourtyard(pcbnew.F_CrtYd if front else pcbnew.B_CrtYd).BBox()
    if box.GetWidth() == 0:
        box = fp.GetBoundingBox(False)
    return [pcbnew.ToMM(v) for v in (box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom())]


def pad_position(fp, number, origin=(100.0, 60.0)):
    for pad in fp.Pads():
        if pad.GetNumber() == number:
            pos = pad.GetPosition()
            return pcbnew.ToMM(pos.x) - origin[0], pcbnew.ToMM(pos.y) - origin[1]
    raise KeyError(number)


def build(parts, fixed, regions, outline, cutouts, keepouts, project_dir, origin=(100.0, 60.0), gap=0.15,
          tracks=(), vias=(), extra=None):
    default_gap = gap
    """Coordinates are board millimetres seen from the front, origin at the
    board's top-left corner. Every part goes on the back face.

    fixed: ref -> (x, y, rotation).
    regions: list of (x0, y0, x1, y1, [ref or (ref, rotation), ...]) with an
    optional sixth item of options ("side": "front", "gap": millimetres);
    parts are packed in rows, left to right, in the order given.
    outline: list of (x, y) corners. cutouts: list of corner lists.
    """
    board = pcbnew.CreateEmptyBoard()
    board.SetCopperLayerCount(4)
    board.GetDesignSettings().SetBoardThickness(mm(1.0))
    ox, oy = origin
    nets = {}
    by_ref = {p["ref"]: p for p in parts}
    footprints = {}

    def net(name):
        if name not in nets:
            nets[name] = pcbnew.NETINFO_ITEM(board, name)
            board.Add(nets[name])
        return nets[name]

    def add(ref, x, y, rot, front=False):
        part = by_ref[ref]
        lib, name = part["footprint"].split(":")
        fp = pcbnew.FootprintLoad(footprint_dir(lib, project_dir), name)
        if fp is None:
            raise SystemExit(f"missing footprint {part['footprint']}")
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref)
        fp.SetValue(part["value"])
        board.Add(fp)
        fp.SetPosition(point(ox + x, oy + y))
        if not front:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            pad_net = part["pin_nets"].get(pad.GetNumber())
            if pad_net:
                pad.SetNet(net(pad_net))
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        footprints[ref] = fp
        return fp

    for ref, (x, y, rot) in fixed.items():
        add(ref, x, y, rot)

    problems = []
    for region in regions:
        x0, y0, x1, y1, refs = region[:5]
        options = region[5] if len(region) > 5 else {}
        front = options.get("side") == "front"
        gap = options.get("gap", default_gap)
        cx, cy, row = x0, y0, 0.0
        for item in refs:
            ref, rot = item if isinstance(item, tuple) else (item, 0)
            fp = add(ref, 0, 0, rot, front)
            left, top, right, bottom = _courtyard(fp, front)
            w, h = right - left, bottom - top
            if cx + w > x1 + 1e-6:
                cx, cy, row = x0, cy + row + gap, 0.0
            if cy + h > y1 + 1e-6:
                problems.append(f"{ref} does not fit in region at ({x0}, {y0})")
            pos = fp.GetPosition()
            fp.SetPosition(pcbnew.VECTOR2I(pos.x + mm(ox + cx - left), pos.y + mm(oy + cy - top)))
            cx += w + gap
            row = max(row, h)
    # Tie the module's centre ground pads to the inner ground plane before
    # routing, so the router works around the vias.
    if "U1" in footprints:
        centre = [p.GetPosition() for p in footprints["U1"].Pads() if p.GetNumber() == "61"]
        xs = sorted({p.x for p in centre})
        ys = sorted({p.y for p in centre})
        for x in [(a + b) // 2 for a, b in zip(xs, xs[1:])]:
            for y in [(a + b) // 2 for a, b in zip(ys, ys[1:])]:
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(pcbnew.VECTOR2I(x, y))
                via.SetWidth(pcbnew.F_Cu, mm(0.45))
                via.SetDrill(mm(0.2))
                via.SetNet(net("GND"))
                board.Add(via)

    # Hand-placed copper, locked so the autorouter leaves it alone.
    if extra:
        more_tracks, more_vias = extra(lambda ref, number: pad_position(footprints[ref], number, origin))
        tracks = list(tracks) + more_tracks
        vias = list(vias) + more_vias
    layers = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}
    for name, layer, width, points in tracks:
        for a, b in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(point(ox + a[0], oy + a[1]))
            track.SetEnd(point(ox + b[0], oy + b[1]))
            track.SetLayer(layers[layer])
            track.SetWidth(mm(width))
            track.SetNet(net(name))
            track.SetLocked(True)
            board.Add(track)
    for name, x, y in vias:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(point(ox + x, oy + y))
        via.SetWidth(pcbnew.F_Cu, mm(0.45))
        via.SetDrill(mm(0.2))
        via.SetNet(net(name))
        via.SetLocked(True)
        board.Add(via)

    placed = set(footprints)
    missing = [p["ref"] for p in parts if p["footprint"] and p["ref"] not in placed]
    if missing:
        problems.append("not placed: " + " ".join(missing))

    corners = [(ox + x, oy + y) for x, y in outline]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(point(*a))
        seg.SetEnd(point(*b))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(mm(0.1))
        board.Add(seg)

    for hole in cutouts:
        pts = [(ox + x, oy + y) for x, y in hole]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            seg = pcbnew.PCB_SHAPE(board)
            seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
            seg.SetStart(point(*a))
            seg.SetEnd(point(*b))
            seg.SetLayer(pcbnew.Edge_Cuts)
            seg.SetWidth(mm(0.1))
            board.Add(seg)

    for x0, y0, x1, y1 in keepouts:
        area = pcbnew.ZONE(board)
        area.SetIsRuleArea(True)
        area.SetLayerSet(pcbnew.LSET.AllCuMask())
        area.SetDoNotAllowTracks(True)
        area.SetDoNotAllowVias(True)
        area.SetDoNotAllowZoneFills(True) if hasattr(area, "SetDoNotAllowZoneFills") else area.SetDoNotAllowCopperPour(True)
        area.SetDoNotAllowPads(False)
        area.SetDoNotAllowFootprints(False)
        area.SetZoneName("Antenna")
        poly = area.Outline()
        poly.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            poly.Append(mm(ox + x), mm(oy + y))
        board.Add(area)

    # Inner planes: ground on one layer, 3.3 V on the other.
    for layer, name in ((pcbnew.In1_Cu, "GND"), (pcbnew.In2_Cu, "+3V3")):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(net(name))
        zone.SetAssignedPriority(0)
        zone.SetLocalClearance(mm(0.2))
        zone.SetMinThickness(mm(0.2))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        poly = zone.Outline()
        poly.NewOutline()
        for x, y in corners:
            poly.Append(mm(x), mm(y))
        board.Add(zone)
    return board, footprints, problems


def fill_zones(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
