"""Write a KiCad schematic in which every pin carries a net label.

Parts are laid out in rows, one row per functional group. Connections are
made by matching label names, not by drawn wires.
"""
import uuid

import symlib
from sexpr import Sym, dump

GRID = 1.27
NAMESPACE = uuid.UUID("6f1d3c1e-58a1-4c3b-9a55-1e0f0d3b7a10")


def _uid(*parts):
    return str(uuid.uuid5(NAMESPACE, "/".join(str(p) for p in parts)))


def _snap(v):
    return round(round(v / GRID) * GRID, 4)


def _effects(justify=None, hide=False):
    node = [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]
    if justify:
        node.append([Sym("justify")] + [Sym(j) for j in justify])
    if hide:
        node.append([Sym("hide"), Sym("yes")])
    return node


def _label(net, x, y, pin_angle, key):
    # The label reads away from the symbol body.
    angle, justify = {0: (180, ["right", "bottom"]), 180: (0, ["left", "bottom"]),
                      90: (270, ["right", "bottom"]), 270: (90, ["left", "bottom"])}[pin_angle]
    # Global labels, so net names match the board's without a sheet prefix.
    return [Sym("global_label"), net, [Sym("shape"), Sym("passive")], [Sym("at"), x, y, angle],
            _effects(justify[:1]), [Sym("uuid"), _uid("label", key)]]


def _extent(pins):
    xs = [p["x"] for p in pins] or [0]
    ys = [p["y"] for p in pins] or [0]
    return min(xs), max(xs), min(ys), max(ys)


def build(parts, groups, title, root_uuid):
    """parts: list of dicts (ref, lib, name, value, footprint, nets, group)."""
    lib_symbols = {}
    items = []
    column_y = {}
    for group, heading, column in groups:
        x_min = 20.0 + column * 290.0
        x_max = x_min + 275.0
        y = column_y.get(column, 28.0)
        members = [p for p in parts if p["group"] == group]
        if not members:
            continue
        items.append([Sym("text"), heading, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), x_min, _snap(y - 12), 0],
                      [Sym("effects"), [Sym("font"), [Sym("size"), 2.5, 2.5], [Sym("bold"), Sym("yes")]],
                       [Sym("justify"), Sym("left"), Sym("bottom")]], [Sym("uuid"), _uid("text", group)]])
        x = x_min
        row_height = 0.0
        for part in members:
            lib_id = f"{part['lib']}:{part['name']}"
            if lib_id not in lib_symbols:
                lib_symbols[lib_id] = symlib.load(part["lib"], part["name"])
            pins = symlib.pins(lib_symbols[lib_id])
            x0, x1, y0, y1 = _extent(pins)
            longest = max([len(n) for n in part["pin_nets"].values() if n] or [4])
            side = longest * 1.3 + 4
            horizontal = any(p["angle"] in (0, 180) for p in pins)
            vertical = any(p["angle"] in (90, 270) for p in pins)
            left = (side if horizontal else 6) - x0
            right = (side if horizontal else 6) + x1
            up = (side if vertical else 8) + y1
            down = (side if vertical else 6) - y0
            if x + left + right > x_max:
                x = x_min
                y += row_height + 6
                row_height = 0.0
            sx, sy = _snap(x + left), _snap(y + up)
            row_height = max(row_height, up + down)
            x += left + right + 4
            items.extend(_instance(part, lib_id, pins, sx, sy, y1, root_uuid))
        column_y[column] = y + row_height + 16
    sheet = [Sym("kicad_sch"), [Sym("version"), 20250114], [Sym("generator"), "inkotp_gen"],
             [Sym("generator_version"), "9.0"], [Sym("uuid"), root_uuid], [Sym("paper"), "A2"],
             [Sym("title_block"), [Sym("title"), title]],
             [Sym("lib_symbols")] + list(lib_symbols.values())]
    sheet.extend(items)
    sheet.append([Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]])
    sheet.append([Sym("embedded_fonts"), Sym("no")])
    return dump(sheet) + "\n"


def _instance(part, lib_id, pins, sx, sy, top, root_uuid):
    ref = part["ref"]
    out = []
    node = [Sym("symbol"), [Sym("lib_id"), lib_id], [Sym("at"), sx, sy, 0], [Sym("unit"), 1],
            [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("no" if ref.startswith("#") else "yes")],
            [Sym("on_board"), Sym("yes")], [Sym("dnp"), Sym("no")], [Sym("uuid"), _uid("sym", ref)]]
    hide_ref = ref.startswith("#")
    node.append([Sym("property"), "Reference", ref, [Sym("at"), sx, _snap(sy - top - 5.08), 0], _effects(hide=hide_ref)])
    node.append([Sym("property"), "Value", part["value"], [Sym("at"), sx, _snap(sy - top - 2.54), 0], _effects()])
    node.append([Sym("property"), "Footprint", part["footprint"], [Sym("at"), sx, sy, 0], _effects(hide=True)])
    node.append([Sym("property"), "Datasheet", "", [Sym("at"), sx, sy, 0], _effects(hide=True)])
    seen = set()
    for pin in pins:
        node.append([Sym("pin"), pin["number"], [Sym("uuid"), _uid("pin", ref, pin["number"])]])
        px, py = round(sx + pin["x"], 4), round(sy - pin["y"], 4)
        if (px, py) in seen:
            continue
        seen.add((px, py))
        net = part["pin_nets"].get(pin["number"])
        if net:
            out.append(_label(net, px, py, pin["angle"], f"{ref}.{pin['number']}"))
        elif pin["type"] != "no_connect":
            out.append([Sym("no_connect"), [Sym("at"), px, py], [Sym("uuid"), _uid("nc", ref, pin["number"])]])
    node.append([Sym("instances"), [Sym("project"), "inkotp",
                 [Sym("path"), "/" + root_uuid, [Sym("reference"), ref], [Sym("unit"), 1]]]])
    return [node] + out
