"""Settings: <data_dir>/config.toml, written by `python -m homehub init`."""
from __future__ import annotations

import os
import secrets
import socket
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DATA_DIR = Path(os.environ.get("HOMEHUB_DIR", "~/HomeHub")).expanduser()


@dataclass
class Scene:
    name: str
    actions: list[dict]
    after: str | None = None      # "17:30": only run at or after this local time
    before: str | None = None     # "06:00": ... or before this one (the window may wrap midnight)


@dataclass
class Config:
    data_dir: Path = DEFAULT_DATA_DIR
    http_host: str = "0.0.0.0"
    http_port: int = 8780
    token: str = ""
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_user: str = "homehub"
    mqtt_password: str = ""
    device_user: str = "device"
    device_password: str = ""
    discovery_port: int = 8781
    advertise_host: str = ""
    keep_days: int = 0            # 0 = keep every message forever
    scenes: dict[str, Scene] = field(default_factory=dict)
    ble_bindkeys: dict[str, str] = field(default_factory=dict)   # MAC -> 32 hex chars
    ble_names: dict[str, str] = field(default_factory=dict)      # MAC -> name shown on the page
    ble_scan: bool = True         # use this computer's Bluetooth (needs `pip install bleak`)
    ota_port: int = 8782

    @property
    def db_path(self) -> Path:
        return self.data_dir / "home.db"

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.toml"


def lan_ip() -> str:
    """The IPv4 address this computer uses on the LAN (no packet is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))          # TEST-NET address, never routed
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def load(data_dir: Path | str | None = None) -> Config:
    d = Path(data_dir).expanduser() if data_dir else DEFAULT_DATA_DIR
    cfg = Config(data_dir=d)
    f = cfg.config_path
    if not f.exists():
        raise FileNotFoundError(f"{f} does not exist: run `python -m homehub init` first")
    raw = tomllib.loads(f.read_text(encoding="utf-8"))
    hub, mqtt, disc = raw.get("hub", {}), raw.get("mqtt", {}), raw.get("discovery", {})
    cfg.http_host = hub.get("http_host", cfg.http_host)
    cfg.http_port = int(hub.get("http_port", cfg.http_port))
    cfg.token = hub.get("token", "")
    cfg.keep_days = int(hub.get("keep_days", 0))
    cfg.mqtt_host = mqtt.get("host", cfg.mqtt_host)
    cfg.mqtt_port = int(mqtt.get("port", cfg.mqtt_port))
    cfg.mqtt_user = mqtt.get("username", cfg.mqtt_user)
    cfg.mqtt_password = mqtt.get("password", "")
    cfg.device_user = mqtt.get("device_username", cfg.device_user)
    cfg.device_password = mqtt.get("device_password", "")
    cfg.discovery_port = int(disc.get("udp_port", cfg.discovery_port))
    cfg.advertise_host = disc.get("advertise_host", "")
    for name, s in (raw.get("scenes") or {}).items():
        cfg.scenes[name] = Scene(name=name, actions=list(s.get("actions", [])),
                                 after=s.get("after"), before=s.get("before"))
    ble = raw.get("ble") or {}
    cfg.ble_bindkeys = {k.upper(): v for k, v in (ble.get("bindkeys") or {}).items()}
    cfg.ble_names = {k.upper(): v for k, v in (ble.get("names") or {}).items()}
    cfg.ble_scan = bool(ble.get("scan", True))
    cfg.ota_port = int(hub.get("ota_port", cfg.ota_port))
    if not cfg.token:
        raise ValueError(f"{f}: [hub] token is empty")
    return cfg


TEMPLATE = """\
# HomeHub 设置。改完重启 HomeHub 生效。
[hub]
http_port = {http_port}
# 控制页面和 API 的口令。手机快捷指令里用 Authorization: Bearer <token>
token = "{token}"
# 消息保留天数，0 = 永久保留
keep_days = 0
# 给设备推送新固件时临时开的下载端口
ota_port = 8782

[mqtt]
host = "127.0.0.1"
port = 1883
username = "homehub"
password = "{mqtt_password}"
# 设备（开关、网关）连 MQTT 用的账号，provision.py 会写进设备
device_username = "device"
device_password = "{device_password}"

[discovery]
# 设备找不到 MQTT 时会广播询问，HomeHub 在这个 UDP 端口回答自己的地址
udp_port = 8781
# 留空 = 自动用本机局域网 IP
advertise_host = ""

# 场景：POST /api/scenes/<名字> 触发。after/before 是本地时间窗口，可跨午夜。
# 设备 id 在控制页面上能看到，例如 sw-1a2b3c。
# [scenes.arrive]
# after = "17:00"
# before = "06:00"
# actions = [ {{ device = "sw-1a2b3c", cmd = "ON" }} ]
#
# [scenes.leave]
# actions = [ {{ device = "sw-1a2b3c", cmd = "OFF" }} ]

[ble]
# 用这台电脑自带的蓝牙收体脂秤等设备的广播（需要 pip install bleak）
scan = true
# 网关转发来的蓝牙设备。小米加密广播（如体脂秤 S400）需要 bindkey 才能解出体重。
# bindkeys = {{ "AA:BB:CC:DD:EE:FF" = "0123456789abcdef0123456789abcdef" }}
# names = {{ "AA:BB:CC:DD:EE:FF" = "体脂秤" }}
"""


def write_new(data_dir: Path, http_port: int = 8780) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    f = data_dir / "config.toml"
    if f.exists():
        return f
    f.write_text(TEMPLATE.format(http_port=http_port, token=secrets.token_urlsafe(18),
                                 mqtt_password=secrets.token_urlsafe(18),
                                 device_password=secrets.token_urlsafe(18)), encoding="utf-8")
    return f
