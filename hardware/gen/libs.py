"""Write the project's own footprints and symbols."""
import os

from sexpr import Sym, dump

FONT = [Sym("effects"), [Sym("font"), [Sym("size"), 0.8, 0.8], [Sym("thickness"), 0.12]]]


def _smd(number, x, y, w, h, layers=("F.Cu", "F.Paste", "F.Mask")):
    return [Sym("pad"), str(number), Sym("smd"), Sym("rect"), [Sym("at"), x, y], [Sym("size"), w, h],
            [Sym("layers")] + list(layers)]


def _slot(number, x, y, w, h, dw, dh):
    return [Sym("pad"), str(number), Sym("thru_hole"), Sym("oval"), [Sym("at"), x, y], [Sym("size"), w, h],
            [Sym("drill"), Sym("oval"), dw, dh], [Sym("layers"), "*.Cu", "*.Mask"]]


def _npth(x, y, d):
    return [Sym("pad"), "", Sym("np_thru_hole"), Sym("circle"), [Sym("at"), x, y], [Sym("size"), d, d],
            [Sym("drill"), d], [Sym("layers"), "*.Cu", "*.Mask"]]


def _line(x1, y1, x2, y2, layer, width=0.1):
    return [Sym("fp_line"), [Sym("start"), x1, y1], [Sym("end"), x2, y2],
            [Sym("stroke"), [Sym("width"), width], [Sym("type"), Sym("solid")]], [Sym("layer"), layer]]


def _rect(x1, y1, x2, y2, layer, width=0.1):
    return [_line(x1, y1, x2, y1, layer, width), _line(x2, y1, x2, y2, layer, width),
            _line(x2, y2, x1, y2, layer, width), _line(x1, y2, x1, y1, layer, width)]


def _footprint(name, descr, items, ref_y=-2.0):
    return [Sym("footprint"), name, [Sym("version"), 20241229], [Sym("generator"), "inkotp_gen"],
            [Sym("layer"), "F.Cu"], [Sym("descr"), descr],
            [Sym("property"), "Reference", "REF**", [Sym("at"), 0, ref_y, 0], [Sym("layer"), "F.SilkS"], FONT],
            [Sym("property"), "Value", name, [Sym("at"), 0, ref_y - 1.2, 0], [Sym("layer"), "F.Fab"], FONT],
            [Sym("attr"), Sym("smd")]] + items


def usb_c_midmount():
    """GCT USB4505 (1.0 mm offset), from gct.co/files/drawings/usb4505.pdf.

    Origin is on the board edge at the connector centreline; the board lies
    towards negative y. The 9.24 x 6.20 mm notch is part of the board outline,
    not of this footprint.
    """
    items = []
    row = [(("A1", "B12"), -3.20, 0.6), (("A4", "B9"), -2.40, 0.6), (("B8",), -1.75, 0.3),
           (("A5",), -1.25, 0.3), (("B7",), -0.75, 0.3), (("A6",), -0.25, 0.3), (("A7",), 0.25, 0.3),
           (("B6",), 0.75, 0.3), (("A8",), 1.25, 0.3), (("B5",), 1.75, 0.3), (("B4", "A9"), 2.40, 0.6),
           (("B1", "A12"), 3.20, 0.6)]
    for names, x, w in row:
        for n in names:
            # 0.05 mm shorter than GCT draws them, to stand 0.2 mm off the notch.
            items.append(_smd(n, x, -6.875, w, 0.95))
    for sx in (-5.62, 5.62):
        items.append(_slot("S1", sx, -1.60, 1.0, 2.2, 0.6, 1.8))
        items.append(_slot("S1", sx, -5.60, 1.0, 1.8, 0.6, 1.4))
    items += _rect(-4.47, -6.0, 4.47, 0.5, "F.Fab")
    items += _rect(-6.4, -7.7, 6.4, 0.75, "F.CrtYd", 0.05)
    return _footprint("USB_C_MidMount", "GCT USB4505-03-0-A mid-mount USB-C receptacle, 16 pin, 1.0 mm offset", items, -9.0)


def battery_pads():
    items = [_smd(1, -1.5, 0, 2.0, 3.0), _smd(2, 1.5, 0, 2.0, 3.0)]
    items += _rect(-2.75, -1.75, 2.75, 1.75, "F.CrtYd", 0.05)
    items.append(_line(-2.9, -1.0, -2.9, 1.0, "F.SilkS", 0.15))
    return _footprint("BatteryPads", "Solder pads for the battery leads, pad 1 positive", items, -2.8)


