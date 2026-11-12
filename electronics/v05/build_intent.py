"""V0.5 设计意图的唯一来源：器件选择、原理图坐标、每个引脚的网络。

python build_intent.py parts   -> 在 EDA 库里逐个确认料号，写 parts_check.json
python build_intent.py intent  -> 用 schematic_pins.json 把“引脚名 → 网络”解析成“引脚号 → 网络”，写 design_intent.json
"""
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parent

# ref, sku, 说明, 原理图坐标, 引脚网络（键可以是引脚号，也可以是 'name:引脚名'），装配方式
PARTS = [
    # ---- 电源输入 ----
    ('J1', 'C492401', '5V 输入 PZ254 2P', (100, 700), {'1': 'VIN5', '2': 'GND'}, 'THT'),
    ('USB1', 'C165948', 'USB-C 16P USB2.0', (100, 560), 'USB', 'SMT'),
    ('R7', 'C23186', '5.1k CC1 下拉', (260, 600), {'1': 'CC1', '2': 'GND'}, 'SMT'),
    ('R8', 'C23186', '5.1k CC2 下拉', (260, 520), {'1': 'CC2', '2': 'GND'}, 'SMT'),
    ('D1', 'C8678', 'SS34 VBUS→VIN5 肖特基', (260, 700), 'DIODE', 'SMT'),
    ('F1', 'C5395', 'RUEF110 自恢复保险丝', (420, 700), {'1': 'VIN5', '2': 'V5_SERVO'}, 'THT'),
    ('C1', 'C713400', '470uF 25V 电解', (560, 700), {'1': 'V5_SERVO', '2': 'GND'}, 'THT'),
    ('C2', 'C14663', '100nF 舵机电源', (680, 700), {'1': 'V5_SERVO', '2': 'GND'}, 'SMT'),
    ('J3', 'C2937625', '舵机 PZ254 3P', (820, 700), {'1': 'GND', '2': 'V5_SERVO', '3': 'SERVO_SIG'}, 'THT'),
    # ---- 3V3 ----
    ('U4', 'C6186', 'AMS1117-3.3', (420, 560), 'LDO', 'SMT'),
    ('C3', 'C15850', '10uF LDO 输入', (560, 560), {'1': 'VIN5', '2': 'GND'}, 'SMT'),
    ('C4', 'C15850', '10uF LDO 输出', (680, 560), {'1': '3V3', '2': 'GND'}, 'SMT'),
    ('C5', 'C15850', '10uF 模组 3V3', (820, 560), {'1': '3V3', '2': 'GND'}, 'SMT'),
    ('C6', 'C14663', '100nF 模组 3V3', (940, 560), {'1': '3V3', '2': 'GND'}, 'SMT'),
    # ---- 模组与启动电路 ----
    ('U3', 'C2838502', 'ESP32-C3-MINI-1-N4', (300, 330), 'MCU', 'SMT'),
    ('R9', 'C25804', '10k EN 上拉', (560, 440), {'1': '3V3', '2': 'EN'}, 'SMT'),
    ('C7', 'C15849', '1uF EN 延时', (680, 440), {'1': 'EN', '2': 'GND'}, 'SMT'),
    ('SW1', 'C318884', 'RESET 按键', (820, 440), 'SW_EN', 'SMT'),
    ('R10', 'C25804', '10k BOOT(GPIO9) 上拉', (560, 360), {'1': '3V3', '2': 'BOOT'}, 'SMT'),
    ('SW2', 'C318884', 'BOOT 按键', (820, 360), 'SW_BOOT', 'SMT'),
    ('R11', 'C25804', '10k GPIO2 绑带上拉', (560, 280), {'1': '3V3', '2': 'IO2_STRAP'}, 'SMT'),
    ('R12', 'C25804', '10k GPIO8 绑带上拉', (680, 280), {'1': '3V3', '2': 'IO8_STRAP'}, 'SMT'),
    ('J6', 'C492403', 'UART0 调试排针 4P（可不焊）', (820, 260), {'1': '3V3', '2': 'GND', '3': 'UART_TX', '4': 'UART_RX'}, 'THT'),
    # ---- 执行器（沿用 V0.4 网络名） ----
    ('R5', 'C22962', '220R PWM 串阻', (100, 160), {'1': 'PWM_IN', '2': 'SERVO_SIG'}, 'SMT'),
    ('R6', 'C25803', '100k PWM 下拉', (220, 160), {'1': 'PWM_IN', '2': 'GND'}, 'SMT'),
    ('R1', 'C23179', '470R U1 LED', (340, 160), {'1': 'KEY1', '2': 'LED1'}, 'SMT'),
    ('R3', 'C25803', '100k KEY1 下拉', (460, 160), {'1': 'KEY1', '2': 'GND'}, 'SMT'),
    ('U1', 'C29276', 'AQY212EHAX PhotoMOS', (580, 160), {'1': 'LED1', '2': 'GND', '3': 'BTN1_B', '4': 'BTN1_A'}, 'SMT'),
    ('J4', 'C492401', '输出1 PZ254 2P', (700, 160), {'1': 'BTN1_A', '2': 'BTN1_B'}, 'THT'),
    ('R2', 'C23179', '470R U2 LED', (340, 60), {'1': 'KEY2', '2': 'LED2'}, 'SMT'),
    ('R4', 'C25803', '100k KEY2 下拉', (460, 60), {'1': 'KEY2', '2': 'GND'}, 'SMT'),
    ('U2', 'C29276', 'AQY212EHAX PhotoMOS', (580, 60), {'1': 'LED2', '2': 'GND', '3': 'BTN2_B', '4': 'BTN2_A'}, 'SMT'),
    ('J5', 'C492401', '输出2 PZ254 2P', (700, 60), {'1': 'BTN2_A', '2': 'BTN2_B'}, 'THT'),
]

