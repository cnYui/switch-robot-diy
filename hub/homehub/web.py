"""Control page and HTTP API on the LAN (standard library only).

Every /api call needs the token from config.toml, as `Authorization: Bearer <token>`
or `?token=<token>` (the live event stream can only use the query form).

GET  /api/devices                     devices with status, state, info
GET  /api/messages?device=&limit=     newest raw MQTT messages
GET  /api/readings?device=&metric=&hours=
GET  /api/commands                    commands sent and who asked
GET  /api/stats                       database file and size
GET  /api/stream?token=               live events (server-sent events)
POST /api/devices/<id>/command        {"cmd": "ON" | "OFF" | "TOGGLE"}
POST /api/devices/<id>/config         {"press_deg": 17, "hold_ms": 400, ...}
POST /api/devices/<id>/name           {"name": "客厅灯"}
POST /api/scenes/<name>               run a scene from config.toml
"""
from __future__ import annotations

import hmac
import json
import logging
import queue
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlparse

from .core import Hub

log = logging.getLogger("homehub.web")
DEV_RE = r"([A-Za-z0-9_.:-]{1,64})"


def make_handler(hub: Hub):
    token = hub.cfg.token

    class Handler(BaseHTTPRequestHandler):
        server_version = "HomeHub"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            log.debug("%s %s", self.address_string(), fmt % args)

        # ------------------------------------------------------------ helpers
        def _send(self, code: int, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _authed(self, qs) -> bool:
            got = ""
            h = self.headers.get("Authorization", "")
            if h.lower().startswith("bearer "):
                got = h[7:].strip()
            elif qs.get("token"):
                got = qs["token"][0]
            return bool(got) and hmac.compare_digest(got.encode(), token.encode())

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 65536:
                raise ValueError("body too large")
            raw = self.rfile.read(n) if n else b""
            if not raw.strip():
                return {}
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("body must be a JSON object")
            return data

        # ------------------------------------------------------------ routes
        def do_GET(self):
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path in ("/", "/index.html"):
                page = resources.files("homehub").joinpath("static/index.html").read_bytes()
                return self._send(200, page, "text/html; charset=utf-8")
            if not u.path.startswith("/api/"):
                return self._send(404, {"error": "not found"})
            if not self._authed(qs):
                return self._send(401, {"error": "token missing or wrong"})
            st = hub.store
            if u.path == "/api/devices":
                return self._send(200, {"devices": st.devices(), "mqtt_connected": hub.connected,
                                        "scenes": sorted(hub.cfg.scenes)})
            if u.path == "/api/messages":
                return self._send(200, st.messages(qs.get("device", [None])[0],
                                                   min(int(qs.get("limit", ["100"])[0]), 2000)))
            if u.path == "/api/readings":
                dev = qs.get("device", [""])[0]
                hours = float(qs.get("hours", ["24"])[0])
                return self._send(200, st.readings(dev, qs.get("metric", [None])[0], time.time() - hours * 3600))
            if u.path == "/api/commands":
                return self._send(200, st.commands())
            if u.path == "/api/stats":
                return self._send(200, st.stats())
            if u.path == "/api/stream":
                return self._stream()
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if not self._authed(qs):
                return self._send(401, {"error": "token missing or wrong"})
            try:
                body = self._body()
                src = body.get("source") or "api"
                m = re.fullmatch(rf"/api/devices/{DEV_RE}/(command|config|name)", u.path)
                if m:
                    dev, what = m.groups()
                    if what == "command":
                        return self._send(200, hub.command(dev, str(body.get("cmd", "")), src))
                    if what == "config":
                        body.pop("source", None)
                        return self._send(200, hub.configure(dev, body, src))
                    name = str(body.get("name", "")).strip()[:40]
                    if not hub.store.set_name(dev, name):
                        return self._send(404, {"error": f"no device {dev}"})
                    return self._send(200, {"device": dev, "name": name})
                m = re.fullmatch(r"/api/scenes/([A-Za-z0-9_-]{1,40})", u.path)
                if m:
                    return self._send(200, hub.run_scene(m.group(1), src))
                return self._send(404, {"error": "not found"})
            except KeyError as e:
                return self._send(404, {"error": f"no scene {e}"})
            except ConnectionError as e:
                return self._send(503, {"error": str(e)})
            except ValueError as e:
                return self._send(400, {"error": str(e)})

        def _stream(self):
            q = hub.events.subscribe()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                self.wfile.write(b": hello\n\n")
                self.wfile.flush()
                while True:
                    try:
                        ev = q.get(timeout=15)
                        self.wfile.write(b"data: " + json.dumps(ev, ensure_ascii=False).encode() + b"\n\n")
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                hub.events.unsubscribe(q)
                self.close_connection = True

    return Handler


def serve(hub: Hub, host: str, port: int) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((host, port), make_handler(hub))
    srv.daemon_threads = True
    return srv
