#!/usr/bin/env python3
"""Simulate the power latch, the reset switch and what surrounds them.

Usage: python3 latch.py

Builds an ngspice netlist of Q1 to Q3, D1, the regulator and a stand-in for
the module, runs it for a set of cases and prints what happened. The
transistor models are generic (ngspice's VDMOS with a subthreshold term), set
to the datasheet's threshold voltage range, not the makers' models. The
module is a behavioural model: see NETLIST.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

NETLIST = """InkOTP power latch
.param vbat={vbat} vthn={vthn} vthp={vthp} r4={r4} boot={boot}
.options reltol=1e-3 abstol=1e-10 vntol=1e-5 method=gear
.temp {temp}
* Thresholds are given the way the datasheets do: BSS138 at 1 mA, AO3401A at
* 250 uA. Vto in the model is a little inside that.
.model NFET VDMOS(Vto={{vthn-0.07}} Kp=0.4 Rd=1 Rs=0.5 Cgs=30p Cgdmax=10p Cgdmin=3p ksubthres=0.08 Is=1e-13)
.model PFET VDMOS(pchan Vto={{vthp+0.01}} Kp=8 Rd=0.03 Rs=0.01 Cgs=600p Cgdmax=200p Cgdmin=60p ksubthres=0.08 Is=1e-12)
* BAT54: about 0.2 uA of reverse leakage at 25 C, doubling every 12 C or so.
.model BAT54 D(Is=2.1e-7 N=1.02 Rs=2.6 Cjo=10p Eg=0.69 Xti=2 Bv=30)
* BAV70: a silicon pair in the same package and pin order, a few nA.
.model BAV70 D(Is=2.5n N=1.75 Rs=0.6 Cjo=1.5p Eg=1.11 Xti=3 Bv=100)
* Drain leakage of Q2 and Q3: 5 nA each at 25 C, about 50 times that at
* 85 C. A guess at typical parts; the datasheet only gives a 0.5 uA maximum.
.model LEAK D(Is=5n N=1 Eg=0.6 Xti=0)
.model ESD D(Is=1e-14 N=1 Rs=50)
.model SW SW(Vt=0.5 Vh=0.05 Ron=1 Roff=1e10)
.model RUN SW(Vt=0.632 Vh=0.01 Ron=30 Roff=1e10)
.model NOTRUN SW(Vt=0.5 Vh=0.05 Ron=1e9 Roff=10)

Vcell cell 0 {{vbat}}
Rcell cell vbat 0.2
Vusb vbus 0 PWL({usb})
R7 vbus vbus_det 100k
R8 vbus_det 0 100k

* Latch
M1 vsw pgate vbat PFET
R4 pgate vbat {{r4}}
D1a pgate swsel {d1}
D1b btnsel swsel {d1}
Vsel selctl 0 PWL({select})
Ssel swsel 0 selctl 0 SW
M2 pgate holdg 0 NFET
R5 hold holdg 1k
R6 holdg 0 1meg
C3 holdg 0 1u
M3 pgate vbus_det 0 NFET
Dlk2 0 pgate LEAK
Dlk3 0 pgate LEAK

* Regulator (AP2112K): on above 1.5 V in, 0.1 V dropout, 55 uA of its own,
* output pulled down when off.
C4 vsw 0 1u
Bldo ldoi 0 V = 0.5 * (1 + tanh((v(vsw) - 1.5) / 0.05)) * min(3.3, max(v(vsw) - 0.1, 0))
Vs ldoi ldoo 0
Rldo ldoo v33 0.5
Bin vsw 0 I = max(i(Vs), 0) + 55u * 0.5 * (1 + tanh((v(vsw) - 1.5) / 0.05))
C5 v33 0 20u
R9 vsw bsense 1meg
R10 bsense 0 1meg
C6 bsense 0 100n

