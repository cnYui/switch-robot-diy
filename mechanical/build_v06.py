"""在 V0.1 装配场景基础上生成 V0.6：新按压臂、整体垫高 1.0 mm、弹性压垫与垫圈的参考体。
不覆盖 switch_robot_86_v01.blend；另存为 switch_robot_86_v06.blend，并导出新的 PRINT_03 STL。
用法：blender -b --python build_v06.py
"""
import bmesh
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector

ROOT = Path('D:/CodeWorkSpace/switch-robot-diy')
OUT = ROOT / 'mechanical'
MM = .001
SHIM = 1.0 * MM            # 支架安装脚下叠两片 0.5 mm M3 平垫圈
FINGER_BOTTOM = 17.5 * MM  # 指杆下端，下面粘 4x7x5.5 mm 弹性压垫

bpy.ops.wm.open_mainfile(filepath=str(OUT / 'switch_robot_86_v01.blend'))
old = bpy.data.objects['PRINT_03_double_press_arm']
scene = old.users_scene[0]
if bpy.context.scene != scene:
    bpy.context.window.scene = scene
assert bpy.context.scene == scene, 'wrong active scene'


def cube(name, size, position):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def boolean(target, tool, operation):
    bpy.context.view_layer.objects.active = target
    modifier = target.modifiers.new('V06 machining', 'BOOLEAN')
    modifier.operation = operation
    modifier.solver = 'EXACT'
    modifier.object = tool
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(tool, do_unlink=True)


def reference(name, size, position, color):
    obj = cube(name, size, position)
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    obj.data.materials.append(material)
    return obj


materials = list(old.data.materials)
bpy.data.objects.remove(old, do_unlink=True)

# 整个机器人安装组（支架、舵机参考体）一起抬高 1.0 mm。
for name in ['PRINT_02_strap_servo_cradle', 'REFERENCE_servo_approximate', 'REFERENCE_servo_output']:
    bpy.data.objects[name].location.z += SHIM

arm = cube('PRINT_03_double_press_arm', (.004, .056, .006), (.024, 0, .025 + SHIM))
arm_bevel = arm.modifiers.new('Original bar bevel', 'BEVEL')
arm_bevel.width = .0007
arm_bevel.segments = 3
bpy.context.view_layer.objects.active = arm
bpy.ops.object.modifier_apply(modifier=arm_bevel.name)
for side in (-1, 1):
    boolean(arm, cube('finger', (.004, .007, .027 - .0175),
                      (.024, side * .024, (.027 + .0175) / 2 + SHIM)), 'UNION')
for y, radius in [(0, .00125), (-.009, .0011), (.009, .0011)]:
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=.010,
                                        location=(.024, y, .025 + SHIM), rotation=(0, math.pi / 2, 0))
    boolean(arm, bpy.context.object, 'DIFFERENCE')
arm.data.materials.clear()
arm.data.materials.append(next(m for m in materials if m and 'arm' in m.name))
arm['status'] = 'V0.6: fingers shortened for elastic pads; print flat on the bar face (see STL export)'

for side in (-1, 1):
    reference('REFERENCE_elastic_pad_4x7x5.5_unmeasured', (.004, .007, .0055),
              (.024, side * .024, FINGER_BOTTOM - .00275 + SHIM), (.12, .12, .12))
    # 垫圈叠放在支架安装脚下方：安装脚底面原为 z=8 mm。
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=.0035, depth=SHIM,
                                        location=(.042, side * .029, .008 + SHIM / 2))
    washer = bpy.context.object
    washer.name = 'REFERENCE_M3_washers_2x0.5mm'
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=.0017, depth=SHIM * 2,
                                        location=(.042, side * .029, .008 + SHIM / 2))
    boolean(washer, bpy.context.object, 'DIFFERENCE')
    steel = bpy.data.materials.get('M3 washer steel') or bpy.data.materials.new('M3 washer steel')
    steel.diffuse_color = (.55, .57, .6, 1)
    washer.data.materials.append(steel)

# 框与支架的连接：原来框上是 3.4 mm 通槽（x=42，宽 x 40.3~43.7），而 86 面板边缘在 x=43，
# 钉头或螺母要落到面板里，装不上。改成实心 + Ø2.5 mm 预钻孔，用 M3 自攻螺丝从上面直接拧进框
# （支架安装脚上的 3.4 mm 长孔保留，仍可沿 y 方向调 ±3 mm）。
frame = bpy.data.objects['PRINT_01_86_adjustable_frame']
for y in (-29, 29):
    boolean(frame, cube('slot fill', (.0036, .0182, .003), (.042, y * MM, .0065)), 'UNION')
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=.00125, depth=.012,
                                        location=(.042, y * MM, .0065))
    boolean(frame, bpy.context.object, 'DIFFERENCE')
frame['status'] = 'V0.6: slots replaced by two 2.5 mm pilot holes for M3 thread-forming screws'


def export_stl(obj, filename, flip=False):
    """复制到原点、最低点落到 z=0 后导出毫米单位 STL；flip 为绕 y 轴翻面。"""
    export = obj.copy()
    export.data = obj.data.copy()
    bpy.context.scene.collection.objects.link(export)
    bpy.ops.object.select_all(action='DESELECT')
    export.select_set(True)
    bpy.context.view_layer.objects.active = export
    if flip:
        export.rotation_euler.y = math.pi
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    export.location.x = export.location.y = 0
    bpy.context.view_layer.update()
    export.location.z -= min((export.matrix_world @ Vector(v)).z for v in export.bound_box)
    bpy.ops.wm.stl_export(filepath=str(OUT / filename), export_selected_objects=True,
                          global_scale=1000, apply_modifiers=True)
    bpy.data.objects.remove(export, do_unlink=True)


# 导出打印朝向：棒材大面贴床，两根指杆朝上，不需要悬空支撑。
export_stl(arm, 'PRINT_03_double_press_arm.stl', flip=True)
export_stl(frame, 'PRINT_01_86_adjustable_frame.stl')


def check(obj, **extra):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    result = {'part': obj.name, 'non_manifold_edges': sum(not e.is_manifold for e in bm.edges),
              'volume_mm3': round(abs(bm.calc_volume()) * 1e9, 2),
              'dimensions_mm': [round(d * 1000, 2) for d in obj.dimensions], **extra}
    bm.free()
    return result


report = {'parts': [
    check(arm, print_orientation='bar flat on bed, fingers up (STL is exported in this orientation)',
          assembly_changes={'cradle_and_servo_raised_mm': SHIM * 1000, 'finger_bottom_mm': FINGER_BOTTOM * 1000}),
    check(frame, change='slots replaced by 2 x 2.5 mm pilot holes at (42, +-29) mm'),
]}
(OUT / 'mesh_checks_v06.json').write_text(json.dumps(report, indent=2), encoding='utf8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'switch_robot_86_v06.blend'))
print(json.dumps(report))
