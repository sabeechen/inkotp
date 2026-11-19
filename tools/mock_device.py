#!/usr/bin/env python3
"""Serve web/index.html with a fake device behind it, for working on the UI.

    python3 tools/mock_device.py [port]

Open http://localhost:8080/#mockcode. Nothing is validated the way the
firmware validates it; this only keeps enough state for the page to behave.
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

TOKEN = "mockcode"
INDEX = Path(__file__).resolve().parent.parent / "web" / "index.html"
DECODER = INDEX.parent / "vendor" / "jsqr.min.js"

state = {
    "accounts": {0: {"label": "Example", "algo": "SHA1", "digits": 6, "period": 30}},
    "nets": ["HomeNet"],
    "pin": {"enabled": False, "length": 0, "pending": False},
    "settings": {"sleepSecs": 60, "unlockSecs": 0, "maxTries": 10, "autoSync": True,
                 "compact": False, "sounds": False, "owner": ""},
    "order": [0],
    "offset": 0,
    "lastSync": 0,
}


class Handler(BaseHTTPRequestHandler):
    def reply(self, body, status=200, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authed(self):
        if self.headers.get("X-Auth") == TOKEN:
            return True
        self.reply({"ok": False, "error": "Wrong code"}, 401)
        return False

    def do_GET(self):
        if self.path == "/":
            return self.reply(INDEX.read_bytes(), ctype="text/html")
        if self.path == "/jsqr.js":
            return self.reply(DECODER.read_bytes(), ctype="text/javascript")
        if self.path == "/api/state" and self.authed():
            now = int(time.time()) + state["offset"]
            return self.reply({
                "ok": True, "version": "mock", "battery": 87, "maxAccounts": 24,
                "time": {"valid": state["lastSync"] > 0, "now": now, "lastSync": state["lastSync"]},
                "accounts": [{"id": i, **state["accounts"][i]} for i in state["order"]],
                "nets": state["nets"], "pin": state["pin"], "settings": state["settings"],
            })
        if not self.path.startswith("/api/"):
            self.reply({"ok": False, "error": "Not found"}, 404)

    def do_POST(self):
        if not self.authed():
            return
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        form = {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}
        error = self.apply(self.path, form)
        self.reply({"ok": False, "error": error} if error else {"ok": True}, 400 if error else 200)

    def apply(self, path, form):
        accounts = state["accounts"]
        if path == "/api/account":
            new = not form.get("id")
            if new and not (form.get("secret") or form.get("uri")):
                return "Secret is required"
            if not form.get("label") and not form.get("uri"):
                return "Name is required"
            slot = min(set(range(24)) - set(accounts)) if new else int(form["id"])
            accounts[slot] = {
                "label": form.get("label") or "From link", "algo": form.get("algo", "SHA1"),
                "digits": int(form.get("digits", 6)), "period": int(form.get("period", 30)),
            }
            if new:
                state["order"].append(slot)
        elif path == "/api/account/delete":
            accounts.pop(int(form["id"]), None)
            state["order"] = [i for i in state["order"] if i in accounts]
        elif path == "/api/account/move":
            order = state["order"]
            at = order.index(int(form["id"])) if int(form["id"]) in order else -1
            to = at + (-1 if form.get("dir") == "up" else 1)
            if at < 0 or not 0 <= to < len(order):
                return "Cannot move that account"
            order[at], order[to] = order[to], order[at]
        elif path == "/api/wifi":
            if form["ssid"] not in state["nets"]:
                state["nets"].append(form["ssid"])
        elif path == "/api/wifi/delete":
            state["nets"] = [n for n in state["nets"] if n != form["ssid"]]
        elif path == "/api/time":
            state["offset"] = int(form["ms"]) // 1000 - int(time.time())
            state["lastSync"] = int(form["ms"]) // 1000
        elif path == "/api/settings":
            state["settings"] = {
                "sleepSecs": int(form["sleepSecs"]), "unlockSecs": int(form["unlockSecs"]),
                "maxTries": int(form["maxTries"]), "autoSync": form["autoSync"] == "1",
                "compact": form.get("compact") == "1", "sounds": form.get("sounds") == "1",
                "owner": form["owner"],
            }
        elif path == "/api/pin":
            # The real device waits for the PIN to be confirmed on its buttons.
            pattern = form.get("pattern", "")
            state["pin"] = {"enabled": bool(pattern), "length": len(pattern), "pending": False}
        elif path == "/api/wipe":
            accounts.clear()
            state["order"] = []
            state["nets"] = []
        else:
            return "Not found"
        return None

    def log_message(self, fmt, *args):
        # Request bodies hold secrets; log the path only.
        sys.stderr.write("%s %s\n" % (self.command, self.path))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"http://localhost:{port}/#{TOKEN}")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
