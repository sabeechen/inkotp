# InkOTP stick: custom board

A first-draft board for a thinner InkOTP: an ESP32-S3-MINI-1, the same 1.54 inch
e-ink panel as the Core Ink, three thumb switches, a reset switch, USB-C and a
LiPo cell (plugged in or soldered) on a 32 x 54.5 mm, four-layer, 1.0 mm board.

**Status: unreviewed draft.** It passes KiCad's electrical and design rule
checks, but it has not been reviewed by a person, built or tested. Do not order
boards from it without going through the list under "Before ordering".

## Files

| File | What it is |
| --- | --- |
| `inkotp.kicad_pro`, `.kicad_sch`, `.kicad_pcb` | KiCad 9 project, schematic and routed board |
| `inkotp.kicad_sym`, `inkotp.pretty/` | Project symbol (clock) and footprints (USB port, panel connector, inductor, battery pads, module) |
| `bom.csv` | Parts list with suggested part numbers |
| `sourcing.md` | DigiKey order list with quantities for hand assembly, and why each part was chosen |
| `docs/` | Schematic PDF and board renders |
| `gen/` | The Python scripts that generate all of the above |
| `sim/` | An ngspice simulation of the power latch and reset switch, with its findings |
| `case/` | A 3D-printed case generated from the board's layout; unprinted first draft, see `case/README.md` |

## How it is generated

`gen/design.py` lists every part and its connections, and `gen/layout.py` says
where each part sits. Both the schematic and the board come from those two
files, so they cannot drift apart. The schematic connects pins by net label
instead of drawn wires.

    python3 gen/build.py schematic   # rewrite the schematic only
    python3 gen/build.py board       # rewrite the board, UNROUTED
    python3 gen/route.py freerouting.jar 200   # autoroute it (needs Docker)
    python3 gen/bom.py               # rewrite bom.csv
    python3 gen/sync.py              # apply a part change to the ROUTED board
    python3 gen/finish.py U5.1 ...   # connect single pads by hand
    python3 gen/labels.py            # print part names on the silkscreen

`build.py board` and `build.py all` discard the routing. The autorouter
(Freerouting 2.1.0) gives a different result on every run and usually leaves a
few connections open; `gen/route_best.py` repeats it and keeps the best
attempt. The last few are quicker to finish by hand than to chase with more
autorouter runs. The committed board is the best of four attempts, finished
with `gen/finish.py`:

- `finish.py R1.2 TP1.1` added a via beside a ground pad and a 3.3 V test pad
  that the pours did not reach;
- its `bridge()` function added two short links on the back face at x = 24 to
  25 mm in the bottom strip, where an inner-layer track had cut the 3.3 V
  plane in two and left the regulator's output on the wrong side.

The USB port's escape routing and the ground vias under the module are placed
by `layout.py` before routing.

### Changing a part without rerouting

When five parts were swapped for ones DigiKey stocks, the board was not
rerouted from scratch. `gen/sync.py` reads `design.py` and updates the routed
board in place: it swaps footprints where they differ, reassigns pad nets, and
removes only the tracks that ran to pads which moved or changed net. That left
six open connections around the clock chip, whose pin order had changed.
`route.py` can finish a partly routed board, but took twelve minutes and left
three open, so they were finished with `finish.py`, which routes a named pad to
the nearest copper of its net:

    python3 gen/finish.py U5.2 U5.3 U5.8 R14.1 U5.1 U5.6 J3.MP

The order matters: each route becomes an obstacle for the next. One leftover
via and a stub of track on the clock's SCL line were then removed by hand.

The reset switch was added the same way. `sync.py` places a new part if
`layout.py` gives it a fixed position, and these connected it and moved the up
switch to the boot pin:

    python3 gen/finish.py U1.4:14.5:0.1 TP4.1:11:0.1 SW4.1:9:0.1

The numbers after a pad are how far to search, in millimetres, and the grid.

## Reset and recovery

SW4, below the three thumb switches on the same edge, pulls the module's
enable pin low. It is the same part as the thumb switches and is meant to sit
behind a pinhole in the case, or a recessed cut-out, so that a thumb cannot
press it by accident.

