"""A pretend switch that speaks exactly what the real firmware speaks.

`python -m homehub simulate` lets you check the whole path (control page, phone shortcut,
database) before the V0.5 board arrives. It logs in with the device account from
config.toml, like a real switch, and answers ON/OFF/TOGGLE and calibration messages.
"""
from __future__ import annotations

import json
import threading
import time


def run(cfg, dev_id: str = "sw-000001", name: str = "模拟开关", host: str | None = None,
        stop: threading.Event | None = None) -> None:
    import paho.mqtt.client as mqtt

    stop = stop or threading.Event()
    base = f"home/{dev_id}"
    state = {"power": "OFF"}
    conf = {"press_deg": 17, "hold_ms": 400, "neutral_us": 1500, "invert": False}
    presses = 0
    started = time.time()
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=dev_id)
    c.username_pw_set(cfg.device_user, cfg.device_password)
    c.will_set(f"{base}/status", "offline", qos=1, retain=True)

    def info():
        return json.dumps({"kind": "switch", "name": name, "fw": "sim", "board": "simulated", "chip": "pc",
                           "mode": "servo", "ip": "127.0.0.1", "mac": "00:00:00:00:00:01", "config": conf},
                          ensure_ascii=False)

    def on_connect(cl, *_):
        cl.publish(f"{base}/status", "online", qos=1, retain=True)
        cl.publish(f"{base}/info", info(), qos=1, retain=True)
        cl.publish(f"{base}/state", json.dumps(state), qos=1, retain=True)
        cl.subscribe([(f"{base}/set", 1), (f"{base}/config/set", 1)])
        print(f"{dev_id} 已连上 MQTT，等待命令")

    def on_message(cl, _ud, msg):
        nonlocal presses
        text = msg.payload.decode("utf-8", "replace").strip()
        if msg.topic.endswith("/config/set"):
            try:
                conf.update({k: v for k, v in json.loads(text).items() if k in conf})
            except ValueError:
                return
            cl.publish(f"{base}/info", info(), qos=1, retain=True)
            cl.publish(f"{base}/event", json.dumps({"type": "config", "result": "saved"}), qos=1)
            print(f"{dev_id} 校准已更新 {conf}")
            return
        word = text.upper()
        if word not in ("ON", "OFF", "TOGGLE"):
            return
        state["power"] = ("OFF" if state["power"] == "ON" else "ON") if word == "TOGGLE" else word
        presses += 1
        time.sleep(conf["hold_ms"] / 1000)                     # the arm moving
        cl.publish(f"{base}/state", json.dumps(state), qos=1, retain=True)
        cl.publish(f"{base}/event", json.dumps({"type": "press", "power": state["power"], "source": "mqtt"}), qos=1)
        print(f"{dev_id} 按下 {state['power']}")

    c.on_connect, c.on_message = on_connect, on_message
    c.connect(host or "127.0.0.1", cfg.mqtt_port, keepalive=30)
    c.loop_start()
    try:
        while not stop.wait(60 if presses or time.time() - started > 5 else 5):
            c.publish(f"{base}/telemetry", json.dumps({"uptime_s": int(time.time() - started), "rssi": -55,
                                                       "heap": 150000, "presses": presses}), qos=1)
    finally:
        c.publish(f"{base}/status", "offline", qos=1, retain=True)
        c.disconnect()
        c.loop_stop()
