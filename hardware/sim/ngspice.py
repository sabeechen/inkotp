"""Run an ngspice netlist through the shared library that KiCad installs.

Usage: python3 ngspice.py file.cir

There is no need for the ngspice command itself. Whatever the netlist's
.control block prints is written to standard output.
"""
import ctypes
import sys

CHAR = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
STAT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
EXIT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
DATA = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p)
INIT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
BG = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)


def run(path, quiet=("stdout Doing analysis", "stdout Using", "stdout No. of Data", "stdout Initial Transient",
                     "stdout Circuit:", "stdout Note:", "stdout Reference value", "stdout  Reference value")):
    lines = []

    def on_char(text, _id, _user):
        text = text.decode(errors="replace")
        if text.strip() in ("stdout", "stderr") or any(text.startswith(q) for q in quiet):
            return 0
        lines.append(text.split(" ", 1)[1] if " " in text else "")
        return 0

    keep = [CHAR(on_char), STAT(lambda *a: 0), EXIT(lambda *a: 0), DATA(lambda *a: 0), INIT(lambda *a: 0),
            BG(lambda *a: 0)]
    lib = ctypes.CDLL("libngspice.so.0")
    lib.ngSpice_Init(*keep, None)
    lib.ngSpice_Command(f"source {path}".encode())
    return lines


if __name__ == "__main__":
    print("\n".join(run(sys.argv[1])))
