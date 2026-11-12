"""第五步：导出 DSN → 按 V0.4 方式改规则（线宽分类、孔位/天线禁布）→ Freerouting 自动布线 → 导入 SES。

python route_pcb.py export   导出 carrier_v05.dsn 并生成 carrier_v05_routing.dsn
python route_pcb.py route    调用 tools/freerouting-2.5.0.jar 生成 carrier_v05_routed.ses
python route_pcb.py import   把 SES 导回嘉立创 EDA
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eda_client import execute

R = Path(__file__).resolve().parent
ROOT = R.parents[1]
MIL = 1 / 0.0254
HOLES = [(4, 4), (56, 4), (56, 36), (4, 36)]
HOLE_KEEPOUT_MM = 3.0
ANTENNA = json.loads((R / 'pcb_layout_mm.json').read_text())['antenna_keepout_mm']
# 线宽（mil）：电源 0.8 mm，3V3 0.5 mm，VBUS 0.45 mm（USB 焊盘间距限制），GND 0.4 mm 打底、最终靠两面铺铜，信号 0.3 mm
CLASSES = {
    'PWR': (31.5, ['VIN5', 'V5_SERVO']),
    'P3V3': (19.7, ['3V3']),
    'VBUS': (17.7, ['VBUS']),
    'GND': (15.7, ['GND']),
}
SIGNAL_WIDTH = 12
CLEAR = 6.5  # 0.165 mm（DRC 要求 0.152 mm，留余量）：USB-C 0.5 mm 间距焊盘之间只有约 0.2 mm


def export():
    # 先清掉旧的布线和过孔（含 GND 缝合过孔），避免 DSN 里带上旧走线
    execute('const l=await eda.pcb_PrimitiveLine.getAll();if(l.length)await eda.pcb_PrimitiveLine.delete(l);'
            'const v=await eda.pcb_PrimitiveVia.getAll();if(v.length)await eda.pcb_PrimitiveVia.delete(v);await eda.pcb_Document.save();'
            'return [(await eda.pcb_PrimitiveLine.getAll()).length,(await eda.pcb_PrimitiveVia.getAll()).length];')
    d = execute('const f=await eda.pcb_ManufactureData.getDsnFile("carrier_v05");return f?await f.text():null;')
    (R / 'carrier_v05.dsn').write_text(d, encoding='utf-8')
    s = d
    W, H = 60 * MIL, 40 * MIL
    inset = 0.8 * MIL
    s = re.sub(r'\(boundary\(path signal 0 [^)]*\)',
               f'(boundary(path signal 0 {inset:.2f} {inset:.2f} {inset:.2f} {H - inset:.2f} {W - inset:.2f} {H - inset:.2f} {W - inset:.2f} {inset:.2f} {inset:.2f} {inset:.2f} )', s)
    s = re.sub(r'\(rule\(clear [\d.]+\)\)', f'(rule(clear {CLEAR}))', s)
    s = re.sub(r'\(rule\(clear [\d.]+ \(type (\w+)\)\)\)', lambda m: f'(rule(clear {CLEAR} (type {m.group(1)})))', s)
    s = re.sub(r'\(rule\(width [\d.]+\)\)', f'(rule(width {SIGNAL_WIDTH}))', s)
    keep = []
    for i, (x, y) in enumerate(HOLES):
        for layer in ('TopLayer', 'BottomLayer'):
            keep.append(f'(keepout MOUNT{i}_{layer} (circle {layer} {2 * HOLE_KEEPOUT_MM * MIL:.3f} {x * MIL:.3f} {y * MIL:.3f}))')
    # USB-C 两个 NPTH 定位柱（DSN 里没有，DRC 要求离槽孔 0.3 mm）：中心约在连接器中心 (±2.89, +1.1) mm
    usb = json.loads((R / 'pcb_layout_mm.json').read_text())['layout']['USB1']
    for i, sx in enumerate((-2.89, 2.89)):
        for layer in ('TopLayer', 'BottomLayer'):
            keep.append(f'(keepout PEG{i}_{layer} (circle {layer} {1.5 * MIL:.3f} {(usb[0] + sx) * MIL:.3f} {(usb[1] + 1.1) * MIL:.3f}))')
    x0, y0, x1, y1 = [v * MIL for v in ANTENNA]
    for layer in ('TopLayer', 'BottomLayer'):
        keep.append(f'(keepout ANT_{layer} (rect {layer} {x0:.2f} {y0:.2f} {x1:.2f} {y1:.2f}))')
        keep.append(f'(via_keepout ANT_V_{layer} (rect {layer} {x0:.2f} {y0:.2f} {x1:.2f} {y1:.2f}))')
    s = re.sub(r'(\(layer BottomLayer\s*\(type signal\)\s*\))', r'\1\n' + '\n'.join(keep), s, count=1)
    # 过孔 0.3/0.6 mm
    s = re.sub(r'\(padstack via0\s*\(shape\(circle TopLayer [\d.]+\)\)\s*\(shape\(circle BottomLayer [\d.]+\)\)',
               '(padstack via0\n      (shape(circle TopLayer 23.6))\n      (shape(circle BottomLayer 23.6))', s)
    # 去掉导出的旧类，重写网络类
    s = re.sub(r"\(class [^\n]*\n(?:\s+.*\n)*?\s{4}\)\n", '', s)
    classes = []
    used = set()
    for name, (w, nets) in CLASSES.items():
        used |= set(nets)
        classes.append(f'    (class {name} {" ".join(chr(34) + n + chr(34) for n in nets)}\n      (circuit\n        (use_via via0)\n      )\n      (rule\n        (width {w})\n        (clearance {CLEAR})\n      )\n    )')
    sig = sorted(set(re.findall(r'\(net (\S+)', s)) - used)
    classes.append(f'    (class SIG {" ".join(chr(34) + n + chr(34) for n in sig)}\n      (circuit\n        (use_via via0)\n      )\n      (rule\n        (width {SIGNAL_WIDTH})\n        (clearance {CLEAR})\n      )\n    )')
    # 类必须放在 (network ...) 里面：插到 (wiring 之前那个闭合 network 的右括号前面
    w = s.index('(wiring') if '(wiring' in s else len(s.rstrip()) - 1
    close = s.rindex(')', 0, w)
    s = s[:close] + '\n'.join(classes) + '\n  ' + s[close:]
    (R / 'carrier_v05_routing.dsn').write_text(s, encoding='utf-8')
    print('nets', len(set(re.findall(r'\(net (\S+)', s))), 'signal nets', sig)


def route(passes='100'):
    jar = ROOT / 'tools' / 'freerouting-2.5.0.jar'
    cmd = ['java', '-jar', str(jar), '-de', str(R / 'carrier_v05_routing.dsn'), '-do', str(R / 'carrier_v05_routed.ses'),
           '-mp', passes, '--gui.enabled=false']
    print(' '.join(cmd))
    p = subprocess.run(cmd, cwd=str(ROOT / 'tools' / 'freerouting-data'), capture_output=True, text=True, timeout=1500)
    (R / 'freerouting.log').write_text(p.stdout[-20000:] + '\n' + p.stderr[-20000:], encoding='utf-8')
    print('exit', p.returncode, (p.stdout + p.stderr)[-1500:])


def ses_segments(ses):
    """解析 SES：返回 [(net, layer, width_mil, (x1,y1), (x2,y2))]，坐标单位 mil。"""
    res = float(re.search(r'\(resolution mil (\d+)\)', ses).group(1))
    segs = []
    for m in re.finditer(r'\(net ("?)([^\s"()]+)\1([\s\S]*?)(?=\n\s*\(net |\Z)', ses):
        net = m.group(2)
        for w in re.finditer(r'\(path (TopLayer|BottomLayer) ([\d.]+)((?:\s+-?[\d.]+)+)\s*\)', m.group(3)):
            layer = 1 if w.group(1) == 'TopLayer' else 2
            width = float(w.group(2)) / res
            nums = [float(v) / res for v in w.group(3).split()]
            pts = list(zip(nums[0::2], nums[1::2]))
            for a, b in zip(pts, pts[1:]):
                segs.append((net, layer, width, a, b))
    return segs


def import_ses():
    ses = (R / 'carrier_v05_routed.ses').read_text(encoding='utf-8')
    code = '''const f=new File([SES],"carrier_v05_routed.ses",{type:"text/plain"});
    const ok=await eda.pcb_Document.importAutoRouteSesFile(f);await eda.pcb_Document.save();
    return {ok,lines:(await eda.pcb_PrimitiveLine.getAll()).length,vias:(await eda.pcb_PrimitiveVia.getAll()).length};'''
    print(execute(code.replace('SES', json.dumps(ses))))
    # 嘉立创 EDA 导入 SES 时不保留线宽（全部变成 10 mil），按 SES 里每段的宽度逐段写回
    segs = ses_segments(ses)
    lines = execute('return (await eda.pcb_PrimitiveLine.getAll()).map(l=>[l.getState_PrimitiveId(),l.getState_Net(),l.getState_Layer(),l.getState_StartX(),l.getState_StartY(),l.getState_EndX(),l.getState_EndY()]);')
    updates, missing = [], []
    for lid, net, layer, x1, y1, x2, y2 in lines:
        best = None
        for snet, sl, w, a, b in segs:
            if sl != layer:
                continue
            for p, q in ((a, b), (b, a)):
                d = abs(p[0] - x1) + abs(p[1] - y1) + abs(q[0] - x2) + abs(q[1] - y2)
                if d < 2 and (best is None or d < best[0]):
                    best = (d, w)
        if best:
            updates.append([lid, best[1]])
        else:
            missing.append([lid, net, layer])
    for i in range(0, len(updates), 60):
        execute('for(const [id,w] of ' + json.dumps(updates[i:i + 60]) + ') await eda.pcb_PrimitiveLine.modify(id,{lineWidth:w}); await eda.pcb_Document.save(); return 1;')
    print('widths restored', len(updates), 'unmatched', len(missing), missing[:10])


if __name__ == '__main__':
    {'export': export, 'route': route, 'import': import_ses}[sys.argv[1]]()






