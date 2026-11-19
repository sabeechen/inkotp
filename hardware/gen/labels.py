#!/usr/bin/env python3
"""Print on the board what each part is and what each pad and switch does.

Usage: python3 labels.py

Every part gets its value (or a short name) in silkscreen beside it, on its
own face. Each label goes against its part where it is clear of pads, other
parts, other labels and the board's edges, and nearer to its own part than to
any other. Identical parts that sit together share one label with a count.
Labels with no such spot are tried further away, then replaced by the part's
reference (which bom.csv explains), and any that still do not fit are listed.
Running this again replaces the labels it made before. It does not look at
tracks; vias are covered by solder mask, so text may cross them.
"""
import os

import pcbnew

import board as board_builder
import build
import layout
import libs

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.normpath(os.path.join(HERE, ".."))
ORIGIN = (100.0, 60.0)

SIZE = (0.8, 0.7, 0.15)   # height, width, line; the board's rules allow no smaller
MARGIN = 0.12             # between a label and anything else
PAD_MARGIN = 0.15 + SIZE[2] / 2   # JLCPCB asks for 0.15 mm from ink to a pad
# (how far from its part a label may sit, how much nearer than to any other part)
PASSES = [(0.6, 0.1), (1.5, 0.0), (2.6, -9.0)]

# What to print instead of the part's value. None prints nothing.
NAMES = {
    "U1": None, "U2": "AP2112K", "U3": "MCP73832", "U4": "USBLC6", "U5": "RV-3032",
    "R1": None, "Q1": None, "Q2": None, "Q3": None, "Q4": None,
    "D1": "BAV70", "D2": "NSR0530", "D3": "NSR0530", "D4": "NSR0530",
    "L1": None, "BZ1": "BUZZER", "J1": "USB-C", "J2": None, "J3": "PANEL", "J4": "BATT",
    "SW1": "UP", "SW2": "SEL", "SW3": "DOWN", "SW4": "RESET",
    "TP1": "3V3", "TP2": "GND", "TP3": "EN", "TP4": "UP",
}
# Labels for single pads: (ref, pad number, which pad of that number, text).
# Only the battery's positive pad is marked: there is no room beside the other.
PADS = [("J2", "1", 0, "BAT+"), ("J3", "1", 0, "1"), ("J3", "24", 0, "24")]
GROUP = 1.0  # identical parts this close together share one label
# Labels at a set place: (text, x, y, face, rotation). The module's goes where
# its antenna will sit, which has no pads. Q1 to Q3 have no room for a name,
# so each carries its reference and a key in the open area below the panel
# connector says which part that is. Q4 has no room even for that; it is the
# only unmarked three-pin part. The battery socket's + is above its positive
# lead.
PLACED = [("ESP32-S3-MINI-1", 9.0, 3.0, "back", 0),
          ("Q1", 10.6, 46.83, "back", 90), ("Q2", 10.6, 50.92, "back", 90), ("Q3", 20.15, 47.45, "back", 0),
          ("+", 8.4, 47.95, "back", 0), ("5.1k", 9.6, 46.5, "back", 90),
          ("Q1 AO3401A", 20.0, 31.4, "back", 0), ("Q2 Q3 BSS138", 20.0, 32.5, "back", 0),
          ("Q4 AO3400A", 20.0, 33.6, "back", 0), ("R2 5.1k", 20.0, 34.7, "back", 0),
          ("C11 100n", 20.0, 35.8, "back", 0), ("C16 1u 25V", 20.0, 36.9, "back", 0)]


def box_of(item):
    box = item.GetBoundingBox()
    mm = pcbnew.ToMM
    return (mm(box.GetLeft()) - ORIGIN[0], mm(box.GetTop()) - ORIGIN[1],
            mm(box.GetRight()) - ORIGIN[0], mm(box.GetBottom()) - ORIGIN[1])


def body(fp):
    """The box around a part's pads and its outline on the fabrication layer.
    This is tighter than its courtyard, which leaves room labels can use."""
    boxes = [box_of(pad) for pad in fp.Pads()]
    boxes += [box_of(shape) for shape in fp.GraphicalItems()
              if shape.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab) and shape.GetClass() != "PCB_TEXT"]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def gap(a, b):
    """Distance between two boxes; 0 if they touch or overlap."""
    dx = max(a[0] - b[2], b[0] - a[2], 0)
    dy = max(a[1] - b[3], b[1] - a[3], 0)
    return (dx * dx + dy * dy) ** 0.5


