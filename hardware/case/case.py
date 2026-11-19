"""A 3D-printed case for the InkOTP stick board.

Three printed parts, plus a dummy board for fit tests:

  tray    the back half: holds the board by its edges, and the cell below it
  bezel   the front half: frames the screen, hooks over the tray's top end and
          is held by four screws at the battery end
  button  a cap for one thumb switch; print three

Coordinates are the board's own, as in gen/layout.py: millimetres seen from the
front, x to the right, y down from the board's top edge. z is 0 on the board's
front face and positive towards the viewer, so the back of the board is at
z = -1.0. Solids are built with y negated, which keeps the front view the
right way round in a CAD program.

    case/.venv/bin/python case/case.py          # write case/out/*.stl and *.step
    case/.venv/bin/python case/case.py check    # also test the fit against the board

Sized for a 0.6 mm nozzle and 0.2 mm layers. Numbers marked UNVERIFIED come
from a drawing or a model, not from a part in the hand.
"""
import os
import subprocess
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gen"))
import layout  # noqa: E402

OUT = os.path.join(HERE, "out")

# ---- The board and what stands on it -------------------------------------

BW, BH = layout.WIDTH, layout.HEIGHT
BT = 1.0                      # board thickness
USB_Y, USB_HALF = layout.USB_Y, 4.47   # port centreline; half the shell's width
USB_SHELL = 3.16              # shell height. GCT's "1.0 mm offset" sinks it 1.0 mm
                              # into the board, so on this board it is flush with
                              # the front face and stands 2.16 mm off the back.
                              # UNVERIFIED on a part.
USB_OVERHANG = 0.5            # the shell's mouth beyond the board edge
SWITCH_Y = [layout.FIXED[s][1] for s in ("SW1", "SW2", "SW3")]
RESET_Y = layout.FIXED["SW4"][1]
SWITCH_H = 1.35               # switch height off the back face
PLUNGER_TIP = BW + 0.6        # x of a plunger's tip at rest (KiCad's model)
SWITCH_TRAVEL = 0.2           # UNVERIFIED: not read from Panasonic's drawing
BUZZER = layout.FIXED["BZ1"][:2]
BACK_TALLEST = 2.95           # the battery socket J4 (JST's drawing)

# Good Display's drawing of the GDEY0154D67.
GLASS_W, GLASS_H, GLASS_T = 31.8, 37.32, 1.0   # +-0.2 wide, +-0.1 thick
VIEW = 27.7                   # viewing area, square
VIEW_BORDER = 2.05            # from the glass's left and top edges
TAPE = 0.1                    # double-sided tape under the glass
GLASS_X = (BW - GLASS_W) / 2

# The cell: a 302530 is 3 x 25 x 30 mm. A 303030 also fits.
CELL_W, CELL_L, CELL_T = 25.0, 30.0, 3.0

# ---- Printing and fit -----------------------------------------------------

WALL = 1.2                    # side walls: two passes of a 0.6 mm nozzle
SKIN_BACK = 0.8               # four layers
SKIN_FRONT = 0.6              # the lip over the glass: three layers
CLR = 0.25                    # between the board's edge and the walls
FIT = 0.12                    # between printed parts that slide together
CORNER = 1.5                  # outside corner radius

# ---- Derived levels (z) ---------------------------------------------------

Z_CAV_F = TAPE + GLASS_T + 0.15         # underside of the bezel, over the glass
Z_FRONT = Z_CAV_F + SKIN_FRONT          # the front face
Z_FLOOR = -BT - BACK_TALLEST - 0.25     # inside floor under the board
Z_BACK = Z_FLOOR - SKIN_BACK            # the back face
Z_CELL = Z_FLOOR + 0.6                  # raised floor under the cell
Z_MARGIN = Z_BACK + 2.4                 # thick floor beside the cell, for screw heads

# ---- Derived positions (x, y) ---------------------------------------------

