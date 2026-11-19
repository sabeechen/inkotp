#!/usr/bin/env python3
"""Run build + route several times and keep the attempt with the fewest open
connections, as counted by KiCad's own design rule check. The autorouter's
results vary from run to run.

Usage: python3 route_best.py /path/to/freerouting.jar [attempts] [passes]
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.normpath(os.path.join(HERE, "..", "inkotp.kicad_pcb"))


def open_connections():
    report = PCB + ".drc.tmp"
    subprocess.run(["kicad-cli", "pcb", "drc", "--severity-error", "--format", "report", "-o", report, PCB],
                   capture_output=True)
    with open(report) as f:
        text = f.read()
    os.remove(report)
    errors = len(re.findall(r"^\[(?!unconnected_items)", text, re.M))
    return len(re.findall(r"^\[unconnected_items\]", text, re.M)), errors


def main():
    jar = sys.argv[1]
    attempts = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    passes = sys.argv[3] if len(sys.argv) > 3 else "150"
    best = None
    for n in range(1, attempts + 1):
        subprocess.run([sys.executable, os.path.join(HERE, "build.py"), "board"], capture_output=True, check=True)
        subprocess.run([sys.executable, os.path.join(HERE, "route.py"), jar, passes], capture_output=True, check=True)
        score = open_connections()
        print(f"attempt {n}: {score[0]} open connections, {score[1]} other errors", flush=True)
        if best is None or score < best:
            best = score
            shutil.copy(PCB, PCB + ".best")
        if score == (0, 0):
            break
    shutil.move(PCB + ".best", PCB)
    print(f"kept: {best[0]} open connections, {best[1]} other errors")


if __name__ == "__main__":
    main()
