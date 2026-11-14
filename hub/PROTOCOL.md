# 设备和中枢之间的约定（MQTT）

所有设备都连电脑上的 Mosquitto（默认 1883 端口，局域网内，用户名密码登录，不出家门）。`<id>` 是设备自己的编号：开关是 `sw-` 加 Wi-Fi MAC 后三字节，例如 `sw-1a2b3c`；电脑自带蓝牙在中枢里是 `pc`。

| 主题 | 方向 | 内容 | 保留 |
|---|---|---|---|
| `home/<id>/status` | 设备→中枢 | `online` / `offline`（offline 是遗嘱，掉线时 broker 代发） | 是 |
| `home/<id>/info` | 设备→中枢 | `{"kind":"switch","name","fw","board","chip","mode","ip","mac","config":{...}}` | 是 |
| `home/<id>/state` | 设备→中枢 | `{"power":"ON"}`，开环记录的状态 | 是 |
| `home/<id>/telemetry` | 设备→中枢 | `{"uptime_s","rssi","heap","presses"}`，每分钟一次 | 否 |
| `home/<id>/event` | 设备→中枢 | `{"type":"press","power","source":"mqtt/button/console"}`、`{"type":"config"}`、`{"type":"ota","stage"/"error"}`、`{"type":"error","message"}` | 否 |
| `home/<id>/set` | 中枢→设备 | `ON` / `OFF` / `TOGGLE`（也接受 `{"power":"ON"}`） | 否 |
| `home/<id>/config/set` | 中枢→设备 | `{"press_deg":1-60,"hold_ms":50-3000,"neutral_us":500-2500,"invert":true/false,"name":"..."}`，存进设备闪存 | 否 |
| `home/<id>/ota` | 中枢→设备 | 固件下载地址 `http://<电脑IP>:8782/switch_mqtt.bin` | 否 |
| `home/<gw>/ble` | 网关→中枢 | 一条蓝牙广播 `{"mac","rssi","name","svc":{"181b":"<hex>"},"mfr":"<hex>"}` | 否 |
| `home/hub/status` | 中枢 | 中枢自己在不在线 | 是 |

收到 `ON` 时开关总是按 ON 那一侧，即使记录的状态已经是 ON：开关是开环的，有人手动拨过时再发一次就能纠正。

开关同时发布 Home Assistant 的自动发现消息 `homeassistant/switch/<id>/config`，以后如果在电脑上加装 Home Assistant 并连到同一个 Mosquitto，开关会自己出现，不用改固件。

找中枢：设备连不上保存的 MQTT 地址超过 30 秒（比如电脑换了 IP），就向 UDP 8781 端口广播 8 个字节 `HOMEHUB?`，中枢回 `{"mqtt":"mqtt://<电脑局域网IP>:1883"}`，设备保存新地址后重连。
