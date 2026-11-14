"""The computer's own Bluetooth as the home's Bluetooth gateway (optional: pip install bleak).

Listens for advertisements and hands the ones worth keeping to the hub as if a gateway
had forwarded them on home/pc/ble: adverts with scale / Xiaomi service data, and any
device listed under [ble] in config.toml. Other phones, watches and earbuds nearby are
ignored, so the database does not fill up with strangers' devices.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time

log = logging.getLogger("homehub.ble")
KEEP_SERVICES = {"181b", "181d", "fe95"}
GW_ID = "pc"


def short_uuid(u: str) -> str:
    u = u.lower()
    return u[4:8] if u.startswith("0000") and u.endswith("-0000-1000-8000-00805f9b34fb") else u


def to_adv(mac: str, rssi: int, name: str | None, service_data: dict, manufacturer_data: dict) -> dict:
    svc = {short_uuid(k): bytes(v).hex() for k, v in service_data.items()}
    adv = {"mac": mac.upper(), "rssi": rssi, "svc": svc}
    if name:
        adv["name"] = name
    if manufacturer_data:
        cid, data = next(iter(manufacturer_data.items()))
        adv["mfr"] = f"{cid:04x}" + bytes(data).hex()
    return adv


class BleGateway(threading.Thread):
    def __init__(self, hub):
        super().__init__(daemon=True, name="ble")
        self.hub = hub
        self.wanted = set(hub.cfg.ble_bindkeys) | set(hub.cfg.ble_names)
        self._last: dict[str, tuple[float, str]] = {}
        self._stop = threading.Event()

    def _seen(self, device, adv_data) -> None:
        adv = to_adv(device.address, adv_data.rssi, adv_data.local_name, adv_data.service_data or {},
                     adv_data.manufacturer_data or {})
        if not (KEEP_SERVICES & set(adv["svc"]) or adv["mac"] in self.wanted):
            return
        key = json.dumps(adv["svc"], sort_keys=True) + adv.get("mfr", "")
        prev = self._last.get(adv["mac"])
        now = time.time()
        if prev and prev[1] == key and now - prev[0] < 10:
            return                                          # same payload again within 10 s
        self._last[adv["mac"]] = (now, key)
        self.hub.handle(f"home/{GW_ID}/ble", json.dumps(adv))

    async def _main(self):
        from bleak import BleakScanner

        async with BleakScanner(detection_callback=self._seen):
            while not self._stop.is_set():
                await asyncio.sleep(1)

    def run(self):
        try:
            import bleak  # noqa: F401
        except ImportError:
            log.info("bleak not installed: the computer's Bluetooth is not used (pip install bleak)")
            return
        self.hub.handle(f"home/{GW_ID}/info", json.dumps({"kind": "gateway", "name": "电脑蓝牙",
                                                          "fw": "homehub", "chip": "电脑自带蓝牙"},
                                                         ensure_ascii=False), retained=True)
        self.hub.handle(f"home/{GW_ID}/status", "online", retained=True)
        while not self._stop.is_set():
            try:
                asyncio.run(self._main())
            except Exception as e:
                log.warning("Bluetooth scan stopped (%s); retrying in 30 s", e)
                self._stop.wait(30)

    def stop(self):
        self._stop.set()
