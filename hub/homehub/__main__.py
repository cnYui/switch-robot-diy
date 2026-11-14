"""python -m homehub init | run | info | provision

init       create ~/HomeHub (config.toml with fresh passwords, Mosquitto config and password file)
run        start everything: Mosquitto (if not already running), MQTT recorder, control page,
           discovery, and the computer's Bluetooth as the Bluetooth gateway
info       print the control page address, the token and the phone shortcut settings
provision  write Wi-Fi and MQTT settings into a device over its USB cable
simulate   a pretend switch, to try the whole path before the real board arrives
ota        send new firmware to a device over Wi-Fi
"""
from __future__ import annotations

import argparse
import getpass
import logging
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import config as cfgmod

log = logging.getLogger("homehub")

WIN_MOSQ = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "mosquitto",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "mosquitto"]


def find_tool(name: str) -> str | None:
    hit = shutil.which(name)
    if hit:
        return hit
    for d in WIN_MOSQ:
        p = d / f"{name}.exe"
        if p.exists():
            return str(p)
    return None


def mosquitto_conf(cfg: cfgmod.Config) -> Path:
    d = cfg.data_dir / "mosquitto"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "mosquitto.conf"
    f.write_text(
        "# Written by `python -m homehub init`. LAN-only broker for the home devices.\n"
        f"listener {cfg.mqtt_port} 0.0.0.0\n"
        "allow_anonymous false\n"
        f"password_file {(d / 'passwd').as_posix()}\n"
        "persistence true\n"
        f"persistence_location {d.as_posix()}/\n"
        f"log_dest file {(d / 'mosquitto.log').as_posix()}\n"
        "log_type error\nlog_type warning\nlog_type notice\n"
        # Linux/macOS: started as root, Mosquitto would switch to a "mosquitto" user that cannot
        # read files in your home folder; keep the user that started it.
        + ("" if os.name == "nt" else f"user {getpass.getuser()}\n"),
        encoding="utf-8")
    return f


def write_passwd(cfg: cfgmod.Config) -> bool:
    tool = find_tool("mosquitto_passwd")
    pw = cfg.data_dir / "mosquitto" / "passwd"
    if not tool:
        return False
    pw.unlink(missing_ok=True)
    pw.touch()
    for user, secret in ((cfg.mqtt_user, cfg.mqtt_password), (cfg.device_user, cfg.device_password)):
        subprocess.run([tool, "-b", str(pw), user, secret], check=True, capture_output=True)
    return True


def port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def cmd_init(a) -> int:
    d = Path(a.dir).expanduser() if a.dir else cfgmod.DEFAULT_DATA_DIR
    f = cfgmod.write_new(d)
    cfg = cfgmod.load(d)
    conf = mosquitto_conf(cfg)
    ok = write_passwd(cfg)
    print(f"设置文件: {f}")
    print(f"数据库:   {cfg.db_path}")
    print(f"Mosquitto 配置: {conf}")
    if not ok:
        print("没找到 mosquitto_passwd：先装 Mosquitto（winget install EclipseFoundation.Mosquitto），再运行一次 init。")
        return 1
    print("好了，下一步：python -m homehub run")
    return 0


def start_broker(cfg: cfgmod.Config) -> subprocess.Popen | None:
    if port_open(cfg.mqtt_host, cfg.mqtt_port):
        log.info("MQTT broker already listening on %s:%s", cfg.mqtt_host, cfg.mqtt_port)
        return None
    exe = find_tool("mosquitto")
    if not exe:
        raise SystemExit("Mosquitto 没装：winget install EclipseFoundation.Mosquitto，然后 python -m homehub init")
    conf = cfg.data_dir / "mosquitto" / "mosquitto.conf"
    if not conf.exists():
        conf = mosquitto_conf(cfg)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    p = subprocess.Popen([exe, "-c", str(conf)], creationflags=flags)
    for _ in range(50):
        if port_open("127.0.0.1", cfg.mqtt_port):
            log.info("started Mosquitto (pid %s)", p.pid)
            return p
        if p.poll() is not None:
            raise SystemExit(f"Mosquitto 启动失败，看日志 {cfg.data_dir / 'mosquitto' / 'mosquitto.log'}")
        time.sleep(0.1)
    raise SystemExit("Mosquitto 5 秒内没有开始监听")


