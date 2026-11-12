Switch Robot Carrier V0.4，2026-11-06。

本版已经完成正式原理图、供应商器件与封装绑定、原理图导入 PCB、双层布线及可读丝印。16 个元件、40 个元件引脚的网络与 design_intent.json 一致，SCH 与 PCB 的供应商料号和 Unique ID 一致。原理图 ERC 无警告，PCB 严格 DRC 返回 passed=true、details=[]。实际 69 段导线均已回读，供电与地线宽 0.8001 mm、信号线宽 0.3048 mm；板内铜间距规则为 0.25 mm、最小线宽规则为 0.30 mm。本次没有下单或付款。

板外形 60×40 mm，建议板厚 1.6 mm、1 oz 铜、两层板。安装孔为 (4,4)、(56,4)、(56,36)、(4,36)，直径 3.2 mm。制造钻孔文件含 40 个电镀元件通孔和 4 个非电镀安装孔；通孔钻径已经从最终 Gerber 的 Excellon 文件核对，未使用编辑器 API 返回的错误缩小钻径作为制造依据。

J1 为稳定 5V 电源输入，1=5V、2=GND。J2 连接另行供电的 3.3V MCU：1=GND、2=PWM_IN、3=KEY1、4=KEY2、5=GND 备用地线。MCU 与板子共地。J3 接位置舵机：1=GND、2=保险丝后的 5V、3=PWM。接线前核对舵机导线次序。J4、J5 分别是两路浮地 PhotoMOS 常开输出，用于跨接低压遥控器按钮触点；本板不接墙壁开关的市电端子。没有反接保护。

本板是外接 MCU 的执行器与隔离输出扩展板，尚未识别的 ESP32 开发板没有被假定为某个固定引脚型号。F1 是 RUEF110 自恢复保险丝，保护与供电性能仍应在实际舵机启动、堵转及工作电压下测量。

carrier_v04_gerber.zip 是最终制造文件。carrier_v04_bom.csv 是按导出的官方物料清单转换的标准 CSV，原始制表符版本保存在 carrier_v04_bom_native.tsv。Switch_Robot_Carrier_V04_native.zip 包含原生文件夹工程，解压后从 .eprj3 文件打开。carrier_v04.epcb、carrier_v04.esch 为最终源文档快照。verification_report.json、electrical_audit.json、pcb_final_state.json 和 pcb_drc_final.json 为检查证据。carrier_v04_pcb.png 是编辑器实际布局截图。carrier_v04_populated.zip 中是 OBJ 和 MTL；3d 目录已经解压，供 CAD/Blender 导入。

元件三维模型属于官方库的近似外形：C1 模型名称为 H16.0，而所选 EEUFR1E471 的本体高度是 12.5 mm；F1 模型名称为 H8.5，而 RUEF110 应按数据手册的最大高度 14.2 mm 检查空间。不能单凭此 OBJ 宣称所有实体外形精确匹配。模型还包含未剪短的通孔引脚；焊后应剪脚并检查与壳体底部的空间。插头高度、线材弯曲、外接 MCU、实际板厚和打印公差尚未完成整机实物核验。

先前输出的操作视频为预设关键帧演示。当前没有运行舵机、推杆及翘板开关的动力学仿真，也没有用模拟运动作为 DRC 或实物受力测试的依据。后续可用 MuJoCo 或 Webots 建立舵机限矩、限速、碰撞、摩擦以及开关双稳态翻转阻力模型，并通过连接程序接入固件或真实 MCU。模型需要实际力与行程数据校准。
