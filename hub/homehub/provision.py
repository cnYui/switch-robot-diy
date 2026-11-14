"""Write Wi-Fi and MQTT settings into a switch or gateway over its USB cable.

The firmware runs a small text console on the ESP32's built-in USB serial port. Each
command answers one line starting with "OK" or "ERR":

  wifi "<ssid>" "<password>"
  mqtt "<mqtt://host:port>" "<user>" "<password>"
  name "<friendly name>"
  status
  reboot
"""
from __future__ import annotations

import re
import time

ANSWER = re.compile(r"(?:^|>\s*)((?:OK|ERR)\b.*)$")


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _open(port: str):
    import serial  # pyserial

    s = serial.Serial()
    s.port, s.baudrate, s.timeout = port, 115200, 0.2
    s.dtr = False          # keep the ESP32 out of reset / download mode while we talk to it
    s.rts = False
    s.open()
    return s


def _ask(ser, line: str, wait_s: float = 3.0) -> str:
    ser.reset_input_buffer()
    ser.write((line + "\r\n").encode("utf-8"))
    end = time.time() + wait_s
    buf = b""
    while time.time() < end:
        buf += ser.read(256)
        for raw in buf.decode("utf-8", "replace").splitlines():
            m = ANSWER.search(raw.strip())
            if m:
                return m.group(1)
    raise TimeoutError(f"device did not answer {line.split()[0]!r}; is the firmware flashed and the port right?")


def provision(port: str, ssid: str, password: str, mqtt_uri: str, user: str, secret: str,
              name: str | None = None) -> int:
    ser = _open(port)
    try:
        time.sleep(0.3)
        print(_ask(ser, "status"))
        steps = [f"wifi {_quote(ssid)} {_quote(password)}",
                 f"mqtt {_quote(mqtt_uri)} {_quote(user)} {_quote(secret)}"]
        if name:
            steps.append(f"name {_quote(name)}")
        for s in steps:
            ans = _ask(ser, s)
            print(s.split()[0], "->", ans)
            if ans.startswith("ERR"):
                return 1
        ser.write(b"reboot\r\n")
        print(f"写好了，设备重启后连 {ssid}，再连 {mqtt_uri}。控制页面上会出现它。")
        return 0
    finally:
        ser.close()
