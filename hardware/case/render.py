"""Render the case to PNG files in case/out, for a quick look without a CAD program.

    case/.venv/bin/python case/render.py
"""
import os

import cadquery as cq
from cadquery.vis import show

import case

VIEWS = {  # name: (what to show, roll, elevation, seen from behind)
    "front": (["tray", "bezel", "button1", "button2", "button3", "glass"], -70, -50, False),
    "back": (["tray", "bezel", "button1", "button2", "button3"], -70, -50, True),
    "tray": (["tray", "button1", "button2", "button3", "dummy-board", "usb", "cell"], -70, -50, False),
    "bezel-inside": (["bezel"], -70, -50, True),
}


def main():
    p = dict(case.parts(), **case.proxies())
    colours = {"tray": "gray30", "bezel": "lightgray", "dummy-board": "darkgreen", "glass": "white",
               "usb": "gray70", "cell": "steelblue"}
    for name, (names, roll, elevation, flip) in VIEWS.items():
        asm = cq.Assembly()
        for n in names:
            solid = p[n].rotate((0, 0, 0), (0, 1, 0), 180) if flip else p[n]
            asm.add(solid, name=n, color=cq.Color(colours.get(n, "orange")))
        show(asm, width=1400, height=900, roll=roll, elevation=elevation, zoom=1.0,
             screenshot=os.path.join(case.OUT, name + ".png"), interact=False)
        print("wrote", name + ".png")


if __name__ == "__main__":
    main()
