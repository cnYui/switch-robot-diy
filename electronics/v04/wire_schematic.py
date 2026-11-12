"""按设计意图连接正式原理图，保留每次成功批次，避免重试时重复布线。"""
from pathlib import Path
import json
import sys
sys.path.insert(0,'D:/CodeWorkSpace/switch-robot-diy')
from eda_client import execute
R=Path(__file__).resolve().parent
parts=json.loads((R/'design_intent.json').read_text())['parts']
bindings={x['ref']:x for x in json.loads((R/'schematic_binding.json').read_text(encoding='utf-8'))}
donefile=R/'wired_schematic_refs.json'
done=json.loads(donefile.read_text()) if donefile.exists() else []
for part in parts:
    if part['ref'] in done:continue
    item={**part,'pins':bindings[part['ref']]['pins']}
    code='''
    const p=PART;
    for(const pin of p.pins){
      const net=p.nets[pin.pinNumber];
      if(net===null){await eda.sch_PrimitivePin.modify(pin.primitiveId,{noConnected:true});continue;}
      if(p.ref==='J1'&&pin.pinNumber==='1')continue;
      const a=pin.rotation*Math.PI/180;
      const x=pin.x+Math.round(40*Math.cos(a));const y=pin.y+Math.round(40*Math.sin(a));
      const port=await eda.sch_PrimitiveComponent.createNetPort('BI',net,x,y,pin.rotation===180?0:180,false);
      if(!port)throw Error('Net port failed '+p.ref+'.'+pin.pinNumber);
      const wire=await eda.sch_PrimitiveWire.create([pin.x,pin.y,x,y],net);
      if(!wire)throw Error('Wire failed '+p.ref+'.'+pin.pinNumber);
    }
    await eda.sch_Document.save();return {ref:p.ref,wired:true};
    '''.replace('PART',json.dumps(item,ensure_ascii=False))
    r=execute(code)
    done.append(part['ref']);donefile.write_text(json.dumps(done),encoding='utf-8')
    print(json.dumps(r),flush=True)
