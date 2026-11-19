# Sourcing for hand assembly

Everything soldered to the board comes from DigiKey (US). The panel, the
battery and the bare boards are the only other orders.

Quantities are for three boards plus spares. Stock figures were read from
digikey.com on 2026-11-15. The resistor and capacitor part numbers at the
bottom were not stock-checked; they are common parts with many equivalents.

## DigiKey order

| Refs | Part number | Maker | Per board | Buy | In stock | Each (USD) |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | ESP32-S3-MINI-1-N8 | Espressif | 1 | 4 | 3,784 | 5.43 |
| U5 | RV-3032-C7-32.768KHZ-2.5PPM-TA-QC | Micro Crystal | 1 | 5 | 25,264 | 3.04 |
| U2 | AP2112K-3.3TRG1 | Diodes Inc. | 1 | 5 | 404,161 | 0.28 |
| U3 | MCP73832T-2ACI/OT | Microchip | 1 | 5 | 42,751 | 0.76 |
| U4 | USBLC6-2SC6 | STMicroelectronics | 1 | 5 | 7,913 | 0.54 |
| Q1 | AO3401A | Alpha & Omega | 1 | 5 | 296,577 | 0.52 |
| Q4 | AO3400A | Alpha & Omega | 1 | 5 | 127,911 | 0.52 |
| Q2 Q3 | BSS138 | onsemi | 2 | 10 | 688,762 | 0.33 |
| D1 | BAV70,215 | Nexperia | 1 | 5 | listed, count not read | 0.13 |
| D2 D3 D4 | NSR0530HT1G | onsemi | 3 | 15 | 200,778 | |
| L1 | 74404032470 | Wurth | 1 | 5 | 8,346 | 1.16 |
| J1 | USB4505-03-0-A | GCT | 1 | 5 | 27,564 | 0.72 |
| J3 | FH34SRJ-24S-0.5SH(50) | Hirose | 1 | 5 | 21,485 | 1.44 |
| J4 | SM02B-SRSS-TB | JST | 1 | 5 | 5,266 | 0.38 |
| (battery lead) | A02SR02SR30K51B | JST | 1 | 3 | 709 | 1.06 |
| SW1 SW2 SW3 SW4 | EVQ-P7J01P | Panasonic | 4 | 20 | 66,706 | 0.29 |
| BZ1 | CPT-9019A-SMT-TR | Same Sky | 1 | 5 | 43,775 | 1.31 |

The spares are there because the USB port and the panel connector are the
hardest parts to solder, and the clock chip is easy to lose.

### Resistors and capacitors (not stock-checked)

| Refs | Value | Suggested part | Per board | Buy |
| --- | --- | --- | --- | --- |
| R1 R2 | 5.1 k 0402 1 % | Yageo RC0402FR-075K1L | 2 | 25 |
| R3 R11 R13 R14 R16 | 10 k 0402 1 % | Yageo RC0402FR-0710KL | 5 | 25 |
| R6 R9 R10 | 1 M 0402 1 % | Yageo RC0402FR-071ML | 3 | 25 |
| R5 R12 | 1 k 0402 1 % | Yageo RC0402FR-071KL | 2 | 25 |
| R4 R7 R8 | 100 k 0402 1 % | Yageo RC0402FR-07100KL | 3 | 25 |
| R15 | 220 R 0402 1 % | Yageo RC0402FR-07220RL | 1 | 25 |
| R17 | 2.2 R 0402 1 % | Yageo RC0402FR-072R2L | 1 | 25 |
| C6 C8 C10 C11 | 100 nF 0402 X7R, 16 V or more | Samsung CL05B104KO5NNNC | 4 | 25 |
| C3 C4 C9 C19 C20 | 1 uF 0402 X5R, 10 V or more | Samsung CL05A105KA5NQNC | 5 | 25 |
| C1 C2 C21 | 4.7 uF 0603 X5R, 10 V or more | Samsung CL10A475KO8NNNC | 3 | 15 |
| C5 C7 | 10 uF 0603 X5R, 10 V or more | Samsung CL10A106KP8NNNC | 2 | 15 |
| C12 | 4.7 uF 0603 X5R, 25 V | Samsung CL10A475KA8NQNC | 1 | 10 |
| C13 to C18 | 1 uF 0603, 25 V | Samsung CL10A105KA8NNNC | 6 | 30 |

C22 is not fitted. If a suggested part is out of stock, any part with the same
value, size and voltage will do.

## What changed to get here

Five parts on the first draft could not be bought from DigiKey US. Each was
replaced by a part that DigiKey holds in depth.

| Was | Problem at DigiKey | Now | Effect on the design |
| --- | --- | --- | --- |
| Micro Crystal RV-3028-C7 clock | 0 in stock, both grades | RV-3032-C7 | Same package, different pin order, so the tracks around it were rerouted. 2.5 ppm against 1 ppm, about 80 seconds a year. Different registers, so firmware needs its own driver. |
| TE 2-1734839-4 panel connector | Obsolete | Hirose FH34SRJ-24S-0.5SH(50) | New footprint with the signal pads in the same place. Half the height (1.0 mm), and it grips both faces of the tail, so the contact-side question goes away. |
| Murata PKMCS0909E4000 buzzer | Out of stock, last-time-buy | Same Sky CPT-9019A-SMT-TR | Same pads. 0.2 mm taller at most. Its response has a peak near 2 kHz, where the click sound is. |
| Taiyo Yuden NR3015T470M inductor | Obsolete | Wurth 74404032470 | New footprint. 0.41 A against 0.32 A; the panel datasheet asks for 0.5 A, which no 47 uH part of this size reaches. |
| Diodes Inc. B0530WS-7-F | 0 in stock | onsemi NSR0530HT1G | Same package and rating. |

## Other orders

- **Panel:** Good Display GDEY0154D67, from buyepaper.com or Good Display's
  AliExpress shop. Buy 3 or 4; the glass is thin and the tail tears.
- **Battery:** a 302530 cell (3 x 25 x 30 mm, about 200 mAh) with a protection
  board and bare wire leads. Most US hobby shops stock 402030 instead, which is
  1 mm thicker and does not match the planned case. A search on 2026-11-16
  found 302530 cells with protection from US sellers on eBay; the listings
  were not opened. 303030 and 302535 cells
  are the same thickness and would also fit below the board. Plug polarity is not
  standardised, and no cell of this size comes with the JST SH plug that J4
  takes, so cut any plug off. Then either solder the leads to the pads at J2,
  or splice them to half of an A02SR02SR30K51B lead (a 2 inch lead with an SH
  plug on each end, so one lead makes two). Positive goes to the contact
  marked `+`; check with a meter before plugging in, because the board has no
  protection against a reversed cell.
- **Bare boards:** 4 layers, 1.0 mm, 0.127 mm track and gap, 0.2 mm drill with
  0.45 mm via pads, one internal slot and one edge notch. Minimum order is
  normally 5. The 0.2 mm drill and the 1.0 mm thickness may each be a priced
  option. Do not order until the "Before ordering" list in README.md is done.
- **Consumables:** solder paste for the back face. A stencil is optional for
  three boards but makes the module, the clock chip, the panel connector and
  the USB port much easier.
