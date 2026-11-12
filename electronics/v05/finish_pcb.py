"""第六步：设置 DRC 规则、两面 GND 铺铜、模组 GND 焊盘过孔与缝合过孔，跑 DRC。

python finish_pcb.py rules | pour | vias | drc
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eda_client import execute

R = Path(__file__).resolve().parent
MIL = 1 / 0.0254
COPPER_CLEARANCE = 0.15   # USB-C 0.5 mm 间距焊盘之间约 0.2 mm；嘉立创常规工艺最小 0.1 mm
ANT = json.loads((R / 'pcb_layout_mm.json').read_text())['antenna_keepout_mm']
HOLES = [(4, 4), (56, 4), (56, 36), (4, 36)]


def rules():
    cfg = execute('return await eda.pcb_Drc.getCurrentRuleConfiguration();')
    (R / 'pcb_rules_before.json').write_text(json.dumps(cfg, indent=1, ensure_ascii=False), encoding='utf-8')
    c = cfg['config']
    t = c['Spacing']['Safe Spacing']['copperThickness1oz']['tables']['1']['content']
    # 前 7 行为 Track/SMD Pad/TH Pad/测试点/Via/填充，彼此间距统一 0.15 mm；铺铜、板框、孔等保持默认（更大）
    for i in range(7):
        for j in range(len(t[i])):
            if j < 7:
                t[i][j] = COPPER_CLEARANCE
    tr = c['Physics']['Track']['copperThickness1oz']['form']['data']['1']
    tr.update({'minValue': 0.3, 'defaultValue': 0.3048})
    ok = execute('return await eda.pcb_Drc.overwriteCurrentRuleConfiguration(' + json.dumps(cfg) + ');')
    back = execute('return await eda.pcb_Drc.getCurrentRuleConfiguration();')
    (R / 'pcb_rules_configured.json').write_text(json.dumps(back, indent=1, ensure_ascii=False), encoding='utf-8')
    print('rules', ok, back['config']['Spacing']['Safe Spacing']['copperThickness1oz']['tables']['1']['content'][0],
          back['config']['Physics']['Track']['copperThickness1oz']['form']['data']['1'])


def pour():
    code = '''
    for(const p of await eda.pcb_PrimitivePour.getAll()) await eda.pcb_PrimitivePour.delete([p.getState_PrimitiveId()]);
    const m=0.4/.0254, W=60/.0254, H=40/.0254;
    const out=[];
    for(const layer of [1,2]){
      const poly=eda.pcb_MathPolygon.createPolygon([m,m,"L",W-m,m,W-m,H-m,m,H-m,m,m]);
      const p=await eda.pcb_PrimitivePour.create("GND",layer,poly,"solid",false,"GND_"+(layer===1?"TOP":"BOTTOM"),1,10,false);
      out.push(!!p);
      if(p&&p.rebuildCopperRegion) await p.rebuildCopperRegion();
    }
    await eda.pcb_Document.save();
    return out;'''
    print('pour', execute(code))


def vias():
    # 模组中间 9 个 GND 焊盘各打一个 0.3/0.6 mm 过孔，另在空白处放缝合过孔（DRC 有冲突的自动删除）
    u3 = execute('''const u=(await eda.pcb_PrimitiveComponent.getAll()).find(c=>c.getState_Designator()==="U3");
      const pads=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(u.getState_PrimitiveId());
      return pads.filter(p=>p.getState_PadNumber()==="49").map(p=>[p.getState_X(),p.getState_Y()]);''')
    # 已经保留的过孔（gnd_vias.json）不重复放；第二轮只补缝合过孔（铺铜填充后它们才不算孤立）
    have = json.loads((R / 'gnd_vias.json').read_text()) if (R / 'gnd_vias.json').exists() else []
    pts = [] if have else [(x * .0254, y * .0254, 'EP') for x, y in u3]
    for x in range(2, 60, 4):
        for y in range(2, 40, 4):
            if ANT[0] - 1 <= x <= ANT[2] + 1 and y >= ANT[1] - 1:
                continue
            if any((x - hx) ** 2 + (y - hy) ** 2 < 3.5 ** 2 for hx, hy in HOLES):
                continue
            if any(abs(h[2] - x) < .1 and abs(h[3] - y) < .1 for h in have):
                continue
            pts.append((x, y, 'STITCH'))
    code = '''const pts=PTS;const ids=[];
      for(const [x,y,k] of pts){const v=await eda.pcb_PrimitiveVia.create("GND",x/.0254,y/.0254,0.3/.0254,0.6/.0254);if(v)ids.push([v.getState_PrimitiveId(),k,x,y]);}
      await eda.pcb_Document.save();return ids;'''
    ids = []
    for i in range(0, len(pts), 40):
        ids += execute(code.replace('PTS', json.dumps(pts[i:i + 40])))
    (R / 'gnd_vias_candidates.json').write_text(json.dumps(have + ids, indent=1), encoding='utf-8')
    print('candidate vias', len(ids), 'existing', len(have))


def prune():
    """删除出现在 DRC 明细里的缝合过孔（压线、压焊盘、离元件太近等）。"""
    ids = json.loads((R / 'gnd_vias_candidates.json').read_text())
    stitch = {i[0]: i for i in ids}  # EP 和缝合过孔都参与检查
    for rnd in range(6):
        # 每轮先重建两面铺铜（rebuildCopperRegion 在编辑器刚启动时可用；卡住时需重启嘉立创 EDA）
        execute('for(const p of await eda.pcb_PrimitivePour.getAll()){await p.rebuildCopperRegion();}await eda.pcb_Document.save();return 1;')
        det = execute('return await eda.pcb_Drc.check(true,false,true);') or []
        bad = set()
        text = json.dumps(det)
        for vid in list(stitch):
            if vid in text:
                bad.add(vid)
        print('round', rnd, 'drc items', len(det), 'bad stitch vias', len(bad))
        if not bad:
            break
        execute('await eda.pcb_PrimitiveVia.delete(' + json.dumps(sorted(bad)) + ');await eda.pcb_Document.save();return 1;')
        for b in bad:
            stitch.pop(b)
    keep = [i for i in ids if i[0] in stitch]
    (R / 'gnd_vias.json').write_text(json.dumps(keep, indent=1), encoding='utf-8')
    print('kept vias', len(keep))


def drc():
    r = execute('await eda.pcb_Document.save();return {passed:await eda.pcb_Drc.check(true,false,false),details:await eda.pcb_Drc.check(true,false,true)};')
    (R / 'pcb_drc.json').write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding='utf-8')
    print('passed', r['passed'], 'details', len(r['details'] or []))
    print(json.dumps(r['details'], ensure_ascii=False)[:4000])


if __name__ == '__main__':
    {'rules': rules, 'pour': pour, 'vias': vias, 'prune': prune, 'drc': drc}[sys.argv[1]]()


