"""在 Blender 中创建 86 开关机器人尺寸原型、独立可打印零件和装配预览。"""
import bpy
import bmesh
import json
import math
from mathutils import Vector, Quaternion

P = {'revision': '0.1-concept', 'units': 'mm', 'switch_face': 86, 'frame_outer': 96, 'frame_opening': 72, 'frame_thickness': 3, 'rocker_assumed_width': 60, 'rocker_assumed_height': 64, 'servo_body_reference': [23, 12.2, 29], 'servo_axis_height': 25, 'arm_half_span': 24, 'arm_foot_drop': 12, 'initial_angle_limit_deg': 8, 'pcb_width': 60, 'pcb_height': 40, 'pcb_mount_holes': [[4, 4], [56, 4], [56, 36], [4, 36]], 'case_outer': [68, 48, 22], 'wall_thickness': 2, 'fit_clearance': 0.3, 'assumptions': 'Servo cradle uses strap retention; measure actual servo, rocker and adhesive gap before printing final parts. Controller connects by wires; no unverified ESP32 pinout is assumed.'}
OUT = 'D:/CodeWorkSpace/switch-robot-diy/mechanical/'
scene = bpy.data.scenes.new('Switch Robot 86 - V0.1')
bpy.context.window.scene = scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'MILLIMETERS'
scene.unit_settings.scale_length = 1

def material(name, color, metallic=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color,1)
    m.use_nodes = True
    node = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    node.inputs['Base Color'].default_value = (*color,1)
    node.inputs['Roughness'].default_value = .34
    node.inputs['Metallic'].default_value = metallic
    return m

ivory = material('Printed PETG - ivory', (.78,.81,.78))
orange = material('Printed arm - amber', (.94,.31,.07))
blue = material('Servo reference only', (.055,.18,.36))
green = material('PCB envelope only', (.025,.24,.15))
gray = material('Switch reference only', (.43,.47,.49))
dark = material('Dark gray', (.055,.07,.085))
gold = material('Brass reference', (.6,.37,.10), .65)

def cube(name, dims, pos, mat=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=Vector(pos)*.001)
    o = bpy.context.object
    o.name = name
    o.dimensions = Vector(dims)*.001
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if mat: o.data.materials.append(mat)
    return o

def cyl(name, radius, depth, pos, axis='Z', mat=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius*.001,depth=depth*.001,location=Vector(pos)*.001)
    o=bpy.context.object; o.name=name
    if axis=='X': o.rotation_euler[1]=math.pi/2
    elif axis=='Y': o.rotation_euler[0]=math.pi/2
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    if mat: o.data.materials.append(mat)
    return o

def boolean(target, cutter, operation='DIFFERENCE'):
    bpy.context.view_layer.objects.active = target
    mod=target.modifiers.new('Exact machining','BOOLEAN'); mod.operation=operation; mod.solver='EXACT'; mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    return target

def bevel(obj, radius=.6):
    bpy.context.view_layer.objects.active=obj
    m=obj.modifiers.new('Printable edge relief','BEVEL');m.width=radius*.001;m.segments=3
    bpy.ops.object.modifier_apply(modifier=m.name)
    return obj

def slot(obj,center,length,width,depth,along='Y'):
    x,y,z=center
    if along=='Y':
        boolean(obj,cube('slot', (width,length-width,depth),center))
        for sign in (-1,1): boolean(obj,cyl('slot end',width/2,depth,(x,y+sign*(length-width)/2,z)))
    else:
        boolean(obj,cube('slot',(length-width,width,depth),center))
        for sign in (-1,1): boolean(obj,cyl('slot end',width/2,depth,(x+sign*(length-width)/2,y,z)))

parts=[]
frame=bevel(cube('PRINT_01_86_adjustable_frame',(P['frame_outer'],P['frame_outer'],3),(0,0,6.5),ivory))
boolean(frame,cube('clear rocker',(72,72,12),(0,0,6)))
for y in (-29,29): slot(frame,(42,y,6.5),18,3.4,12)
parts.append(frame)

cradle=bevel(cube('PRINT_02_strap_servo_cradle',(38,42,3),(46,0,17),ivory))
for sign in (-1,1):
    boolean(cradle,cube('side wall',(38,3,15),(46,sign*19.5,23)), 'UNION')
    boolean(cradle,cube('mount foot',(10,16,3),(42,sign*29,9.5)), 'UNION')
    boolean(cradle,cube('support',(10,8,8),(42,sign*18,13)), 'UNION')
    slot(cradle,(42,sign*29,9.5),10,3.4,15)
for x in (33,59):
    for sign in (-1,1): boolean(cradle,cube('strap feed',(3.2,6,6),(x,sign*14,17)))
parts.append(cradle)

arm=bevel(cube('PRINT_03_double_press_arm',(4,56,6),(24,0,25),orange),.7)
for sign in (-1,1):
    boolean(arm,cube('press finger',(4,7,15),(24,sign*24,19.5)), 'UNION')
    boolean(arm,cube('soft pad seat',(7,8,2),(24,sign*24,11.5)), 'UNION')
boolean(arm,cyl('stock horn center screw',1.25,10,(24,0,25),'X'))
for y in (-9,9): boolean(arm,cyl('stock horn fastening',1.1,10,(24,y,25),'X'))
parts.append(arm)

