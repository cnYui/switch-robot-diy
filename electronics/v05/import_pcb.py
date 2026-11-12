"""第三步：原理图导入 PCB，回读每个焊盘的网络，与 design_intent.json 逐脚比对。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eda_client import execute

R = Path(__file__).resolve().parent
docs = json.loads((R / 'project_documents.json').read_text(encoding='utf-8'))
intent = json.loads((R / 'design_intent.json').read_text(encoding='utf-8'))

execute('await eda.dmt_EditorControl.openDocument(' + json.dumps(docs['pcb']) + ');return true;')
if '--no-import' not in sys.argv:
    print('import', execute('const r=await eda.pcb_Document.importChanges();await eda.pcb_Document.save();return r;'))

pads = execute('''
const out={};
for(const c of await eda.pcb_PrimitiveComponent.getAll()){
  const pads=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
  out[c.getState_Designator()]={layer:c.getState_Layer(),x:c.getState_X(),y:c.getState_Y(),rot:c.getState_Rotation(),
    pads:(pads||[]).map(p=>({n:p.getState_PadNumber(),net:p.getState_Net(),x:p.getState_X(),y:p.getState_Y()}))};
}
return out;
''')
(R / 'pcb_imported_components.json').write_text(json.dumps(pads, indent=1, ensure_ascii=False), encoding='utf-8')

problems = []
for part in intent['parts']:
    comp = pads.get(part['ref'])
    if not comp:
        problems.append(part['ref'] + ' missing in PCB')
        continue
    # 符号引脚号与封装焊盘号一致；多焊盘共用同一引脚时（如 USB 外壳、模组 GND）按引脚号前缀匹配
    for pad in comp['pads']:
        want = part['nets'].get(pad['n'])
        if want is None and pad['n'] not in part['nets']:
            # 未在符号里出现的焊盘（例如散热焊盘）只要求是 GND 或空
            if pad['net'] not in ('', 'GND', None):
                problems.append(f"{part['ref']}.{pad['n']} unexpected pad net {pad['net']}")
            continue
        if (want or '') != (pad['net'] or ''):
            problems.append(f"{part['ref']}.{pad['n']} intent={want} pcb={pad['net']}")
extra = set(pads) - {p['ref'] for p in intent['parts']}
problems += [f'{e} extra in PCB' for e in sorted(extra)]
(R / 'pcb_net_check.json').write_text(json.dumps({'problems': problems}, indent=1, ensure_ascii=False), encoding='utf-8')
print('components', len(pads), 'problems', len(problems))
for p in problems[:60]:
    print(' ', p)