def text_size(board, text, size):
    """Width and height of a label. KiCad measures the width; the height it
    reports includes the blank space between lines, so that is worked out
    here from the letter height."""
    height, width, line = size
    item = pcbnew.PCB_TEXT(board)
    item.SetText(text)
    item.SetTextSize(pcbnew.VECTOR2I(board_builder.mm(width), board_builder.mm(height)))
    item.SetTextThickness(board_builder.mm(line))
    lines = text.count("\n") + 1
    return pcbnew.ToMM(item.GetBoundingBox().GetWidth()), (lines - 1) * height * 1.62 + height + line


def candidates(anchor, w, h, reach):
    """Boxes for a label of this size against each side of an anchor box,
    nearest first. A label slides along a side only while its middle stays
    over the part."""
    x0, y0, x1, y1 = anchor
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    out = []
    for step in range(0, int(reach / 0.1) + 1):
        d = MARGIN + step * 0.1
        for tw, th, rot in ((w, h, 0), (h, w, 90)):
            for k in range(0, 40):
                for slide in ((k * 0.1, -k * 0.1) if k else (0.0,)):
                    cost = d + abs(slide) * 0.5
                    if abs(slide) <= (x1 - x0) / 2:
                        out.append((cost, (cx + slide - tw / 2, y1 + d, cx + slide + tw / 2, y1 + d + th), rot))
                        out.append((cost, (cx + slide - tw / 2, y0 - d - th, cx + slide + tw / 2, y0 - d), rot))
                    if abs(slide) <= (y1 - y0) / 2:
                        out.append((cost, (x1 + d, cy + slide - th / 2, x1 + d + tw, cy + slide + th / 2), rot))
                        out.append((cost, (x0 - d - tw, cy + slide - th / 2, x0 - d, cy + slide + th / 2), rot))
    out.sort(key=lambda c: c[0])
    return out


def add_text(board, text, box, rot, size, back):
    height, width, line = size
    item = pcbnew.PCB_TEXT(board)
    item.SetText(text)
    item.SetLayer(pcbnew.B_SilkS if back else pcbnew.F_SilkS)
    item.SetTextSize(pcbnew.VECTOR2I(board_builder.mm(width), board_builder.mm(height)))
    item.SetTextThickness(board_builder.mm(line))
    item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    item.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    item.SetMirrored(back)
    item.SetPosition(board_builder.point(ORIGIN[0] + (box[0] + box[2]) / 2, ORIGIN[1] + (box[1] + box[3]) / 2))
    item.SetTextAngleDegrees(rot)
    board.Add(item)
    placed[0] += 1


placed = [0]


def board_labels(board):
    return [d for d in board.GetDrawings()
            if d.GetClass() == "PCB_TEXT" and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]


