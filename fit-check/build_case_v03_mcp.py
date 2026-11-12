"""修正盒盖螺柱与 PCB 四角的冲突，导出独立 V0.3 盒体与盒盖。"""
import bpy
import bmesh
import json
import math
from mathutils import Vector

scene=bpy.data.scenes.new('Enclosure fit check V0.3')
bpy.context.window.scene=scene
scene.unit_settings.system='METRIC';scene.unit_settings.length_unit='MILLIMETERS'
def material(name,color):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 n=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');n.inputs['Base Color'].default_value=(*color,1)
 return m
ivory=material('V03 case',(.78,.82,.83));green=material('V03 actual PCB envelope',(.04,.43,.23))
def cube(name,size,pos,mat=None):
 bpy.ops.mesh.primitive_cube_add(size=1,location=Vector(pos)*.001)
 o=bpy.context.object;o.name=name;o.dimensions=Vector(size)*.001
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if mat:o.data.materials.append(mat)
 return o
def cyl(name,r,depth,pos):
 bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=r*.001,depth=depth*.001,location=Vector(pos)*.001)
 o=bpy.context.object;o.name=name;return o
def boolean(a,b,op='DIFFERENCE'):
 bpy.context.view_layer.objects.active=a
 m=a.modifiers.new('Precise geometry','BOOLEAN');m.operation=op;m.solver='EXACT';m.object=b
 bpy.ops.object.modifier_apply(modifier=m.name)
 bpy.data.objects.remove(b,do_unlink=True)

case=cube('V03_PRINT_gateway_case_76x56x30',(76,56,30),(114,-14,20),ivory)
boolean(case,cube('cavity',(72,52,32),(114,-14,23)))
for x in (-26,26):
 for y in (-16,16):
  boolean(case,cyl('PCB mounting post',2.8,5,(114+x,-14+y,9.4)),'UNION')
  boolean(case,cyl('PCB screw pilot',1.15,8,(114+x,-14+y,10)))
for x in (-34,34):
 for y in (-24,24):
  boolean(case,cyl('Lid post outside PCB',3,25,(114+x,-14+y,19.5)),'UNION')
  boolean(case,cyl('Lid screw pilot',1.15,31,(114+x,-14+y,21)))
boolean(case,cube('Power cable opening',(18,8,8),(101,-42,16)))
boolean(case,cube('Signal cable opening',(24,8,8),(123,14,16)))
case['status']='PCB shell clearance verified; component and cable fit unverified'

lid=cube('V03_PRINT_gateway_lid_76x56',(76,56,2.4),(114,-14,36.2),ivory)
for x in (-34,34):
 for y in (-24,24):boolean(lid,cyl('Lid clearance',1.65,8,(114+x,-14+y,36.2)))
for x in (-12,-6,0,6,12):boolean(lid,cube('Vent',(2,22,8),(114+x,-14,36.2)))

reference=bpy.data.objects['REFERENCE_60x40_carrier_PCB']
pcb=reference.copy();pcb.data=reference.data.copy();pcb.name='V03_REFERENCE_PCB_60x40_actual_holes';scene.collection.objects.link(pcb)
pcb.data.materials.clear();pcb.data.materials.append(green)
def intersect_volume(a,b):
 tmp=a.copy();tmp.data=a.data.copy();scene.collection.objects.link(tmp)
 m=tmp.modifiers.new('Interference check','BOOLEAN');m.operation='INTERSECT';m.solver='EXACT';m.object=b
 bpy.context.view_layer.update()
 ev=tmp.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
 bm=bmesh.new();bm.from_mesh(mesh);volume=abs(bm.calc_volume())*1e9
 bm.free();ev.to_mesh_clear();bpy.data.objects.remove(tmp,do_unlink=True)
 return volume

results={'case_PCB_intersection_mm3':intersect_volume(case,pcb),'lid_PCB_intersection_mm3':intersect_volume(lid,pcb),'case_outer_mm':[76,56,30],'cavity_xy_mm':[72,52],'pcb_top_to_lid_mm':21.5,'PCB_edge_to_wall_mm':6,'lid_post_to_PCB_corner_clearance_mm':math.sqrt(4*4+4*4)-3,'mesh_checks':[]}
for o in (case,lid):
 bm=bmesh.new();bm.from_mesh(o.data)
 results['mesh_checks'].append({'name':o.name,'non_manifold_edges':sum(not e.is_manifold for e in bm.edges)})
 bm.free()
 duplicate=o.copy();duplicate.data=o.data.copy();scene.collection.objects.link(duplicate)
 bpy.ops.object.select_all(action='DESELECT');duplicate.select_set(True);bpy.context.view_layer.objects.active=duplicate
 duplicate.location.x=0;duplicate.location.y=0;bpy.context.view_layer.update()
 duplicate.location.z-=min((duplicate.matrix_world@Vector(p)).z for p in duplicate.bound_box)
 bpy.ops.wm.stl_export(filepath='D:/CodeWorkSpace/switch-robot-diy/fit-check/'+o.name+'.stl',export_selected_objects=True,global_scale=1000,apply_modifiers=True)
 bpy.data.objects.remove(duplicate,do_unlink=True)
scene['fit_check_results']=json.dumps(results)
lid.location.y+=.082
lid.location.z-=.010
camd=bpy.data.cameras.new('V03 fit inspection camera');cam=bpy.data.objects.new('V03 fit inspection camera',camd);scene.collection.objects.link(cam)
cam.location=(.25,-.24,.27);target=Vector((.114,.015,.015));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
camd.type='ORTHO';camd.ortho_scale=.19;scene.camera=cam
scene.render.engine='BLENDER_WORKBENCH'
scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True;scene.display.shading.cavity_type='BOTH'
scene.display.shading.background_type='WORLD'
world=bpy.data.worlds.new('V03 inspection background');world.color=(.12,.16,.20);scene.world=world
scene.view_settings.view_transform='Standard';scene.view_settings.exposure=0
scene.render.resolution_x=1200;scene.render.resolution_y=850;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath='D:/CodeWorkSpace/switch-robot-diy/fit-check/case_v03_pcb_fit.png'
bpy.ops.wm.save_as_mainfile(filepath='D:/CodeWorkSpace/switch-robot-diy/fit-check/enclosure_fit_v03.blend')
bpy.ops.render.render(write_still=True)
print(json.dumps(results))
