import json
import socket
import threading
import time
import urllib.request
from datetime import datetime

import pytest

from homehub import config as cfgmod
from homehub import decoders
from homehub.core import Hub, in_window
from homehub.discovery import QUERY, DiscoveryResponder
from homehub.store import Store
from homehub.web import serve


class FakeClient:
    def __init__(self):
        self.sent = []

    def publish(self, topic, payload, qos=0, retain=False):
        self.sent.append((topic, payload))
        return type("R", (), {"rc": 0})()


@pytest.fixture
def hub(tmp_path):
    cfgmod.write_new(tmp_path)
    text = (tmp_path / "config.toml").read_text(encoding="utf-8")
    text += '\n[scenes.arrive]\nafter = "17:00"\nbefore = "06:00"\nactions = [ { device = "sw-aabbcc", cmd = "ON" } ]\n'
    (tmp_path / "config.toml").write_text(text, encoding="utf-8")
    cfg = cfgmod.load(tmp_path)
    h = Hub(cfg, Store(cfg.db_path), client=FakeClient())
    h.connected = True
    yield h
    h.store.close()


def test_device_lifecycle(hub):
    hub.handle("home/sw-aabbcc/status", b"online", retained=True)
    hub.handle("home/sw-aabbcc/info", json.dumps({"kind": "switch", "fw": "0.1.0", "ip": "192.168.1.50"}))
    hub.handle("home/sw-aabbcc/state", b'{"power":"OFF"}')
    hub.handle("home/sw-aabbcc/telemetry", b'{"rssi":-61,"uptime_s":120,"heap":150000}')
    d = hub.store.device("sw-aabbcc")
    assert d["kind"] == "switch" and d["status"] == "online" and d["state"] == {"power": "OFF"}
    assert {r["metric"] for r in hub.store.readings("sw-aabbcc")} == {"rssi", "uptime_s", "heap"}
    # the retained status replay is not stored as new history, the rest is
    topics = [m["topic"] for m in hub.store.messages()]
    assert "home/sw-aabbcc/status" not in topics and "home/sw-aabbcc/telemetry" in topics


def test_command_and_config(hub):
    assert hub.command("sw-aabbcc", "on")["sent"] == "ON"
    hub.configure("sw-aabbcc", {"press_deg": 20})
    assert hub.client.sent == [("home/sw-aabbcc/set", "ON"), ("home/sw-aabbcc/config/set", '{"press_deg": 20}')]
    assert [c["cmd"] for c in hub.store.commands()][::-1] == ["ON", 'CONFIG {"press_deg": 20}']
    with pytest.raises(ValueError):
        hub.command("sw-aabbcc", "explode")


def test_scene_window(hub):
    night = datetime(2026, 11, 14, 22, 0)
    noon = datetime(2026, 11, 14, 12, 0)
    assert hub.run_scene("arrive", now=night)["ran"] is True
    assert hub.run_scene("arrive", now=noon)["ran"] is False
    assert in_window(hub.cfg.scenes["arrive"], datetime(2026, 1, 1, 5, 59))
    with pytest.raises(KeyError):
        hub.run_scene("nope")


def test_scale_decoders():
    # Mi Body Composition Scale 2: kg, stable, impedance 500 ohm, 65.30 kg -> raw 13060
    p = bytes([0x02, 0x26, 0xEA, 0x07, 11, 14, 8, 30, 0]) + (500).to_bytes(2, "little") + (13060).to_bytes(2, "little")
    assert decoders.mi_scale_v2(p) == {"weight_kg": 65.3, "impedance_ohm": 500.0}
    unstable = bytes([0x02, 0x02]) + p[2:]
    assert decoders.mi_scale_v2(unstable) is None
    # Mi Scale v1: stable kg 70.00 -> raw 14000
    v1 = bytes([0x22]) + (14000).to_bytes(2, "little") + bytes(7)
    assert decoders.mi_scale_v1(v1) == {"weight_kg": 70.0}


def test_ble_forwarding_creates_reading(hub):
    p = bytes([0x02, 0x24, 0xEA, 0x07, 11, 14, 8, 30, 0, 0, 0]) + (13060).to_bytes(2, "little")
    adv = {"mac": "aa:bb:cc:dd:ee:ff", "rssi": -70, "svc": {"181b": p.hex()}}
    hub.handle("home/gw-112233/ble", json.dumps(adv))
    d = hub.store.device("ble-aabbccddeeff")
    assert d["kind"] == "ble" and d["state"] == {"weight_kg": 65.3}
    assert hub.store.readings("ble-aabbccddeeff", "weight_kg")[0]["value"] == 65.3


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def test_http_api(hub):
    port = _free_port()
    srv = serve(hub, "127.0.0.1", port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    tok = hub.cfg.token

    def call(path, body=None, token=tok):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {token}"} if token else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")

    try:
        hub.handle("home/sw-aabbcc/info", '{"kind":"switch"}')
        assert call("/api/devices", token="")[0] == 401
        assert call("/api/devices", token="wrong")[0] == 401
        code, j = call("/api/devices")
        assert code == 200 and j["devices"][0]["id"] == "sw-aabbcc"
        assert call("/api/devices/sw-aabbcc/command", {"cmd": "TOGGLE"}) == (200, {"device": "sw-aabbcc", "sent": "TOGGLE"})
        assert call("/api/devices/sw-aabbcc/command", {"cmd": "bad"})[0] == 400
        assert call("/api/devices/sw-aabbcc/name", {"name": "客厅灯"})[1]["name"] == "客厅灯"
        assert call("/api/scenes/missing", {})[0] == 404
        with urllib.request.urlopen(base + "/", timeout=5) as r:
            assert "家庭中枢" in r.read().decode()
        hub.connected = False
        assert call("/api/devices/sw-aabbcc/command", {"cmd": "ON"})[0] == 503
    finally:
        srv.shutdown()


def test_discovery_reply():
    port = _free_port()
    d = DiscoveryResponder(port, 1883)
    d.start()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3)
        s.sendto(QUERY, ("127.0.0.1", port))
        data, _ = s.recvfrom(256)
        assert json.loads(data) == {"mqtt": "mqtt://127.0.0.1:1883"}
    finally:
        d.stop()
