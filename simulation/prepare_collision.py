"""按 CAD 的构成体拆分碰撞体，保留凹形空隙；质量取自原始封闭网格。"""
import hashlib
import json
from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
report = {'method': 'CAD construction primitives, not a single convex hull',
          'approximation': 'Fastener/strap holes omitted; bar/base outer bevels conservatively filled by at most 0.7mm. Press pad and finger extents exact.',
          'parts': {}}


def blocks(name):
    if name == 'frame':
        return [((.012,.096,.003), (s*.042,0,.0065)) for s in (-1,1)] + [
            ((.072,.012,.003), (0,s*.042,.0065)) for s in (-1,1)]
    if name == 'cradle':
        out = [((.038,.042,.003), (.046,0,.017))]
        for s in (-1,1):
            out += [((.038,.003,.015), (.046,s*.0195,.023)),
                    ((.010,.016,.003), (.042,s*.029,.0095)),
                    ((.010,.008,.008), (.042,s*.018,.013))]
        return out
    out = [((.004,.056,.006), (0,0,0))]
    if name == 'arm_v06':
        # V0.6：指杆下端抬高到 17.5 mm，下面粘 4×7 mm、自由高度 5.5 mm 的弹性压垫（泡棉/TPU）。
        # 第 2、4 个碰撞体是压垫接触面（被模型装到弹簧滑块上），不是打印件的一部分。
        bottom = .0175
        for s in (-1,1):
            out += [((.004,.007,.027-bottom), (0,s*.024,(.027+bottom)/2-.025)),
                    ((.004,.007,.001739), (0,s*.024,(.013739+.012)/2-.025))]
        return out
    z = (lambda a: .022-(.022-a)*20/23 if a < .022 and name != 'arm_v01' else a)
    for s in (-1,1):
        out += [((.004,.007,z(.027)-z(.012)), (0,s*.024,(z(.027)+z(.012))/2-.025)),
                ((.005 if name=='arm_v05' else .007,.008,z(.0125)-z(.0105)),
                 (0,s*.024,(z(.0125)+z(.0105))/2-.025))]
    return out
for name in ['frame', 'cradle', 'arm_v01', 'arm_v02', 'arm_v05', 'arm_v06']:
    path = ASSETS / (name + '.obj')
    mesh = trimesh.load_mesh(path, process=True)
    mesh.fix_normals()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    cache = ASSETS / (name + '_collision.json')
    if cache.exists() and json.loads(cache.read_text()).get('method') == 'cad_primitives' and json.loads(cache.read_text())['source_sha256'] == digest:
        report['parts'][name] = json.loads(cache.read_text())
        print(name, 'cached', flush=True)
        continue
    pieces = []
    for dimensions, center in blocks(name):
        box = trimesh.creation.box(dimensions)
        box.apply_translation(center)
        pieces.append((box.vertices, box.faces))
    out = []
    for i, (vertices, faces) in enumerate(pieces):
        filename = f'{name}_col_{i:02}.obj'
        trimesh.Trimesh(vertices, faces, process=False).export(ASSETS / filename)
        out.append(filename)
    mass_props = mesh.mass_properties
    entry = {
        'source_sha256': digest, 'hulls': out, 'method': 'cad_primitives',
        'watertight': bool(mesh.is_watertight),
        'volume_mm3': float(mesh.volume * 1e9),
        'solid_density_kg_m3': 1240,
        'effective_mass_fraction_assumed': .55,
        'mass_kg': float(mesh.volume * 1240 * .55),
        'center_of_mass_m': mass_props['center_mass'].tolist(),
        'inertia_kg_m2': (mass_props['inertia'] * 1240 * .55).tolist(),
        'hull_volume_excess_ratio': float(sum(trimesh.Trimesh(v, f).volume for v, f in pieces) / mesh.volume - 1),
    }
    cache.write_text(json.dumps(entry, indent=2), encoding='utf8')
    report['parts'][name] = entry
    print(name, len(pieces), 'hulls', 'mass', entry['mass_kg'], flush=True)
    if name in ('arm_v05', 'arm_v06'):
        printable = mesh.copy()
        printable.vertices *= 1000
        printable.vertices[:, 2] -= printable.bounds[0, 2]
        printable.export(ROOT / ('V05_CANDIDATE_press_arm.stl' if name == 'arm_v05' else 'V06_press_arm.stl'))
(ASSETS / 'collision_manifest.json').write_text(json.dumps(report, indent=2), encoding='utf8')
print('Collision assets ready', flush=True)