XL, XR = -CLR - WALL, BW + CLR + WALL   # outside faces of the long walls
YT = -CLR - WALL                        # outside of the top (antenna) end
BAT_GAP = 3.0                           # board to cell: room for the plug and wires
Y_BAY0 = BH + CLR + BAT_GAP             # the cell bay
Y_BAY1 = Y_BAY0 + CELL_L + 1.0
CELL_X0 = (BW - CELL_W - 1.0) / 2
CELL_X1 = BW - CELL_X0
LANYARD_SLOT, LANYARD_BAR = 2.5, 2.0
Y_SLOT0 = Y_BAY1 + WALL
YE = Y_SLOT0 + LANYARD_SLOT + LANYARD_BAR   # outside of the bottom end

# Screws: M2 x 4 thread-forming, pan head, from the back into the bezel.
SCREW_X = [(-CLR + CELL_X0) / 2, BW - (-CLR + CELL_X0) / 2]
SCREW_Y = [Y_BAY0 + 3.0, Y_BAY1 - 3.0]
SCREW_CLEAR, SCREW_PILOT = 2.4, 1.7
HEAD_D, HEAD_DEPTH = 4.2, 1.6

# Thumb switch caps, one per switch, side by side in one window.
CAP_HALF = 2.85               # half a cap's length; the switches are 6 mm apart
CAP_PROUD = 0.6               # how far a cap stands out of the wall
CAP_REST_GAP = 0.05           # cap to plunger at rest
CAP_STOP = SWITCH_TRAVEL + 0.1    # travel before a cap stops against the board edge
WIN_Y0, WIN_Y1 = SWITCH_Y[0] - CAP_HALF - 0.15, SWITCH_Y[-1] + CAP_HALF + 0.15
WIN_Z0 = -3.4                 # bottom of the window; its top is open to the bezel
CAP_FOOT_Z = Z_FLOOR + 0.2    # the foot that keeps a cap from falling out

# Hook at the antenna end: a skirt on the bezel with a nib under a groove.
HOOK_X0, HOOK_X1 = 4.0, 28.0
HOOK_LIP = 0.8                # the bezel is this much longer than the tray
NIB = 0.4
NIB_Z0, NIB_Z1 = -1.5, -0.9

# Ribs on the tray that the bezel's walls drop over, to line the halves up.
TONGUE_H = 0.8
TONGUES = [(-CLR - WALL / 2, 2.0, -CLR, 35.0),
           (BW + CLR, 24.5, BW + CLR + WALL / 2, 53.0)]

# Where the tray touches the back of the board: (x0, y0, x1, y1). `check`
# tests these against the courtyards of the parts on the back face.
LEDGES = [(-CLR, -CLR, 28.4, 0.6),            # top edge, beyond the module
          (-CLR, -CLR, 0.7, 22.0),            # left edge, beside the module
          (-CLR, 50.4, 4.6, BH + CLR),        # bottom left, beside the battery socket
          (21.3, 51.2, 25.3, BH + CLR),       # bottom edge, between buzzer and J2
          (31.7, 24.0, BW + CLR, 37.5)]       # right edge, beside the capacitors
# Where the bezel holds the front of the board down, clear of the glass.
POSTS = [(0.5, 50.2, 7.5, 54.2)]

USB_WIN = (USB_Y - USB_HALF - 0.25, USB_Y + USB_HALF + 0.25)
USB_RELIEF = (USB_WIN[0] - 2.3, USB_WIN[1] + 2.3)   # wall thinned for the plug's body


def box(x0, y0, x1, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, -y1, z0))


def cyl(x, y, d, z0, z1):
    return cq.Workplane("XY").circle(d / 2).extrude(z1 - z0).translate((x, -y, z0))


def shell(y0, z0, z1, flat_face):
    """The outside shape of one half, with the edge of its flat face eased."""
    s = box(XL, y0, XR, YE, z0, z1).edges("|Z").fillet(CORNER)
    return s.faces(flat_face).chamfer(0.4)