- **Tap:** resets the processor. The power latch rides through (C3 holds Q2
  on for about a second).
- **Hold for two seconds or more, on battery:** C3 discharges, the latch lets
  go and the device switches off, even if the firmware has hung with its
  hold line high. On USB power the device stays on.
- **Hold Up, tap reset:** the up switch is on IO0, the boot-mode pin, so the
  chip starts its built-in USB loader. That loader is in ROM and cannot be
  erased, so a board with broken firmware can always be reflashed. Holding
  Up while switching on does the same; on battery the device switches off
  again when the switches are released.

None of this has been tried on hardware. Firmware should still enable the
chip's watchdog, which recovers from most hangs without anyone pressing
anything.

## Battery

The cell lies below the board's bottom edge and connects in one of two ways,
which are the same two nets:

- **J4**, a JST SH side-entry socket (SM02B-SRSS-TB, 2.9 mm tall) below the
  USB port, mouth out of the bottom edge. `+` on the silkscreen marks its
  positive contact. It sits 0.3 mm from the USB port's shell tab, which is
  why `inkotp.kicad_dru` lets those two courtyards overlap, and its footprint
  is KiCad's with one corner of the outline removed.
- **J2**, two solder pads in the opposite bottom corner.

The board has no protection against a reversed cell and none of its own
against running the cell flat. What there is:

- When off, Q1 disconnects everything except the clock's backup pin and the
  charger's leakage, a few microamps in all by the datasheets (not measured),
  which a 200 mAh cell can supply for years.
- When on, firmware can read the cell through IO1 and switch off by letting
  go of the hold line. It does not do this yet for this board; about 3.3 V is
  a sensible threshold.
- If firmware hangs with the hold line high, nothing on the board stops the
  drain. The cell's own protection board is then the only cut-off, usually
  near 2.5 V, which is why `sourcing.md` asks for a protected cell. The
  watchdog and the reset switch are the defences against the hang itself.
- The charger (MCP73832) trickle-charges a deeply discharged cell before
  charging at full current.

## Labels

`gen/labels.py` prints each part's value or name beside it in silkscreen, and
the function of each switch, test pad and the battery's positive pad. Text is
0.8 mm tall with 0.15 mm lines and stays 0.15 mm from pads. Run it again after
any change to the parts; it replaces its own labels.

- Identical parts that sit together share one label with a count, such as
  `1u 25V x5`.
- Six parts had no room for their name and carry their reference instead:
  Q1, Q2, Q3, C11, C16 and R2. A key printed in the open area below the panel
  connector says what each is, and `bom.csv` lists every reference.
- Three parts have no label at all: Q4 (AO3400A), the three-pin part between
  the inductor and the board edge, which the key lists; L1 (47uH), the
  inductor; and R12 (1k), the small part between the battery socket and the
  one labelled `100n`.
- The transistor marks, the key, the socket's `+` and one `5.1k` are at
  positions set by hand in `labels.py`, not found by the script.
- The top row beside the clock chip is tight: its three small parts are, from
  the up switch towards the module, 10k, 10k and 100n. `10k x2` is printed at
  the switch end.
- `PANEL` marks the connector, with `1` and `24` at its end contacts. The
  battery's negative pad is the unmarked one next to `BAT+`.

## Fabrication limits

The board's rules in `inkotp.kicad_pro` (written by `gen/libs.py`) and
`inkotp.kicad_dru` are JLCPCB's published limits for multilayer boards, read in
November 2026, and the board passes KiCad's rule check against them. Order it
as four layers, 1.0 mm thick, with tented vias.

