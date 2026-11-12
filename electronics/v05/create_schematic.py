"""第一步：按 BOM 在 V0.5 原理图放置正式库器件，回读每个器件的引脚编号和名称。

器件 UUID 来自 parts_check.json（由 check_parts.py 在 EDA 库里按 LCSC 编号确认）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eda_client import execute

R = Path(__file__).resolve().parent
intent = json.loads((R / 'design_intent.json').read_text(encoding='utf-8'))
checked = {p['lcsc']: p for p in json.loads((R / 'parts_check.json').read_text(encoding='utf-8'))['parts']}
page = json.loads((R / 'project_documents.json').read_text(encoding='utf-8'))['schematic_page']

items = []
for part in intent['parts']:
    eda = checked[part['sku']]['eda']
    items.append({'ref': part['ref'], 'xy': part['xy_sch'], 'lib': eda['library_uuid'], 'dev': eda['device_uuid']})

code = '''
const parts=__CHUNK__;
const present=await eda.sch_PrimitiveComponent.getAll();
const out=[];
for(const part of parts){
  let comp=present.find(c=>c.getState_Designator()===part.ref);
  if(!comp)comp=await eda.sch_PrimitiveComponent.create({libraryUuid:part.lib,uuid:part.dev},part.xy[0],part.xy[1],"",0,false,true,true);
  if(!comp)throw Error('create failed '+part.ref);
  await eda.sch_PrimitiveComponent.modify(comp.getState_PrimitiveId(),{x:part.xy[0],y:part.xy[1],designator:part.ref,uniqueId:'SR05-'+part.ref,addIntoBom:true,addIntoPcb:true});
  const pins=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(comp.getState_PrimitiveId());
  out.push({ref:part.ref,pins:pins.map(p=>({n:p.getState_PinNumber(),name:p.getState_PinName(),x:p.getState_X(),y:p.getState_Y(),rot:p.getState_Rotation()}))});
}
await eda.sch_Document.save();
return out;
'''
execute('await eda.dmt_EditorControl.openDocument(' + json.dumps(page) + ');return true;')
res = []
for i in range(0, len(items), 5):
    res += execute(code.replace('__CHUNK__', json.dumps(items[i:i+5])))
    print('chunk', i, flush=True)
(R / 'schematic_pins.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
print('placed', len(res))

