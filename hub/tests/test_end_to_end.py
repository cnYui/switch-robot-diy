"""Whole path with a real Mosquitto: hub run + pretend switch + HTTP API. Skipped without Mosquitto."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from homehub.__main__ import find_tool

pytestmark = pytest.mark.skipif(not (find_tool("mosquitto") and find_tool("mosquitto_passwd")),
                                reason="Mosquitto not installed")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait_for(fn, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            v = fn()
            if v:
                return v
        except Exception:
            pass
        time.sleep(0.2)
    raise AssertionError("timed out")


def test_switch_round_trip(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    py = [sys.executable, "-m", "homehub", "--dir", str(tmp_path)]
    assert subprocess.run(py + ["init"], env=env, capture_output=True).returncode == 0
    mport, hport, dport = free_port(), free_port(), free_port()
    cfgf = tmp_path / "config.toml"
    text = cfgf.read_text(encoding="utf-8")
    text = text.replace("port = 1883", f"port = {mport}").replace("http_port = 8780", f"http_port = {hport}")
    text = text.replace("udp_port = 8781", f"udp_port = {dport}").replace("scan = true", "scan = false")
    cfgf.write_text(text, encoding="utf-8")
    subprocess.run(py + ["init"], env=env, capture_output=True)       # rewrite mosquitto.conf for the port
    token = next(l.split('"')[1] for l in text.splitlines() if l.startswith("token"))
    hub = subprocess.Popen(py + ["run"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    sim = None
    try:
        wait_for(lambda: socket.create_connection(("127.0.0.1", hport), 0.5))
        sim = subprocess.Popen(py + ["simulate", "--id", "sw-e2e001"], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def api(path, body=None):
            req = urllib.request.Request(f"http://127.0.0.1:{hport}{path}",
                                         data=json.dumps(body).encode() if body is not None else None,
                                         headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read())

        dev = wait_for(lambda: next((d for d in api("/api/devices")["devices"]
                                     if d["id"] == "sw-e2e001" and d["status"] == "online"), None))
        assert dev["kind"] == "switch" and dev["state"] == {"power": "OFF"}
        assert api("/api/devices/sw-e2e001/command", {"cmd": "ON"})["sent"] == "ON"
        wait_for(lambda: api("/api/devices")["devices"][0]["state"] == {"power": "ON"})
        api("/api/devices/sw-e2e001/config", {"press_deg": 21})
        wait_for(lambda: api("/api/devices")["devices"][0]["info"]["config"]["press_deg"] == 21)
        topics = [m["topic"] for m in api("/api/messages?limit=50")]
        assert "home/sw-e2e001/set" in topics and "home/sw-e2e001/event" in topics
        # a device that lost the broker's address asks the LAN and gets it back
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3)
        s.sendto(b"HOMEHUB?", ("127.0.0.1", dport))
        assert json.loads(s.recvfrom(256)[0])["mqtt"].endswith(f":{mport}")
    finally:
        for p in (sim, hub):
            if p is not None:
                p.terminate()
                p.wait(10)
    # mosquitto started by the hub is stopped with it; the data stays in the file
    assert (tmp_path / "home.db").stat().st_size > 0
