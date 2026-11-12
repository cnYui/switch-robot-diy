# 86 开关机器人与 Wi-Fi 遥控桥接器：V0.1 设计草稿

## 仓库说明

内容：Blender 机械件（mechanical/、fit-check/、demo/）、嘉立创 EDA 控制板（electronics/）、MuJoCo 仿真（simulation/）。全部是仿真与设计稿，没有实物验证，不能直接投产。

没有放进仓库的：`tools/`（嘉立创官方桥接 [easyeda-api-skill](https://github.com/easyeda/easyeda-api-skill)、freerouting 布线器 jar、本机 MCP 虚拟环境）、`simulation/.venv`（按 simulation/requirements.txt 重新安装）、`demo/frames` 和 `demo/captioned_frames`（演示视频的逐帧图）、日志和一个过期的打包 zip。仿真脚本要在 simulation 目录里直接用虚拟环境的 python 运行，Blender 脚本用 `blender -b --python xxx.py`。文档里的 `C:/Users/yui/...` 之类路径是作者本机路径。本仓库暂未指定许可证。

此目录包含通过本机 Blender MCP 和嘉立创官方 API Gateway 创建的机械原型与电路布局草稿。日期：2026-11-05。

## V0.6 机械修复（2026-11-12，仅仿真验证）

MuJoCo 仿真发现的机械问题已经按下面修改，细节和数据见 simulation/README.md：

- 按压臂换成 V0.6：mechanical/PRINT_03_double_press_arm.stl（已按“棒材平放、指杆朝上”的打印朝向导出，0 个非流形边）。旧版归档在 mechanical/archive，文件名带 DO_NOT_PRINT。Blender 装配在 mechanical/switch_robot_86_v06.blend，由 mechanical/build_v06.py 生成；switch_robot_86_v01.blend 没有改动。
- 指杆下端抬高到 17.5 mm，下面粘两块 4×7×5.5 mm 的弹性压垫（泡棉或 TPU，外购，不在 STL 内）。
- 支架整体垫高 1.0 mm：每个安装脚下叠两片 0.5 mm 的 M3 平垫圈，增减 0.5 mm 即可微调安装高度。
- 舵机名义按压角改为 17°。固件还没有写，这个角度只是仿真里的数值。
- 框 PRINT_01 把 (42, ±29) 的 3.4 mm 通槽改成 Ø2.5 mm 预钻孔（槽下面是 86 面板，钉头放不下）。螺丝、垫圈、扎带、压垫等采购规格见 mechanical/HARDWARE_BOM.md。
- 回位弹簧（0.05 N·m/rad 以上）仿真里有效，但还没有进 CAD；没有它，断电后臂会停在压垫刚脱离翘板的位置。

没有解决的：翻转阻力 5 N 以上的开关会把压垫压到底，9 N 的开关舵机推不动，只能量到真实开关力之后选舵机。压垫刚度、行程、开关力和舵机反向转动阻力全是假设值，需要实物测量。electronics/ 没有改动，本次修改不影响 PCB。下面的内容是 V0.1 的原始说明。

## 当前状态

机械：已保存 Blender 原生工程和五个毫米单位 STL，五个零件的网格检查均为 0 个非流形边。网格闭合不代表已经通过装配、运动干涉、强度和真实开关的按压力测试。尚未实际打印。

电路：在嘉立创中创建了独立本地工程，完成 60×40 mm 板框、四个 M3 安装孔、40 个有网络的电气焊盘、接口与器件的初步摆放和部分布线。当前使用独立焊盘与丝印描述封装，尚未注册为完整器件库元件。概念接线图使用图形块及导线，并不是完成 ERC 检查、能与 PCB 自动同步的电气原理图。不能据此直接打样或生成装配订单。

嘉立创 DRC 已执行并修复发现的 +5V 走线间距冲突；最后一次检查仍有 Connection Error，来自未完成的网络连接。完整结果见 electronics/drc_draft.json。不存在“DRC 已通过”的结论。

电脑连接的 Espressif Device / COM8 尚未识别出具体芯片型号。本稿没有假定它的 GPIO 引脚、外形尺寸或 Wi-Fi/蓝牙能力，也没有改动它的固件。

## 两种使用路线

自制机器人：经确认支持联网的 ESP32 通过网络服务接收命令，由 PWM 控制舵机，双向按压臂分别压下翘板开关两端。第一版以 SG90 类成品舵机的约 23×12.2×29 mm 包络作尺寸参考，没有设计舵机内部的电机、反馈电位器、齿轮或控制器。

现成机器人改造：保留原遥控器与电池，把板上 J4 或 J5 的两根隔离输出线并接在原遥控器相应按键的两个电气节点上。ESP32 触发 PhotoMOS，让原遥控器发送原有无线指令。需要先测量按键电压、接触方式、导通电阻要求、漏电容忍度；触摸式按键或特殊扫描电路可能不适用。无需假定其无线方式是红外、315/433 MHz 射频还是其他协议。

PhotoMOS 只针对低压遥控器按键，本 PCB 未按市电隔离规范设计。J4/J5 不与本板 GND 相连。板上接口不提供灯已实际开/关的状态检测；只有一个切换按键的遥控器也不能保证命令等价于独立 ON/OFF。

异地控制还需要远程服务：例如 MQTT 服务器，或 Home Assistant 加远程访问。ESP32 本身接上家庭 Wi-Fi 只解决局域网连接。本稿没有部署服务器、写入 Wi-Fi 凭据、实现米家接入或实现可用的远程控制固件。

## 机械文件

mechanical/switch_robot_86_v01.blend 是原生装配场景；assembly_preview.png 是 Blender 渲染。五个 PRINT_*.stl 是独立结构零件，导出单位为 mm。蓝色舵机、绿色 PCB 和开关面板是包络参考，不是打印件。

安装框外尺寸 96×96 mm、内开口 72×72 mm、厚度 3 mm。内侧落在 86 面板边缘附近；实际使用前需要核对原面板边缘可粘贴区域和摇板活动范围。四边并未为所有多联面板保证兼容。

托架采用绑带固定舵机，滑槽允许调整相对位置。双臂半跨度 24 mm，压脚中心位于两端；舵机轴线参考高度 25 mm。使用舵机原装舵盘作转接，中心孔和两侧孔只是原型孔位，必须按实际舵盘复核，不包含可直接咬合舵机花键的精密齿形。先干装并检查中立位置两端都脱离开关，再逐步校准两侧行程，8° 只是最初的几何参考，不是可直接使用的固件控制角度。

（V0.7 起网关盒换成 76×56×30 mm 的 V0.3 版，下面 68×48×22 的旧盒四根盖柱会顶住 PCB 四角，已移到 mechanical/archive。）网关盒外尺寸 68×48×22 mm，壁厚约 2 mm，适配 60×40 mm PCB。PCB 孔位为 (4,4)、(56,4)、(56,36)、(4,36) mm。壳体螺柱按小螺钉自攻试孔设计，实际螺钉与打印收缩需要校核。主控包络仅为占位，不能当作电脑所连板子的尺寸。电容、接插件与实际主控的高度都未完成包络复核。

STL 导出只是平移到底面，未给所有零件选择最佳打印朝向。特别是托架与双臂，应在切片软件中旋转并检查悬垂、孔位和支撑；不能把“平底导出”理解为“全部免支撑”。建议先用低成本材料做尺寸样件，再决定最终材料、壁厚和填充。

## 电路接口与初选器件

J1：1=5V 输入，2=GND。F1 暂为 5.08 mm 间距的自恢复保险丝占位，保持电流、动作电流和压降需要根据实测舵机启动/堵转电流选择。没有输入反接保护和电源管理。

J2：1=GND，2=PWM，3=KEY1，4=KEY2，5=AUX。使用来自已确认主控的 3.3V GPIO；GPIO 选择避开启动绑带、USB 和板上已有功能。主控暂由自己的 USB 供电，与 J1 共地，不把外部 5V 倒灌到未知开发板。

J3：1=GND，2=+5V，3=SERVO。连接前核对舵机线序与 3.3V PWM 兼容性。舵机使用独立充足的 5V 电源，不能从 ESP32 的 3.3V 引脚供电。C1 初选 470uF/10V、5 mm 脚距；C2 为 100nF、2.54 mm 脚距，实际封装均需核对。

U1/U2 初选 Panasonic AQY212EH DIP4 PhotoMOS：1=输入 LED 阳极，2=输入 LED 阴极，3/4=隔离开关输出。布局采用 7.62 mm 跨距、2.54 mm 引脚间距的初步孔位，投板前仍要按采购料号尺寸图核对。R1/R2 为 470Ω，配合 3.3V GPIO 驱动；R3/R4 为 100kΩ 下拉。R5 为 220Ω PWM 串联电阻，R6 为 100kΩ PWM 下拉。电阻孔距均为 7.62 mm 的手焊原型占位。

J4：BTN1_A / BTN1_B；J5：BTN2_A / BTN2_B。分别跨接到遥控器对应按键，隔离输出没有正负极方向约束，但能否正确触发仍要实测。控制程序应使用短脉冲并在开机默认保持输出关闭；固件尚未编写。

## 可编辑源与复现

design_parameters.json 保存初始尺寸。model_robot.py 为常规 Blender Python 源，model_robot_mcp.py 为适用于当前 MCP 安全模式的自包含脚本。已有 Blender 场景经过额外的 2 mm 按压臂侧向间隙修正，两份脚本也已同步该修正。

create_pcb_draft.js、create_wiring_concept.js 保存编辑器调用源；eda_client.py 调用本机官方桥接器。它们是生成脚本，重跑会追加图元，不应在已有文档直接重复运行。电路后续进行过一次定点间距修正，已同步到 create_pcb_draft.js；布局元数据 placement_and_nets.json 记录的是初始放置，最终几何以 carrier_v01.epcb 和原生工程为准。PCB 脚本假设先创建了单一闭合板框。

electronics/native-project 保存完整嘉立创本地工程快照，使用其中 .eprj3 工程打开。原编辑器工程保存在 C:/Users/yui/Documents/LCEDA-Pro/projects/Switch Robot DIY V0.1。electronics 下同时保留 .epcb、.esch 源文档与接线 SVG。

tools/easyeda-api-skill 为本次使用的官方桥接依赖本地副本，不是产品固件。start_blender_mcp.py 用于启动已安装的 Blender MCP 插件。

## 下一步需要的实物验证

识别主控型号与可用 GPIO；测量具体舵机及舵盘；测量摇板宽高、转轴位置、按压行程及力；确认遥控器按键电压与触点。完成这些后，再选择自制机械臂或改造遥控器的实际路线，补完整器件库与电气原理图、完成布线和 ERC/DRC，通过台架测试后才具备打样依据。

## 参考

SG90 原厂尺寸：https://torqpro.com/product/sg90-analog/

PhotoMOS 原厂资料：https://na.industrial.panasonic.com/products/relays-contactors/semiconductor-relays/lineup/photomos-relays/series/12428

ESPHome 红外/射频转发：https://esphome.io/components/remote_transmitter/

米家产品接入：https://iot.mi.com/new/doc/accesses/direct-access/productcenter/create-product

嘉立创官方桥接：https://github.com/easyeda/easyeda-api-skill
