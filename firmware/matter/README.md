# 开关机器人 Matter 固件

基于 ESP-IDF + [esp-matter](https://github.com/espressif/esp-matter) 的 Wi-Fi Matter 固件。设备在 Matter 里是一个“插座 / On-Off Plug-in Unit”，手机上点“开”就按 86 开关的 ON 那一侧，点“关”就按 OFF 那一侧，按完回到中立位。配网走蓝牙，之后只用 Wi-Fi。苹果家庭、Google Home、Amazon Alexa、Home Assistant（Matter 集成）以及支持 Matter 的小米中枢都可以添加，不需要额外的云服务。

固件没有在实物上跑过，也还没有完整编译通过（写作环境拿不到 esp-matter 的在线依赖），只对照 esp-matter 当前版本（ESP-IDF 6.0）的头文件核对过 API。第一次编译如果报错，多半是 esp-matter 版本间的接口差异。按压角度、保持时间这些都是仿真里的数值，要在真实开关上校准。

## 芯片要求

esp-matter 支持 ESP32、ESP32-C3、ESP32-S3、ESP32-C6（Wi-Fi）。需要 4 MB 以上 Flash。ESP32-C2、ESP32-S2 不支持（前者资源不够，后者没有蓝牙配网）。仓库 README 里提到的那块 Espressif 开发板型号还没确认，先用 `idf.py set-target` 选对芯片。

## 两种执行方式（menuconfig → Switch Robot）

舵机模式（默认，自制机器人路线）：J2 第 2 脚 PWM（默认 GPIO4）驱动 J3 上的舵机。中立 1500 µs，按压角 17°（≈189 µs），保持 400 ms 后回中，回中后默认停 PWM，消除舵机嗡嗡声。停 PWM 依赖回位弹簧，弹簧还没进 CAD；装弹簧之前请把 “Stop PWM after returning to neutral” 关掉。方向反了就勾 “Swap ON/OFF press direction”。

PhotoMOS 模式（改造现成遥控器路线）：KEY1（默认 GPIO5）经 U1 短接 J4 = 遥控器的“开”键，KEY2（默认 GPIO6）经 U2 短接 J5 = “关”键，每次闭合 400 ms。只有一个切换键的遥控器不适用这个模式。

本地按键默认是开发板 BOOT 键（ESP32/S3 为 GPIO0，C3/C6 为 GPIO9）：短按在本地切换一次并同步到 Matter，按住 5 秒清除配对和 Wi-Fi，重新进入配网。设为 -1 关闭。GPIO 编号要按实际开发板和 J2 接线改，默认值没有核对过具体板子。

## 编译与烧录

```bash
# 已装好 ESP-IDF 和 esp-matter 时
. $IDF_PATH/export.sh && . $ESP_MATTER_PATH/export.sh
cd firmware/matter
idf.py set-target esp32c3        # 换成你的芯片
idf.py menuconfig                # Switch Robot 菜单里改模式和引脚
idf.py build flash monitor

# 或者用官方 Docker 镜像只编译
docker run --rm -v $PWD:/project -w /project espressif/esp-matter:latest \
  bash -c "idf.py set-target esp32c3 && idf.py build"
```

## 配网

默认用的是 Matter SDK 自带的测试证书，串口日志里会打出配网二维码链接，手动配对码是 `34970112332`（passcode 20202021，discriminator 3840）。苹果家庭和 Google Home 会提示“未认证配件”，确认后可以添加。小米中枢对未认证 Matter 设备的支持情况我不确定，需要实测。测试证书只适合自用，不能拿去卖。

## 已知限制

开环控制：固件不知道灯实际是开还是关。如果有人手动拨了开关，Matter 里的状态会和实际不一致；这时在 App 里先切到反方向再切回来即可（Matter 状态没变化时不会触发按压）。

上电不动作：重启后舵机只回中立，不会按照保存的状态去按开关，避免断电恢复时把灯误拨。

连续快速发命令时只执行最后一条。
