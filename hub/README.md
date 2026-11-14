# HomeHub：用自己的电脑当家庭中枢

开关（V0.5 板，ESP32-C3）通过家里 Wi-Fi 连到这台电脑。电脑上跑两样东西：Mosquitto（MQTT 消息服务器）和 HomeHub（这个目录）。HomeHub 把每一条消息记进电脑上的 SQLite 数据库 `~/HomeHub/home.db`，在局域网里提供控制页面和 HTTP 接口，手机快捷指令也通过它开灯。电脑自带的蓝牙同时当蓝牙网关，收体脂秤之类的广播。没有任何数据出家门，不依赖厂商 App 或云。

```
iPhone 快捷指令 ──HTTP──┐
控制页面（浏览器）──HTTP─┤
                         ├─ HomeHub ──记录──> ~/HomeHub/home.db（SQLite）
开关 ESP32-C3 ──Wi-Fi/MQTT── Mosquitto ┘    └─ 电脑蓝牙 ← 体脂秤等蓝牙广播
```

## 安装（Windows）

需要 Python 3.11 以上和 winget（Windows 11 自带）。在仓库根目录打开 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File hub\windows\install.ps1 -AutoStart
```

它会：装 Mosquitto；在 `%USERPROFILE%\HomeHub\venv` 建 Python 环境装 HomeHub 和 bleak（蓝牙）；生成 `config.toml`（随机口令和 MQTT 密码）和 Mosquitto 配置；弹一次管理员确认，停用 Mosquitto 自带的 Windows 服务（改由 HomeHub 带自己的配置启动），并给防火墙加四条只对本地子网开放的入站规则（TCP 1883、8780、8782，UDP 8781）；`-AutoStart` 让它登录 Windows 后自动在后台运行。最后打印控制页面地址和口令。

不想开机自启就去掉 `-AutoStart`，需要时双击 `hub\windows\start_hub.bat`。

如果电脑在家里 Wi-Fi 上被标成“公用网络”，上面的防火墙规则已经按“任何配置文件”放行本地子网；但若你以前在弹窗里拒绝过 python.exe 联网，Windows 会留下针对 python.exe 的阻止规则，它优先于放行规则，这时到“Windows 防火墙 → 允许应用通过防火墙”里删掉那条，或把家里网络改成“专用”。

macOS / Linux：`pip install ./hub bleak`，装好 mosquitto，然后 `python -m homehub init && python -m homehub run`。

## 常用命令

```
python -m homehub info        控制页面地址、口令、手机快捷指令怎么填
python -m homehub run         启动（install.ps1 -AutoStart 后不用手动）
python -m homehub simulate    模拟一个开关，没有硬件时先把整条链路跑通
python -m homehub provision COM7 --ssid 家里WiFi --password 密码 --name 客厅灯
                              用 USB 线给刚烧好固件的开关写 Wi-Fi 和 MQTT 设置
python -m homehub ota sw-1a2b3c firmware\switch_mqtt\release\switch_mqtt.bin
                              开关装到墙上以后，通过 Wi-Fi 更新固件
```

## 手机到家自动开灯

iPhone“快捷指令 → 自动化 → 新建个人自动化 → 无线局域网 → 选家里的 Wi-Fi → 立即运行”，操作选“获取 URL 内容”：URL 填 `http://<电脑IP>:8780/api/scenes/arrive`，方法 POST，头部加 `Authorization`，值 `Bearer <口令>`（`python -m homehub info` 会打印出完整的值）。用“连上家里 Wi-Fi”而不是“到达位置”触发，是因为到达位置时手机可能还没连上家里网络，请求发不到电脑。

场景 `arrive` 在 `~/HomeHub/config.toml` 里写，例如只在 17:00 到次日 6:00 之间开灯：

```toml
[scenes.arrive]
after = "17:00"
before = "06:00"
actions = [ { device = "sw-1a2b3c", cmd = "ON" } ]
```

电脑必须开着（睡眠时收不到请求）。要在外面也能控制，可以用你已经装了的 Tailscale 访问 `http://<电脑的 Tailscale IP>:8780`，数据仍然只在这台电脑上。

## 数据在哪

全部在 `~/HomeHub/home.db`，四张表：`messages`（每条 MQTT 原始消息）、`devices`（设备和最新状态）、`readings`（信号强度、体重等数值，带时间）、`commands`（谁在什么时候发了什么命令）。用任何 SQLite 工具都能直接查，例如 `sqlite3 home.db "select * from readings where metric='weight_kg'"`。`config.toml` 里 `keep_days = 0` 表示永久保留。

## 蓝牙设备

`run` 时如果装了 bleak，就用电脑蓝牙听广播，只保留体重秤 / 小米服务数据（0x181D、0x181B、0xFE95）和 `config.toml` 的 `[ble]` 里列出的设备，附近别人的手机耳机不会进数据库。小米体重秤 1 代（0x181D）和体脂秤 2（0x181B）不加密，按 openScale 开源驱动的格式直接解出体重和阻抗；体脂秤 S400 的广播是加密的，需要先取得它的 bindkey 填进 `[ble] bindkeys`，并 `pip install xiaomi-ble home-assistant-bluetooth`。这几种格式都没有拿实物秤验证过。

## 测试

```
pip install ./hub[test] && python -m pytest hub/tests
```

`test_end_to_end.py` 需要本机装了 Mosquitto：它真的启动 broker、中枢和模拟开关，通过 HTTP 发 ON、改校准、做 UDP 找中枢，再检查数据库。

消息格式见 [PROTOCOL.md](PROTOCOL.md)。
