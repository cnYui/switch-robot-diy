"""在嘉立创 EDA 器件库按 LCSC 编号逐个确认器件（封装、基础/扩展库），并查询立创商城公开库存。

用法: python check_parts.py C2838502 C6186 ...   -> 打印结果
      python check_parts.py --search 关键词       -> 打印 EDA 搜索结果摘要
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eda_client import execute


def eda_lookup(code):
    r = execute('return await eda.lib_Device.search(' + json.dumps(code) + ');') or []
    hit = [x for x in r if x.get('supplierId') == code]
    # 同一个 LCSC 编号可能有多个 EDA 器件条目；首条缺 JLCPCB Part Class 时再按型号搜一次，优先用属性完整的条目
    if hit and not any((x.get('otherProperty') or {}).get('JLCPCB Part Class') for x in hit) and hit[0].get('manufacturerId'):
        r2 = execute('return await eda.lib_Device.search(' + json.dumps(hit[0]['manufacturerId']) + ');') or []
        hit += [x for x in r2 if x.get('supplierId') == code]
    hit.sort(key=lambda x: not (x.get('otherProperty') or {}).get('JLCPCB Part Class'))
    if not hit:
        return None
    x = hit[0]
    op = x.get('otherProperty', {})
    return {
        'name': x['name'], 'manufacturer_part': x.get('manufacturerId'),
        'manufacturer': x.get('manufacturer'),
        'footprint': x.get('footprintName'), 'library_uuid': x['libraryUuid'],
        'device_uuid': x['uuid'], 'jlc_part_class': op.get('JLCPCB Part Class'),
        'supplier_footprint': op.get('Supplier Footprint'),
        'description': x.get('description'),
    }


def lcsc_stock(code):
    url = 'https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=' + code
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'switch-robot-parts-check/1.0'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            d = json.load(resp)
        r = d.get('result') or {}
        return {'lcsc_stock': r.get('stockNumber'), 'lcsc_model': r.get('productModel'),
                'lcsc_package': r.get('encapStandard')}
    except Exception as exc:  # 网络失败时如实记录
        return {'lcsc_stock': None, 'lcsc_error': str(exc)}


def check(code):
    out = {'lcsc': code, 'eda': eda_lookup(code)}
    out.update(lcsc_stock(code))
    return out


if __name__ == '__main__':
    if sys.argv[1] == '--search':
        r = execute('return await eda.lib_Device.search(' + json.dumps(sys.argv[2]) + ');') or []
        for x in r[:25]:
            op = x.get('otherProperty', {})
            print(x.get('supplierId'), '|', x.get('manufacturerId'), '|', x.get('footprintName'), '|',
                  op.get('JLCPCB Part Class'))
    else:
        print(json.dumps([check(c) for c in sys.argv[1:]], ensure_ascii=False, indent=1))


