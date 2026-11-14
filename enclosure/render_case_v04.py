"""Two section drawings of the V0.4 control box with the V0.5 board, USB-C receptacle and a plug.

Left: horizontal cut at the USB-C centre height, seen from above. Right: the -y wall seen
from outside (cut 1 mm inside the outer face). Grey = box, green = board, light = receptacle,
dark outline = plug overmold. Coordinates: STL frame (box centred on x/y, bottom z = 0).
"""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import trimesh

HERE = Path(__file__).resolve().parent
plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
case = trimesh.load(HERE / 'PRINT_04_control_box_v04.stl')
USB_Z = 6.9 + 1.6 + 3.26 / 2
BOARD_EDGE_Y = -20.0


def draw_section(ax, plane_origin, plane_normal, to2d):
    sec = case.section(plane_origin=plane_origin, plane_normal=plane_normal)
    loops = [[to2d(p) for p in poly] for poly in sec.discrete]

    def area(xy):
        return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(xy, xy[1:] + xy[:1]))) / 2

    loops.sort(key=area, reverse=True)
    outer = loops[0]
    inside = [l for l in loops[1:] if all(min(p[i] for p in outer) <= l[0][i] <= max(p[i] for p in outer) for i in (0, 1))]
    for i, xy in enumerate(loops):
        hole = i > 0 and xy in inside and len(loops) > 1 and plane_normal[2] == 0
        ax.fill([p[0] for p in xy], [p[1] for p in xy], facecolor='white' if hole else '#b8c2c6',
                edgecolor='#59656b', lw=0.8, zorder=1 if not hole else 1.5)


fig, (a, b) = plt.subplots(1, 2, figsize=(13, 5.6), dpi=130)
draw_section(a, [0, 0, USB_Z], [0, 0, 1], lambda p: (p[0], p[1]))
a.add_patch(Rectangle((-30, -20), 60, 40, facecolor='#1f7a4d', alpha=0.35, edgecolor='#1f7a4d', zorder=3, label='V0.5 板（60×40）'))
a.add_patch(Rectangle((-4.47, BOARD_EDGE_Y - 0.5), 8.94, 7.35, facecolor='#d9dee2', edgecolor='#444', zorder=3, label='USB-C 母座'))
a.add_patch(Rectangle((-6.25, BOARD_EDGE_Y - 0.5 - 18), 12.5, 18, facecolor='none', edgecolor='#222', lw=1.6,
                      ls='--', zorder=3, label='插头外壳 12.5×6.5'))
a.set_title(f'俯视剖面（z = {USB_Z:.1f} mm，USB-C 中心高度）')
a.set_xlim(-42, 42); a.set_ylim(-48, 32); a.set_aspect('equal'); a.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=8)
a.set_xlabel('x mm'); a.set_ylabel('y mm')

draw_section(b, [0, -27.0, 0], [0, 1, 0], lambda p: (p[0], p[2]))
b.add_patch(Rectangle((-30, 6.9), 60, 1.6, facecolor='#1f7a4d', alpha=0.6, edgecolor='#1f7a4d', zorder=3, label='板（在墙后 6 mm）'))
b.add_patch(Rectangle((-6.25, USB_Z - 3.25), 12.5, 6.5, facecolor='none', edgecolor='#222', lw=1.6, ls='--',
                      zorder=3, label='插头外壳'))
b.add_patch(Rectangle((-4.47, USB_Z - 1.63), 8.94, 3.26, facecolor='#d9dee2', edgecolor='#444', zorder=3, label='USB-C 母座'))
b.set_title('从外面看 USB-C 那面墙（开口 14×9 mm）')
b.set_xlim(-42, 42); b.set_ylim(-3, 33); b.set_aspect('equal'); b.legend(loc='upper center', bbox_to_anchor=(0.5, -0.18), ncol=3, fontsize=8)
b.set_xlabel('x mm'); b.set_ylabel('z mm（盒底 = 0）')
fig.tight_layout()
fig.savefig(HERE / 'case_v04_fit.png', facecolor='white')
print(HERE / 'case_v04_fit.png')
