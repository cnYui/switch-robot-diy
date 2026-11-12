# Switch Robot Carrier V0.5（2026-11-12）

V0.4 执行器板 + 板载 ESP32-C3-MINI-1-N4 + USB-C。60×40×1.6 mm，两层，1 oz，四个 M3 孔位置与 V0.4 相同（(4,4)、(56,4)、(56,36)、(4,36)，Φ3.2）。用嘉立创 EDA 专业版 V4.1.78 通过官方 API 桥接完成，独立工程“Switch Robot Carrier V0.5”，没有改动 V0.4 工程。**没有下单、没有付款。**

## 检查结果

- 原理图 ERC：`[]`（无错误、无警告）→ `schematic_erc.json`
- PCB DRC：`passed=true`，明细 `[]` → `pcb_drc.json`。规则集为嘉立创 EDA 自带的 “JLCPCB Capability(Two Layers Board)”：铜间距 0.152 mm（线-线 0.102 mm），最小线宽 0.127 mm。我按 V0.4 的方式尝试覆盖成 0.25 mm 间距规则没有生效（API 返回空），而且 USB-C 0.5 mm 间距的信号焊盘之间本来就只有约 0.2 mm，0.25 mm 规则本身做不到。布线时给 Freerouting 的间距是 0.165 mm。
- 33 个器件、全部焊盘网络与 `design_intent.json` 逐脚一致（0 处不符）→ `pcb_net_check.json`
- 线宽（实际回读）：VIN5 / V5_SERVO 0.8 mm（进 SOT-223、保险丝焊盘处收窄到 0.6 mm），3V3 0.5 mm，VBUS 0.45 mm（进 USB 焊盘处 0.34 mm），GND 走线 0.4 mm + 两面整板 GND 铺铜，信号 0.3 mm，个别进模组/USB 细间距焊盘的短段由 Freerouting 收窄到 0.23 mm。见 `verification_report.json`。
- 天线：模组天线端朝板上边，模组外形贴齐板边（伸出约 0.1 mm）；天线下方 x 21.5–38.5 mm、y 34.8–40 mm 设了全层禁布区（禁止走线、填充、铺铜，也不放过孔），截图里是灰色网格区。
- USB-C 在板下边正中，插口朝外。D+/D- 走线约 25 mm，未做等长/阻抗控制（USB 2.0 全速 12 Mbit/s 足够）。
- 过孔 111 个，其中 GND 84 个（模组中间 GND 焊盘只放下 3 个过孔，其余 6 个位置和底层从模组下方经过的走线冲突，已删除；其余为全板缝合过孔）。

## 器件（全部在 EDA 器件库按 LCSC 编号确认，库存为 2026-11-12 立创商城公开库存）

| 位号 | 料号 | 型号 | 库 | 库存 | 装配 |
|---|---|---|---|---|---|
| U3 | C2838502 | ESP32-C3-MINI-1-N4 | 扩展 | 13494 | SMT |
| U4 | C6186 | AMS1117-3.3 SOT-223 | 基础 | 1002620 | SMT |
| USB1 | C165948 | TYPE-C-31-M-12 | 扩展 | 263870 | SMT |
| D1 | C8678 | SS34 SMA | 基础 | 1955140 | SMT |
| U1,U2 | C29276 | AQY212EHAX SOP-4 | 扩展 | 5666 | SMT |
| SW1,SW2 | C318884 | TS-1187A-B-A-B | 基础 | 545200 | SMT |
| R1,R2 | C23179 | 470Ω 0603 | 基础 | 1133900 | SMT |
| R3,R4,R6 | C25803 | 100kΩ 0603 | 基础 | 6187100 | SMT |
| R5 | C22962 | 220Ω 0603 | 基础 | 968300 | SMT |
| R9–R12 | C25804 | 10kΩ 0603 | 基础 | 3711800 | SMT |
| R7,R8 | C23186 | 5.1kΩ 0603 | 基础 | 14441900 | SMT |
| C2,C6 | C14663 | 100nF 0603 | 基础 | 17200 | SMT |
| C7 | C15849 | 1µF 0603 | 基础 | 1380200 | SMT |
| C3,C4,C5 | C15850 | 10µF 0805 | 基础 | 1790160 | SMT |
| C1 | C713400 | EEUFR1E471B 470µF/25V D10×12.5 | 扩展 | 380 | 插件 |
| F1 | C5395 | RUEF110 | 扩展 | 935 | 插件 |
| J1,J4,J5 | C492401 | PZ254V-11-02P | 扩展 | 768500 | 插件 |
| J3 | C2937625 | PZ254V-11-03P | 扩展 | 960640 | 插件 |
| J6 | C492403 | PZ254V-11-04P（调试，可不焊） | 扩展 | 60300 | 插件 |