def usb_and_lanyard(part):
    # Thin the wall around the port so a plug's body can reach, then the slot.
    part = part.cut(box(XL - 1, USB_RELIEF[0], XL + WALL / 2, USB_RELIEF[1], Z_BACK - 1, Z_FRONT + 1))
    return part.cut(box(9, Y_SLOT0, BW - 9, Y_SLOT0 + LANYARD_SLOT, Z_BACK - 1, Z_FRONT + 1))


def tray():
    t = shell(YT, Z_BACK, 0, "<Z")
    t = t.cut(box(-CLR, -CLR, BW + CLR, Y_BAY0, Z_FLOOR, 1))
    t = t.cut(box(CELL_X0, Y_BAY0 - 0.01, CELL_X1, Y_BAY1, Z_CELL, 1))
    for x0, x1 in ((-CLR, CELL_X0), (CELL_X1, BW + CLR)):
        t = t.cut(box(x0, Y_BAY0 - 0.01, x1, Y_BAY1, Z_MARGIN, 1))
    for x0, y0, x1, y1 in LEDGES:
        t = t.union(box(x0 - 0.05, y0 - 0.05, x1, y1, Z_FLOOR - 0.05, -BT))
    # A rib that keeps the cell off the board's bottom edge; wires pass either side.
    t = t.union(box(11, Y_BAY0 - 0.85, 25, Y_BAY0 - 0.25, Z_FLOOR - 0.05, -BT - 0.6))
    for x0, y0, x1, y1 in TONGUES:
        t = t.union(box(x0, y0, x1, y1, -0.05, TONGUE_H))

    # USB port: open at the top so the board drops in with the port fitted.
    t = t.cut(box(XL - 1, USB_WIN[0], -CLR + 0.01, USB_WIN[1], -USB_SHELL - 0.25, 1))
    # Thumb switches: one window, open at the top, for the three caps.
    t = t.cut(box(BW + CLR - 0.01, WIN_Y0, XR + 1, WIN_Y1, WIN_Z0, 1))
    # Reset: a pocket the plunger slides down into, and a pinhole to reach it.
    t = t.cut(box(BW + CLR - 0.01, RESET_Y - 1.3, BW + CLR + 0.5, RESET_Y + 1.3, -BT - SWITCH_H - 0.25, 1))
    t = t.cut(cq.Workplane("YZ").center(-RESET_Y, -BT - SWITCH_H / 2).circle(0.75).extrude(3).translate((BW, 0, 0)))
    t = t.cut(cyl(BUZZER[0], BUZZER[1], 2.0, Z_BACK - 1, Z_FLOOR + 1))
    # Groove for the bezel's hook.
    t = t.cut(box(HOOK_X0 - 0.5, YT - 1, HOOK_X1 + 0.5, YT + NIB + 0.1, NIB_Z0 - 0.2, NIB_Z1 + 0.15))
    for x in SCREW_X:
        for y in SCREW_Y:
            t = t.cut(cyl(x, y, SCREW_CLEAR, Z_BACK - 1, Z_MARGIN + 1))
            t = t.cut(cyl(x, y, HEAD_D, Z_BACK - 1, Z_BACK + HEAD_DEPTH))
    return usb_and_lanyard(t)


