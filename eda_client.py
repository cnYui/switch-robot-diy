"""通过嘉立创官方本地桥接调用编辑器，并保存每次调用的结果。"""
import json
from pathlib import Path
import sys
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent

def execute(code):
    request = urllib.request.Request(
        'http://127.0.0.1:49620/execute',
        data=json.dumps({'code': code}).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode('utf-8', errors='replace')) from None
    if not result.get('success'):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result.get('result')

if __name__ == '__main__':
    source = Path(sys.argv[1])
    result = execute(source.read_text(encoding='utf-8-sig'))
    output = source.with_suffix('.result.json')
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))
