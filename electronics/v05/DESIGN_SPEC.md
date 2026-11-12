Switch Robot Carrier V0.5 设计要求（2026-11-12）

目标：在 V0.4 执行器板上直接集成一颗嘉立创可贴片的 ESP32 模组，让 firmware/matter 的 Matter 固件有确定的芯片和引脚，板子在嘉立创一次下单 PCB + SMT，收到后用 USB-C 一根线就能烧录。本文件是给 EDA 执行的要求，最终以 electronics/v05 里的 design_intent.json、DRC/ERC 结果和导出文件为准。

主控选 ESP32-C3-MINI-1-N4（乐鑫，4 MB Flash，板载 PCB 天线，LCSC C2838502）。理由：esp-matter 支持 ESP32-C3，固件 partitions.csv 按 4 MB 写的；C3 有片上 USB-Serial-JTAG，不需要 USB 转串口芯片；MINI-1 体积 13.2×16.6 mm，60×40 板放得下。下单前必须在嘉立创 EDA 的器件库里确认 C2838502 有库存且属于 SMT 可贴装（基础或扩展库）。缺货时的备选按顺序是 ESP32-C3-MINI-1-N4-A、ESP32-C3-WROOM-02-N4，引脚映射保持下面的 GPIO 编号不变。

引脚分配与固件 Kconfig 默认值一致，固件只需要 `idf.py set-target esp32c3`，不用改 menuconfig：GPIO4 = PWM_IN（舵机 PWM，原 J2-2）；GPIO5 = KEY1（PhotoMOS U1，原 J2-3）；GPIO6 = KEY2（PhotoMOS U2，原 J2-4）；GPIO9 = BOOT 按键（固件里的本地按键，短按切换，长按 5 s 恢复出厂）；GPIO18 = USB_D-，GPIO19 = USB_D+；EN = 复位。GPIO2、GPIO8 是启动绑带脚，按乐鑫参考设计各用 10 kΩ 上拉到 3V3（MINI-1 数据手册若说明模组内部已处理则照手册），不要接到其它负载。GPIO20/21（UART0 RX/TX）引到一个 4P 2.54 测试排针 J6（3V3、GND、TX、RX），只做调试备用，可以不焊。

电源：J1 保留为 5V 输入（舵机供电主路），新增 USB-C 母座（16P，仅 USB2.0，例如 TYPE-C-31-M-12 / C165948，以库存为准），CC1、CC2 各 5.1 kΩ 下拉。USB VBUS 经一颗肖特基二极管（如 SS14 / C2480）并入 VIN5，防止 J1 的外部 5V 倒灌电脑 USB 口；J1 直接接 VIN5。F1、C1、C2 和舵机支路保持 V0.4 的拓扑。3V3 用 AMS1117-3.3（C6186，SOT-223）从 VIN5 降压，输入输出各一颗 10 µF；模组 3V3 脚旁再放 10 µF + 100 nF。EN 脚 10 kΩ 上拉 + 1 µF 对地，配一颗复位按键对地；GPIO9 配一颗 BOOT 按键对地（内部有上拉，另加 10 kΩ 上拉更稳）。

执行器部分沿用 V0.4 电路和网络名：R5 220 Ω 串在 PWM_IN 与 SERVO_SIG 之间，R6 100 kΩ 下拉 PWM_IN；R1/R2 470 Ω 驱动 U1/U2（AQY212EH）输入 LED，R3/R4 100 kΩ 下拉 KEY1/KEY2；J3 舵机、J4/J5 浮地输出不变。原 J2 外接 MCU 排针删除（PWM_IN、KEY1、KEY2 改由模组直接驱动）。

器件尽量用嘉立创 SMT 基础库，降低贴片费：电阻电容改为 0603（10 µF 用 0805），例如 470 Ω C23179、100 kΩ C25803、220 Ω C22962、10 kΩ C25804、5.1 kΩ C23186、100 nF C14663、1 µF C15849、10 µF C15850；这些编号要在 EDA 库里逐个确认封装和库存，查不到或已非基础库就换同规格的基础库料。按键用 SMD 轻触开关（例如 TS-1187A 系列，以库存为准）。PhotoMOS 优先换成贴片版（AQY212EHAX、AQY212GS 等同系列 SOP4，确认 LCSC 有货），没有就保留 DIP-4 插件。J1、J3、J4、J5、F1、C1 保持插件，可以手焊，也可以在嘉立创下单时勾选插件焊接。

板子：仍为 60×40×1.6 mm、两层、1 oz，四个 M3 孔位置不变（适配 V0.3 网关盒）。模组天线端必须朝板边，天线区下方所有层不铺铜、不走线，最好天线伸出或贴齐板边，按 MINI-1 数据手册的净空要求。USB-C 放在板边，便于插线；网关盒还没有 USB 开孔，这一点记入 README，由机械线程处理。GND 两面铺铜，模组 GND 焊盘多打过孔。电源线宽沿用 V0.4（VIN5/V5_SERVO/GND 0.8 mm，信号 0.3 mm），USB D+/D- 尽量等长、短。

交付物（放 electronics/v05）：嘉立创 EDA 原生工程压缩包、.esch/.epcb 快照、ERC 和 DRC 结果（要求无错误）、Gerber 压缩包、嘉立创格式 BOM（Comment、Designator、Footprint、LCSC 料号）、坐标文件 CPL（Designator、Mid X、Mid Y、Layer、Rotation）、PCB 截图，以及一份 README 说明怎么在嘉立创下单（上传 Gerber，开 SMT，上传 BOM 和 CPL，核对器件方向，特别是模组和 PhotoMOS 的 1 脚）和怎么烧录固件。不下单、不付款。
