"""将原理图导入的正式封装布局在 60x40 mm 板上，建立机械孔和板框。"""
import json,sys
from pathlib import Path
sys.path.insert(0,r'D:\CodeWorkSpace\switch-robot-diy')
from eda_client import execute
R=Path(__file__).resolve().parent
layout={'J1':[8,9,90],'F1':[16,9,0],'C1':[27,9,0],'C2':[27,18,0],'J3':[7,24,90],'J2':[24,35.5,0],'U1':[42,13,270],'U2':[42,27,270],'J4':[53,13,90],'J5':[53,27,90],'R1':[29,24,90],'R2':[33,31,0],'R3':[17,23,0],'R4':[17,27.5,0],'R5':[15,18,0],'R6':[15,31,0]}
(R/'pcb_layout_mm.json').write_text(json.dumps(layout,indent=2),encoding='utf8')
r=execute('const layout='+json.dumps(layout)+';const all=await eda.pcb_PrimitiveComponent.getAll();for(const p of all){const a=layout[p.getState_Designator()];if(!a)throw Error("Unexpected component");await eda.pcb_PrimitiveComponent.modify(p.getState_PrimitiveId(),{x:a[0]/.0254,y:a[1]/.0254,rotation:a[2]});}return true;')
print('layout',r)
r=execute('const p=eda.pcb_MathPolygon.createPolygon([0,0,"L",60/.0254,0,60/.0254,40/.0254,0,40/.0254,0,0]);const outline=await eda.pcb_PrimitivePolyline.create("",11,p,.2/.0254,true);const h=[];for(const [x,y]of [[4,4],[56,4],[56,36],[4,36]]){const pad=await eda.pcb_PrimitivePad.create(12,"",x/.0254,y/.0254,0,["ELLIPSE",3.2/.0254,3.2/.0254],"",["ROUND",3.2/.0254],0,0,0,false,0,[],null,null,true);h.push(pad);}await eda.pcb_Document.save();return {outline,holes:h};')
(R/'pcb_mechanical_primitives.json').write_text(json.dumps(r,indent=2),encoding='utf8');print('outline/holes',bool(r['outline']),len(r['holes']))