所有贴片件都在嘉立创 SMT 库：基础库 11 种，扩展库 3 种（模组 C2838502、USB-C C165948、PhotoMOS C29276，扩展库每种会多收换料费）。插件件 C1、F1、J1、J3、J4、J5、J6 需要手焊，或下单时勾选插件焊接。库存取的是立创商城公开接口；嘉立创 SMT 仓库存以下单页显示为准。

替换记录（详见 `parts_check.json`）：
- D1：规格书的 SS14 C2480 在 EDA 器件库按编号搜不到 → SS34 C8678（基础库，同为 SMA，3A/40V）。
- U1/U2：按规格书换贴片版 AQY212EHAX C29276（与 AQY212EH 同芯片、同引脚定义）。
- C1：V0.4 的 C407944 库存为 0 → 同系列 EEUFR1E471B C713400（470µF/25V，D10×12.5，5 mm 脚距）。
- C2：插件 100nF 改 0603 C14663；R1–R6 改 0603（规格书要求）。
- J3：C2937625 在库里有两条器件记录，第一条缺属性导致 ERC 警告，改用属性完整的那条（同一料号）。

## 引脚

GPIO4=PWM_IN（R5 220Ω→J3 舵机信号，R6 100k 下拉），GPIO5=KEY1（R1→U1），GPIO6=KEY2（R2→U2），GPIO9=BOOT（SW2 + R10 10k 上拉），EN=复位（SW1 + R9 10k + C7 1µF），GPIO18=USB_D-，GPIO19=USB_D+，GPIO20/21=UART0 RX/TX→J6，GPIO2、GPIO8 各 10k 上拉（启动绑带，不接其它负载）。J6：1=3V3、2=GND、3=TX(GPIO21)、4=RX(GPIO20)。J1：1=5V、2=GND。J3：1=GND、2=保险丝后 5V、3=PWM。J4/J5 为浮地常开输出，不接市电。

电源：USB VBUS → SS34 → VIN5；J1 直接接 VIN5（SS34 防止 J1 的 5V 倒灌电脑）。VIN5 → F1 → V5_SERVO（C1 470µF + C2 100nF）→ J3；VIN5 → AMS1117 → 3V3。

## 在嘉立创下单（不要在这一步之外再改设计）

1. 打开嘉立创下单页，上传 `carrier_v05_gerber.zip`。板厚 1.6 mm，2 层，1 oz，其余默认。
2. 打开 “SMT 贴片”，贴片面选 **顶层**。
3. 上传 BOM：`carrier_v05_bom_jlc.csv`（列：Comment、Designator、Footprint、LCSC Part #）；上传坐标：`carrier_v05_cpl_jlc.csv`（Designator、Mid X、Mid Y、Layer、Rotation）。如果页面不认 UTF-8 的 BOM，可以用 EDA 原始导出的 `carrier_v05_bom_native.csv`。
4. 插件件（C1、F1、J1、J3、J4、J5、J6）在 BOM 页可以选“不贴”自己焊，或勾选插件焊接。
5. 在贴片预览里逐个核对方向，特别是：
   - **U3 模组**：1 脚（GND，左上，靠 SW1 一侧）和天线朝板上边；
   - **U1/U2 PhotoMOS**：1 脚（LED 阳极，接 R1/R2）的圆点位置；
   - **D1**：阴极（色环）朝 VIN5（左侧，靠 F1）；
   - **USB1**：插口朝板下边；
   - **U4**：散热片（3V3）在左侧。
   预览方向不对就在页面里旋转修正，不要改坐标文件之外的东西。
