"""Turn Bluetooth advertisements forwarded by the gateway into numbers.

The gateway sends home/<gw-id>/ble with {"mac", "rssi", "name", "svc": {"181b": "<hex>"}, "mfr": "<hex>"}
(svc keys are 16-bit service-data UUIDs). Built in, no extra packages:

  0x181D  Xiaomi Mi Smart Scale (v1) - unencrypted weight
  0x181B  Xiaomi Mi Body Composition Scale 2 - unencrypted weight + impedance

Both layouts follow openScale's open-source drivers; neither was checked against a scale here.
Encrypted Xiaomi MiBeacon (0xFE95, e.g. Body Composition Scale S400) needs the device's bindkey
and the optional `xiaomi-ble` package (pip install xiaomi-ble); without it the raw advert is still
stored, so nothing is lost and it can be decoded later.
"""
from __future__ import annotations

LB_KG = 0.45359237


def _u16(b: bytes, i: int) -> int:
    return b[i] | (b[i + 1] << 8)


def _scale_kg(raw: int, lbs: bool, jin: bool) -> float:
    if lbs:
        return round(raw / 100 * LB_KG, 2)
    if jin:
        return round(raw / 100 / 2, 2)
    return round(raw / 200, 2)


def mi_scale_v1(data: bytes) -> dict | None:
    """Service data 0x181D (10 bytes). Only stable readings with weight on the scale."""
    if len(data) < 10:
        return None
    ctrl = data[0]
    removed, stable = ctrl & 0x80, ctrl & 0x20
    if removed or not stable:
        return None
    return {"weight_kg": _scale_kg(_u16(data, 1), lbs=bool(ctrl & 0x01), jin=bool(ctrl & 0x10))}


def mi_scale_v2(data: bytes) -> dict | None:
    """Service data 0x181B (13 bytes). Weight, plus impedance once the measurement finished."""
    if len(data) < 13:
        return None
    c0, c1 = data[0], data[1]
    removed, stable, has_imp = c1 & 0x80, c1 & 0x20, c1 & 0x02
    if removed or not stable:
        return None
    out = {"weight_kg": _scale_kg(_u16(data, 11), lbs=bool(c0 & 0x01), jin=bool(c1 & 0x40))}
    if has_imp:
        imp = _u16(data, 9)
        if 0 < imp < 3000:
            out["impedance_ohm"] = float(imp)
    return out


def mibeacon(mac: str, data: bytes, rssi: int, bindkey: str | None) -> dict | None:
    """Encrypted Xiaomi adverts through the optional xiaomi-ble package (untested here)."""
    try:
        from home_assistant_bluetooth import BluetoothServiceInfo
        from xiaomi_ble import XiaomiBluetoothDeviceData
    except ImportError:
        return None
    dev = XiaomiBluetoothDeviceData(bindkey=bytes.fromhex(bindkey) if bindkey else None)
    info = BluetoothServiceInfo(name="", address=mac, rssi=rssi, manufacturer_data={},
                                service_data={"0000fe95-0000-1000-8000-00805f9b34fb": data},
                                service_uuids=[], source="homehub-gateway")
    try:
        upd = dev.update(info)
    except Exception:
        return None
    out = {}
    for key, val in getattr(upd, "entity_values", {}).items():
        v = getattr(val, "native_value", None)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[getattr(key, "key", str(key))] = float(v)
    return out or None


def decode(adv: dict, bindkeys: dict[str, str] | None = None) -> dict:
    """Numbers found in one forwarded advert; {} when nothing is known about it."""
    svc = {k.lower(): v for k, v in (adv.get("svc") or {}).items()}
    out: dict = {}
    try:
        if "181d" in svc:
            out.update(mi_scale_v1(bytes.fromhex(svc["181d"])) or {})
        if "181b" in svc:
            out.update(mi_scale_v2(bytes.fromhex(svc["181b"])) or {})
        if "fe95" in svc:
            mac = str(adv.get("mac", "")).upper()
            out.update(mibeacon(mac, bytes.fromhex(svc["fe95"]), int(adv.get("rssi", 0)),
                                (bindkeys or {}).get(mac)) or {})
    except ValueError:
        pass
    return out