# 规格书推荐料号 -> 实际使用料号的替换记录
REPLACEMENTS = [
    {'refs': 'D1', 'spec': 'C2480 (SS14)', 'used': 'C8678 (SS34)',
     'reason': 'C2480 在嘉立创 EDA 器件库按编号搜索不到；SS34 C8678 为基础库、SMA 同封装、3A/40V 比 SS14 余量更大'},
    {'refs': 'U1,U2', 'spec': 'C2894775 (AQY212EH DIP-4, V0.4)', 'used': 'C29276 (AQY212EHAX SOP-4)',
     'reason': '按规格书优先换贴片版；AQY212EHAX 与 AQY212EH 同芯片、引脚定义相同，可 SMT 贴装'},
    {'refs': 'C1', 'spec': 'C407944 (EEUFR1E471)', 'used': 'C713400 (EEUFR1E471B)',
     'reason': 'C407944 立创商城库存为 0；EEUFR1E471B 同系列 470uF/25V、D10×12.5 mm、5 mm 脚距'},
    {'refs': 'C2', 'spec': 'C3689569 (100nF 插件, V0.4)', 'used': 'C14663 (100nF 0603)',
     'reason': '规格书要求阻容改 0603 基础库；C2 不在保留插件的名单里'},
    {'refs': 'R1-R6', 'spec': 'V0.4 插件电阻', 'used': '0603 基础库电阻',
     'reason': '规格书要求'},
]


def lookup_parts():
    from check_parts import check
    seen = {}
    for ref, sku, desc, _, _, mount in PARTS:
        if sku not in seen:
            seen[sku] = check(sku)
            seen[sku].update({'refs': [], 'description': desc, 'mount': mount})
        seen[sku]['refs'].append(ref)
    out = []
    for sku, d in seen.items():
        eda = d['eda'] or {}
        cls = eda.get('jlc_part_class')
        d['jlc_library'] = {'Basic Part': '基础库', 'Extended Part': '扩展库'}.get(cls, '未标注')
        d['smt_assemblable'] = d['mount'] == 'SMT' and cls in ('Basic Part', 'Extended Part') and (d.get('lcsc_stock') or 0) > 0
        d['qty'] = len(d['refs'])
        d['stock_ok'] = (d.get('lcsc_stock') or 0) >= d['qty'] * 5
        out.append(d)
    doc = {
        'checked_at': '2026-11-12',
        'method': 'eda.lib_Device.search(LCSC 编号) 精确匹配 supplierId，读取封装与 "JLCPCB Part Class"；库存取立创商城公开商品接口 stockNumber（嘉立创 SMT 仓库存未单独核对，下单页会再显示）',
        'parts': out,
        'replacements': REPLACEMENTS,
    }
    (R / 'parts_check.json').write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding='utf-8')
    for d in out:
        print(d['lcsc'], d['qty'], d.get('lcsc_stock'), d['jlc_library'], d['mount'], (d['eda'] or {}).get('footprint'))


if __name__ == '__main__':
    if sys.argv[1] == 'parts':
        lookup_parts()