6. 确认价格后**由你自己付款**，我这边没有下单。

## 烧录固件

板子只用 USB-C 一根线供电和烧录（ESP32-C3 片上 USB-Serial-JTAG，不需要 USB 转串口芯片）。

```bash
cd firmware/matter
idf.py set-target esp32c3
idf.py build
idf.py -p <串口> flash monitor
```

Windows 上串口一般是 `COMx`（设备管理器里 “USB 串行设备”），Linux 是 `/dev/ttyACM0`。如果下载失败：按住 BOOT（SW2），点一下 RESET（SW1），松开 BOOT，再执行 flash。

## 未验证事项

- 没有做实物：上电、USB 枚举、烧录、Wi-Fi/Thread 射频性能、舵机启动/堵转时 VIN5 跌落和 3V3 是否复位，都还没测。
- 网关盒（V0.3）还没有 USB-C 开孔，需要机械线程加；USB 口中心在板下边 x=30 mm 处。
- 天线净空：按 MINI-1 手册“天线贴齐板边、下方不铺铜”做了，但天线两侧的铜只退到 x 21.5–38.5 mm，没有做更宽的净空；外壳材质也会影响信号。
- 没有 USB ESD 保护器件；D+/D- 没有串阻（C3 内置）。
- AMS1117 从 5V 降 3.3V，模组发射峰值约 350 mA 时 LDO 发热约 0.6 W，SOT-223 靠铺铜散热，没做热仿真。
- 模组下方有底层走线经过（3V3、BOOT、USB 等），是常见做法，但会减少模组中间 GND 焊盘的过孔数（现为 3 个）。
- 坐标文件旋转角是 EDA 导出值，嘉立创个别器件的封装原点/方向定义可能不同，必须以第 5 步的预览为准。
- 库存会变化，下单当天以页面为准；C1（380）、F1（935）库存偏少。

## 文件

- `Switch_Robot_Carrier_V05_native.zip`：原生工程，解压后用 EDA 打开 `.eprj3`
- `carrier_v05.esch` / `carrier_v05.epcb`：源文档快照；`carrier_v05_schematic.png` / `carrier_v05_pcb.png`：截图
- `carrier_v05_gerber.zip`、`carrier_v05_bom_jlc.csv`、`carrier_v05_cpl_jlc.csv`（以及 EDA 原始导出 `*_native.csv`）
- `schematic_erc.json`、`pcb_drc.json`、`pcb_net_check.json`、`verification_report.json`、`parts_check.json`、`design_intent.json`
- 脚本（按顺序）：`check_parts.py` / `build_intent.py`（选料、网络）→ `create_schematic.py` → `wire_schematic.py` → `import_pcb.py` → `layout_pcb.py` → `route_pcb.py`（DSN→Freerouting→SES）→ `finish_pcb.py`（铺铜、过孔、DRC）→ `finalize_and_export.py`

## 过程中遇到的 EDA API 问题（再做时注意）

- `sch_PrimitivePin.modify(id,{noConnected:true})` 会把引脚 Y 坐标取反，把未用引脚移出符号、甚至压到别的引脚上（USB 的 SBU1 被移到 D- 上）。必须同时传原来的 x/y。
- `pcb_Document.importChanges()` 会弹确认框，需要在界面上点“应用修改”。
- SES 导入不保留线宽（全部变 0.254 mm），`route_pcb.py` 会按 SES 逐段写回线宽。
- `rebuildCopperRegion()` 和界面的铺铜重建在会话中途会卡住，重启嘉立创 EDA 后恢复正常。
- USB-C 封装的两个 NPTH 定位柱不在导出的 DSN 里，需要手动加禁布区，否则 DRC 报“槽孔到走线”间距不足。
- 覆盖当前 DRC 规则配置（`overwriteCurrentRuleConfiguration`）没有生效，最终沿用 EDA 自带的嘉立创两层板工艺规则。
