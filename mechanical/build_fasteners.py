"""V0.7 紧固件层：在 V0.6 装配场景里加入真实尺寸的螺丝和垫圈，换上能放下 PCB 的 V0.3 网关盒，
并逐个检查螺丝与各零件的干涉体积。不覆盖 V0.6 / V0.3 的 blend，另存为 switch_robot_86_v07_fasteners.blend。
用法：blender -b --python build_fasteners.py
长度单位：脚本内用毫米，写入 Blender 时换成米。
"""
import bpy
import bmesh
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path('D:/CodeWorkSpace/switch-robot-diy')
OUT = ROOT / 'mechanical'
MM = .001

bpy.ops.wm.open_mainfile(filepath=str(OUT / 'switch_robot_86_v06.blend'))
scene = bpy.data.scenes['Switch Robot 86 - V0.1']
if bpy.context.window is not None:
    bpy.context.window.scene = scene

# ---------- 1. 换上 V0.3 网关盒（68x48x22 旧盒的 4 根盖柱会插进 PCB 的四个角，装不下 PCB） ----------
for old in ('PRINT_04_gateway_case', 'PRINT_05_gateway_lid'):
    bpy.data.objects.remove(bpy.data.objects[old], do_unlink=True)
with bpy.data.libraries.load(str(ROOT / 'fit-check' / 'enclosure_fit_v03.blend'), link=False) as (src, dst):
    dst.objects = ['V03_PRINT_gateway_case_76x56x30', 'V03_PRINT_gateway_lid_76x56']
case, lid = dst.objects
for o in (case, lid):
    scene.collection.objects.link(o)
case.name = 'PRINT_04_gateway_case_V03'
lid.name = 'PRINT_05_gateway_lid_V03'
# V0.3 文件里盖子被移到旁边观察（y +82 mm, z -10 mm），挪回闭合位置。
lid.location.y -= 82 * MM
lid.location.z += 10 * MM
bpy.context.view_layer.update()


def bounds(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return ([min(p[i] for p in pts) / MM for i in range(3)], [max(p[i] for p in pts) / MM for i in range(3)])


lo, hi = bounds(lid)
assert abs(lo[2] - 35.0) < 1e-3 and abs(lo[1] + 42.0) < 1e-3, ('lid not closed', lo, hi)

# ---------- 2. 框下加 0.5 mm 泡棉双面胶（框抬高 0.5），每个脚下只留 1 片 0.5 mm 垫圈，合计仍抬高 1.0 mm ----------
frame = bpy.data.objects['PRINT_01_86_adjustable_frame']
frame.location.z += 0.5 * MM
frame['tape_under_frame_mm'] = 0.5
for o in [o for o in bpy.data.objects if o.name.startswith('REFERENCE_M3_washers_2x0.5mm')]:
    bpy.data.objects.remove(o, do_unlink=True)
bpy.context.view_layer.update()

steel = bpy.data.materials.new('Fastener 304 steel')
steel.diffuse_color = (.62, .64, .67, 1)
objects_made = []


def boolean(target, tool, op):
    bpy.context.view_layer.objects.active = target
    m = target.modifiers.new('fastener boolean', 'BOOLEAN')
    m.operation = op
    m.solver = 'EXACT'
    m.object = tool
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(tool, do_unlink=True)


def washer(name, centre, outer, inner, thick, props):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=outer / 2 * MM, depth=thick * MM,
                                        location=Vector(centre) * MM)
    w = bpy.context.object
    w.name = name
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=inner / 2 * MM, depth=thick * MM * 2,
                                        location=Vector(centre) * MM)
    boolean(w, bpy.context.object, 'DIFFERENCE')
    w.data.materials.append(steel)
    for k, v in props.items():
        w[k] = v
    w['outer_mm'] = outer
    w['inner_mm'] = inner
    w['thick_mm'] = thick
    w['centre_mm'] = list(centre)
    objects_made.append(w)
    return w


def screw(name, d, length, dk, k, bearing_point, axis, props, tip=1.2):
    """盘头十字自攻螺丝：dk 头径、k 头厚、d 螺纹大径、length 头下到尖端。bearing_point 是承压面上的点，axis 从头指向尖。"""
    axis = Vector(axis).normalized()
    rot = Vector((0, 0, 1)).rotation_difference(axis).to_euler()
    p = Vector(bearing_point)
    parts = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=dk / 2 * MM, depth=k * MM,
                                        location=(p - axis * k / 2) * MM, rotation=rot)
    parts.append(bpy.context.object)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=d / 2 * MM, depth=(length - tip) * MM,
                                        location=(p + axis * (length - tip) / 2) * MM, rotation=rot)
    parts.append(bpy.context.object)
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=d / 2 * MM, radius2=.25 * MM, depth=tip * MM,
                                    location=(p + axis * (length - tip / 2)) * MM, rotation=rot)
    parts.append(bpy.context.object)
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    s = bpy.context.object
    s.name = name
    s.data.materials.append(steel)
    s['thread_d_mm'] = d
    s['length_under_head_mm'] = length
    s['head_dia_mm'] = dk
    s['head_height_mm'] = k
    s['recess'] = 'Phillips recess not modelled'
    s['bearing_point_mm'] = list(p)
    s['axis'] = list(axis)
    s['tip_mm'] = tip
    for key, v in props.items():
        s[key] = v
    objects_made.append(s)
    return s


