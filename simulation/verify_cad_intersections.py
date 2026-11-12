"""用 Blender 精确布尔交集独立核验碰撞简化模型发现的几何冲突。"""
import bpy
import bmesh
import json
import math
from pathlib import Path
from mathutils import Vector

ROOT = Path('D:/CodeWorkSpace/switch-robot-diy/simulation')
bpy.ops.wm.read_factory_settings(use_empty=True)


def load(name, position=(0,0,0)):
    vertices, faces = [], []
    for line in (ROOT / 'assets' / (name+'.obj')).read_text().splitlines():
        if line.startswith('v '): vertices.append([float(v) for v in line.split()[1:4]])
        elif line.startswith('f '): faces.append([int(v.split('/')[0])-1 for v in line.split()[1:]])
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = position
    return obj


def volume(a, b):
    test = a.copy()
    test.data = a.data.copy()
    bpy.context.scene.collection.objects.link(test)
    modifier = test.modifiers.new('Exact independent intersection', 'BOOLEAN')
    modifier.operation = 'INTERSECT'
    modifier.solver = 'EXACT'
    modifier.object = b
    bpy.context.view_layer.update()
    evaluated = test.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    result = abs(bm.calc_volume()) * 1e9
    bm.free()
    evaluated.to_mesh_clear()
    bpy.data.objects.remove(test, do_unlink=True)
    return result


cradle = load('cradle')
rocker = load('rocker_original', (0,0,.007))
rocker.rotation_euler.x = math.radians(3.5)
report = {}
for name in ['arm_v01', 'arm_v02', 'arm_v05', 'arm_v06']:
    arm = load(name, (.024,0,.025))
    neutral = volume(arm, rocker)
    scans = []
    # V0.6 的名义按压角为 17°，所以扫描范围扩到 ±20°，检查按压臂整个摆动范围内都不碰支架。
    for angle in [-20,-18,-17,-16,-14,-12,-10,-7,-6,-5.7,-5.5,-5.2,-5,-4.9,-4.7,-4.5,-4,0,4,4.5,4.7,4.9,5,5.2,5.5,5.7,6,7,10,12,14,16,17,18,20]:
        arm.rotation_euler.x = math.radians(angle)
        scans.append({'angle_deg': angle, 'cradle_intersection_mm3': volume(arm,cradle)})
    report[name] = {'neutral_rocker_overlap_mm3': neutral, 'sweep': scans,
                    'maximum_cradle_overlap_mm3': max(x['cradle_intersection_mm3'] for x in scans)}
    bpy.data.objects.remove(arm, do_unlink=True)
(ROOT/'results/exact_cad_intersections.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report))
