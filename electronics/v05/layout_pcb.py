"""第四步：60×40 mm 板框、4 个 M3 孔、器件布局、天线禁布区，并用实际封装外框检查重叠/出板/压孔。

坐标单位 mm，旋转单位度。API 内部单位为 mil（mm/0.0254）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eda_client import execute

R = Path(__file__).resolve().parent
W, H = 60, 40
HOLES = [(4, 4), (56, 4), (56, 36), (4, 36)]
# 模组天线朝 +Y（板上边），USB-C 开口朝 -Y（板下边）
LAYOUT = {
    'U3': [30, 29.0, 0],
    'USB1': [30, 4.9, 0],
    'D1': [21, 6.5, 0],
    'R7': [25.6, 10.6, 0],
    'R8': [34.4, 10.6, 0],
    'U4': [30, 16.2, 0],
    'C3': [37.6, 18.0, 90],
    'C4': [24.4, 16.2, 90],
    'J1': [9, 12, 90],
    'F1': [17, 13, 90],
    'C1': [10, 21.5, 0],
    'C2': [3.4, 30, 90],
    'J3': [9, 31, 90],
    'R5': [11.9, 30.5, 90],
    'R6': [11.9, 34.6, 90],
    'SW1': [16.6, 30.4, 0],
    'SW2': [16.6, 36.8, 0],
    'C5': [19.0, 24.6, 0],
    'C6': [21.2, 29.0, 90],
    'R9': [19.0, 21.6, 0],
    'C7': [21.4, 18.4, 0],
    'R11': [21.2, 33.0, 90],
    'R12': [33.0, 21.6, 0],
    'R10': [36.4, 21.6, 0],
    'U1': [47, 8.8, 90],
    'J4': [55, 11.5, 90],
    'R1': [43.6, 13.7, 0],
    'R3': [47.6, 13.7, 0],
    'U2': [47, 18.5, 90],
    'J5': [55, 21, 90],
    'R2': [43.6, 23.6, 0],
    'R4': [47.6, 23.6, 0],
    'J6': [47, 31, 0],
}
# 天线下方所有层禁止走线/填充/覆铜（模组焊盘最高到 y≈34.4）
ANTENNA_KEEPOUT = [21.5, 34.8, 38.5, 40]
ALLOWED_OVERHANG = {'U3': 0.5, 'USB1': 0.5}  # 天线、USB 口允许贴齐或略伸出板边


def mil(v):
    return v / 0.0254


def place():
    layout = {k: [mil(v[0]), mil(v[1]), v[2]] for k, v in LAYOUT.items()}
    execute('''const L=LAYOUT;for(const p of await eda.pcb_PrimitiveComponent.getAll()){const a=L[p.getState_Designator()];if(!a)throw Error("unexpected "+p.getState_Designator());
      await eda.pcb_PrimitiveComponent.modify(p.getState_PrimitiveId(),{x:a[0],y:a[1],rotation:a[2],layer:1});}await eda.pcb_Document.save();return true;'''
            .replace('LAYOUT', json.dumps(layout)))


def mechanics():
    # 只在没有板框时创建板框、孔和禁布区
    code = '''
    const lines=(await eda.pcb_PrimitivePolyline.getAll()).filter(p=>p.getState_Layer()===11);
    const out={outline:lines.length};
    if(!lines.length){
      const p=eda.pcb_MathPolygon.createPolygon([0,0,"L",W,0,W,H,0,H,0,0]);
      out.outline=!!(await eda.pcb_PrimitivePolyline.create("",11,p,.2/.0254,true));
      out.holes=[];
      for(const [x,y] of HOLES){out.holes.push(!!(await eda.pcb_PrimitivePad.create(12,"",x/.0254,y/.0254,0,["ELLIPSE",3.2/.0254,3.2/.0254],"",["ROUND",3.2/.0254],0,0,0,false,0,[],null,null,true)));}
      const k=KO;
      const poly=eda.pcb_MathPolygon.createPolygon([k[0]/.0254,k[1]/.0254,"L",k[2]/.0254,k[1]/.0254,k[2]/.0254,k[3]/.0254,k[0]/.0254,k[3]/.0254,k[0]/.0254,k[1]/.0254]);
      out.keepout=!!(await eda.pcb_PrimitiveRegion.create(12,poly,[5,6,7],"ANTENNA_KEEPOUT"));
    }
    await eda.pcb_Document.save();return out;'''
    code = (code.replace('W,0,W,H,0,H', f'{mil(W)},0,{mil(W)},{mil(H)},0,{mil(H)}')
            .replace('HOLES', json.dumps(HOLES)).replace('KO', json.dumps(ANTENNA_KEEPOUT)))
    return execute(code)


def check():
    bb = execute('''const o={};for(const c of await eda.pcb_PrimitiveComponent.getAll()){o[c.getState_Designator()]=await eda.pcb_Primitive.getPrimitivesBBox([c.getState_PrimitiveId()]);}return o;''')
    boxes = {k: [v['minX'] * .0254, v['minY'] * .0254, v['maxX'] * .0254, v['maxY'] * .0254] for k, v in bb.items()}
    issues = []
    names = sorted(boxes)
    for i, a in enumerate(names):
        A = boxes[a]
        ov = ALLOWED_OVERHANG.get(a, 0)
        if A[0] < -ov or A[1] < -ov or A[2] > W + ov or A[3] > H + ov:
            issues.append(f'{a} outside board {[round(v, 2) for v in A]}')
        for hx, hy in HOLES:
            cx, cy = min(max(hx, A[0]), A[2]), min(max(hy, A[1]), A[3])
            if (cx - hx) ** 2 + (cy - hy) ** 2 < 2.0 ** 2:
                issues.append(f'{a} too close to hole ({hx},{hy})')
        for b in names[i + 1:]:
            B = boxes[b]
            if A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]:
                dx = min(A[2], B[2]) - max(A[0], B[0])
                dy = min(A[3], B[3]) - max(A[1], B[1])
                issues.append(f'{a} overlaps {b} by {dx:.2f}x{dy:.2f} mm')
    return boxes, issues


if __name__ == '__main__':
    docs = json.loads((R / 'project_documents.json').read_text(encoding='utf-8'))
    execute('await eda.dmt_EditorControl.openDocument(' + json.dumps(docs['pcb']) + ');return true;')
    place()
    print('mechanics', mechanics())
    boxes, issues = check()
    (R / 'pcb_layout_mm.json').write_text(json.dumps({'layout': LAYOUT, 'bbox_mm': boxes, 'antenna_keepout_mm': ANTENNA_KEEPOUT,
                                                      'issues': issues}, indent=1), encoding='utf-8')
    print(len(issues), 'issues')
    for s in issues:
        print(' ', s)