* Module stand-in: 33 mA load. It runs once EN is above 2.5 V and the rail
* above 2.7 V, and {{boot}} s later firmware drives HOLD high and turns on
* the select pull-up. Until then, and in reset, its pins are open, apart
* from the protection diodes to the rail. "fwoff" is firmware letting go.
Rload v33 0 100
R11 en v33 10k
C9 en 0 1u
Vrst rstctl 0 PWL({reset})
Srst en 0 rstctl 0 SW
Balive alive 0 V = (v(en) > 2.5 && v(v33) > 2.7) ? 1 : 0
Rdel alive bt {{boot*1e6}}
Cdel bt 0 1u
Sdis bt 0 alive 0 NOTRUN
Vfw fwoff 0 PWL({fwoff})
Bhold holdsrc 0 V = v(fwoff) > 0.5 ? 0 : v(v33)
Shold holdsrc hold bt 0 RUN
Spu v33 pu bt 0 RUN
Rpu pu btnsel 45k
Desd1 btnsel v33 ESD
Desd2 hold v33 ESD
Rpin1 btnsel 0 1g
Rpin2 hold 0 1g

{extra}
.control
{analysis}
.endc
.end
"""

DEFAULTS = dict(vbat=3.8, vthn=1.3, vthp=-0.9, r4="100k", boot=0.3, temp=25,
                usb="0 0", select="0 0", reset="0 0", fwoff="0 0", d1="BAV70", extra="")


def pulse(start, length):
    """A control voltage that is high from start for length seconds."""
    return f"0 0 {start} 0 {start + 0.001} 1 {start + length} 1 {start + length + 0.001} 0"


def run(analysis, **changes):
    values = dict(DEFAULTS, **changes)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out.txt")
        text = NETLIST.format(analysis=analysis.format(out=out), **values)
        path = os.path.join(tmp, "latch.cir")
        with open(path, "w") as f:
            f.write(text)
        log = subprocess.run([sys.executable, os.path.join(HERE, "ngspice.py"), path],
                             capture_output=True, text=True).stdout
        rows = []
        if os.path.exists(out):
            for line in open(out):
                parts = line.split()
                try:
                    rows.append([float(p) for p in parts])
                except ValueError:
                    pass
        return rows, log


NAMES = ["vsw", "v33", "pgate", "holdg", "en", "bsense", "btnsel"]


def tran(stop, **changes):
    """Run a transient; returns a list of dicts, one per time step."""
    cols = " ".join(f"v({n})" for n in NAMES)
    rows, log = run(f"tran 1m {stop}\nset wr_singlescale\nwrdata {{out}} {cols}", **changes)
    if not rows:
        raise SystemExit("simulation failed:\n" + log)
    return [dict(zip(["t"] + NAMES, r)) for r in rows]


def at(trace, t, name):
    return min(trace, key=lambda r: abs(r["t"] - t))[name]


def first(trace, after, test):
    for r in trace:
        if r["t"] >= after and test(r):
            return r["t"]
    return None


CORNERS = [dict(vbat=vb, vthn=vn, vthp=vp) for vb in (3.3, 4.2) for vn in (0.8, 1.5) for vp in (-0.5, -1.3)]


def on(trace, t):
    return at(trace, t, "v33") > 3.0


def behave(base):
    """Cases 1 to 5 for one choice of D1 and R4."""
    def sim(stop, **changes):
        return tran(stop, **dict(base, **changes))

    print("1. Wake on battery: how long must select be held?")
    for boot in (0.3, 0.6):
        result = []
        for press in (0.05, 0.2, boot - 0.05, boot + 0.05, boot + 0.2):
            ok = all(on(sim(2.5, select=pulse(0.1, press), boot=boot, **c), 2.4) for c in CORNERS)
            result.append(f"{press:.2f} s {'stays on' if ok else 'drops out'}")
        print(f"   firmware takes {boot} s to raise HOLD: " + "; ".join(result))
    t = sim(1.5, select=pulse(0.1, 0.5))
    rise = first(t, 0.1, lambda r: r["v33"] > 3.0)
    print(f"   3.3 V rail is up {1000 * (rise - 0.1):.0f} ms after the press; "
          f"select reads {at(t, 0.55, 'btnsel'):.2f} V pressed, {at(t, 1.2, 'btnsel'):.2f} V released")
    print(f"   battery sense reads {at(t, 0.2, 'bsense'):.2f} V at 0.1 s, {at(t, 0.4, 'bsense'):.2f} V at 0.3 s, "
          f"{at(t, 1.4, 'bsense'):.2f} V settled (half of 3.8 V is 1.90)")

    print("2. Firmware lets go of HOLD at 2.0 s")
    times = []
    for c in CORNERS:
        t = sim(4.0, select=pulse(0.1, 0.5), fwoff="0 0 2.0 0 2.001 1", **c)
        off = first(t, 2.0, lambda r: r["v33"] < 0.3)
        times.append(off - 2.0 if off and not on(t, 3.9) else None)
    print("   off after " + ("FAILED in a corner" if None in times else
                             f"{1000 * min(times):.0f} to {1000 * max(times):.0f} ms, and stays off"))

    print("3. Reset pressed at 2.0 s, on battery, firmware would keep running")
    for hold in (0.1, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0):
        outcomes = []
        for c in CORNERS:
            t = sim(2.0 + hold + 2.5, select=pulse(0.1, 0.5), reset=pulse(2.0, hold), **c)
            outcomes.append(on(t, 2.0 + hold + 2.4))
        text = "restarts and stays on" if all(outcomes) else "switches off" if not any(outcomes) else \
            f"depends on the parts ({sum(outcomes)} of {len(outcomes)} corners stay on)"
        print(f"   held {hold:.1f} s: {text}")

    print("4. Same, by BSS138 threshold (3.8 V cell): longest press that still restarts")
    for vn in (0.8, 1.3, 1.5):
        last = None
        for hold in [x / 10 for x in range(1, 40)]:
            t = sim(2.0 + hold + 2.5, select=pulse(0.1, 0.5), reset=pulse(2.0, hold), vthn=vn)
            if on(t, 2.0 + hold + 2.4):
                last = hold
            else:
                break
        print(f"   threshold {vn} V: {last} s")

    print("5. USB power")
    t = sim(8.0, usb="0 0 0.1 0 0.101 5", reset=pulse(2.0, 3.0))
    print(f"   plugging in with no press: {'comes on' if on(t, 1.5) else 'stays off'}; "
          f"reset held 3 s: rail {'stays up' if at(t, 4.9, 'vsw') > 3 else 'drops'}, "
          f"{'running again' if on(t, 7.9) else 'off'} afterwards")
    t = sim(6.0, usb="0 0 0.1 0 0.101 5 3.0 5 3.001 0", fwoff="0 0 2.0 0 2.001 1")
    print(f"   firmware lets go while plugged in: {'stays on' if on(t, 2.9) else 'off'}; "
          f"after unplugging: {'on' if on(t, 5.9) else 'off'}")
    t = sim(6.0, usb="0 0 0.1 0 0.101 5 3.0 5 3.001 0")
    print(f"   unplugged while firmware holds on: {'stays on' if on(t, 5.9) else 'off'}")



def leakage():
    print("6. Switched off, on battery, 4.2 V cell: does leakage into the gate node turn Q1 on?")
    print("   (started in the off state and left for 20 s; Q1 at its typical and its lowest threshold)")
    off = (".ic v(pgate)=4.2 v(swsel)=4.2 v(vsw)=0 v(v33)=0 v(holdg)=0 v(bt)=0 v(en)=0 v(bsense)=0 "
           "v(btnsel)=0 v(hold)=0 v(ldoo)=0 v(vbat)=4.2")
    cols = "v(vbat)-v(pgate) v(vsw) v(v33) i(Vcell)"
    for d1, r4 in (("BAT54", "1meg"), ("BAT54", "100k"), ("BAV70", "1meg"), ("BAV70", "100k")):
        print(f"   D1 = {d1}{'C' if d1 == 'BAT54' else ''}, R4 = {r4}")
        for vthp in (-0.9, -0.5):
            cells = []
            for temp in (25, 45, 60, 85):
                rows, log = run(f"tran 2m 20 uic\nset wr_singlescale\nwrdata {{out}} {cols}",
                                d1=d1, r4=r4, temp=temp, vbat=4.2, vthp=vthp, extra=off)
                if not rows:
                    raise SystemExit("simulation failed:\n" + log)
                _, gate, vsw, v33, current = rows[-1]
                state = "ON" if v33 > 3 else "off"
                cells.append(f"{temp} C: gate -{gate:.2f} V, {state}, {-1e6 * current:.1f} uA")
            print(f"      Q1 threshold {vthp} V: " + "; ".join(cells))


def main():
    for name, base in (("FIRST DRAFT: D1 = BAT54C, R4 = 1M", dict(d1="BAT54", r4="1meg")),
                       ("AS DRAWN: D1 = BAV70, R4 = 100k", dict(d1="BAV70", r4="100k"))):
        print(f"=== {name} ===")
        behave(base)
    print("=== Off-state leakage ===")
    leakage()


if __name__ == "__main__":
    main()
