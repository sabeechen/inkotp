"""The InkOTP stick board: every part, its footprint and its connections.

This file is the single source for both the schematic and the board. Pin keys
are pin numbers or pin names; a name applies to every pin that carries it.
Pins that are not listed are left unconnected.
"""

R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOT235 = "Package_TO_SOT_SMD:SOT-23-5"
SOD323 = "Diode_SMD:D_SOD-323"
TESTPAD = "TestPoint:TestPoint_Pad_D1.0mm"

GROUPS = [
    ("usb", "USB-C and charger", 0),
    ("power", "Power latch and 3.3 V regulator", 0),
    ("mcu", "MCU module", 0),
    ("clock", "Clock", 1),
    ("input", "Buttons and buzzer", 1),
    ("epd", "E-ink panel connector and drive circuit", 1),
    ("test", "Test pads and power flags", 1),
]

PARTS = []


def part(ref, symbol, value, footprint, group, nets):
    lib, name = symbol.split(":")
    PARTS.append({"ref": ref, "lib": lib, "name": name, "value": value,
                  "footprint": footprint, "group": group, "nets": nets})


def res(ref, value, a, b, group):
    part(ref, "Device:R", value, R0402, group, {"1": a, "2": b})


def cap(ref, value, a, b, group, footprint=C0402):
    part(ref, "Device:C", value, footprint, group, {"1": a, "2": b})


# --- USB-C and charger -------------------------------------------------------
part("J1", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C", "inkotp:USB_C_MidMount", "usb",
     {"VBUS": "VBUS", "GND": "GND", "SHIELD": "GND", "CC1": "CC1", "CC2": "CC2",
      "D+": "USB_DP", "D-": "USB_DN"})
res("R1", "5.1k", "CC1", "GND", "usb")
res("R2", "5.1k", "CC2", "GND", "usb")
part("U4", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", "usb",
     {"I/O1": "USB_DP", "I/O2": "USB_DN", "GND": "GND", "VBUS": "VBUS"})
# Open-drain STAT, so the MCU can read it with its own pull-up.
part("U3", "Battery_Management:MCP73832-2-OT", "MCP73832T-2ACI/OT", SOT235, "usb",
     {"V_{DD}": "VBUS", "V_{SS}": "GND", "V_{BAT}": "VBAT", "PROG": "CHG_PROG", "STAT": "CHG_STAT"})
res("R3", "10k", "CHG_PROG", "GND", "usb")  # 100 mA charge current
cap("C1", "4.7u", "VBUS", "GND", "usb", C0603)
cap("C2", "4.7u", "VBAT", "GND", "usb", C0603)
part("J2", "Connector_Generic:Conn_01x02", "Battery", "inkotp:BatteryPads", "usb",
     {"1": "VBAT", "2": "GND"})
# The same connection as J2, as a socket: JST SH, side entry, facing the bottom
# edge, where the cell lies. Fit one or the other.
part("J4", "Connector_Generic_MountingPin:Conn_01x02_MountingPin", "SM02B-SRSS-TB",
     "inkotp:JST_SH_SM02B-SRSS-TB", "usb",
     {"1": "VBAT", "2": "GND", "MP": "GND"})

# --- Power latch and regulator -----------------------------------------------
# Q1 connects the battery to everything except the clock's backup pin. Its gate
# is pulled low by the select switch (D1), by the MCU holding itself on
# (Q2) or by USB power being present (Q3).
part("Q1", "Transistor_FET:AO3401A", "AO3401A", SOT23, "power",
     {"S": "VBAT", "D": "VSW", "G": "PGATE"})
# 100k, not more: leakage into this node when off flows through R4 and must
# not move Q1's gate. For the same reason D1 is a silicon pair, not a
# Schottky, whose leakage switched the board on when warm in simulation
# (see sim/README.md).
res("R4", "100k", "PGATE", "VBAT", "power")
part("D1", "Diode:BAV70", "BAV70", SOT23, "power",
     {"1": "PGATE", "2": "BTN_SELECT", "3": "SW_SELECT"})
part("Q2", "Transistor_FET:BSS138", "BSS138", SOT23, "power",
     {"D": "PGATE", "S": "GND", "G": "HOLD_G"})
res("R5", "1k", "HOLD", "HOLD_G", "power")
res("R6", "1M", "HOLD_G", "GND", "power")
cap("C3", "1u", "HOLD_G", "GND", "power")  # rides through an MCU reset
part("Q3", "Transistor_FET:BSS138", "BSS138", SOT23, "power",
     {"D": "PGATE", "S": "GND", "G": "VBUS_DET"})
