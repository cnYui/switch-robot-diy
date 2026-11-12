"""将正式 PCB 的三维导出按材质拆分，并核查未剪引脚和壳体的静态冲突。"""
import json
from pathlib import Path
import numpy as np
import trimesh

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'electronics/v04/3d/carrier_v04_populated.obj'
material_file=SOURCE.with_suffix('.mtl')
materials={}
current=None
for line in material_file.read_text().splitlines():
    a=line.split()
    if not a:continue
    if a[0]=='newmtl':current=a[1];materials[current]=[.5,.5,.5,1]
    elif a[0]=='Kd':materials[current][:3]=list(map(float,a[1:4]))
    elif a[0]=='d':materials[current][3]=float(a[1])
vertices=[];groups={};current=None
for line in SOURCE.read_text().splitlines():
    a=line.split()
    if not a:continue
    if a[0]=='v':vertices.append(list(map(float,a[1:4])))
    elif a[0]=='usemtl':current=a[1];groups.setdefault(current,[])
    elif a[0]=='f':groups[current].append([int(x.split('/')[0])-1 for x in a[1:]])
vertices=np.array(vertices)
case=trimesh.load_mesh(ROOT/'assets/case_v03.obj')
lid=trimesh.load_mesh(ROOT/'assets/lid_v03_closed.obj')
board_vertices=[]
for faces in groups.values():
    part=vertices[np.unique(np.array(faces).reshape(-1))]
    if np.ptp(part[:,0])>55 and np.ptp(part[:,1])>38:
        board_vertices.append(part)
assert board_vertices, 'Native board substrate geometry not found'
board_bottom_local_mm=min(p[:,2].min() for p in board_vertices)
# 以实际导出的板底面贴合螺柱，而不是假定元件原点就是基板表面。
offset=np.array([84,-34,11.9-board_bottom_local_mm+.005])
raw=(vertices+offset)/1000
trimmed=vertices.copy()
trimmed[:,2]=np.maximum(trimmed[:,2],board_bottom_local_mm-1.5)
trimmed=(trimmed+offset)/1000
np.random.seed(7)
raw_hits=case.contains(raw)
trimmed_hits=case.contains(trimmed)
lid_hits=lid.contains(trimmed)
out=[]
for index,(material,faces) in enumerate(groups.items()):
    faces=np.array(faces,dtype=np.int64)
    used,inverse=np.unique(faces.reshape(-1),return_inverse=True)
    local_faces=inverse.reshape(faces.shape)
    mesh=trimesh.Trimesh(trimmed[used],local_faces,process=False)
    filename=f'pcb_material_{index:02}.obj'
    mesh.export(ROOT/'assets'/filename)
    color=np.clip(materials[material],0,1).tolist()
    color[3]=1
    out.append({'file':filename,'rgba':color,'source_material':material})
(ROOT/'assets/pcb_materials.json').write_text(json.dumps(out,indent=2),encoding='utf8')
report={
 'method':'Actual PCB export vertex-in-watertight-case test; not a full triangle intersection or tolerance proof',
 'raw_vertices_inside_case':int(raw_hits.sum()),
 'raw_penetrating_vertex_examples_mm':(raw[raw_hits][:8]*1000).tolist(),
 'trimmed_vertices_inside_case':int(trimmed_hits.sum()),
 'trimmed_vertices_inside_lid':int(lid_hits.sum()),
 'lead_trim_assumption_mm_below_board':1.5,
 'native_pcb_origin_global_mm':float(offset[2]),
 'native_pcb_underside_local_mm':float(board_bottom_local_mm),
 'standoff_support_plane_mm':11.9,'alignment_epsilon_mm':.005,
 'case_inner_floor_mm':7,'lid_inside_mm':35,
 'raw_lowest_z_mm':float(raw[:,2].min()*1000),
 'trimmed_lowest_z_mm':float(trimmed[:,2].min()*1000),
 'model_highest_z_mm':float(trimmed[:,2].max()*1000),
 'lid_clearance_from_library_model_mm':float(35-trimmed[:,2].max()*1000),
 'library_model_approximations':['C1 generic H16 vs part H12.5','F1 library H8.5 vs max part H14.2'],
 'unverified':['wire/plug bend space','actual MCU board','board and print tolerances'],
}
(ROOT/'results/pcb_case_check.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report),flush=True)