def fpc_connector():
    """Hirose FH34SRJ-24S-0.5SH(50), from the FH34 catalogue's mounting pattern.

    Contacts touch both faces of the tail. The tail enters from the positive-y
    side, where the two retention pads are; the signal leads and the flip-up
    actuator are on the other side. Seen from above with the leads at the top,
    contact 1 is at the right. The signal row sits at y = -1.35 so that this
    footprint can stand in for KiCad's TE 2-1734839-4 without moving a track.
    """
    items = [_smd(n, 5.75 - (n - 1) * 0.5, -1.35, 0.3, 0.8) for n in range(1, 25)]
    items += [_smd("MP", x, 1.15, 0.4, 0.8) for x in (-6.75, 6.75)]
    items += _rect(-7.0, -2.1, 7.0, 1.7, "F.Fab")
    items.append(_line(6.2, -2.1, 5.75, -1.8, "F.Fab"))
    items += _rect(-7.3, -2.4, 7.3, 2.0, "F.CrtYd", 0.05)
    return _footprint("Hirose_FH34SRJ-24S-0.5SH", "Hirose FH34SRJ-24S-0.5SH(50) FPC connector, 24 pin, 0.5 mm, "
                      "top and bottom contact, 1.0 mm high", items, -3.2)


def inductor():
    """Wurth WE-LQS 3015, from the 74404032470 datasheet's land pattern."""
    items = [_smd(1, -1.2, 0, 1.0, 2.7), _smd(2, 1.2, 0, 1.0, 2.7)]
    items += _rect(-1.5, -1.5, 1.5, 1.5, "F.Fab")
    items += _rect(-1.95, -1.75, 1.95, 1.75, "F.CrtYd", 0.05)
    return _footprint("L_Wuerth_WE-LQS-3015", "Wurth WE-LQS 3015 power inductor, 3 x 3 x 1.5 mm", items, -2.4)


def clock_symbol():
    """Micro Crystal RV-3032-C7. Same package as the RV-3028-C7 that KiCad has
    a symbol for, but with a different pin order."""
    return _box_symbol("RV-3032-C7", "U", [(1, "VBACKUP"), (2, "SDA"), (3, "~{INT}"), (4, "EVI")],
                       [(8, "SCL"), (7, "CLKOUT"), (6, "VDD"), (5, "VSS")])


def module_footprint():
    """The stock ESP32-S3-MINI-1 footprint without Espressif's antenna
    keep-out, which is wider than this whole board. The board defines a
    smaller keep-out of its own."""
    from sexpr import parse
    with open("/usr/share/kicad/footprints/RF_Module.pretty/ESP32-S2-MINI-1.kicad_mod") as f:
        node = parse(f.read())
    kept = []
    for item in node:
        if isinstance(item, list):
            if item[0] == "zone":
                continue
            layer = [x for x in item if isinstance(x, list) and x[0] == "layer"]
            if layer and layer[0][1] == "F.CrtYd":
                continue
        kept.append(item)
    kept[1] = "ESP32-S3-MINI-1"
    kept += _rect(-7.95, -10.5, 7.95, 10.5, "F.CrtYd", 0.05)
    return kept


def battery_socket():
    """The stock JST SH SM02B-SRSS-TB footprint without the corner of its
    outline that would print over the USB port's shell pad."""
    from sexpr import parse
    with open("/usr/share/kicad/footprints/Connector_JST.pretty/"
              "JST_SH_SM02B-SRSS-TB_1x02-1MP_P1.00mm_Horizontal.kicad_mod") as f:
        node = parse(f.read())
    kept = []
    for item in node:
        if isinstance(item, list) and item[0] == "fp_line":
            layer = [x for x in item if isinstance(x, list) and x[0] == "layer"][0][1]
            ends = [x for x in item if isinstance(x, list) and x[0] in ("start", "end")]
            if layer == "F.SilkS" and all(float(str(e[1])) > 1.0 and float(str(e[2])) < 0.8 for e in ends):
                continue
        kept.append(item)
    kept[1] = "JST_SH_SM02B-SRSS-TB"
    return kept


