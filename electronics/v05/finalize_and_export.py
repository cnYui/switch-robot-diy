"""第七步：重建铺铜、终检（ERC、DRC、线宽、焊盘网络），导出制造文件和原生工程。"""
import csv
import hashlib
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eda_client import execute

R = Path(__file__).resolve().parent
docs = json.loads((R / 'project_documents.json').read_text(encoding='utf-8'))
intent = json.loads((R / 'design_intent.json').read_text(encoding='utf-8'))
checked = {p['lcsc']: p for p in json.loads((R / 'parts_check.json').read_text(encoding='utf-8'))['parts']}
WIDTH = {'VIN5': .8001, 'V5_SERVO': .8001, '3V3': .5004, 'VBUS': .4496, 'GND': .3988}  # 各网络类的主线宽（mm）


def file_bytes(call):
    data = execute('const f=await ' + call + ';return f?Array.from(new Uint8Array(await f.arrayBuffer())):null;')
    assert data, call
    return bytes(data)


# ---- 原理图 ----
execute('await eda.dmt_EditorControl.openDocument(' + json.dumps(docs['schematic_page']) + ');return 1;')
sch = execute('await eda.sch_Document.save();return {erc:await eda.sch_Drc.check(true,false,true),source:await eda.sys_FileManager.getDocumentSource()};')
(R / 'carrier_v05.esch').write_text(sch['source'], encoding='utf-8')
(R / 'schematic_erc.json').write_text(json.dumps(sch['erc'], indent=1, ensure_ascii=False), encoding='utf-8')
assert sch['erc'] == [], sch['erc']
sch_png = execute('await eda.dmt_EditorControl.zoomToAllPrimitives();const b=await eda.dmt_EditorControl.getCurrentRenderedAreaImage();return b?Array.from(new Uint8Array(await b.arrayBuffer())):null;')
(R / 'carrier_v05_schematic.png').write_bytes(bytes(sch_png))

# ---- PCB ----
execute('await eda.dmt_EditorControl.openDocument(' + json.dumps(docs['pcb']) + ');return 1;')
execute('for(const p of await eda.pcb_PrimitivePour.getAll()){await p.rebuildCopperRegion();}await eda.pcb_Document.save();return 1;')
st = execute('''await eda.pcb_Document.save();return {passed:await eda.pcb_Drc.check(true,false,false),details:await eda.pcb_Drc.check(true,false,true),
  lines:(await eda.pcb_PrimitiveLine.getAll()).map(l=>({net:l.getState_Net(),layer:l.getState_Layer(),w:l.getState_LineWidth()})),
  vias:(await eda.pcb_PrimitiveVia.getAll()).map(v=>({net:v.getState_Net(),hole:v.getState_HoleDiameter(),d:v.getState_Diameter()})),
  poured:(await eda.pcb_PrimitivePoured.getAll()).length,
  rules:await eda.pcb_Drc.getCurrentRuleConfigurationName(),
  source:await eda.sys_FileManager.getDocumentSource()};''')
assert st['passed'] is True and st['details'] == [], st['details']
assert st['poured'] >= 2
widths = {}
for ln in st['lines']:
    mm = round(ln['w'] * .0254, 4)
    widths.setdefault(ln['net'], set()).add(mm)
    assert mm >= .228, (ln['net'], mm)  # Freerouting 在细间距焊盘处会收窄到 0.2286 mm
for net, want in list(WIDTH.items()) + [('USB_DP', .3048)]:
    assert abs(max(widths[net]) - want) < .002, (net, widths[net])
(R / 'carrier_v05.epcb').write_text(st.pop('source'), encoding='utf-8')
(R / 'pcb_drc.json').write_text(json.dumps({'passed': st['passed'], 'details': st['details'], 'rule_set': st['rules']}, indent=1, ensure_ascii=False), encoding='utf-8')
net_check = json.loads((R / 'pcb_net_check.json').read_text(encoding='utf-8'))
assert net_check['problems'] == []

