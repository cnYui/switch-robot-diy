"""用商城正式器件建立原理图；每个端口均绑定明确的电气网络。"""
from pathlib import Path
import json
import sys
sys.path.insert(0,'D:/CodeWorkSpace/switch-robot-diy')
from eda_client import execute
ROOT=Path(__file__).resolve().parent
intent=json.loads((ROOT/'design_intent.json').read_text(encoding='utf-8'))
candidates=json.loads((ROOT.parent/'procurement_candidates.json').read_text(encoding='utf-8'))
bycode={p['supplier_code']:p for p in candidates['parts']}
docs=json.loads((ROOT/'project_documents.json').read_text())
page=docs['boards'][0]['schematic']['page'][0]['uuid']
items=[]
for item in intent['parts']:
    p=bycode[item['sku']]
    items.append({**item,'libraryUuid':p['library_uuid'],'deviceUuid':p['device_uuid']})
code='''
const parts=PARTS;
const present=await eda.sch_PrimitiveComponent.getAll();
const ids=[];
for(const part of parts){
 let comp=present.find(c=>c.getState_Designator()===part.ref);
 if(!comp)comp=await eda.sch_PrimitiveComponent.create({libraryUuid:part.libraryUuid,uuid:part.deviceUuid},part.xy_sch[0],part.xy_sch[1],"",0,false,true,true);
 if(!comp)throw Error('Component could not be created: '+part.ref);
 await eda.sch_PrimitiveComponent.modify(comp.getState_PrimitiveId(),{x:part.xy_sch[0],y:part.xy_sch[1],designator:part.ref,uniqueId:'SR04-'+part.ref,addIntoBom:true,addIntoPcb:true});
 const pins=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(comp.getState_PrimitiveId());
 ids.push({ref:part.ref,id:comp.getState_PrimitiveId(),pins});
}
await eda.sch_Document.save();
return {components:ids,source:await eda.sys_FileManager.getDocumentSource()};
'''.replace('PARTS',json.dumps(items,ensure_ascii=False))
execute('await eda.dmt_EditorControl.openDocument('+json.dumps(page)+');return true;')
r=execute(code)
(ROOT/'schematic_binding.json').write_text(json.dumps(r['components'],indent=2,ensure_ascii=False),encoding='utf-8')
(ROOT/'schematic_bound_source.esch').write_text(r['source'],encoding='utf-8')
print(json.dumps({'bound_components':len(r['components']),'pins':{p['ref']:[{'n':i['pinNumber'],'x':i['x'],'y':i['y'],'angle':i['rotation']} for i in p['pins']] for p in r['components']}},ensure_ascii=False))
