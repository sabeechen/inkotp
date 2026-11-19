# InkOTP stick: printed case

**Status: first draft, not printed.** It clears the board model in software;
nothing here has been tried on a printer or against real parts.

`case.py` builds the case from the same numbers as the board
(`../gen/layout.py`), so a change to the board outline or to a switch position
carries through. Outside size is 35.5 x 96.7 x 6.85 mm.

| File in `out/` | What it is | Print |
| --- | --- | --- |
| `tray.stl` | Back half. Holds the board by its edges and the cell below it. | Back face down, one |
| `bezel.stl` | Front half, with the screen window. | Front face down, one |
| `button.stl` | Cap for one thumb switch. | Standing on one end, three |
| `dummy-board.stl` | A blank the size of the board, 1.0 mm thick. | Flat, one |
| `*.step`, `assembly.step` | The same parts for a CAD program. | |
| `*.png` | Renders, from `render.py`. | |

## Building

CadQuery is not packaged for Ubuntu, so it lives in an environment inside this
folder (about 1.8 GB). To recreate it:

    python3 -m venv --without-pip --system-site-packages case/.venv
    pip --python case/.venv/bin/python install cadquery

Then, from `hardware/`:

    case/.venv/bin/python case/case.py          # write the models
    case/.venv/bin/python case/case.py check    # and test them against the board
    case/.venv/bin/python case/render.py        # write the renders

`check` exports the routed board from KiCad with its 3D part models and
reports any overlap with the printed parts. KiCad has no models for the USB
port, the panel connector or the inductor, so the script adds plain blocks for
the USB shell, the glass and the cell. It also tests the places where the case
touches the board against the parts' courtyards.

## How it goes together

1. Drop the three button caps into the window in the tray's right wall. Each
   has a foot that sits behind the wall, under the switch bodies.
2. Lower the assembled board into the tray, screen up. The USB port and the
   switch plungers pass down open-topped slots. The board rests on ledges
   along its top and left edges and at three points lower down.
3. Plug in or solder the cell and lay it in the bay below the board. Wires
   run either side of the rib.
4. Hook the bezel's top edge over the tray's top end, swing it down, and fit
   four M2 x 4 mm thread-forming pan-head screws from the back.

The glass is taped to the board, not to the bezel. The bezel's lip covers the
glass border up to the edge of the viewing area and stands 0.15 mm off it.

Each cap stops against the board's edge 0.3 mm into its travel, so a hard
squeeze loads the board and the opposite wall, not the switch's solder joints.

## Settings

Sized for a 0.6 mm nozzle and 0.2 mm layers: 1.2 mm side walls, a 0.6 mm lip
over the glass, a 0.8 mm back. The constants at the top of `case.py` set every
clearance. The ones most likely to need changing after a test print:

| Constant | Now | What it does |
| --- | --- | --- |
| `CLR` | 0.25 | Gap between the board's edge and the walls |
| `FIT` | 0.12 | Gap where the bezel drops over the tray's ribs |
| `CAP_REST_GAP` | 0.05 | Play between a cap and its switch at rest |
| `CAP_STOP` | 0.3 | Cap travel before it stops against the board |
| `CAP_PROUD` | 0.6 | How far the caps stand out of the wall |
| `NIB` | 0.4 | Depth of the hook at the antenna end |
| `BAT_GAP` | 3.0 | Room between the board and the cell for the plug and wires |

## Not verified

- **USB port height.** GCT's selection guide gives a 3.16 mm shell and a
  1.0 mm "mid-mount offset". The case assumes the offset is how far the shell
  sinks into the board, which puts it flush with the front face and 2.16 mm
  off the back. The drawing itself could not be opened.
- **Switch travel.** Taken as 0.2 mm. Plunger position and height come from
  KiCad's model of the switch, not Panasonic's drawing.
- **Buzzer sound hole.** The 2 mm hole in the back is over the buzzer's
  centre; where the part's own hole is was not checked.
- **Panel.** Outline, viewing area and thickness are from Good Display's
  drawing. The fold of the tail between the glass and the slot is assumed to
  stay below the top of the glass.
- **Cell.** The bay is 26 x 31 x 3.6 mm for a 3 x 25 x 30 mm cell.
- **Screws.** The bosses take a 1.7 mm pilot hole and 3.1 mm of thread. A
  pan head up to 4 mm across and 1.6 mm tall sits flush.

## Printing notes

- Use PLA or plain PETG. Carbon-fibre filament absorbs radio signals and can
  conduct, and the antenna sits against the top wall.
- The hook's nib and the tray's groove are 0.4 mm overhangs with nothing
  under them. They are the first thing to look at if the top end does not
  hold.
- The screw-head recesses are on the tray's bed side, so the rim of each
  screw hole prints over air for a layer. Clean them with a 2.5 mm drill if
  needed.
- Print the dummy board first. With the switches, the USB port and the
  battery socket taped or glued to it, it tests the fit, the button feel and
  the USB opening before the real boards arrive.
