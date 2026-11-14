"""Control box V0.4 for the Switch Robot Carrier V0.5: the V0.3 box with a USB-C opening.

V0.3 (fit-check/build_case_v03_mcp.py, Blender) was drawn before the V0.5 board existed: its
two cable slots do not line up with the V0.5 USB-C (centre of a long edge), and the
receptacle sits 8 mm behind the outer wall face (6 mm gap + 2 mm wall), so a plug cannot
reach it through a small hole. V0.4 rebuilds the same solid with manifold3d (same boxes,
cylinders and boolean order as the Blender script, 64-segment cylinders), drops the old
18x8 power slot (V0.5 is powered through USB-C; J1 stays unused), and cuts a 14x9 mm
opening in the -y wall centred on the USB-C, large enough for a standard plug overmold to
pass through the wall and reach the receptacle. The +y signal slot (servo / J4 / J5 wires)
and everything else are unchanged; the V0.3 lid still fits.

Coordinates are the assembly's (mm): box centre (114, -14), box bottom z = 5, PCB on the
posts at z 11.9..13.5, USB-C on the board's bottom edge (V0.5 y = 0) facing -y.

Run: python -I enclosure/build_case_v04.py   (needs manifold3d, trimesh, numpy)
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import Manifold, set_circular_segments

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
set_circular_segments(64)
CX, CY = 114.0, -14.0

# Assumptions about parts that are not measured (see README):
PCB_Z0, PCB_T = 11.9, 1.6                    # board bottom on the 5 mm posts, 1.6 mm board
USB_BODY = (8.94, 7.35, 3.26)                # TYPE-C-31-M-12 receptacle, datasheet-class size
USB_Z = PCB_Z0 + PCB_T + USB_BODY[2] / 2     # receptacle centre height
PLUG_OVERMOLD = (12.5, 6.5)                  # common USB-C cable plug overmold (w, h)
OPENING = (14.0, 9.0)                        # V0.4 opening (w, h)


def box(size, centre):
    return Manifold.cube(size, center=True).translate(centre)


def cyl(r, h, centre):
    return Manifold.cylinder(h, r, center=True).translate(centre)


def case(version):
    c = box((76, 56, 30), (CX, CY, 20)) - box((72, 52, 32), (CX, CY, 23))
    for x in (-26, 26):
        for y in (-16, 16):
            c = c + cyl(2.8, 5, (CX + x, CY + y, 9.4))
            c = c - cyl(1.15, 8, (CX + x, CY + y, 10))
    for x in (-34, 34):
        for y in (-24, 24):
            c = c + cyl(3, 25, (CX + x, CY + y, 19.5))
            c = c - cyl(1.15, 31, (CX + x, CY + y, 21))
    if version == 'v03':
        c = c - box((18, 8, 8), (101, -42, 16))                # old power slot
    else:
        c = c - box((OPENING[0], 8, OPENING[1]), (CX, -41, USB_Z))   # USB-C opening, -y wall
    c = c - box((24, 8, 8), (123, 14, 16))                     # signal slot, +y wall (unchanged)
    return c


def to_trimesh(m):
    mesh = m.to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=True)


def overlap(a, b):
    return (a ^ b).volume()


def main():
    report = {}
    v03 = case('v03')
    ref = trimesh.load(ROOT / 'fit-check' / 'V03_PRINT_gateway_case_76x56x30.stl')
    report['v03_rebuild_volume_mm3'] = round(v03.volume(), 1)
    report['v03_blender_stl_volume_mm3'] = round(float(ref.volume), 1)

    v04 = case('v04')
    pcb = box((60, 40, PCB_T), (CX, CY, PCB_Z0 + PCB_T / 2))
    board_edge_y = CY - 20                                    # V0.5 y = 0 edge, facing -y
    receptacle = box(USB_BODY, (CX, board_edge_y + USB_BODY[1] / 2 - 0.5, USB_Z))
    # plug overmold from the receptacle face out through the wall, 25 mm long
    plug = box((PLUG_OVERMOLD[0], 25, PLUG_OVERMOLD[1]), (CX, board_edge_y - 0.5 - 12.5, USB_Z))
    report['v04_volume_mm3'] = round(v04.volume(), 1)
    report['pcb_case_overlap_mm3'] = abs(round(overlap(v04, pcb), 3))
    report['receptacle_case_overlap_mm3'] = round(overlap(v04, receptacle), 3)
    report['plug_overmold_case_overlap_mm3'] = round(overlap(v04, plug), 3)
    report['plug_overmold_case_overlap_v03_mm3'] = round(overlap(v03, plug), 3)
    report['opening_mm'] = {'width': OPENING[0], 'height': OPENING[1], 'centre_x_from_box_centre': 0,
                            'z_from_box_bottom': [round(USB_Z - OPENING[1] / 2 - 5, 2),
                                                  round(USB_Z + OPENING[1] / 2 - 5, 2)],
                            'wall': '-y long wall'}
    report['receptacle_face_to_outer_wall_mm'] = round(board_edge_y - 0.5 - (CY - 28), 2)
    report['assumptions'] = {'pcb_bottom_z': PCB_Z0, 'usb_body_mm': USB_BODY, 'plug_overmold_mm': PLUG_OVERMOLD}

    tm = to_trimesh(v04)
    report['v04_watertight'] = bool(tm.is_watertight)
    report['v04_bounds_mm'] = np.round(tm.bounds, 2).tolist()
    out = tm.copy()
    out.apply_translation([-CX, -CY, -5])                     # same placement rule as the V0.3 STL export
    out.export(HERE / 'PRINT_04_control_box_v04.stl')
    (HERE / 'case_v04_checks.json').write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=1, ensure_ascii=False))
    ok = (report['pcb_case_overlap_mm3'] == 0 and report['receptacle_case_overlap_mm3'] == 0
          and report['plug_overmold_case_overlap_mm3'] == 0 and report['v04_watertight'])
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
