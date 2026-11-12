"""检查 V0.7 紧固件：螺丝与各零件的干涉、螺纹咬合长度、尖端后面的自由长度。
先运行 build_fasteners.py（生成 _fastener_meshes/ 和 fastener_spec_v07.json），再运行本脚本：
  simulation/.venv/Scripts/python.exe -I mechanical/verify_fasteners.py
用蒙特卡洛取点判断，不依赖 Blender 布尔：在螺丝实体内均匀取点，数落在各零件实体里的点。
"""
import json
from pathlib import Path

import numpy as np
import trimesh

OUT = Path(__file__).resolve().parent
rng = np.random.default_rng(7)
spec = json.loads((OUT / 'fastener_spec_v07.json').read_text(encoding='utf8'))

solids = {}
for f in sorted((OUT / '_fastener_meshes').glob('*.npz')):
    if f.stem.startswith('FASTENER_'):
        continue
    d = np.load(f)
    m = trimesh.Trimesh(d['v'], d['f'], process=False)
    solids[f.stem] = m
    if not m.is_watertight:
        print('warning: not watertight, containment may be unreliable:', f.stem)

# 每种螺丝咬合的零件；水平方向没有建模的（舵盘）写 None
THREADS_INTO = {'F1': 'PRINT_04_gateway_case_V03', 'F2': 'PRINT_04_gateway_case_V03',
                'F3': 'PRINT_01_86_adjustable_frame', 'F4': None}


def basis(axis):
    a = np.asarray(axis, float)
    helper = np.array([1, 0, 0]) if abs(a[0]) < .9 else np.array([0, 1, 0])
    u = np.cross(a, helper)
    u /= np.linalg.norm(u)
    return u, np.cross(a, u)


def sample(s, n=40000):
    """返回 (点, 沿轴坐标 t, 体积)。t=0 在承压面，向尖端为正；头在 t<0。"""
    a = np.asarray(s['axis'], float)
    p0 = np.asarray(s['bearing_point_mm'], float)
    d, L, dk, k, tip = s['thread_d_mm'], s['length_under_head_mm'], s['head_dia_mm'], s['head_height_mm'], s['tip_mm']
    u, v = basis(a)
    vols = {'head': np.pi * (dk / 2) ** 2 * k, 'shank': np.pi * (d / 2) ** 2 * (L - tip),
            'tip': np.pi * tip * ((d / 2) ** 2 + (d / 2) * .25 + .25 ** 2) / 3}
    total = sum(vols.values())
    pts, ts = [], []
    for name, vol in vols.items():
        m = max(int(n * vol / total), 500)
        if name == 'head':
            t = rng.uniform(-k, 0, m); rmax = np.full(m, dk / 2)
        elif name == 'shank':
            t = rng.uniform(0, L - tip, m); rmax = np.full(m, d / 2)
        else:
            t = rng.uniform(L - tip, L, m); rmax = d / 2 + (.25 - d / 2) * (t - (L - tip)) / tip
        r = np.sqrt(rng.uniform(0, 1, m)) * rmax
        th = rng.uniform(0, 2 * np.pi, m)
        pts.append(p0 + np.outer(t, a) + np.outer(r * np.cos(th), u) + np.outer(r * np.sin(th), v))
        ts.append(t)
    return np.vstack(pts), np.concatenate(ts), total


def free_beyond_tip(s, limit=40.0, step=.05):
    a = np.asarray(s['axis'], float)
    p0 = np.asarray(s['bearing_point_mm'], float)
    L = s['length_under_head_mm']
    ts = np.arange(L + step, L + limit, step)
    pts = p0 + np.outer(ts, a)
    for t, p in zip(ts, pts):
        pass
    hit = np.zeros(len(ts), bool)
    for m in solids.values():
        lo, hi = m.bounds
        near = np.all((pts > lo - .01) & (pts < hi + .01), axis=1)
        if near.any():
            hit[near] |= m.contains(pts[near])
    return round(float(ts[hit.argmax()] - L), 2) if hit.any() else None


rows = []
for s in spec:
    name = s['name']
    if name.startswith('FASTENER_W1'):
        c = np.asarray(s['centre_mm'], float)
        row = {'fastener': name, 'type': 'washer', 'outer_mm': s['outer_mm'], 'inner_mm': s['inner_mm'],
               'thick_mm': s['thick_mm'], 'z_range_mm': [round(c[2] - s['thick_mm'] / 2, 3), round(c[2] + s['thick_mm'] / 2, 3)]}
        rows.append(row)
        continue
    fid = name.split('_')[1]
    pts, t, vol = sample(s)
    row = {'fastener': name, 'type': 'screw', 'role': s['role'], 'id': fid, 'thread_into': THREADS_INTO[fid],
           'overlap': {}, 'free_beyond_tip_mm': free_beyond_tip(s)}
    for pname, m in solids.items():
        lo, hi = m.bounds
        near = np.all((pts > lo) & (pts < hi), axis=1)
        if not near.any():
            continue
        inside = np.zeros(len(pts), bool)
        inside[near] = m.contains(pts[near])
        n = int(inside.sum())
        if n:
            row['overlap'][pname] = {'volume_mm3': round(n / len(pts) * vol, 2),
                                     'axial_from_bearing_mm': [round(float(t[inside].min()), 2), round(float(t[inside].max()), 2)],
                                     'engaged_length_mm': round(float(t[inside].max() - t[inside].min()), 2)}
    bad = {k: v for k, v in row['overlap'].items() if k != THREADS_INTO[fid]}
    row['interference_with_other_parts'] = bad
    row['verdict'] = 'PASS' if not bad else 'INTERFERENCE'
    rows.append(row)
    print(name, row['verdict'], 'thread:', row['overlap'].get(THREADS_INTO[fid], '-'), 'others:', bad or 'none',
          'free beyond tip:', row['free_beyond_tip_mm'])

(OUT / 'fastener_checks_v07.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding='utf8')
