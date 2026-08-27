#!/usr/bin/env python3
from __future__ import annotations
import json
import urllib.request

def main():
    marker = __import__('pathlib').Path(__file__).resolve().parents[2] / 'governance' / 'PACKAGE_BUILD.txt'
    if marker.is_file():
        print('Package:', marker.read_text(encoding='utf-8').splitlines()[0])
    try:
        with urllib.request.urlopen('http://127.0.0.1:8010/api/atoms', timeout=8) as r:
            atoms=json.loads(r.read().decode('utf-8'))
    except Exception as exc:
        print('Core is not reachable:', exc); return 2
    degraded=[a for a in atoms if (a.get('health') or {}).get('state') == 'degraded']
    failed=[a for a in atoms if a.get('state') == 'failed' or (a.get('health') or {}).get('state') == 'unhealthy']
    print('Total:',len(atoms),' Degraded:',len(degraded),' Failed/Unhealthy:',len(failed))
    print('\nDEGRADED:')
    for a in degraded:
        h=a.get('health') or {}; print('#%s %s :: %s' % (a.get('id'),a.get('name_ar') or a.get('name'),h.get('message') or '(health check not run yet)'))
    print('\nFAILED OR UNHEALTHY:')
    for a in failed:
        h=a.get('health') or {}; print('#%s %s :: %s' % (a.get('id'),a.get('name_ar') or a.get('name'),h.get('message') or a.get('last_error') or 'unknown'))
    return 0
if __name__=='__main__': raise SystemExit(main())
