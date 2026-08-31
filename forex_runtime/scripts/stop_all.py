"""إيقاف خدمات QUANT_NQ المعروفة فقط، بدون تشغيل واجهة سطح مكتب."""
from __future__ import annotations
import os
import signal
import time

PORTS = {8010, 8020, 8090, 8092, 8093, 8098}

def main() -> int:
    try:
        import psutil
    except ImportError:
        print("psutil غير مثبت — ثبّت requirements.txt")
        return 1
    me = os.getpid()
    pids = set()
    for c in psutil.net_connections(kind="tcp"):
        if c.laddr and c.laddr.port in PORTS and c.pid and c.pid != me:
            pids.add(c.pid)
    if not pids:
        print("لا توجد خدمات QUANT_NQ عاملة على المنافذ المحددة.")
        return 0
    procs = []
    for pid in sorted(pids):
        try:
            p = psutil.Process(pid)
            print(f"إيقاف PID={pid}: {p.name()}")
            p.terminate(); procs.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _, alive = psutil.wait_procs(procs, timeout=5)
    for p in alive:
        try: p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    print("تم إيقاف خدمات QUANT_NQ المحددة.")
    return 0

if __name__ == "__main__": raise SystemExit(main())