- Tracks and gaps are 0.127 mm; vias are 0.45 mm with a 0.2 mm hole, the
  smallest JLCPCB makes without a surcharge. PCBWay's standard limits ask for
  a wider ring around each via (0.15 mm against this board's 0.125 mm).
- Copper stays 0.2 mm from every routed edge. To get there the USB port's
  pads are 0.05 mm shorter than GCT draws them, and five tracks and a via
  beside the panel slot and the right edge were moved by hand.
- Label text is 0.8 mm tall. JLCPCB asks for 1.0 mm, which does not fit on
  the back face; expect the labels to print but not crisply.
- The slot and the USB notch are drawn with square inside corners. A router
  leaves them rounded, by a radius JLCPCB does not publish; check that the
  USB port's body clears the notch corners.
- Thickness is held to 10% and the outline to 0.2 mm (0.1 mm on request).

## Layout

Coordinates in `layout.py` are seen from the front (screen side). The glass
covers the top 37.3 mm, so everything behind it is on the back face. The
panel's tail passes through the slot below the glass and folds up the back
into its connector. Below the slot there is no glass; the chips for charging
and power sit on the back there, and their resistors and capacitors sit on the
front with hand-solder pads.

Inner layer 1 is ground and inner layer 2 is 3.3 V.

## Before ordering

- **Edge switches.** Four Panasonic EVQP7J01P side-push switches use KiCad's
  stock footprint. Panasonic does not say where the board edge should sit; it
  is set 1.5 mm from the switch centre, leaving about 0.6 mm of plunger
  overhang. The switches have no mounting tabs, so the case's button cap must
  bottom out on the case and not on the switches.
- **3.3 V plane.** The regulator's output reaches the rest of the board through
  the two hand-added links described above. Rerouting the inner-layer track
  that splits the plane would be better.
- **USB port footprint.** Drawn from GCT's USB4505 drawing, which gives the
  pattern for a 0.8 mm board; this board is 1.0 mm.
- **Panel connector.** Hirose FH34SRJ-24S-0.5SH(50), which touches both faces
  of the tail. Its footprint is drawn from Hirose's catalogue and has not been
  checked against a part. The pad order follows Good Display's photos and
  drawing of the GDEY0154D67 with the tail folded behind the board. The signal
  pads are where the earlier TE connector's were, so how far the tail reaches
  into this connector is an estimate, good to about 0.5 mm; the fold has that
  much slack, but confirm the tail reaches and seats.
- **Clock.** RV-3032-C7 in place of the RV-3028-C7. Its clock output pin is
  left open and is on by default; firmware should turn it off, and must enable
  the backup switchover. The routing around it was done by `finish.py`.
- **Buzzer.** Same Sky CPT-9019A-SMT-TR on the Murata footprint, which has the
  same pads. Its datasheet draws the pads turned a quarter turn from the body
  views; check which edges the terminals are on before soldering.
- **Panel drive circuit.** Copied from the panel datasheet's reference circuit.
  The datasheet's two pin tables disagree about pin 4, so C22 is an unfitted
  footprint there. The inductor (Wurth 74404032470) saturates at 0.41 A against
  the 0.5 A the datasheet asks for; no 47 uH part of this size reaches 0.5 A.
  Its footprint is drawn from Wurth's datasheet.
- **Antenna.** Copper is kept clear only directly under and beside the
  antenna, far less than Espressif recommends. Expect reduced Wi-Fi range.
- **Routing quality.** Autorouted. The boost stage, the USB data pair and the
  battery and 3.3 V paths have not been laid out with any care.
- **Power latch.** Simulated in `sim/` but not built. The simulation found
  that the first draft (a Schottky pair for D1, 1 M for R4) could switch
  itself on when warm, so D1 is now a BAV70 and R4 is 100 k. The models are
  generic; see `sim/README.md` for how far to trust them.
- **Reset switch.** Untested, like the power latch it works with. Its two
  hold times depend on C3 and R6; see "Reset and recovery".
- **Battery.** The socket's position against the USB port, and which way
  round the lead goes, have not been checked on a part.
- **Labels.** Placed by script and checked only against KiCad's silkscreen
  rules and a render. The text is smaller than JLCPCB's stated minimum; see
  "Fabrication limits". Compare them with `bom.csv` before trusting one.
- **Firmware.** The pin map differs from the Core Ink, and the board has no
  support in the firmware yet. The up switch is on IO0. Firmware must raise
  the hold line as early as it can, because the board stays on only while
  select is held until then, and should wait 0.3 s after power-on before
  reading the battery.

## Soldering

The back face needs hot air or a hotplate for the module, the clock chip and
the USB port. The front face carries only two-terminal passives and
can be done with an iron afterwards.