def bezel():
    b = shell(YT - HOOK_LIP, 0, Z_FRONT, ">Z")
    b = b.cut(box(-CLR, -CLR, BW + CLR, Y_BAY0, -1, Z_CAV_F))
    b = b.cut(box(GLASS_X + VIEW_BORDER, VIEW_BORDER, GLASS_X + VIEW_BORDER + VIEW, VIEW_BORDER + VIEW, 0, Z_FRONT + 1))
    for x0, y0, x1, y1 in POSTS:
        b = b.union(box(x0, y0, x1, y1, 0.05, Z_CAV_F + 0.05))
    for x0, y0, x1, y1 in TONGUES:
        b = b.cut(box(x0 - FIT, y0 - 0.3, x1 + FIT, y1 + 0.3, -1, TONGUE_H + 0.1))
    # Room over the USB shell, in case it stands higher than the drawing says.
    b = b.cut(box(XL - 1, USB_WIN[0], -CLR + 0.01, USB_WIN[1], -1, 0.3))
    # Screw bosses that hang down beside the cell.
    for x in SCREW_X:
        for y in SCREW_Y:
            b = b.union(box(x - 1.45, y - 2.5, x + 1.45, y + 2.5, Z_MARGIN + 0.1, 0.05))
    for x in SCREW_X:
        for y in SCREW_Y:
            b = b.cut(cyl(x, y, SCREW_PILOT, Z_MARGIN - 1, Z_FRONT - 0.6))
    # The hook: a skirt down the outside of the tray's top wall, with a nib.
    b = b.union(box(HOOK_X0, YT - HOOK_LIP, HOOK_X1, YT - 0.1, NIB_Z0 - 0.1, 0.05))
    b = b.union(box(HOOK_X0, YT - 0.15, HOOK_X1, YT + NIB, NIB_Z0, NIB_Z1))
    return usb_and_lanyard(b)


def button(c=0.0):
    """One switch cap, for the switch at y = c. The section is the same along
    its length, so it prints standing on one end."""
    inner = PLUNGER_TIP + CAP_REST_GAP
    y0, y1 = c - CAP_HALF, c + CAP_HALF
    cap = box(inner, y0, XR + CAP_PROUD, y1, WIN_Z0 + 0.1, -0.2)
    try:
        cap = cap.faces(">X").edges("|Y").fillet(0.5)
    except Exception:
        pass
    # Neck through the wall, and a foot behind the wall under the switch body.
    cap = cap.union(box(BW + CLR - 0.1, y0, inner + 0.01, y1, WIN_Z0 + 0.1, -BT - SWITCH_H - 0.25))
    cap = cap.union(box(BW - 0.7, y0, BW + CLR - 0.09, y1, CAP_FOOT_Z, -BT - SWITCH_H - 0.25))
    # Pads that stop the cap against the board's edge, clear of the plunger.
    for a, b in ((y0 + 0.2, y0 + 1.1), (y1 - 1.1, y1 - 0.2)):
        cap = cap.union(box(BW + CAP_STOP, a, inner + 0.01, b, -BT + 0.1, -0.2))
    return cap


def dummy_board():
    """A blank the size of the real board, to print and tape parts onto."""
    pts = [(x, -y) for x, y in layout.OUTLINE]
    b = cq.Workplane("XY").polyline(pts).close().extrude(BT).translate((0, 0, -BT))
    x0, y0, x1, y1 = layout.SLOT
    return b.cut(box(x0, y0, x1, y1, -BT - 1, 1))


def proxies():
    """Stand-ins for what KiCad's 3D export leaves out."""
    return {
        "glass": box(GLASS_X, 0, GLASS_X + GLASS_W, GLASS_H, TAPE, TAPE + GLASS_T),
        "usb": box(-USB_OVERHANG, USB_Y - USB_HALF, 6.0, USB_Y + USB_HALF, -USB_SHELL, 0),
        "cell": box((BW - CELL_W) / 2, Y_BAY0 + 0.5, (BW + CELL_W) / 2, Y_BAY0 + 0.5 + CELL_L, Z_CELL, Z_CELL + CELL_T),
    }


def parts():
    p = {"tray": tray(), "bezel": bezel(), "dummy-board": dummy_board()}
    for i, c in enumerate(SWITCH_Y):
        p["button%d" % (i + 1)] = button(c)
    return p


def volume(a, b):
    try:
        return a.intersect(b).val().Volume()
    except Exception:
        return 0.0


