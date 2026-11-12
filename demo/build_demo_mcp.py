"""在现有模型副本上完成装配、翘板两稳态和按压动作的演示动画。"""
import bpy
import math
import json
from mathutils import Vector

source=bpy.context.scene
scene=bpy.data.scenes.new('86 Robot - assembled and operating V0.2')
bpy.context.window.scene=scene
scene.unit_settings.system='METRIC'
scene.unit_settings.length_unit='MILLIMETERS'
scene.render.fps=12
scene.frame_start=1
scene.frame_end=216
scene['purpose']='Assembly and motion illustration, not a physical validation or functioning electronics demo'
scene['rocker_states_deg']='-3.5 / +3.5; retains position after arm retracts'
root=bpy.data.objects.new('WALL_MOUNT_ORIENTATION',None)
scene.collection.objects.link(root)
root.rotation_euler[0]=math.pi/2
copies={}
for original in list(source.objects):
    if original.type=='MESH' and original.name!='Studio surface':
        o=original.copy();o.data=original.data.copy();o.animation_data_clear()
        o.name='DEMO_'+original.name
        scene.collection.objects.link(o)
        o.parent=root
        copies[original.name]=o

def mat(name,color):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    n=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    n.inputs['Base Color'].default_value=(*color,1);n.inputs['Roughness'].default_value=.4
    return m

ivory=mat('DEMO porcelain shell',(.76,.80,.81))
gray=mat('DEMO wall',(.28,.34,.39))
black=mat('DEMO cable',(.025,.035,.043))
silver=mat('DEMO screws',(.42,.48,.52))
amber=mat('DEMO moving arm',(.96,.36,.055))
white=mat('DEMO rocker',(.93,.94,.91))
blue=mat('DEMO servo',(.045,.18,.34))
def applymat(o,m):
    o.data.materials.clear();o.data.materials.append(m)

def cube(name,dims,pos,material,parent=root,bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=Vector(pos)*.001)
    o=bpy.context.object;o.name=name;o.dimensions=Vector(dims)*.001
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.parent=parent
    applymat(o,material)
    if bevel:
        mod=o.modifiers.new('Soft edges','BEVEL');mod.width=bevel*.001;mod.segments=3
    return o

def cyl(name,r,depth,pos,material,axis='Z'):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=r*.001,depth=depth*.001,location=Vector(pos)*.001)
    o=bpy.context.object;o.name=name;o.parent=root
    if axis=='X':o.rotation_euler[1]=math.pi/2
    applymat(o,material)
    return o

def cable(name,points,radius=1.1,material=black):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.resolution_u=12
    c.bevel_depth=radius*.001;c.bevel_resolution=3
    s=c.splines.new('BEZIER');s.bezier_points.add(len(points)-1)
    for p,co in zip(s.bezier_points,points):
        p.co=Vector(co)*.001;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
    o=bpy.data.objects.new(name,c);scene.collection.objects.link(o);o.parent=root;c.materials.append(material)
    return o

for name in ['PRINT_01_86_adjustable_frame','PRINT_02_strap_servo_cradle','PRINT_04_gateway_case','PRINT_05_gateway_lid']:
    applymat(copies[name],ivory)
rocker=copies['REFERENCE_rocker_assumed'];applymat(rocker,white)
servo=copies['REFERENCE_servo_approximate'];applymat(servo,blue)
arm=copies['PRINT_03_double_press_arm'];applymat(arm,amber)
for v in arm.data.vertices:
    global_z=(v.co.z+arm.location.z)*1000
    if global_z<22:
        global_z=22-(22-global_z)*(20/23)
        v.co.z=global_z*.001-arm.location.z
arm['revision']='V0.2 press tips shortened by 1.5 mm for neutral clearance above tilted rocker'
arm['neutral_lowest_tip_mm']=12.0
arm['illustrative_press_angle_deg']=11.4

lid=copies['PRINT_05_gateway_lid']
lid.location.y-=.066
lid.location.z+=.022
lid['assembly']='Closed on case rim; animation opens it only to explain assembly'
horn=cyl('DEMO stock horn adapter',4.0,4,(26.2,0,25),silver,'X')
horn['status']='Stock horn dimensional illustration; fastener geometry not verified'
cyl('DEMO horn center screw',1.65,2,(21.5,0,25),silver,'X')

straps=[]
for x in (34,55):
    o=cable('DEMO servo retention strap '+str(x),[(x,-17,18),(x,-18,32),(x,-5,33.5),(x,15.5,32),(x,16.5,18),(x,-17,18)],.8)
    straps.append(o)
    cube('DEMO strap lock '+str(x),(3,4,3),(x,15.5,31),black)

fasteners=[]
for y in (-29,29):
    cyl('DEMO mounting screw',2.7,2,(42,y,12),silver)
for x in (84,144):
    for y in (-34,6):
        o=cyl('DEMO lid screw',2.5,1.8,(x,y,30),silver)
        fasteners.append(o)

lead=cable('DEMO servo control cable',[(58,-8,25),(72,-5,27),(74,25,23),(108,26,20),(123,10,16)],1.2)
power=cable('DEMO low voltage supply',[(101,-38,16),(103,-49,16),(112,-60,14),(135,-70,13)],1.3)