def _box_symbol(name, ref, left, right):
    """A plain rectangle symbol with pins down each side."""
    rows = max(len(left), len(right))
    half_h = rows * 1.27 + 1.27
    half_w = 7.62
    sym = [Sym("symbol"), name, [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes")],
           [Sym("on_board"), Sym("yes")]]
    for key, value, y in (("Reference", ref, half_h + 1.27), ("Value", name, -half_h - 1.27),
                          ("Footprint", "", 0), ("Datasheet", "", 0), ("Description", "", 0)):
        effects = [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]
        if key not in ("Reference", "Value"):
            effects.append([Sym("hide"), Sym("yes")])
        sym.append([Sym("property"), key, value, [Sym("at"), 0, y, 0], effects])
    body = [Sym("symbol"), name + "_0_1",
            [Sym("rectangle"), [Sym("start"), -half_w, half_h], [Sym("end"), half_w, -half_h],
             [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]],
             [Sym("fill"), [Sym("type"), Sym("background")]]]]
    pins = [Sym("symbol"), name + "_1_1"]
    for side, x, angle in ((left, -half_w - 2.54, 0), (right, half_w + 2.54, 180)):
        for i, (number, pin_name) in enumerate(side):
            y = half_h - 2.54 - i * 2.54
            pins.append([Sym("pin"), Sym("passive"), Sym("line"), [Sym("at"), x, y, angle], [Sym("length"), 2.54],
                         [Sym("name"), pin_name, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]],
                         [Sym("number"), str(number), [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]]])
    return sym + [body, pins]


POWER_NETS = ["VBUS", "VBAT", "VSW", "+3V3", "EPD_SW", "EPD_RESE"]


def project_file(project_dir):
    """Set net classes and board rules in the project file that KiCad writes
    alongside the board. Sizes in millimetres."""
    import json
    path = os.path.join(project_dir, "inkotp.kicad_pro")
    with open(path) as f:
        data = json.load(f)
    # JLCPCB's published limits for multilayer boards, except text height,
    # which they give as 1.0 mm.
    data["board"]["design_settings"]["rules"].update({
        "min_clearance": 0.1, "min_track_width": 0.1, "min_via_diameter": 0.45, "min_resolved_spokes": 1,
        "min_through_hole_diameter": 0.2, "min_via_annular_width": 0.1,
        "min_copper_edge_clearance": 0.2, "min_hole_clearance": 0.2, "min_hole_to_hole": 0.25,
        "min_text_height": 0.8, "min_text_thickness": 0.15, "min_silk_clearance": 0.0})
    data["board"]["design_settings"]["rule_severities"].update({
        "text_height": "error", "text_thickness": "error", "silk_overlap": "error", "silk_over_copper": "error"})
    default = data["net_settings"]["classes"][0]
    default.update({"clearance": 0.127, "track_width": 0.127, "via_diameter": 0.45, "via_drill": 0.2})
    power = dict(default, name="Power", track_width=0.25, priority=0)
    data["net_settings"]["classes"] = [default, power]
    data["net_settings"]["netclass_patterns"] = [{"netclass": "Power", "pattern": n} for n in POWER_NETS]
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def write(project_dir, footprints, symbols):
    pretty = os.path.join(project_dir, "inkotp.pretty")
    os.makedirs(pretty, exist_ok=True)
    for fp in footprints:
        with open(os.path.join(pretty, fp[1] + ".kicad_mod"), "w") as f:
            f.write(dump(fp) + "\n")
    lib = [Sym("kicad_symbol_lib"), [Sym("version"), 20241209], [Sym("generator"), "inkotp_gen"],
           [Sym("generator_version"), "9.0"]] + symbols
    with open(os.path.join(project_dir, "inkotp.kicad_sym"), "w") as f:
        f.write(dump(lib) + "\n")
    with open(os.path.join(project_dir, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table\n\t(version 7)\n\t(lib (name "inkotp")(type "KiCad")(uri "${KIPRJMOD}/inkotp.pretty")(options "")(descr "InkOTP footprints"))\n)\n')
    with open(os.path.join(project_dir, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n\t(version 7)\n\t(lib (name "inkotp")(type "KiCad")(uri "${KIPRJMOD}/inkotp.kicad_sym")(options "")(descr "InkOTP symbols"))\n)\n')
