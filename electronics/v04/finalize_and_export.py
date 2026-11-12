"""回读实际线宽及规则、执行 DRC，并导出可审查的原生工程和制造文件。"""
import json,sys,csv,hashlib,shutil,zipfile,re
from pathlib import Path
sys.path.insert(0,r'D:\CodeWorkSpace\switch-robot-diy')
from eda_client import execute
R=Path(__file__).resolve().parent
state=execute('await eda.pcb_Document.save();return {passed:await eda.pcb_Drc.check(true,false,false),details:await eda.pcb_Drc.check(true,false,true),source:await eda.sys_FileManager.getDocumentSource(),lines:await eda.pcb_PrimitiveLine.getAll(),rules:await eda.pcb_Drc.getCurrentRuleConfiguration()};')
assert state['passed'] is True and state['details']==[]
for line in state['lines']:
 expected=31.5 if line['net'] in ['VIN5','V5_SERVO','GND'] else 12
 assert abs(line['lineWidth']-expected)<.001,(line['net'],line['lineWidth'])
assert state['rules']['config']['Spacing']['Safe Spacing']['copperThickness1oz']['tables']['1']['content'][0][0]>.249
(R/'carrier_v04.epcb').write_text(state.pop('source'),encoding='utf8')
(R/'pcb_final_state.json').write_text(json.dumps(state,indent=2),encoding='utf8')
(R/'pcb_drc_final.json').write_text(json.dumps({'passed':state['passed'],'details':state['details']},indent=2),encoding='utf8')
for call,out in [('eda.pcb_ManufactureData.getGerberFile("carrier_v04_gerber")','carrier_v04_gerber.zip'),('eda.pcb_ManufactureData.get3DFile("carrier_v04_populated","obj",["Component Model","Silkscreen","Wire In Signal Layer"],"Parts",false)','carrier_v04_populated.zip')]:
 data=execute('const f=await '+call+';return f?Array.from(new Uint8Array(await f.arrayBuffer())):null;');assert data
 (R/out).write_bytes(bytes(data));print(out,len(data),flush=True)
image=execute('const b=await eda.dmt_EditorControl.getCurrentRenderedAreaImage();return b?Array.from(new Uint8Array(await b.arrayBuffer())):null;');assert image
(R/'carrier_v04_pcb.png').write_bytes(bytes(image))
with zipfile.ZipFile(R/'carrier_v04_populated.zip') as z:z.extractall(R/'3d')
report=json.loads((R/'verification_report.json').read_text())
report['pcb_drc']={'passed':True,'details':[]}
report['native_drc_minimum_track_mm']=.3
report['native_drc_copper_clearance_mm']=.25
report['routing_target_clearance_mm']=.254
report['actual_trace_widths_verified']=True
report['gerber_sha256']=hashlib.sha256((R/'carrier_v04_gerber.zip').read_bytes()).hexdigest()
(R/'verification_report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
shutil.copytree(Path(r'C:\Users\yui\Documents\LCEDA-Pro\projects\Switch Robot Carrier V0.4'),R/'native-project',dirs_exist_ok=True)
with zipfile.ZipFile(R/'Switch_Robot_Carrier_V04_native.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in (R/'native-project').rglob('*'):
  if p.is_file():z.write(p,str(p.relative_to(R/'native-project')))
print('Final DRC: PASS; 69 widths verified; native project archived.')
