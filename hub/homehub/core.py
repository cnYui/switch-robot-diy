"""MQTT side of the hub: record everything, keep device rows current, send commands.

Topic contract (also in hub/PROTOCOL.md), <id> like sw-1a2b3c (switch) or gw-4d5e6f (gateway):
  home/<id>/status      "online" | "offline"     retained, offline is the device's last will
  home/<id>/info        JSON {kind, fw, ip, mac, ...}   retained
  home/<id>/state       JSON {power: "ON"|"OFF", ...}   retained
  home/<id>/telemetry   JSON {uptime_s, rssi, heap, ...} every minute
  home/<id>/event       JSON {type, ...}
  home/<id>/ble         JSON one forwarded Bluetooth advert (gateway)
  home/<id>/set         command to the device: "ON" | "OFF" | "TOGGLE"
  home/<id>/config/set  JSON settings saved in the device (press angle, hold time, ...)
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from datetime import datetime

from . import decoders
from .config import Config, Scene
from .store import Store

log = logging.getLogger("homehub")
COMMANDS = {"ON", "OFF", "TOGGLE"}
NUMERIC_TELEMETRY = ("rssi", "uptime_s", "heap", "presses", "temp_c", "ble_seen")


class Events:
    """Fan-out of live events to the control page (server-sent events)."""

    def __init__(self):
        self._subs: list[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def publish(self, ev: dict) -> None:
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(ev)
            except queue.Full:
                pass


def _json(payload: str):
    try:
        return json.loads(payload)
    except ValueError:
        return None


def in_window(scene: Scene, now: datetime | None = None) -> bool:
    if not scene.after and not scene.before:
        return True
    t = (now or datetime.now()).strftime("%H:%M")
    a, b = scene.after or "00:00", scene.before or "24:00"
    return (a <= t < b) if a <= b else (t >= a or t < b)


class Hub:
    def __init__(self, cfg: Config, store: Store, client=None):
        self.cfg = cfg
        self.store = store
        self.events = Events()
        self.client = client          # paho client, set by connect(); tests pass a fake
        self.connected = False

    # ------------------------------------------------------------ inbound
    def handle(self, topic: str, payload: bytes | str, retained: bool = False) -> None:
        text = payload.decode("utf-8", "replace") if isinstance(payload, (bytes, bytearray)) else payload
        parts = topic.split("/")
        if len(parts) < 3 or parts[0] != "home":
            return
        dev, sub = parts[1], "/".join(parts[2:])
        now = time.time()
        if not (retained and sub in ("status", "info", "state")):
            self.store.add_message(topic, text, now)       # retained replays are not new history
        data = _json(text)
        if sub == "status":
            self.store.touch_device(dev, now, status=text.strip())
        elif sub == "info" and isinstance(data, dict):
            self.store.touch_device(dev, now, info=data, kind=data.get("kind", "device"))
        elif sub == "state":
            self.store.touch_device(dev, now, state=data if data is not None else {"raw": text})
        elif sub == "telemetry" and isinstance(data, dict):
            self.store.touch_device(dev, now)
            for k in NUMERIC_TELEMETRY:
                if isinstance(data.get(k), (int, float)):
                    self.store.add_reading(dev, k, data[k], now)
        elif sub == "ble" and isinstance(data, dict):
            self._ble(dev, data, now)
        elif sub in ("set", "config/set"):
            pass                                            # our own commands, already logged
        else:
            self.store.touch_device(dev, now)
        self.events.publish({"ts": now, "topic": topic, "payload": data if data is not None else text})

    def _ble(self, gw: str, adv: dict, now: float) -> None:
        mac = str(adv.get("mac", "")).upper()
        if not mac:
            return
        self.store.touch_device(gw, now)
        values = decoders.decode(adv, self.cfg.ble_bindkeys)
        if not values:
            return
        dev = "ble-" + mac.replace(":", "").lower()
        if self.store.device(dev) is None:
            self.store.touch_device(dev, now, kind="ble", name=self.cfg.ble_names.get(mac),
                                    info={"kind": "ble", "mac": mac, "via": gw})
        self.store.touch_device(dev, now, state=values, status="online")
        for k, v in values.items():
            self.store.add_reading(dev, k, v, now)
        self.events.publish({"ts": now, "topic": f"home/{dev}/reading", "payload": values})

    # ------------------------------------------------------------ outbound
    def command(self, dev: str, cmd: str, source: str = "api") -> dict:
        cmd = cmd.strip().upper()
        if cmd not in COMMANDS:
            raise ValueError(f"unknown command {cmd!r}; use ON, OFF or TOGGLE")
        self._publish(f"home/{dev}/set", cmd)
        self.store.add_command(dev, cmd, source)
        return {"device": dev, "sent": cmd}

    def configure(self, dev: str, settings: dict, source: str = "api") -> dict:
        if not isinstance(settings, dict) or not settings:
            raise ValueError("settings must be a non-empty JSON object")
        body = json.dumps(settings, ensure_ascii=False)
        self._publish(f"home/{dev}/config/set", body)
        self.store.add_command(dev, "CONFIG " + body, source)
        return {"device": dev, "sent": settings}

    def run_scene(self, name: str, source: str = "api", now: datetime | None = None) -> dict:
        sc = self.cfg.scenes.get(name)
        if sc is None:
            raise KeyError(name)
        if not in_window(sc, now):
            return {"scene": name, "ran": False, "reason": f"outside {sc.after or '00:00'}-{sc.before or '24:00'}"}
        sent = []
        for a in sc.actions:
            if "cmd" in a:
                sent.append(self.command(a["device"], a["cmd"], f"scene:{name}:{source}"))
            elif "config" in a:
                sent.append(self.configure(a["device"], a["config"], f"scene:{name}:{source}"))
        return {"scene": name, "ran": True, "sent": sent}

    def _publish(self, topic: str, payload: str) -> None:
        if self.client is None or not self.connected:
            raise ConnectionError("HomeHub is not connected to the MQTT broker (is Mosquitto running?)")
        self.store.add_message(topic, payload)
        info = self.client.publish(topic, payload, qos=1, retain=False)
        if getattr(info, "rc", 0) != 0:
            raise ConnectionError(f"MQTT publish failed (rc={info.rc})")

    # ------------------------------------------------------------ broker connection
    def connect(self) -> None:
        import paho.mqtt.client as mqtt

        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"homehub-{int(time.time())}")
        if self.cfg.mqtt_user:
            c.username_pw_set(self.cfg.mqtt_user, self.cfg.mqtt_password)
        c.will_set("home/hub/status", "offline", qos=1, retain=True)

        def on_connect(cl, _ud, _flags, rc, _props=None):
            if getattr(rc, "is_failure", False) or (isinstance(rc, int) and rc != 0):
                log.error("MQTT connect refused: %s", rc)
                return
            self.connected = True
            cl.subscribe("home/#", qos=1)
            cl.publish("home/hub/status", "online", qos=1, retain=True)
            log.info("connected to MQTT %s:%s", self.cfg.mqtt_host, self.cfg.mqtt_port)

        def on_disconnect(_cl, _ud, _flags, rc, _props=None):
            self.connected = False
            log.warning("MQTT disconnected (%s), retrying", rc)

        def on_message(_cl, _ud, msg):
            if msg.topic.startswith("home/hub/"):
                return
            try:
                self.handle(msg.topic, msg.payload, bool(msg.retain))
            except Exception:
                log.exception("bad message on %s", msg.topic)

        c.on_connect, c.on_disconnect, c.on_message = on_connect, on_disconnect, on_message
        c.reconnect_delay_set(1, 30)
        c.connect_async(self.cfg.mqtt_host, self.cfg.mqtt_port, keepalive=30)
        c.loop_start()
        self.client = c

    def close(self) -> None:
        if self.client is not None and hasattr(self.client, "loop_stop"):
            try:
                self.client.publish("home/hub/status", "offline", qos=1, retain=True)
                self.client.disconnect()
                self.client.loop_stop()
            except Exception:
                pass
