"""临时放置一个器件，回读符号引脚位置，检查是否有引脚重叠（会造成原理图误连），然后删除。

python probe_symbol.py C2765186 ...
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eda_client import execute
from check_parts import check

CODE = '''
const c=await eda.sch_PrimitiveComponent.create({libraryUuid:LIB,uuid:DEV},2000,2000,"",0,false,true,true);
const pins=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
const o=pins.map(p=>[p.getState_PinNumber(),p.getState_PinName(),p.getState_X()-2000,p.getState_Y()-2000]);
await eda.sch_PrimitiveComponent.delete([c.getState_PrimitiveId()]);
return o;
'''

for code in sys.argv[1:]:
    d = check(code)
    e = d['eda']
    r = execute(CODE.replace('LIB', json.dumps(e['library_uuid'])).replace('DEV', json.dumps(e['device_uuid'])))
    pos = {}
    for n, name, x, y in r:
        pos.setdefault((x, y), []).append(n + '/' + name)
    print(code, d.get('lcsc_stock'), e['jlc_part_class'], e['footprint'])
    print('  overlaps:', [v for v in pos.values() if len(v) > 1])
    print('  pins:', r)