wall=cube('DEMO wall surface',(480,5,350),(45,5,0),gray,parent=None,bevel=2)
backplate=copies['REFERENCE_86_faceplate']
applymat(backplate,mat('DEMO switch plate',(.52,.59,.63)))
cube('DEMO adhesive strip top',(80,5,1),(0,41,4.8),black)
cube('DEMO adhesive strip bottom',(80,5,1),(0,-41,4.8),black)

def assemble(obj,offset,begin=1,end=48):
    target=obj.location.copy()
    obj.location=target+Vector(offset)*.001;obj.keyframe_insert(data_path='location',frame=begin)
    obj.location=target;obj.keyframe_insert(data_path='location',frame=end)
    return obj

assemble(copies['PRINT_01_86_adjustable_frame'],(0,0,10),1,22)
assemble(copies['PRINT_02_strap_servo_cradle'],(0,0,24),1,30)
assemble(servo,(0,0,48),1,36)
assemble(copies['REFERENCE_servo_output'],(0,0,48),1,36)
assemble(arm,(-22,0,28),1,42)
assemble(horn,(-22,0,28),1,42)
assemble(copies['REFERENCE_60x40_carrier_PCB'],(0,0,18),1,32)
assemble(copies['REFERENCE_external_MCU_envelope_not_verified'],(0,0,18),1,32)
assemble(copies['REFERENCE_terminal'],(0,0,18),1,32)
assemble(lid,(0,0,55),1,48)
for o in fasteners:assemble(o,(0,0,65),1,52)
for o in straps:
    o.scale=(.001,.001,.001);o.keyframe_insert(data_path='scale',frame=28)
    o.scale=(1,1,1);o.keyframe_insert(data_path='scale',frame=40)

for frame,deg in [(1,0),(72,0),(85,0),(99,-11.4),(104,-11.4),(116,0),(126,0),(147,11.4),(152,11.4),(164,0),(216,0)]:
    arm.rotation_euler[0]=math.radians(deg);arm.keyframe_insert(data_path='rotation_euler',frame=frame)
for frame,deg in [(1,3.5),(95,3.5),(99,-3.5),(143,-3.5),(147,3.5),(216,3.5)]:
    rocker.rotation_euler[0]=math.radians(deg);rocker.keyframe_insert(data_path='rotation_euler',frame=frame)

camd=bpy.data.cameras.new('DEMO camera');cam=bpy.data.objects.new('DEMO camera',camd);scene.collection.objects.link(cam)
camd.type='ORTHO';scene.camera=cam
def camera_key(frame,position,target,scale):
    cam.location=Vector(position)
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    camd.ortho_scale=scale
    cam.keyframe_insert(data_path='location',frame=frame)
    cam.keyframe_insert(data_path='rotation_euler',frame=frame)
    camd.keyframe_insert(data_path='ortho_scale',frame=frame)
for f in (1,68):camera_key(f,(-.115,-.33,.155),(.051,-.015,.003),.25)
for f in (84,166):camera_key(f,(-.095,-.27,.095),(.015,-.018,.0),.148)
for f in (192,216):camera_key(f,(-.115,-.33,.155),(.051,-.015,.003),.25)

scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=1120;scene.render.resolution_y=840;scene.render.resolution_percentage=100
sh=scene.display.shading
sh.light='STUDIO';sh.color_type='MATERIAL';sh.show_shadows=True;sh.show_cavity=True;sh.cavity_type='BOTH'
sh.curvature_ridge_factor=1.3;sh.curvature_valley_factor=1.0
sh.show_specular_highlight=True;sh.show_object_outline=False
sh.background_type='WORLD'
world=bpy.data.worlds.new('DEMO world');world.color=(.28,.34,.39);scene.world=world
scene.view_settings.view_transform='Standard';scene.view_settings.exposure=0
scene.render.image_settings.file_format='PNG'
scene.render.film_transparent=False
scene.render.filepath='D:/CodeWorkSpace/switch-robot-diy/demo/frames/frame_'
for f,name in [(1,'ASSEMBLY'),(54,'ASSEMBLED'),(85,'PRESS UPPER'),(99,'UPPER DOWN'),(116,'ARM RETRACTED'),(126,'PRESS LOWER'),(147,'LOWER DOWN'),(164,'ARM RETRACTED'),(192,'ASSEMBLED')]:
    scene.timeline_markers.new(name,frame=f)
scene.frame_set(60)
bpy.context.view_layer.update()
points={}
for name,co in [('frame',(-40,38,8)),('servo',(45,-5,32)),('arm',(24,24,19)),('gateway',(114,-14,29)),('cable',(74,25,23))]:
    p=cam.matrix_world.inverted()@(root.matrix_world@(Vector(co)*.001))
    points[name]=[float(.5+p.x/camd.ortho_scale),float(.5+p.y/(camd.ortho_scale*840/1120))]
scene['still_label_points']=json.dumps(points)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.shading.color_type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath='D:/CodeWorkSpace/switch-robot-diy/demo/switch_robot_assembled_v02.blend')
scene.render.filepath='D:/CodeWorkSpace/switch-robot-diy/demo/assembled_raw.png'
bpy.ops.render.render(write_still=True)
scene.render.filepath='D:/CodeWorkSpace/switch-robot-diy/demo/frames/frame_'
print(json.dumps({'scene':scene.name,'frames':216,'fps':12,'label_points':points,'rocker_angles':[-3.5,3.5],'arm_angles':[-11.4,11.4]}))