res("R7", "100k", "VBUS", "VBUS_DET", "power")
res("R8", "100k", "VBUS_DET", "GND", "power")
part("U2", "Regulator_Linear:AP2112K-3.3", "AP2112K-3.3", SOT235, "power",
     {"VIN": "VSW", "EN": "VSW", "GND": "GND", "VOUT": "+3V3"})
cap("C4", "1u", "VSW", "GND", "power")
cap("C5", "10u", "+3V3", "GND", "power", C0603)
res("R9", "1M", "VSW", "BAT_SENSE", "power")
res("R10", "1M", "BAT_SENSE", "GND", "power")
cap("C6", "100n", "BAT_SENSE", "GND", "power")

# --- MCU module ---------------------------------------------------------------
part("U1", "RF_Module:ESP32-S3-MINI-1", "ESP32-S3-MINI-1-N8", "inkotp:ESP32-S3-MINI-1", "mcu",
     {"GND": "GND", "3V3": "+3V3", "EN": "EN",
      "USB_D+": "USB_DP", "USB_D-": "USB_DN",
      # Right-hand pins (IO0 to IO11) face the switches and clock; bottom pins
      # (IO12 to IO26) face the panel connector and the strip below it.
      # The up switch is on IO0, the boot-mode pin: holding it during a reset
      # starts the chip's built-in USB loader.
      "IO0": "BTN_UP", "IO1": "BAT_SENSE", "IO5": "BTN_SELECT", "IO6": "BTN_DOWN",
      "IO7": "HOLD", "IO8": "SDA", "IO9": "SCL", "IO10": "RTC_INT", "IO11": "BUZZ",
      "IO12": "EPD_SCK", "IO13": "EPD_DC", "IO14": "EPD_RST", "IO15": "EPD_BUSY",
      "IO16": "EPD_CS", "IO17": "EPD_MOSI", "IO18": "VBUS_DET", "IO21": "CHG_STAT"})
cap("C7", "10u", "+3V3", "GND", "mcu", C0603)
cap("C8", "100n", "+3V3", "GND", "mcu")
res("R11", "10k", "EN", "+3V3", "mcu")
cap("C9", "1u", "EN", "GND", "mcu")

# --- Clock ----------------------------------------------------------------------
# Runs from 3.3 V while the device is on and from the battery, through its
# backup pin, while it is off. Temperature compensated, 2.5 ppm. The clock
# output is not used; firmware should turn it off to save power.
part("U5", "inkotp:RV-3032-C7", "RV-3032-C7", "Package_SON:MicroCrystal_C7_SON-8_1.5x3.2mm_P0.9mm", "clock",
     {"VDD": "+3V3", "VSS": "GND", "VBACKUP": "RTC_BACKUP", "SDA": "SDA", "SCL": "SCL",
      "~{INT}": "RTC_INT", "EVI": "GND"})
res("R12", "1k", "VBAT", "RTC_BACKUP", "clock")
cap("C10", "100n", "RTC_BACKUP", "GND", "clock")
cap("C11", "100n", "+3V3", "GND", "clock")
res("R13", "10k", "SDA", "+3V3", "clock")
res("R14", "10k", "SCL", "+3V3", "clock")

# --- Buttons and buzzer ---------------------------------------------------------
# Three side-push switches on the right edge, under the thumb. A printed cap in
# the case can span them as one rocker. Pad 2 is the pair nearest the board edge.
EDGE_SWITCH = "Button_Switch_SMD:SW_SPST_EVQP7A"
part("SW1", "Switch:SW_Push", "EVQP7J01P", EDGE_SWITCH, "input", {"1": "BTN_UP", "2": "GND"})
part("SW2", "Switch:SW_Push", "EVQP7J01P", EDGE_SWITCH, "input", {"1": "SW_SELECT", "2": "GND"})
part("SW3", "Switch:SW_Push", "EVQP7J01P", EDGE_SWITCH, "input", {"1": "BTN_DOWN", "2": "GND"})
# Reset, below the thumb switches and meant to sit behind a pinhole in the
# case. Held for about two seconds on battery it also lets the power latch
# drop out (C3 discharges through R6), which switches a hung device off.
part("SW4", "Switch:SW_Push", "EVQP7J01P", EDGE_SWITCH, "input", {"1": "EN", "2": "GND"})
# Same Sky's land pattern is the same as the Murata PKMCS0909E's.
part("BZ1", "Device:Buzzer", "CPT-9019A-SMT", "Buzzer_Beeper:Buzzer_Murata_PKMCS0909E", "input",
     {"1": "BUZZ_P", "2": "GND"})
