"""Minimal s-expression reader and writer for KiCad files."""


class Sym(str):
    """An unquoted atom."""


def parse(text):
    pos = 0
    n = len(text)

    def read():
        nonlocal pos
        out = []
        while pos < n:
            c = text[pos]
            if c in " \t\r\n":
                pos += 1
            elif c == "(":
                pos += 1
                out.append(read())
            elif c == ")":
                pos += 1
                return out
            elif c == '"':
                pos += 1
                buf = []
                while text[pos] != '"':
                    if text[pos] == "\\":
                        buf.append(text[pos:pos + 2])
                        pos += 2
                    else:
                        buf.append(text[pos])
                        pos += 1
                pos += 1
                out.append("".join(buf))
            else:
                start = pos
                while pos < n and text[pos] not in " \t\r\n()":
                    pos += 1
                out.append(Sym(text[start:pos]))
        return out

    return read()[0]


def dump(node, depth=0):
    if isinstance(node, list):
        pad = "\t" * depth
        flat = all(not isinstance(x, list) for x in node)
        if flat:
            return "(" + " ".join(dump(x) for x in node) + ")"
        parts = ["(" + dump(node[0])]
        for x in node[1:]:
            if isinstance(x, list):
                parts.append("\n" + pad + "\t" + dump(x, depth + 1))
            else:
                parts.append(" " + dump(x))
        return "".join(parts) + "\n" + pad + ")"
    if isinstance(node, Sym):
        return str(node)
    if isinstance(node, str):
        return '"' + node + '"'
    if isinstance(node, float):
        return f"{node:.4f}".rstrip("0").rstrip(".")
    return str(node)


def find(node, key):
    return [x for x in node[1:] if isinstance(x, list) and x and x[0] == key]


def first(node, key):
    found = find(node, key)
    return found[0] if found else None