def cmd_run(a) -> int:
    from .ble_scan import BleGateway
    from .core import Hub
    from .discovery import DiscoveryResponder
    from .store import Store
    from .web import serve

    cfg = cfgmod.load(a.dir)
    from logging.handlers import RotatingFileHandler
    fh = RotatingFileHandler(cfg.data_dir / "homehub.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(fh)
    broker = None if a.no_broker else start_broker(cfg)
    store = Store(cfg.db_path)
    hub = Hub(cfg, store)
    hub.connect()
    disc = DiscoveryResponder(cfg.discovery_port, cfg.mqtt_port, cfg.advertise_host)
    disc.start()
    srv = serve(hub, cfg.http_host, cfg.http_port)
    threading.Thread(target=srv.serve_forever, daemon=True, name="http").start()
    ble = None
    if cfg.ble_scan:
        ble = BleGateway(hub)
        ble.start()
    ip = cfg.advertise_host or cfgmod.lan_ip()
    print(f"HomeHub 在运行。控制页面: http://{ip}:{cfg.http_port}/  （口令见 python -m homehub info）")
    print(f"数据库: {cfg.db_path}   按 Ctrl+C 退出")

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
    last_prune = 0.0
    while not stop.wait(5):
        if time.time() - last_prune > 86400:
            store.prune(cfg.keep_days)
            last_prune = time.time()
        if broker is not None and broker.poll() is not None:
            log.error("Mosquitto exited (%s); restarting", broker.returncode)
            broker = start_broker(cfg)
    srv.shutdown()
    disc.stop()
    if ble is not None:
        ble.stop()
    hub.close()
    store.close()
    if broker is not None:
        broker.terminate()
    return 0


def cmd_info(a) -> int:
    cfg = cfgmod.load(a.dir)
    ip = cfg.advertise_host or cfgmod.lan_ip()
    base = f"http://{ip}:{cfg.http_port}"
    print(f"控制页面   {base}/   （第一次打开时输入口令）")
    print(f"口令       {cfg.token}")
    print(f"数据库     {cfg.db_path}")
    print(f"MQTT       mqtt://{ip}:{cfg.mqtt_port}  设备账号 {cfg.device_user}")
    print()
    print("iPhone 快捷指令（自动化 → 个人 → 无线局域网 → 选家里的 Wi-Fi → 立即运行）：")
    print("  操作“获取 URL 内容”")
    print(f"    URL      {base}/api/scenes/arrive")
    print("    方法     POST")
    print(f"    头部     Authorization = Bearer {cfg.token}")
    print("  场景 arrive 在 config.toml 的 [scenes.arrive] 里定义要开哪些灯。")
    print()
    print("直接开关某个设备：")
    print(f'  curl -X POST -H "Authorization: Bearer {cfg.token}" -d "{{\\"cmd\\":\\"ON\\"}}" '
          f"{base}/api/devices/<设备id>/command")
    return 0


def cmd_provision(a) -> int:
    from .provision import provision

    cfg = cfgmod.load(a.dir)
    host = a.mqtt_host or cfg.advertise_host or cfgmod.lan_ip()
    uri = f"mqtt://{host}:{cfg.mqtt_port}"
    return provision(a.port, a.ssid, a.password, uri, cfg.device_user, cfg.device_password, a.name)


def cmd_simulate(a) -> int:
    from .simulate import run

    cfg = cfgmod.load(a.dir)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    print(f"模拟开关 {a.id} 启动，按 Ctrl+C 退出")
    run(cfg, a.id, a.name, stop=stop)
    return 0


def cmd_ota(a) -> int:
    import functools
    import http.server
    import json as _json

    import paho.mqtt.client as mqtt

    cfg = cfgmod.load(a.dir)
    fw = Path(a.firmware).resolve()
    if not fw.is_file() or fw.suffix != ".bin":
        raise SystemExit(f"{fw} 不是 .bin 文件（用 build/switch_mqtt.bin，不是 merged 那个）")
    if fw.stat().st_size > 0x1E0000:
        raise SystemExit("固件超过 1.875 MB 的 OTA 分区")
    ip = cfg.advertise_host or cfgmod.lan_ip()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(fw.parent))
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", cfg.ota_port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://{ip}:{cfg.ota_port}/{fw.name}"
    done = threading.Event()
    result = {}

    def on_message(_c, _u, msg):
        try:
            ev = _json.loads(msg.payload)
        except ValueError:
            return
        if ev.get("type") == "ota":
            print("设备:", ev)
            if "error" in ev or str(ev.get("stage", "")).startswith("done"):
                result.update(ev)
                done.set()

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"homehub-ota-{int(time.time())}")
    c.username_pw_set(cfg.mqtt_user, cfg.mqtt_password)
    c.on_message = on_message
    c.connect(cfg.mqtt_host, cfg.mqtt_port)
    c.subscribe(f"home/{a.device}/event", qos=1)
    c.loop_start()
    c.publish(f"home/{a.device}/ota", url, qos=1)
    print(f"已通知 {a.device} 从 {url} 下载，等待最多 3 分钟")
    ok = done.wait(180)
    c.loop_stop()
    srv.shutdown()
    if not ok:
        print("没等到结果：设备在线吗？防火墙放行了", cfg.ota_port, "端口吗？")
        return 1
    return 0 if "error" not in result else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="homehub", description="自己电脑上的家庭中枢")
    ap.add_argument("--dir", help="数据目录（默认 ~/HomeHub，或环境变量 HOMEHUB_DIR）")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="第一次使用：生成设置、密码和 Mosquitto 配置")
    r = sub.add_parser("run", help="启动中枢")
    r.add_argument("--no-broker", action="store_true", help="不自动启动 Mosquitto")
    sub.add_parser("info", help="显示控制页面地址、口令和手机快捷指令设置")
    p = sub.add_parser("provision", help="用 USB 线给开关/网关写入 Wi-Fi 和 MQTT 设置")
    p.add_argument("port", help="串口，例如 COM5（Windows）或 /dev/ttyACM0")
    p.add_argument("--ssid", required=True, help="家里 Wi-Fi 名称（2.4 GHz）")
    p.add_argument("--password", required=True, help="Wi-Fi 密码")
    p.add_argument("--name", help="设备名字，例如 客厅灯")
    p.add_argument("--mqtt-host", help="默认用本机局域网 IP")
    s = sub.add_parser("simulate", help="模拟一个开关，没有硬件时试整条链路")
    s.add_argument("--id", default="sw-000001")
    s.add_argument("--name", default="模拟开关")
    o = sub.add_parser("ota", help="通过 Wi-Fi 给设备更新固件")
    o.add_argument("device", help="设备 id，例如 sw-1a2b3c")
    o.add_argument("firmware", help="build/switch_mqtt.bin")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    return {"init": cmd_init, "run": cmd_run, "info": cmd_info, "provision": cmd_provision,
            "simulate": cmd_simulate, "ota": cmd_ota}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
