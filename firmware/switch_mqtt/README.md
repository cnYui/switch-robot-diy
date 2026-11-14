# 开关固件（连自己电脑的家庭中枢）

给 Switch Robot Carrier V0.5（ESP32-C3-MINI-1-N4）用的 ESP-IDF 固件：连家里 Wi-Fi，连电脑上的 Mosquitto，收到 `home/<id>/set` 的 ON/OFF/TOGGLE 就按 86 开关对应的一侧。不经过任何云，不需要米家或别的 App。和 `firmware/matter`（Matter 版）二选一烧录；要接自己电脑的中枢就用这个。

引脚按 V0.5 板：GPIO4 舵机 PWM（J3），GPIO5/6 PhotoMOS（J4/J5，改造遥控器路线），GPIO9 BOOT 键（SW2），USB-C 走芯片自带的 USB-Serial-JTAG。

## 不装 ESP-IDF 直接烧

`release/switch_mqtt_esp32c3_merged.bin` 是编译好的完整镜像（引导程序 + 分区表 + 应用），用 ESP-IDF v5.4.1 编译，0 个警告。电脑上有 esptool 就能烧：

```
python -m esptool --chip esp32c3 write_flash 0x0 firmware\switch_mqtt\release\switch_mqtt_esp32c3_merged.bin
```

板子用 USB-C 接电脑，设备管理器里会出现一个“USB 串行设备 (COMx)”，esptool 会自己找；找不到就加 `-p COMx`。下载失败时按住 BOOT（SW2）点一下 RESET（SW1）再松开 BOOT。

## 写入 Wi-Fi 和 MQTT 设置

烧好后不拔线，在电脑上运行（中枢已经 `init` 过）：

```
python -m homehub provision COMx --ssid "家里WiFi" --password "Wi-Fi密码" --name 客厅灯
```

它通过 USB 串口把 Wi-Fi、电脑的 MQTT 地址和设备账号写进开关，然后重启。ESP32-C3 只支持 2.4 GHz Wi-Fi。开关上线后会出现在控制页面里。

串口里也可以手动敲命令（任何串口工具，回车结尾，每条回一行 OK/ERR）：`status`、`wifi "名称" "密码"`、`mqtt "mqtt://192.168.1.32:1883" "device" "密码"`、`name "客厅灯"`、`press on`、`press off`、`reboot`、`forget`。

## 装到墙上以后

校准：控制页面上开关卡片的“校准按压”里改按压角度、保持时间、中立脉宽、方向，保存后立即生效并存进开关，不用重新烧录。17° / 400 ms / 1500 µs 都是仿真值，要在真实开关上调。

更新固件：`python -m homehub ota sw-xxxxxx firmware\switch_mqtt\release\switch_mqtt.bin`（注意是不带 merged 的那个）。开关从电脑下载、校验后重启；新固件 5 分钟内连不上中枢会自动退回旧版本。

电脑换了 IP：开关连不上原地址 30 秒后会在局域网里广播找中枢，自动改用新地址。

BOOT 键：短按切换一次，按住 5 秒清掉 Wi-Fi 和 MQTT 设置（校准保留），重新 provision。

上电时舵机只回中立位，不会按开关；收到 ON 时总是按 ON 那一侧（开环控制，手动拨过之后再发一次就能纠正）。

## 自己编译

```
docker run --rm -v %cd%:/project -w /project espressif/idf:v5.4.1 idf.py build
```

或装好 ESP-IDF 5.4 后 `idf.py build flash monitor`。`idf.py menuconfig` 的 “Switch Robot” 菜单里切换舵机 / PhotoMOS 模式和引脚，“Home hub defaults” 里可以把 Wi-Fi 和 MQTT 直接编进固件（一般不需要）。

## 没验证过的

固件只在编译层面验证过，没有在 V0.5 实物板上跑过（板子还没下单）。中枢那一侧用模拟开关（`python -m homehub simulate`）和真实 Mosquitto 跑通了整条链路，消息格式与本固件一致，见 `hub/PROTOCOL.md`。
