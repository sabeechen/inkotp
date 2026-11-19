#!/usr/bin/env python3
"""Generate the InkOTP stick's KiCad project from design.py.

Usage: python3 build.py [schematic|board|all]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.normpath(os.path.join(HERE, ".."))
ROOT_UUID = "3b0b4c0a-7d0e-4c58-9d3e-2f7f0a6f1c01"

import libs
import symlib


def resolve(parts):
    """Turn each part's name-or-number net map into a per-pin-number map."""
    for part in parts:
        pins = symlib.pins(symlib.load(part["lib"], part["name"]))
        nets = dict(part["nets"])
        out = {}
        for pin in pins:
            for key in (pin["number"], pin["name"]):
                if key in part["nets"]:
                    out[pin["number"]] = part["nets"][key]
                    nets.pop(key, None)
                    break
        if nets:
            raise SystemExit(f"{part['ref']}: no pin called {sorted(nets)}")
        part["pin_nets"] = out
    return parts


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    libs.write(PROJECT_DIR, [libs.usb_c_midmount(), libs.battery_pads(), libs.module_footprint(), libs.battery_socket(),
                             libs.fpc_connector(), libs.inductor()], [libs.clock_symbol()])
    import design
    parts = resolve(design.PARTS)
    if what in ("schematic", "all"):
        import schematic
        text = schematic.build(parts, design.GROUPS, "InkOTP stick", ROOT_UUID)
        with open(os.path.join(PROJECT_DIR, "inkotp.kicad_sch"), "w") as f:
            f.write(text)
        print("wrote inkotp.kicad_sch,", len(parts), "parts")
    if what in ("board", "all"):
        import layout
        layout.write(parts, PROJECT_DIR)


if __name__ == "__main__":
    main()
