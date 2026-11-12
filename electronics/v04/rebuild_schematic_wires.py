"""根据当前正式器件引脚重建网络端口及短线，并保留 ERC 结果。"""
import json,sys
from pathlib import Path
sys.path.insert(0,r'D:\CodeWorkSpace\switch-robot-diy')
from eda_client import execute
R=Path(__file__).resolve().parent
parts=json.loads((R/'design_intent.json').read_text())['parts']
execute('const p=(await eda.sch_PrimitiveComponent.getAll()).filter(p=>p.getState_ComponentType()==="netport"); await eda.sch_PrimitiveComponent.delete(p); const w=await eda.sch_PrimitiveWire.getAll();await eda.sch_PrimitiveWire.delete(w);await eda.sch_Document.save();return {ports:p.length,wires:w.length};')
for p in parts:
 code='''const p=PART;const c=(await eda.sch_PrimitiveComponent.getAll()).find(c=>c.getState_Designator()===p.ref);const pins=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());const out=[];for(const pin of pins){const net=p.nets[pin.getState_PinNumber()];if(net===null){await eda.sch_PrimitivePin.modify(pin.getState_PrimitiveId(),{noConnected:true});continue;}if(net===undefined)throw Error('Unknown pin');const a=pin.getState_Rotation()*Math.PI/180;const x=pin.getState_X()+Math.round(40*Math.cos(a));const y=pin.getState_Y()+Math.round(40*Math.sin(a));const w=await eda.sch_PrimitiveWire.create([pin.getState_X(),pin.getState_Y(),x,y],net);const port=await eda.sch_PrimitiveComponent.createNetPort('BI',net,x,y,pin.getState_Rotation()===180?0:180,false);out.push({pin:pin.getState_PinNumber(),net,wire:!!w,port:!!port});}await eda.sch_Document.save();return {ref:p.ref,out};'''.replace('PART',json.dumps(p))
 print(json.dumps(execute(code)),flush=True)
r=execute('return await eda.sch_Drc.check(true,false,true);')
(R/'schematic_erc_final.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print('ERC',json.dumps(r))
