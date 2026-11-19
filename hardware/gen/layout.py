"""Where everything sits on the InkOTP stick board.

All coordinates are millimetres seen from the front (screen side), origin at
the board's top-left corner. The screen glass covers y = 0 to 37.3, so every
part behind it is on the back face; its tail passes through the slot and folds
up the back into J3. Below the slot there is no glass, and low passives sit on
the front face there.
"""
import os

import pcbnew

import board as board_builder
import design
import libs

WIDTH, HEIGHT = 32.0, 54.5
USB_Y = 43.6          # centreline of the USB port on the left edge
USB_HALF, USB_DEPTH = 4.62, 6.2
SLOT = (8.5, 38.3, 23.6, 40.3)

OUTLINE = [(0, 0), (WIDTH, 0), (WIDTH, HEIGHT), (0, HEIGHT),
           (0, USB_Y + USB_HALF), (USB_DEPTH, USB_Y + USB_HALF),
           (USB_DEPTH, USB_Y - USB_HALF), (0, USB_Y - USB_HALF)]
CUTOUTS = [[(SLOT[0], SLOT[1]), (SLOT[2], SLOT[1]), (SLOT[2], SLOT[3]), (SLOT[0], SLOT[3])]]

# No copper under or beside the module's antenna. This is far smaller than the
# clearance Espressif recommends, which does not fit on a board this size.
KEEPOUTS = [(0.0, 0.0, 17.2, 6.1)]

FIXED = {
    "U1": (9.0, 11.25, 180),    # antenna along the top edge
    # Switch plungers overhang the right edge by about 0.6 mm.
    "SW1": (WIDTH - 1.5, 3.2, -90),
    "SW2": (WIDTH - 1.5, 9.2, -90),
    "SW3": (WIDTH - 1.5, 15.2, -90),
    "SW4": (WIDTH - 1.5, 20.8, -90),  # reset, behind a pinhole in the case
    "BZ1": (26.2, 45.9, 0),     # in the strip, clear of the glass
    "J3": (16.05, 27.7, 180),   # mouth towards the slot
    "J1": (0.0, USB_Y, 90),     # mouth out of the left edge
    "J2": (28.6, 52.5, 0),
    "J4": (7.9, 51.5, 180),     # below the USB port, mouth out of the bottom edge
    "R1": (8.5, 45.9, 90),      # beside the USB port's CC pads
    "R2": (8.5, 41.6, 90),
}

GAP = 0.3  # between courtyards

REGIONS = [
    # Between the module and the switches: clock, module decoupling, select diode.
    (18.2, 0.8, 27.8, 13.2, ["U5", ("C11", 90), ("R13", 90), ("R14", 90), "D1", ("C7", 90), ("C8", 90)],
     {"gap": 0.6}),
    # Where the buzzer used to be: reset parts and test pads, left loose for routing.
    (18.6, 14.0, 27.8, 22.5, ["TP4", ("R11", 90), ("C9", 90), ("R15", 90), "TP3"], {"gap": 1.5}),
    # Left of the panel connector: boost stage.
    (0.55, 22.3, 6.6, 37.4, ["L1", ("C21", 90), "Q4", ("C12", 90), ("D2", 90), ("D3", 90),
                             ("D4", 90), ("C16", 90), ("C22", 90)]),
    # Between the module and the panel connector.
    # The middle is left clear for the panel's signals.
    (6.9, 22.2, 11.6, 25.1, ["R16", "R17"]),
    (16.55, 22.1, 19.0, 25.1, [("C19", 90), ("C20", 90)], {"gap": 0.2}),
    # Right of the panel connector: the panel's reservoir capacitors.
    (25.7, 23.6, 31.5, 37.6, [("C13", 90), ("C14", 90), ("C15", 90), ("C17", 90), ("C18", 90)]),
    # Under the folded tail: flat test pads only.
    (10.0, 33.2, 22.2, 37.7, ["TP1", "TP2"]),
    # Back of the strip below the slot: USB protection, charger, power latch, regulator.
    (11.0, 41.0, 20.7, 52.9, ["U4", "U3", "Q1", "Q3", "Q2", "U2"], {"gap": 0.6}),
    (11.0, 53.1, 20.7, 54.2, ["R12", "C10"]),
    # Front of the same strip: their passives.
    (9.5, 41.2, 31.4, 54.0, design.FRONT, {"side": "front", "gap": 1.6}),
]


# Escape routing for the USB port, whose pads end at x = 7.35. USB-C repeats
# D+ and D- on interleaved pins, so each pair is joined on the front face.
_PAD = 7.35
TRACKS = [
    ("USB_DP", "B", 0.127, [(_PAD - 0.3, USB_Y - 0.75), (9.0, USB_Y - 0.75)]),
    ("USB_DP", "B", 0.127, [(_PAD - 0.3, USB_Y + 0.25), (9.0, USB_Y + 0.25)]),
    ("USB_DP", "F", 0.127, [(9.0, USB_Y - 0.75), (9.0, USB_Y + 0.25)]),
    ("USB_DN", "B", 0.127, [(_PAD - 0.3, USB_Y - 0.25), (8.35, USB_Y - 0.25)]),
    ("USB_DN", "B", 0.127, [(_PAD - 0.3, USB_Y + 0.75), (8.35, USB_Y + 0.75)]),
    ("USB_DN", "F", 0.127, [(8.35, USB_Y - 0.25), (8.35, USB_Y + 0.75)]),
    ("VBUS", "B", 0.25, [(_PAD - 0.3, USB_Y - 2.4), (7.75, USB_Y - 2.4)]),
    ("VBUS", "B", 0.25, [(_PAD - 0.3, USB_Y + 2.4), (7.75, USB_Y + 2.4)]),
    ("VBUS", "F", 0.25, [(7.75, USB_Y - 2.4), (7.75, USB_Y + 2.4)]),
]
VIAS = [
    ("USB_DP", 9.0, USB_Y - 0.75), ("USB_DP", 9.0, USB_Y + 0.25),
    ("USB_DN", 8.35, USB_Y - 0.25), ("USB_DN", 8.35, USB_Y + 0.75),
    ("VBUS", 7.75, USB_Y - 2.4), ("VBUS", 7.75, USB_Y + 2.4),
]


def write(parts, project_dir):
    board, footprints, problems = board_builder.build(parts, FIXED, REGIONS, OUTLINE, CUTOUTS, KEEPOUTS, project_dir, gap=GAP,
                                                          tracks=TRACKS, vias=VIAS)
    path = os.path.join(project_dir, "inkotp.kicad_pcb")
    pcbnew.SaveBoard(path, board)
    libs.project_file(project_dir)
    print("wrote inkotp.kicad_pcb,", len(footprints), "footprints")
    for p in problems:
        print("PROBLEM:", p)
    return footprints
