#!/usr/bin/env python3
"""Autoroute the generated board with Freerouting and add ground pours.

Usage: python3 route.py /path/to/freerouting.jar [passes]

Freerouting runs in the eclipse-temurin:21-jre Docker image, so Java does not
need to be installed. The board is read from inkotp.kicad_pcb and the result
is written back to the same file. Tracks already on the board are kept where
the router can work around them, so this also finishes a partly routed board.
"""
import os
import shutil
import subprocess
import sys
import tempfile

import pcbnew

import board as board_builder
import layout

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.normpath(os.path.join(HERE, ".."))


def main():
    jar = os.path.abspath(sys.argv[1])
    passes = sys.argv[2] if len(sys.argv) > 2 else "40"
    pcb = os.path.join(PROJECT_DIR, "inkotp.kicad_pcb")
    work = tempfile.mkdtemp(prefix="inkotp-route-")
    shutil.copy(jar, os.path.join(work, "freerouting.jar"))
    board = pcbnew.LoadBoard(pcb)
    # A board that is already routed (see sync.py) carries the outer-layer
    # pours from last time. Take them off so the router sees only tracks.
    pours = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)]
    if pours:
        for zone in pours:
            board.Remove(zone)
        pcbnew.SaveBoard(pcb, board)
    if not pcbnew.ExportSpecctraDSN(board, os.path.join(work, "inkotp.dsn")):
        raise SystemExit("DSN export failed")
    subprocess.run(["docker", "run", "--rm", "-u", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/work",
                    "-v", f"{work}:/work", "-w", "/work", "eclipse-temurin:21-jre",
                    "java", "-Djava.awt.headless=true", "-jar", "freerouting.jar",
                    "--gui.enabled=false", f"--router.max_passes={passes}", "--router.optimizer.enabled=false",
                    "-de", "inkotp.dsn", "-do", "inkotp.ses", "-mp", passes],
                   check=True)
    board = pcbnew.LoadBoard(pcb)
    if not pcbnew.ImportSpecctraSES(board, os.path.join(work, "inkotp.ses")):
        raise SystemExit("SES import failed")
    gnd = board.FindNet("GND")
    ox, oy = 100.0, 60.0
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(gnd)
        zone.SetLocalClearance(board_builder.mm(0.2))
        zone.SetMinThickness(board_builder.mm(0.2))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        poly = zone.Outline()
        poly.NewOutline()
        for x, y in layout.OUTLINE:
            poly.Append(board_builder.mm(ox + x), board_builder.mm(oy + y))
        board.Add(zone)
    board_builder.fill_zones(board)
    pcbnew.SaveBoard(pcb, board)
    import libs
    libs.project_file(PROJECT_DIR)
    print("routed board written; work files in", work)


if __name__ == "__main__":
    main()
