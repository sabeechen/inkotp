#!/usr/bin/env python3
"""Write the parts list for the InkOTP stick board to ../bom.csv.

Part numbers are suggestions that match the footprints and ratings in
design.py. Check stock and datasheets before ordering.
"""
import csv
import os
import re
from collections import OrderedDict

import design

HERE = os.path.dirname(os.path.abspath(__file__))

# (value, footprint name) -> (manufacturer, part number, note)
SUGGESTED = {
    ("ESP32-S3-MINI-1-N8", "ESP32-S3-MINI-1"): ("Espressif", "ESP32-S3-MINI-1-N8", "PCB antenna version, 8 MB flash"),
    ("AP2112K-3.3", "SOT-23-5"): ("Diodes Inc.", "AP2112K-3.3TRG1", "600 mA LDO with enable"),
    ("MCP73832T-2ACI/OT", "SOT-23-5"): ("Microchip", "MCP73832T-2ACI/OT", "4.2 V charger, open-drain status"),
    ("USBLC6-2SC6", "SOT-23-6"): ("STMicroelectronics", "USBLC6-2SC6", "USB ESD protection"),
    ("RV-3032-C7", "MicroCrystal_C7_SON-8_1.5x3.2mm_P0.9mm"): ("Micro Crystal", "RV-3032-C7-32.768KHZ-2.5PPM-TA-QC", "temperature-compensated clock"),
    ("AO3401A", "SOT-23"): ("Alpha & Omega", "AO3401A", "P-channel, battery switch"),
    ("AO3400A", "SOT-23"): ("Alpha & Omega", "AO3400A", "N-channel 30 V, panel boost switch"),
    ("BSS138", "SOT-23"): ("onsemi", "BSS138", "N-channel, logic level"),
    ("BAV70", "SOT-23"): ("Nexperia", "BAV70,215", "dual switching diode, common cathode; not a Schottky, which leaks too much"),
    ("NSR0530H", "D_SOD-323"): ("onsemi", "NSR0530HT1G", "30 V 0.5 A Schottky"),
    ("47u", "L_Wuerth_WE-LQS-3015"): ("Wurth", "74404032470", "47 uH, 3 x 3 x 1.5 mm, 0.41 A saturation; the panel datasheet asks for 0.5 A"),
    ("USB-C", "USB_C_MidMount"): ("GCT", "USB4505-03-0-A", "mid-mount, 1.0 mm offset"),
    ("SM02B-SRSS-TB", "JST_SH_SM02B-SRSS-TB"): ("JST", "SM02B-SRSS-TB", "battery socket, JST SH 2 pin side entry, 2.9 mm tall; optional, the pads at J2 do the same job"),
    ("Panel FPC", "Hirose_FH34SRJ-24S-0.5SH"): ("Hirose", "FH34SRJ-24S-0.5SH(50)", "24 pin 0.5 mm, contacts on both faces, 1.0 mm tall"),
    ("EVQP7J01P", "SW_SPST_EVQP7A"): ("Panasonic", "EVQP7J01P", "side-push tactile switch, 1.6 N, 1.35 mm tall"),
    ("CPT-9019A-SMT", "Buzzer_Murata_PKMCS0909E"): ("Same Sky", "CPT-9019A-SMT-TR", "piezo sounder, 9 x 9 x 1.9 mm"),
    ("Battery", "BatteryPads"): ("", "", "solder pads only, no part"),
}
PASSIVE_NOTE = {"R": "resistor, 1 %", "C": "ceramic capacitor, X5R or X7R"}
OFF_BOARD = [
    ("Panel", 1, "Good Display", "GDEY0154D67", "1.54 in 200 x 200 e-ink panel"),
    ("Battery", 1, "", "LiPo 3.7 V, about 3 x 26 x 30 mm, with protection circuit", "for example a 302530 cell, 200 to 250 mAh"),
    ("PCB", 1, "", "4 layer, 1.0 mm thick, 32 x 54.5 mm", "0.127 mm track and gap, 0.2 mm drill"),
]


def natural(ref):
    m = re.match(r"([A-Z#]+)(\d+)", ref)
    return (m.group(1), int(m.group(2)))


def rows():
    groups = OrderedDict()
    for part in design.PARTS:
        if not part["footprint"] or part["footprint"].startswith("TestPoint"):
            continue
        key = (part["value"], part["footprint"].split(":")[1].split("_Pad")[0])
        groups.setdefault(key, []).append(part["ref"])
    out = []
    for (value, footprint), refs in groups.items():
        refs.sort(key=natural)
        maker, mpn, note = SUGGESTED.get((value, footprint), ("", "", ""))
        if not mpn and refs[0][0] in PASSIVE_NOTE and footprint[:2] in ("R_", "C_"):
            note = PASSIVE_NOTE[refs[0][0]] + (", 25 V or higher" if "25V" in value else "")
            if value == "DNP":
                note = "not fitted"
        out.append((" ".join(refs), len(refs), value, footprint, maker, mpn, note))
    out.sort(key=lambda r: natural(r[0].split()[0]))
    return out


def main():
    path = os.path.normpath(os.path.join(HERE, "..", "bom.csv"))
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["References", "Quantity", "Value", "Footprint", "Manufacturer", "Part number", "Note"])
        for row in rows():
            w.writerow(row)
        for name, qty, maker, mpn, note in OFF_BOARD:
            w.writerow([name, qty, "", "off board", maker, mpn, note])
    print("wrote", path)
    for row in rows():
        print(" | ".join(str(c) for c in row))


if __name__ == "__main__":
    main()