case=cube('PRINT_04_gateway_case',(68,48,22),(114,-14,16),ivory)
boolean(case,cube('hollow',(64,44,24),(114,-14,19)))
for x in (-26,26):
    for y in (-16,16):
        boolean(case,cyl('pcb standoff',2.8,5,(114+x,-14+y,9.4)), 'UNION')
        boolean(case,cyl('pilot hole',1.15,8,(114+x,-14+y,10)))
for x in (-30,30):
    for y in (-20,20):
        boolean(case,cyl('lid post',3,17,(114+x,-14+y,15.5)), 'UNION')
        boolean(case,cyl('lid pilot',1.15,22,(114+x,-14+y,17)))
boolean(case,cube('power and signal access',(18,8,8),(101,-38,16)))
boolean(case,cube('servo and remote wiring',(24,8,8),(123,10,16)))
parts.append(case)
lid=bevel(cube('PRINT_05_gateway_lid',(68,48,2.4),(114,52,6.2),ivory),.6)
for x in (-30,30):
    for y in (-20,20): boolean(lid,cyl('lid clearance',1.65,7,(114+x,52+y,6.2)))
for x in (-12,-6,0,6,12): slot(lid,(114+x,52,6.2),22,2,8)
parts.append(lid)

cube('REFERENCE_86_faceplate',(86,86,5),(0,0,2.5),gray)
bevel(cube('REFERENCE_rocker_assumed',(60,64,4),(0,0,7),ivory),1.2)
cube('REFERENCE_servo_approximate',(26,23,12.2),(44,-5.5,25),blue)
cyl('REFERENCE_servo_output',2.8,6,(29,0,25),'X',gold)
pcb=cube('REFERENCE_60x40_carrier_PCB',(60,40,1.6),(114,-14,12.7),green)
for x in (-26,26):
    for y in (-16,16): boolean(pcb,cyl('mount hole',1.6,5,(114+x,-14+y,12.7)))
cube('REFERENCE_external_MCU_envelope_not_verified',(26,20,5),(109,-13,16),blue)
cube('REFERENCE_terminal',(8,8,9),(93,-22,18),green)

def label(text,pos,size=3.0):
    curve=bpy.data.curves.new('Annotation','FONT');curve.body=text;curve.size=size*.001
    o=bpy.data.objects.new(text,curve);scene.collection.objects.link(o);o.location=Vector(pos)*.001;curve.materials.append(dark)
    return o
label('86 / DOUBLE PRESS',( -45,-57,5),4)
label('STRAP CRADLE / ADJUSTABLE',(-45,-63,5),2.7)
label('WIFI BRIDGE / 60 x 40 PCB',(80,-47,5),3)
label('V0.1  -  FIT CHECK REQUIRED',(80,81,5),2.6)
label('VENTED LID',(81,22,5),3)

for obj in parts:
    obj['status']='V0.1 dimensional prototype; measure and dry-fit before use'
    obj['print_material']='PETG suggested; no supports only after inspecting orientation'
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    duplicate=obj.copy();duplicate.data=obj.data.copy();scene.collection.objects.link(duplicate)
    bpy.ops.object.select_all(action='DESELECT');duplicate.select_set(True);bpy.context.view_layer.objects.active=duplicate
    duplicate.location.x=0;duplicate.location.y=0
    bpy.context.view_layer.update()
    minz=min((duplicate.matrix_world@Vector(v)).z for v in duplicate.bound_box)
    duplicate.location.z-=minz
    bpy.ops.wm.stl_export(filepath=OUT+obj.name+'.stl',export_selected_objects=True,global_scale=1000,apply_modifiers=True)
    bpy.data.objects.remove(duplicate,do_unlink=True)

report=[]
for obj in parts:
    bm=bmesh.new();bm.from_mesh(obj.data)
    bad=sum(not e.is_manifold for e in bm.edges)
    volume=abs(bm.calc_volume())*1e9
    report.append({'part':obj.name,'non_manifold_edges':bad,'volume_mm3':round(volume,2),'dimensions_mm':[round(d*1000,2) for d in obj.dimensions]})
    bm.free()
scene['mesh_checks'] = json.dumps(report)

world=bpy.data.worlds.new('Studio world');scene.world=world;world.use_nodes=True
world.node_tree.nodes.get('Background').inputs[0].default_value=(.75,.80,.85,1)
world.node_tree.nodes.get('Background').inputs[1].default_value=.5
floor=cube('Studio surface',(600,500,2),(40,0,-3),material('Studio paper',(.80,.83,.84)))
for name,pos,energy,size in [('Key',(-100,-100,250),28,.25),('Fill',(220,-30,180),18,.2),('Rim',(80,180,250),24,.2)]:
    d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size
    o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=Vector(pos)*.001
    o.rotation_euler=(Vector((.05,0,0))-o.location).to_track_quat('-Z','Y').to_euler()
camd=bpy.data.cameras.new('Engineering overview');cam=bpy.data.objects.new('Engineering overview',camd);scene.collection.objects.link(cam)
cam.location=(.26,-.32,.36);target=Vector((.052,.005,.012));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();camd.type='ORTHO';camd.ortho_scale=.27;scene.camera=cam
scene.view_settings.exposure=-3.2
scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1600;scene.render.resolution_y=1150;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=OUT+'assembly_preview.png'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=.29
            area.spaces.active.region_3d.view_location=target
            area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
            area.spaces.active.shading.color_type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=OUT+'switch_robot_86_v01.blend')
bpy.ops.render.render(write_still=True)
print(json.dumps({'saved':str(OUT),'mesh_checks':report}))
