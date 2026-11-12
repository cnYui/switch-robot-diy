"""从已有 Blender 工程提取真实网格，保留原件并输出可比较的按压臂版本。"""
import bpy
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path('D:/CodeWorkSpace/switch-robot-diy')
OUT = ROOT / 'simulation/assets'
OUT.mkdir(parents=True, exist_ok=True)
manifest = {}


def export_obj(obj, name, origin=(0, 0, 0), adjust=None):
    mesh = obj.to_mesh()
    mesh.calc_loop_triangles()
    vertices = []
    for vertex in mesh.vertices:
        co = obj.matrix_world @ vertex.co
        if adjust:
            co = adjust(co.copy())
        vertices.append(co - Vector(origin))
    faces = [tuple(t.vertices) for t in mesh.loop_triangles]
    with (OUT / (name + '.obj')).open('w') as file:
        file.write('# CAD geometry, metres, no animation\n')
        for v in vertices:
            file.write('v %.10g %.10g %.10g\n' % tuple(v))
        for f in faces:
            file.write('f %d %d %d\n' % tuple(i + 1 for i in f))
    obj.to_mesh_clear()
    manifest[name] = {
        'source_object': obj.name, 'origin_m': list(origin),
        'vertices': len(vertices), 'triangles': len(faces),
        'bounds_mm': [[min(v[i] for v in vertices) * 1000 for i in range(3)],
                      [max(v[i] for v in vertices) * 1000 for i in range(3)]],
    }


bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'mechanical/switch_robot_86_v01.blend'))
names = {
    'frame': 'PRINT_01_86_adjustable_frame',
    'cradle': 'PRINT_02_strap_servo_cradle',
    'faceplate': 'REFERENCE_86_faceplate',
    'rocker_original': 'REFERENCE_rocker_assumed',
    'servo_body': 'REFERENCE_servo_approximate',
    'servo_shaft': 'REFERENCE_servo_output',
}
for name, original in names.items():
    export_obj(bpy.data.objects[original], name,
               origin=(0, 0, .007) if name == 'rocker_original' else (0, 0, 0))

original = bpy.data.objects['PRINT_03_double_press_arm']
export_obj(original, 'arm_v01', origin=(.024, 0, .025))


def shortened(co):
    if co.z < .022:
        co.z = .022 - (.022 - co.z) * 20 / 23
    return co


export_obj(original, 'arm_v02', origin=(.024, 0, .025), adjust=shortened)

# 另建候选件，缩窄软垫座来保留与支架前缘的横向间隙，不覆写旧 STL。
def cube(size, position):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def boolean(target, tool, operation):
    bpy.context.view_layer.objects.active = target
    modifier = target.modifiers.new('Candidate machining', 'BOOLEAN')
    modifier.operation = operation
    modifier.solver = 'EXACT'
    modifier.object = tool
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(tool, do_unlink=True)


arm = cube((.004, .056, .006), (.024, 0, .025))
arm.name = 'V05_CANDIDATE_double_press_arm'
bevel = arm.modifiers.new('Original bar bevel', 'BEVEL')
bevel.width = .0007
bevel.segments = 3
bpy.context.view_layer.objects.active = arm
bpy.ops.object.modifier_apply(modifier=bevel.name)
for side in (-1, 1):
    boolean(arm, cube((.004, .007, .015), (.024, side * .024, .0195)), 'UNION')
    boolean(arm, cube((.005, .008, .002), (.024, side * .024, .0115)), 'UNION')
for y, radius in [(0, .00125), (-.009, .0011), (.009, .0011)]:
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=.010,
                                      location=(.024, y, .025), rotation=(0, 1.57079632679, 0))
    boolean(arm, bpy.context.object, 'DIFFERENCE')
export_obj(arm, 'arm_v05', origin=(.024, 0, .025), adjust=shortened)

# V0.6：指杆下端抬高到 z=17.5 mm，下面粘 4×7 mm、自由高度 5.5 mm 的弹性压垫（泡棉/TPU，外购件，不在本 STL 内）。
arm6 = cube((.004, .056, .006), (.024, 0, .025))
arm6.name = 'V06_double_press_arm'
bevel6 = arm6.modifiers.new('Original bar bevel', 'BEVEL')
bevel6.width = .0007
bevel6.segments = 3
bpy.context.view_layer.objects.active = arm6
bpy.ops.object.modifier_apply(modifier=bevel6.name)
for side in (-1, 1):
    boolean(arm6, cube((.004, .007, .027 - .0175), (.024, side * .024, (.027 + .0175) / 2)), 'UNION')
for y, radius in [(0, .00125), (-.009, .0011), (.009, .0011)]:
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=.010,
                                      location=(.024, y, .025), rotation=(0, 1.57079632679, 0))
    boolean(arm6, bpy.context.object, 'DIFFERENCE')
export_obj(arm6, 'arm_v06', origin=(.024, 0, .025))

bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'fit-check/enclosure_fit_v03.blend'))
export_obj(bpy.data.objects['V03_PRINT_gateway_case_76x56x30'], 'case_v03')
export_obj(bpy.data.objects['V03_PRINT_gateway_lid_76x56'], 'lid_v03_closed',
           adjust=lambda co: co + Vector((0, -.082, .010)))
(OUT / 'cad_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
print('CAD exported:', json.dumps(manifest))
