# Power latch simulation

`python3 latch.py` simulates the power latch (Q1 to Q3, D1, R4 to R8, C3),
the reset switch and the regulator with ngspice, and prints what happens in
each case. `results.txt` is its last output. It needs only the ngspice
library that KiCad installs; `ngspice.py` runs a netlist through it.

## What the model is

- Transistors are ngspice's generic VDMOS model, set to the datasheets'
  lowest, typical and highest threshold voltages. They are not the makers'
  models, and threshold does not change with temperature here (in a real
  part it falls as it warms, which makes leakage results optimistic).
- D1's leakage is modelled as 0.2 uA at 25 C and 4 V, rising about 90 times
  by 85 C. That is in line with BAT54 datasheet curves, but real parts vary
  several-fold.
- Q2 and Q3 leak 5 nA each at 25 C. That is a guess at a typical part.
- The module is a stand-in: a 33 mA load whose pins are open until firmware
  has started, with protection diodes from each pin to the 3.3 V rail.
  Firmware raises the hold line a set time after reset is released.
- The panel, clock, charger and USB data are not modelled.

## What it found

1. **The first draft could switch itself on when warm.** It had a Schottky
   pair (BAT54C) for D1 and 1 M for R4. With the device off, D1's leakage
   flowed through R4 and pulled Q1's gate down: 0.18 V at 25 C, and enough to
   turn Q1 on by 45 C. The design now has a silicon pair (BAV70, same package
   and pins) and 100 k, with which the gate moves 0.06 V at 85 C. The script
   still runs the first draft for comparison.
2. **Select must be held until firmware raises the hold line.** The rail is
   up 1 ms after the press, but letting go before firmware has started
   switches it off again.
3. **Reset:** a tap of up to 0.5 s restarts and stays on in every corner; 2 s
   or more switches off in every corner; in between depends on the parts.
4. **Firmware power-off** takes about 10 ms and stays off.
5. **USB** behaves as designed: plugging in switches on, nothing switches off
   while plugged in, and unplugging leaves it on only if firmware holds it.
6. **Battery sense** needs about 0.3 s after power-on to settle.