def main():
    import design
    parts = {p["ref"]: p for p in build.resolve(design.PARTS)}
    pcb = os.path.join(PROJECT_DIR, "inkotp.kicad_pcb")
    board = pcbnew.LoadBoard(pcb)
    old = board_labels(board)
    if old:
        # pcbnew's objects are unusable once anything has been removed, so
        # save and load again before reading the board.
        for item in old:
            board.Remove(item)
        pcbnew.SaveBoard(pcb, board)
        board = pcbnew.LoadBoard(pcb)
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}

    # What a label must stay clear of, per face: (box, owner, kind).
    blocked = {False: [], True: []}
    for ref, fp in footprints.items():
        back = fp.IsFlipped()
        blocked[back].append((body(fp), ref, "part"))
        for pad in fp.Pads():
            through = pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            for face in ((False, True) if through else (back,)):
                blocked[face].append((box_of(pad), ref + "." + pad.GetNumber(), "pad"))
        for shape in fp.GraphicalItems():
            if shape.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                blocked[shape.GetLayer() == pcbnew.B_SilkS].append((box_of(shape), "silk", "silk"))
    w, h = layout.WIDTH, layout.HEIGHT
    notch = (-1.0, layout.USB_Y - layout.USB_HALF, layout.USB_DEPTH, layout.USB_Y + layout.USB_HALF)
    edges = [(-9, -9, 0.25, h + 9), (w - 0.25, -9, w + 9, h + 9), (-9, -9, w + 9, 0.25), (-9, h - 0.25, w + 9, h + 9),
             tuple(v + d for v, d in zip(notch, (-0.25, -0.25, 0.25, 0.25))),
             tuple(v + d for v, d in zip(layout.SLOT, (-0.25, -0.25, 0.25, 0.25)))]
    for face in blocked:
        blocked[face] += [(edge, "edge", "edge") for edge in edges]

    def place(text, anchor, back, own, inside, reach, lead):
        """own: the parts the label names. inside: whether it may sit within
        their outlines (pad labels). lead: how much nearer the label must be
        to its own part than to any other, so it is clear which it names."""
        tw, th = text_size(board, text, SIZE)
        for _, box, rot in candidates(anchor, tw, th, reach):
            mine = gap(box, anchor)
            if all((inside and owner in own) or (
                    gap(box, other) >= (PAD_MARGIN if kind == "pad" else MARGIN) and (kind != "part" or owner in own or gap(box, other) >= mine + lead))
                    for other, owner, kind in blocked[back]):
                add_text(board, text, box, rot, SIZE, back)
                blocked[back].append((box, "label", "label"))
                return True
        return False

    for text, x, y, face, rot in PLACED:
        tw, th = text_size(board, text, SIZE)
        if rot:
            tw, th = th, tw
        box = (x - tw / 2, y - th / 2, x + tw / 2, y + th / 2)
        add_text(board, text, box, rot, SIZE, face == "back")
        blocked[face == "back"].append((box, "label", "label"))

    jobs = []
    for ref, pad_number, index, text in PADS:
        fp = footprints[ref]
        pad = [p for p in fp.Pads() if p.GetNumber() == pad_number][index]
        # A pad's label may sit inside its own part's outline.
        jobs.append((text, box_of(pad), fp.IsFlipped(), (ref, ref + "." + pad_number), True, f"{ref} pad {pad_number}"))
    # Identical parts that sit together share one label with a count.
    groups = []
    for ref, fp in sorted(footprints.items()):
        text = NAMES.get(ref, parts[ref]["value"])
        if not text:
            continue
        box, back = body(fp), fp.IsFlipped()
        near = [g for g in groups if g[0] == text and g[1] == back and any(gap(box, b) < GROUP for b in g[2])]
        merged = [text, back, [box], [ref]]
        for g in near:
            merged[2] += g[2]
            merged[3] += g[3]
            groups.remove(g)
        groups.append(merged)
    for text, back, boxes, refs in groups:
        anchor = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
        text = text.replace(" ", "\n") + (f"\nx{len(refs)}" if len(refs) > 1 else "")
        jobs.append((text, anchor, back, tuple(refs), False, " ".join(refs)))
    # Long labels first: they have the fewest places to go. Each pass allows
    # labels further from their part and less clearly its own.
    jobs.sort(key=lambda j: -len(j[0]))
    loose, failed = [], []
    for reach, lead in PASSES:
        left = []
        for job in jobs:
            text, anchor, back, own, inside, what = job
            if not place(text, anchor, back, own, inside, reach, lead):
                left.append(job)
            elif (reach, lead) != PASSES[0]:
                loose.append(f"{what} ({text})".replace("\n", " "))
        jobs = left
    # Where the name does not fit, the reference is shorter and bom.csv says
    # what it is.
    by_ref, failed = [], []
    for text, anchor, back, own, inside, what in jobs:
        if not inside and any(place("\n".join(own), anchor, back, own, inside, reach, lead) for reach, lead in PASSES):
            by_ref.append(f"{what} ({text})".replace("\n", " "))
        else:
            failed.append(f"{what} ({text})".replace("\n", " "))
    print(f"{placed[0]} labels placed")
    if loose:
        print(f"{len(loose)} placed less close to their part:", ", ".join(loose))
    if by_ref:
        print(f"{len(by_ref)} labelled with their reference instead:", ", ".join(by_ref))
    if failed:
        print(f"{len(failed)} with no room:", ", ".join(failed))
    pcbnew.SaveBoard(pcb, board)
    libs.project_file(PROJECT_DIR)


if __name__ == "__main__":
    main()
