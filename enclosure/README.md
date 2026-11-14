# 控制盒 V0.4（装 V0.5 开关板）

V0.3 网关盒（`fit-check/`，76×56×30）是在 V0.5 板之前画的：两个线缆槽都对不上 V0.5 长边正中的 USB-C，而且 USB-C 插座口在外墙面以内约 7.5 mm（板边到内墙 6 mm 加 2 mm 墙厚），从小孔里插不到底。V0.4 只改这一处，其余与 V0.3 完全相同，V0.3 的盒盖照用。

`build_case_v04.py` 用 manifold3d 按 V0.3 Blender 脚本的同一组方块、圆柱和布尔顺序重建盒体（64 段圆柱）。重建出的 V0.3 体积 24329.0 mm³，与 `fit-check` 里 Blender 导出的 STL 一致。在此基础上：去掉 −y 墙上原来 18×8 的电源线槽（V0.5 由 USB-C 供电，J1 不再接线），在同一面墙正中开 14×9 mm 的口，中心对准 USB-C 高度（盒底以上 5.6–14.6 mm），让普通 USB-C 线的插头外壳能穿过墙直接插到底。+y 墙上 24×8 的信号线槽（舵机线、J4/J5）不变。

检查结果见 `case_v04_checks.json`：PCB、USB-C 母座、12.5×6.5 mm 的插头外壳与盒体的交叠体积都是 0（V0.3 里同一个插头会和墙交叠 133.8 mm³）；网格封闭。`case_v04_fit.png` 是 USB-C 高度的俯视剖面和那面墙的外视图。

装板方向：USB-C 朝开了大口的那面墙（板上 U3 模组天线那一边朝信号线槽）。四个安装孔对称，装反了也拧得上，所以装之前看一下方向。

没验证的：USB-C 母座尺寸按 TYPE-C-31-M-12 同类规格书估计（8.94×7.35×3.26 mm），插头外壳按常见 12.5×6.5 mm，粗头线（外壳超过 14×9）插不进去；打印收缩和实际装配都没有试过。

文件：`PRINT_04_control_box_v04.stl`（盒体，毫米，底面在 z=0）、`PRINT_05_control_box_lid_v03.stl`（盒盖，原 V0.3 文件的拷贝）。重新生成：`python -I enclosure/build_case_v04.py && python -I enclosure/render_case_v04.py`（需要 manifold3d、trimesh、numpy、scipy、matplotlib）。
