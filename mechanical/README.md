机械件，2026-11-12 更新（V0.6；紧固件 V0.7）。

V0.7：所有螺丝和垫圈都建了实体，见 switch_robot_86_v07_fasteners.blend 和 HARDWARE_BOM.md 开头。PRINT_04 / PRINT_05 已换成 fit-check 里的 V0.3 网关盒（76×56×30），旧盒放不下 PCB，在 archive。重新生成：blender -b --python build_fasteners.py，然后 simulation/.venv/Scripts/python.exe -I mechanical/verify_fasteners.py。

当前可打印的按压臂：PRINT_03_double_press_arm.stl（V0.6）。STL 已经按“棒材大面贴床、两根指杆朝上”的朝向导出，不需要悬空支撑。旧版（指杆更长，带 7 mm 垫座，中立时与翘板穿入约 0.216 mm）在 archive/PRINT_03_double_press_arm_V01_DO_NOT_PRINT.stl，只留作对照，不要打印。

V0.6 与旧版的区别：指杆下端从约 12 mm 抬到 17.5 mm，没有垫座；下面用胶粘一块 4×7 mm、自由高度 5.5 mm 的弹性压垫（泡棉或 TPU，外购，在 Blender 里只有参考体）。仿真假设压垫刚度 2 N/mm、有效压缩 2.5 mm（压缩约 45%），实物压垫必须测量，选型建议范围 1.5 ~ 2.5 N/mm。

安装（V0.7 起：框下 0.5 mm 双面胶 + 每脚 1 片 0.5 mm 垫圈，合计仍为 1.0 mm；下面是 V0.6 原文）：支架 PRINT_02 的每个安装脚下叠两片 0.5 mm 的 M3 平垫圈（共垫高 1.0 mm），这是仿真里的名义安装高度；装好后测量中立位置压垫到翘板的空隙，目标约 2 mm，再用增减 0.5 mm 垫圈微调。框到面板的双面胶也会抬高支架，垫圈加胶的总厚度按 1.0 mm 算。

框 PRINT_01 改了：原来 (42, ±29) 的 3.4 mm 通槽改成 Ø2.5 mm 预钻孔，因为槽下面是 86 面板，钉头和螺母放不下。旧框在 archive/PRINT_01_86_adjustable_frame_V01_slotted.stl，不要打印。PRINT_02 没有改动。螺丝、垫圈和其他小件见 HARDWARE_BOM.md。

文件：switch_robot_86_v06.blend 是 V0.6 的装配场景（新臂、抬高后的支架与舵机参考体、垫圈和压垫参考体），由 build_v06.py 在 V0.1 场景基础上生成，用 blender -b --python build_v06.py 重新生成会覆盖 PRINT_03 STL 和 V0.6 场景。switch_robot_86_v01.blend 保持原样，仿真的 export_cad.py 仍从它导出旧版本做对照。mesh_checks_v06.json 是新臂和新框的网格检查（均为 0 个非流形边）。

没有打印验证：打印材料、公差、胶粘强度、压垫实际刚度、舵盘连接都没有实物数据。
