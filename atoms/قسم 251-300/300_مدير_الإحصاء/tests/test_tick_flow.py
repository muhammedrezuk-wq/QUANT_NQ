# اختبار تحويل قسم 300 للتكة (Owner 2026-08-22): وحدات تنشر weight/confidence
# على كل تكة، والمدير يجمعها على دورة تكة.
import asyncio, importlib.util, sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

# نحمّل وحدة 301 كاملة ومدير 300
import types
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); sys.modules[name]=m; spec.loader.exec_module(m); return m

u301 = load("_u301", str(folder.parent / "301_المتوسط" / "atom.py"))
m300 = load("_m300", str(folder / "atom.py"))

class L:
    def __getattr__(self, n): return lambda *a, **k: None
class B:
    def __init__(self): self.e=[]
    def subscribe(self, *a): pass
    async def publish(self, n, p): self.e.append((n,p))

async def main():
    # 1) وحدة 301 على تكة
    b=B(); a=u301.Atom()
    await a.initialize(u301.AtomContext(301, {'window_size':3}, L(), b.publish, b.subscribe))
    await a.start()
    tick={'symbol':'NQ','account_id':'A','broker':'BR','price':100.0,'sequence':1,
          'timestamp':1000.0,'timeframe':'tick'}
    await a._on_tick(tick)
    out=[p for n,p in b.e if n==u301.EVENT_OUT]
    assert out, "301 لم ينشر"
    last=out[-1]
    assert last.get('weight') is not None, "301 بلا وزن"
    assert last.get('confidence') is not None, "301 بلا ثقة"
    assert last.get('ready') is True, "301 غير ready"
    assert last['cycle_id'].endswith('1'), last['cycle_id']
    print("ok 301 ينشر وزن/ثقة/ready على تكة, cycle_id=%s" % last['cycle_id'])

    # 2) المدير 300 يجمع
    b2=B(); mgr=m300.Atom()
    await mgr.initialize(m300.AtomContext(300, {'timeout_seconds':5.0}, L(), b2.publish, b2.subscribe))
    await mgr.start()
    await mgr._on_tick(tick)
    # محاكاة وصول وحدة واحدة من 301
    await mgr._on_unit_state(last)
    print("ok مدير 300 جمع وحدة 301، open=%d" % len(mgr._cycles))

asyncio.run(main())
print("PASS")