# ---- 制造文件 ----
(R / 'carrier_v05_gerber.zip').write_bytes(file_bytes('eda.pcb_ManufactureData.getGerberFile("carrier_v05_gerber")'))
bom_raw = file_bytes('eda.pcb_ManufactureData.getBomFile("carrier_v05_bom_native","csv")')
(R / 'carrier_v05_bom_native.csv').write_bytes(bom_raw)
cpl_raw = file_bytes('eda.pcb_ManufactureData.getPickAndPlaceFile("carrier_v05_cpl_native","csv",' + '"mm"' + ')')
(R / 'carrier_v05_cpl_native.csv').write_bytes(cpl_raw)


def read_table(raw):
    for enc in ('utf-16', 'utf-8-sig', 'gbk'):
        try:
            text = raw.decode(enc)
            if '\t' in text.splitlines()[0] or ',' in text.splitlines()[0]:
                break
        except Exception:
            continue
    delim = '\t' if text.splitlines()[0].count('\t') > text.splitlines()[0].count(',') else ','
    return list(csv.DictReader(io.StringIO(text), delimiter=delim))


cpl = read_table(cpl_raw)
(R / 'cpl_columns.json').write_text(json.dumps(list(cpl[0].keys()), ensure_ascii=False), encoding='utf-8')

# 嘉立创格式 BOM（按 design_intent 生成，保证料号与 parts_check.json 一致）
groups = {}
for p in intent['parts']:
    c = checked[p['sku']]
    key = p['sku']
    g = groups.setdefault(key, {'Comment': c['lcsc_model'] or c['eda']['manufacturer_part'], 'Designator': [],
                                'Footprint': c['eda']['footprint'], 'LCSC Part #': key,
                                'JLC Library': c['jlc_library'], 'Mount': p['mount']})
    g['Designator'].append(p['ref'])
with open(R / 'carrier_v05_bom_jlc.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #', 'Quantity', 'JLC Library', 'Assembly'])
    for g in groups.values():
        w.writerow([g['Comment'], ','.join(g['Designator']), g['Footprint'], g['LCSC Part #'], len(g['Designator']),
                    g['JLC Library'], 'SMT' if g['Mount'] == 'SMT' else 'THT（手焊或下单勾选插件焊接）'])


def col(row, *names):
    for n in names:
        for k in row:
            if k and k.strip().lower() == n.lower():
                return row[k]
    raise KeyError(names)


with open(R / 'carrier_v05_cpl_jlc.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for row in cpl:
        ref = col(row, 'Designator')
        if not ref:
            continue
        layer = col(row, 'Layer')
        w.writerow([ref, col(row, 'Mid X', 'Center-X(mm)', 'Center-X'), col(row, 'Mid Y', 'Center-Y(mm)', 'Center-Y'),
                    'Top' if layer.lower().startswith('t') else 'Bottom', col(row, 'Rotation')])

png = execute('await eda.dmt_EditorControl.zoomToAllPrimitives();const b=await eda.dmt_EditorControl.getCurrentRenderedAreaImage();return b?Array.from(new Uint8Array(await b.arrayBuffer())):null;')
(R / 'carrier_v05_pcb.png').write_bytes(bytes(png))

# ---- 原生工程 ----
src = Path(r'C:\Users\yui\Documents\LCEDA-Pro\projects')
proj = [p for p in src.iterdir() if p.name.startswith('Switch Robot Carrier V0.5')]
with zipfile.ZipFile(R / 'Switch_Robot_Carrier_V05_native.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for p in proj:
        if p.is_dir():
            for q in p.rglob('*'):
                if q.is_file():
                    z.write(q, str(q.relative_to(src)))
        else:
            z.write(p, p.name)

report = {
    'date': '2026-11-12',
    'erc': 'no errors, no warnings ([])',
    'drc': {'passed': True, 'details': [], 'rule_set': st['rules']},
    'pad_net_mismatches_vs_design_intent': 0,
    'components': len(intent['parts']),
    'tracks': len(st['lines']),
    'vias': {'total': len(st['vias']), 'gnd': sum(1 for v in st['vias'] if v['net'] == 'GND')},
    'track_widths_mm': {k: sorted(v) for k, v in sorted(widths.items())},
    'gnd_pour_regions': st['poured'],
    'native_project_files': [p.name for p in proj],
    'gerber_sha256': hashlib.sha256((R / 'carrier_v05_gerber.zip').read_bytes()).hexdigest(),
}
(R / 'verification_report.json').write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
print(json.dumps(report, indent=1, ensure_ascii=False))