res("R15", "220", "BUZZ", "BUZZ_P", "input")

# --- E-ink panel -----------------------------------------------------------------
# Good Display GDEY0154D67, wired as in section 9 of its datasheet. The tail
# folds behind the board, which reverses its pin order as the connector sees
# it. The Hirose connector numbers its contacts from the other end to most, so
# the two reversals cancel: connector pad n carries panel pin n.
PANEL = {2: "EPD_GDR", 3: "EPD_RESE", 4: "EPD_PIN4", 5: "EPD_VSH2", 8: "GND", 9: "EPD_BUSY",
         10: "EPD_RST", 11: "EPD_DC", 12: "EPD_CS", 13: "EPD_SCK", 14: "EPD_MOSI", 15: "+3V3",
         16: "+3V3", 17: "GND", 18: "EPD_VDD", 20: "EPD_VSH1", 21: "EPD_VGH", 22: "EPD_VSL",
         23: "EPD_VGL", 24: "EPD_VCOM"}
part("J3", "Connector_Generic_MountingPin:Conn_01x24_MountingPin", "Panel FPC", "inkotp:Hirose_FH34SRJ-24S-0.5SH", "epd",
     dict({str(pin): net for pin, net in PANEL.items()}, MP="GND"))
part("L1", "Device:L", "47u", "inkotp:L_Wuerth_WE-LQS-3015", "epd", {"1": "+3V3", "2": "EPD_SW"})
part("Q4", "Transistor_FET:AO3400A", "AO3400A", SOT23, "epd", {"D": "EPD_SW", "G": "EPD_GDR", "S": "EPD_RESE"})
res("R16", "10k", "EPD_GDR", "GND", "epd")
res("R17", "2.2", "EPD_RESE", "GND", "epd")
part("D2", "Device:D_Schottky", "NSR0530H", SOD323, "epd", {"A": "EPD_SW", "K": "EPD_VGH"})
part("D3", "Device:D_Schottky", "NSR0530H", SOD323, "epd", {"A": "EPD_FLY", "K": "GND"})
part("D4", "Device:D_Schottky", "NSR0530H", SOD323, "epd", {"A": "EPD_VGL", "K": "EPD_FLY"})
cap("C12", "4.7u 25V", "EPD_SW", "EPD_FLY", "epd", C0603)
cap("C13", "1u 25V", "EPD_VGH", "GND", "epd", C0603)
cap("C14", "1u 25V", "EPD_VGL", "GND", "epd", C0603)
cap("C15", "1u 25V", "EPD_VSH1", "GND", "epd", C0603)
cap("C16", "1u 25V", "EPD_VSH2", "GND", "epd", C0603)
cap("C17", "1u 25V", "EPD_VSL", "GND", "epd", C0603)
cap("C18", "1u 25V", "EPD_VCOM", "GND", "epd", C0603)
cap("C19", "1u", "EPD_VDD", "GND", "epd")
cap("C20", "1u", "+3V3", "GND", "epd")
cap("C21", "4.7u", "+3V3", "GND", "epd", C0603)
# The datasheet's two pin tables disagree about pin 4; leave this unfitted
# unless the panel turns out to need it.
cap("C22", "DNP", "EPD_PIN4", "GND", "epd", C0603)

# Parts on the front face are soldered with an iron, so they get longer pads.
FRONT = ["R3", "C1", "C2", "R4", "R7", "R8", "R5", "R6", "C3", "C4", "C5", "R9", "R10", "C6"]
HAND_SOLDER = {R0402: "Resistor_SMD:R_0402_1005Metric_Pad0.72x0.64mm_HandSolder",
               C0402: "Capacitor_SMD:C_0402_1005Metric_Pad0.74x0.62mm_HandSolder",
               C0603: "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder"}
for _part in PARTS:
    if _part["ref"] in FRONT:
        _part["footprint"] = HAND_SOLDER[_part["footprint"]]

# --- Test pads ----------------------------------------------------------------------
# The serial console is on USB, so the UART pins have no pads.
for i, net in enumerate(["+3V3", "GND", "EN", "BTN_UP"], start=1):
    part(f"TP{i}", "Connector:TestPoint", net, TESTPAD, "test", {"1": net})
for i, net in enumerate(["GND", "VBUS", "VSW", "RTC_BACKUP"], start=1):
    part(f"#FLG{i}", "power:PWR_FLAG", "PWR_FLAG", "", "test", {"1": net})