M3 = dict(d=3.0, dk=5.3, k=1.9)   # 5.3 / 1.9 / 3.0 来自卖家 M3*6、M3*8 规格图
M2 = dict(d=2.0, dk=3.8, k=1.4)   # 假设值：卖家 M2*6 规格图还没读到，收货后量
SKU_BRT = 'https://detail.tmall.com/item.htm?id=15858629599'
SKU_TZ = 'https://detail.tmall.com/item.htm?id=849674040028'

for i, (sx, sy) in enumerate([(-26, -16), (26, -16), (26, 16), (-26, 16)], 1):
    screw(f'FASTENER_F1_pcb_to_standoff_{i}', length=6, bearing_point=(114 + sx, -14 + sy, 13.5), axis=(0, 0, -1),
          props={'role': 'PCB -> case standoff', 'taobao_item': SKU_BRT, 'taobao_sku': 'M3*6(200粒)304'}, **M3)
for i, (sx, sy) in enumerate([(-34, -24), (34, -24), (34, 24), (-34, 24)], 1):
    screw(f'FASTENER_F2_lid_to_post_{i}', length=12, bearing_point=(114 + sx, -14 + sy, 37.4), axis=(0, 0, -1),
          props={'role': 'lid -> lid post', 'taobao_item': SKU_BRT, 'taobao_sku': 'M3*12(200粒)304'}, **M3)
for i, sy in enumerate((-29, 29), 1):
    screw(f'FASTENER_F3_cradle_to_frame_{i}', length=6, bearing_point=(42, sy, 12.0), axis=(0, 0, -1),
          props={'role': 'cradle foot -> frame pilot', 'taobao_item': SKU_BRT, 'taobao_sku': 'M3*6(200粒)304'}, **M3)
    washer(f'FASTENER_W1_washer_{i}', (42, sy, 8.75), 7.0, 3.2, 0.5,
           {'role': 'shim under cradle foot', 'taobao_item': SKU_TZ, 'taobao_sku': '3*7*0.5(500只)'})
for i, sy in enumerate((-9, 9), 1):
    screw(f'FASTENER_F4_arm_to_horn_{i}', length=6, bearing_point=(22, sy, 26), axis=(1, 0, 0),
          props={'role': 'press arm -> SG90 horn', 'taobao_item': SKU_BRT, 'taobao_sku': 'M2*6(200粒)304',
                 'head_dims_source': 'assumed, measure on delivery'}, **M2)
bpy.context.view_layer.update()

# ---------- 3. 导出世界坐标网格和螺丝参数，供 verify_fasteners.py 做干涉与咬合检查 ----------
# （Blender 的 EXACT 布尔对 0.35 mm 的薄壳咬合结果不稳定：四个对称位置得到 0 / 8 / 10 / 88 mm3，所以不用它判定。）
import numpy as np
mesh_dir = OUT / '_fastener_meshes'
mesh_dir.mkdir(exist_ok=True)
depsgraph = bpy.context.evaluated_depsgraph_get()
scene_parts = [o for o in scene.objects if o.type == 'MESH' and o.name.startswith(('PRINT_', 'REFERENCE_', 'FASTENER_'))]
for o in scene_parts:
    ev = o.evaluated_get(depsgraph)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    verts = np.array([(o.matrix_world @ v.co) / MM for v in me.vertices], dtype=float)
    tris = np.array([t.vertices[:] for t in me.loop_triangles], dtype=np.int64)
    np.savez_compressed(mesh_dir / (o.name + '.npz'), v=verts, f=tris)
    ev.to_mesh_clear()

fast = list(objects_made)
spec = []
for o in fast:
    spec.append({k: (list(o[k]) if hasattr(o[k], '__len__') and not isinstance(o[k], str) else o[k])
                 for k in o.keys()} | {'name': o.name})
(OUT / 'fastener_spec_v07.json').write_text(json.dumps(spec, indent=1, ensure_ascii=False), encoding='utf8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'switch_robot_86_v07_fasteners.blend'))
print('saved', len(scene_parts), 'meshes')