def check(p):
    """Test the case against the routed board: KiCad's 3D export for the parts
    that have models, courtyards for where the case touches the board."""
    import pcbnew
    pcb = os.path.join(HERE, "..", "inkotp.kicad_pcb")
    step = os.path.join(OUT, "board.step")
    subprocess.run(["kicad-cli", "pcb", "export", "step", "--force", "--subst-models", "--user-origin", "100x60mm",
                    "-o", step, pcb], check=True, capture_output=True)
    # KiCad puts the board's back face at z = 0.
    board = cq.importers.importStep(step).translate((0, 0, -BT))
    bb = board.val().BoundingBox()
    print("board model: x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f" % (bb.xmin, bb.xmax, -bb.ymax, -bb.ymin, bb.zmin, bb.zmax))
    bad = 0
    things = dict(proxies(), board=board)
    printed = ["tray", "bezel", "button1", "button2", "button3"]
    for name in printed:
        for other, solid in things.items():
            v = volume(p[name], solid)
            if v > 0.001:
                bad += 1
                print("CLASH: %s and %s overlap by %.3f mm3" % (name, other, v))
    for i, a in enumerate(printed):
        for b in printed[i + 1:]:
            v = volume(p[a], p[b])
            if v > 0.001:
                bad += 1
                print("CLASH: %s and %s overlap by %.3f mm3" % (a, b, v))

    b = pcbnew.LoadBoard(pcb)
    for side, layer, areas in (("back", pcbnew.B_CrtYd, LEDGES), ("front", pcbnew.F_CrtYd, POSTS)):
        for f in b.GetFootprints():
            if f.IsFlipped() != (side == "back"):
                continue
            c = f.GetCourtyard(layer).BBox()
            fx0, fx1 = c.GetLeft() / 1e6 - 100, c.GetRight() / 1e6 - 100
            fy0, fy1 = c.GetTop() / 1e6 - 60, c.GetBottom() / 1e6 - 60
            for x0, y0, x1, y1 in areas:
                if x0 < fx1 and fx0 < x1 and y0 < fy1 and fy0 < y1:
                    bad += 1
                    print("CLASH: %s support (%.1f, %.1f)-(%.1f, %.1f) is on %s's courtyard" % (side, x0, y0, x1, y1, f.GetReference()))
    print("check: %d problem%s" % (bad, "" if bad == 1 else "s"))
    return bad


def main():
    os.makedirs(OUT, exist_ok=True)
    p = parts()
    for name in ("tray", "bezel", "dummy-board"):
        cq.exporters.export(p[name], os.path.join(OUT, name + ".stl"), tolerance=0.01, angularTolerance=0.1)
        cq.exporters.export(p[name], os.path.join(OUT, name + ".step"))
    cap = button(0.0)
    cq.exporters.export(cap, os.path.join(OUT, "button.stl"), tolerance=0.01, angularTolerance=0.1)
    cq.exporters.export(cap, os.path.join(OUT, "button.step"))
    asm = cq.Assembly()
    colours = {"tray": (0.25, 0.25, 0.28), "bezel": (0.85, 0.85, 0.82), "dummy-board": (0.1, 0.45, 0.2)}
    for name, solid in list(p.items()) + list(proxies().items()):
        asm.add(solid, name=name, color=cq.Color(*colours.get(name, (0.9, 0.5, 0.1))))
    asm.save(os.path.join(OUT, "assembly.step"))
    print("outside: %.1f x %.1f x %.2f mm" % (XR - XL + CAP_PROUD, YE - YT + HOOK_LIP, Z_FRONT - Z_BACK))
    for name in ("tray", "bezel"):
        print("%s: %.1f cm3" % (name, p[name].val().Volume() / 1000))
    if "check" in sys.argv[1:]:
        sys.exit(1 if check(p) else 0)


if __name__ == "__main__":
    main()