def positions():
    # 5 列网格；U3 单独放右侧，USB1 占左上两格（引脚间距 10，需要更多空间放端口）
    pos, i = {'U3': [1000, 400], 'USB1': [160, 155]}, 0
    for ref, *_ in PARTS:
        if ref in pos:
            continue
        while i in (0, 5):
            i += 1
        pos[ref] = [140 + (i % 5) * 160, 110 + (i // 5) * 90]
        i += 1
    return pos


def write_intent(pins=None):
    pos = positions()
    parts = []
    for ref, sku, desc, _, nets, mount in PARTS:
        entry = {'ref': ref, 'sku': sku, 'description': desc, 'mount': mount, 'xy_sch': pos[ref]}
        if pins is not None:
            entry['nets'] = resolve(ref, nets, pins[ref])
        parts.append(entry)
    doc = {
        'revision': '0.5',
        'board_mm': [60, 40, 1.6],
        'layers': 2,
        'copper_oz': 1,
        'mount_holes_mm': [[4, 4, 3.2], [56, 4, 3.2], [56, 36, 3.2], [4, 36, 3.2]],
        'description': 'ESP32-C3-MINI-1-N4 integrated carrier: one 5V positional servo and two isolated remote-button outputs, USB-C power/programming. Does not switch mains.',
        'gpio': {'GPIO4': 'PWM_IN', 'GPIO5': 'KEY1', 'GPIO6': 'KEY2', 'GPIO9': 'BOOT', 'GPIO18': 'USB_DN', 'GPIO19': 'USB_DP',
                 'GPIO20': 'UART_RX', 'GPIO21': 'UART_TX', 'GPIO2': 'IO2_STRAP (10k pull-up)', 'GPIO8': 'IO8_STRAP (10k pull-up)', 'EN': 'EN'},
        'parts': parts,
    }
    if pins is not None:
        nets = {}
        for p in parts:
            for n, net in p['nets'].items():
                if net:
                    nets.setdefault(net, []).append(p['ref'] + '.' + n)
        doc['nets'] = dict(sorted(nets.items()))
    (R / 'design_intent.json').write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__' and sys.argv[1] == 'place':
    write_intent()
    docs = {'project': '77a7169cd0272fe0e42718323b556aaee3a8616ec5905cc9b01f917bfeb33959',
            'schematic': '62fec29a44376eb3', 'schematic_page': '32e98844194e3702', 'pcb': 'e5d7cd18df0d2b54'}
    (R / 'project_documents.json').write_text(json.dumps(docs, indent=1), encoding='utf-8')


SPECIAL = {
    'USB': {'name:VBUS': 'VBUS', 'name:GND': 'GND', 'name:EH': 'GND', 'name:CC1': 'CC1', 'name:CC2': 'CC2',
            'name:DP1': 'USB_DP', 'name:DP2': 'USB_DP', 'name:DN1': 'USB_DN', 'name:DN2': 'USB_DN',
            'name:SBU1': None, 'name:SBU2': None},
    'DIODE': {'name:A': 'VBUS', 'name:K': 'VIN5'},
    'LDO': {'name:GND': 'GND', 'name:VIN': 'VIN5', 'name:VOUT': '3V3'},
    'SW_EN': {'name:A': 'EN', 'name:B': 'EN', 'name:C': 'GND', 'name:D': 'GND'},
    'SW_BOOT': {'name:A': 'BOOT', 'name:B': 'BOOT', 'name:C': 'GND', 'name:D': 'GND'},
    'MCU': {'name:GND': 'GND', 'name:3V3': '3V3', 'name:EN': 'EN', 'name:IO2': 'IO2_STRAP', 'name:IO8': 'IO8_STRAP',
            'name:IO9': 'BOOT', 'name:IO4': 'PWM_IN', 'name:IO5': 'KEY1', 'name:IO6': 'KEY2',
            'name:IO18': 'USB_DN', 'name:IO19': 'USB_DP', 'name:RXD0': 'UART_RX', 'name:TXD0': 'UART_TX',
            'name:IO0': None, 'name:IO1': None, 'name:IO3': None, 'name:IO7': None, 'name:IO10': None, 'name:NC': None},
}


def resolve(ref, nets, pins):
    table = SPECIAL[nets] if isinstance(nets, str) else nets
    out = {}
    for p in pins:
        if p['n'] in table:
            out[p['n']] = table[p['n']]
        elif 'name:' + p['name'] in table:
            out[p['n']] = table['name:' + p['name']]
        else:
            raise SystemExit(f'{ref} pin {p["n"]}/{p["name"]} has no net')
    return dict(sorted(out.items(), key=lambda kv: (len(kv[0]), kv[0])))


if __name__ == '__main__' and sys.argv[1] == 'intent':
    pins = {p['ref']: p['pins'] for p in json.loads((R / 'schematic_pins.json').read_text(encoding='utf-8'))}
    write_intent(pins)
    d = json.loads((R / 'design_intent.json').read_text(encoding='utf-8'))
    for net, members in d['nets'].items():
        print(net, len(members), ' '.join(members) if len(members) < 12 else '')



