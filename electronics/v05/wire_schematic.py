"""第二步（注意：sch_PrimitivePin.modify 只传 noConnected 会把引脚 Y 坐标取反、把引脚移出符号，必须同时传原 x/y）：清掉旧端口/导线，按 design_intent.json 给每个引脚接短线 + 网络端口，未用引脚标 NC，然后跑 ERC。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eda_client import execute

R = Path(__file__).resolve().parent
parts = json.loads((R / 'design_intent.json').read_text(encoding='utf-8'))['parts']

# 删除计划外的器件（例如超时重试留下的未命名器件）以及旧的端口和导线
wanted = [p['ref'] for p in parts]
print(execute('''
const wanted=WANTED;
const all=await eda.sch_PrimitiveComponent.getAll();
const extra=all.filter(c=>c.getState_ComponentType()==="part"&&!wanted.includes(c.getState_Designator()));
if(extra.length)await eda.sch_PrimitiveComponent.delete(extra);
const ports=all.filter(c=>c.getState_ComponentType()==="netport");
if(ports.length)await eda.sch_PrimitiveComponent.delete(ports);
const w=await eda.sch_PrimitiveWire.getAll(); if(w.length)await eda.sch_PrimitiveWire.delete(w);
await eda.sch_Document.save();
return {extra:extra.map(c=>c.getState_Designator()),ports:ports.length,wires:w.length};
'''.replace('WANTED', json.dumps(wanted))))

CODE = '''
const p=PART; const only=ONLY;
const c=(await eda.sch_PrimitiveComponent.getAll()).find(c=>c.getState_Designator()===p.ref);
const pins=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
const out=[];let k=0;
for(const pin of pins){
  const n=pin.getState_PinNumber();
  if(only && !only.includes(n)) continue;
  const net=p.nets[n];
  if(net===undefined) throw Error('unknown pin '+p.ref+'.'+n);
  if(net===null){await eda.sch_PrimitivePin.modify(pin.getState_PrimitiveId(),{noConnected:true,x:pin.getState_X(),y:pin.getState_Y()});out.push([n,'NC']);continue;}
  const a=pin.getState_Rotation()*Math.PI/180; const L=(p.ref==='USB1'&&(k++%2))?75:40;
  const x=pin.getState_X()+Math.round(L*Math.cos(a)); const y=pin.getState_Y()+Math.round(L*Math.sin(a));
  const w=await eda.sch_PrimitiveWire.create([pin.getState_X(),pin.getState_Y(),x,y],net);
  const port=await eda.sch_PrimitiveComponent.createNetPort('BI',net,x,y,pin.getState_Rotation()===180?0:180,false);
  if(!w||!port) throw Error('wire/port failed '+p.ref+'.'+n);
  out.push([n,net]);
}
await eda.sch_Document.save();
return {ref:p.ref,n:out.length};
'''

for p in parts:
    keys = list(p['nets'])
    step = 12
    for i in range(0, len(keys), step):
        only = keys[i:i + step] if len(keys) > step else None
        r = execute(CODE.replace('PART', json.dumps(p, ensure_ascii=False)).replace('ONLY', json.dumps(only)))
        print(json.dumps(r), flush=True)

erc = execute('return await eda.sch_Drc.check(true,false,true);')
(R / 'schematic_erc.json').write_text(json.dumps(erc, indent=1, ensure_ascii=False), encoding='utf-8')
print('ERC', json.dumps(erc, ensure_ascii=False)[:3000])



