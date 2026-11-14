"""Answer devices that ask "where is the hub?" on the LAN.

A device that cannot reach its saved MQTT address (the computer got a new IP from the
router, or the device was set up on another network) broadcasts the 8 bytes
b"HOMEHUB?" to UDP port 8781. HomeHub replies to the sender with
{"mqtt": "mqtt://<this computer's LAN IP>:1883"} and the device saves that address.
"""
from __future__ import annotations

import json
import logging
import socket
import threading

log = logging.getLogger("homehub.discovery")
QUERY = b"HOMEHUB?"


def local_ip_for(peer: str) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((peer, 9))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def reply_for(peer_ip: str, mqtt_port: int, advertise_host: str = "") -> bytes:
    host = advertise_host or local_ip_for(peer_ip)
    return json.dumps({"mqtt": f"mqtt://{host}:{mqtt_port}"}).encode()


class DiscoveryResponder(threading.Thread):
    def __init__(self, port: int, mqtt_port: int, advertise_host: str = ""):
        super().__init__(daemon=True, name="discovery")
        self.port, self.mqtt_port, self.advertise_host = port, mqtt_port, advertise_host
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", port))
        self._stop = False

    def run(self):
        while not self._stop:
            try:
                data, (ip, port) = self.sock.recvfrom(256)
            except OSError:
                return
            if data.strip() != QUERY:
                continue
            msg = reply_for(ip, self.mqtt_port, self.advertise_host)
            log.info("discovery: %s asked, answered %s", ip, msg.decode())
            try:
                self.sock.sendto(msg, (ip, port))
            except OSError as e:
                log.warning("discovery reply to %s failed: %s", ip, e)

    def stop(self):
        self._stop = True
        self.sock.close()
