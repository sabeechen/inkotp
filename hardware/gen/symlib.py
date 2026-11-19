"""Load symbols from the installed KiCad libraries, flattening derived ones."""
import copy
import os

from sexpr import Sym, find, first, parse

SYMBOL_DIR = "/usr/share/kicad/symbols"
PROJECT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_cache = {}


def _library(lib):
    if lib not in _cache:
        base = PROJECT_DIR if lib == "inkotp" else SYMBOL_DIR
        with open(os.path.join(base, lib + ".kicad_sym")) as f:
            tree = parse(f.read())
        _cache[lib] = {s[1]: s for s in find(tree, "symbol")}
    return _cache[lib]


def load(lib, name):
    """Return a standalone symbol node named "lib:name"."""
    symbols = _library(lib)
    node = copy.deepcopy(symbols[name])
    parent = first(node, "extends")
    if parent is not None:
        base = copy.deepcopy(symbols[parent[1]])
        while first(base, "extends") is not None:
            up = copy.deepcopy(symbols[first(base, "extends")[1]])
            base = _merge(up, base, first(base, "extends")[1])
        node = _merge(base, node, parent[1])
    node[1] = f"{lib}:{name}"
    return node


def _merge(base, child, base_name):
    """Apply a derived symbol's name and properties on top of its parent."""
    name = child[1]
    props = {p[1]: p for p in find(child, "property")}
    out = [base[0], name]
    for item in base[2:]:
        if isinstance(item, list) and item[0] == "property" and item[1] in props:
            out.append(props.pop(item[1]))
        elif isinstance(item, list) and item[0] == "symbol":
            unit = copy.deepcopy(item)
            unit[1] = name + unit[1][len(base_name):]
            out.append(unit)
        elif isinstance(item, list) and item[0] == "extends":
            continue
        else:
            out.append(item)
    out.extend(props.values())
    return out


def pins(node):
    """List (number, name, x, y, angle, type) for every pin of a symbol."""
    out = []
    for unit in find(node, "symbol"):
        for pin in find(unit, "pin"):
            at = first(pin, "at")
            out.append({
                "number": first(pin, "number")[1],
                "name": first(pin, "name")[1],
                "x": float(at[1]), "y": float(at[2]), "angle": int(float(at[3])),
                "type": str(pin[1]),
                "hidden": any(isinstance(x, list) and x[0] == "hide" and (len(x) == 1 or x[1] == "yes") for x in pin) or Sym("hide") in pin,
            })
    return out


def prop(node, key):
    for p in find(node, "property"):
        if p[1] == key:
            return p[2]
    return ""
