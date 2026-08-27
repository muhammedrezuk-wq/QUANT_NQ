import asyncio
import importlib.util
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location("_atom524_final", folder / "atom.py")
mod = importlib.util.module_from_spec(spec); sys.modules["_atom524_final"] = mod; spec.loader.exec_module(mod)

class Logger:
    def debug(self,*a,**k): pass
    def info(self,*a,**k): pass
    def warning(self,*a,**k): pass
    def error(self,*a,**k): pass
    def critical(self,*a,**k): pass

class Bus:
    def __init__(self): self.events=[]
    def subscribe(self,*a): pass
    async def publish(self,name,payload): self.events.append((name,payload))
    def context(self,cfg=None):
        return mod.AtomContext(524,cfg or {"milestone_mult":2,"extract_fraction":.5,
            "full_targets":{},"default_full_target":0},Logger(),self.publish,self.subscribe)

def ledger(gross, R=50, floating=0, account="A", symbol="X"):
    return {"account_id":account,"symbol":symbol,"R":R,"budget":R,"budgeted":True,
            "realized_gross":gross,"K":gross,"X":0,"floating_economic":floating}

def events(bus,name): return [p for n,p in bus.events if n==name]

async def main():
    b=Bus(); a=mod.Atom(); await a.initialize(b.context()); await a.start()
    for gross in (50,100,200): await a._on_ledger({"ledgers":[ledger(gross)]})
    assert [p["amount"] for p in events(b,mod.EVENT_PARTIAL)] == [25,50,100]
    await a._on_ledger({"ledgers":[ledger(200)]})
    assert len(events(b,mod.EVENT_PARTIAL)) == 3
    print("OK — R/2R/4R: 25 ثم 50 ثم 100، وكل مرحلة مرة واحدة")

    b2=Bus(); a2=mod.Atom(); await a2.initialize(b2.context()); await a2.start()
    await a2._on_ledger({"ledgers":[ledger(400)]})
    req=events(b2,mod.EVENT_PARTIAL)
    assert [p["amount"] for p in req] == [25,50,100,200]
    for p in req: await a2._on_confirm({"extraction_id":p["extraction_id"],"actual_amount":p["amount"]})
    extracted=events(b2,mod.EVENT_EXTRACTED)
    assert sum(p["amount"] for p in extracted)==375
    assert not a2._pending
    print("OK — قفزة إلى 400 تُخرج 25+50+100+200 = 375 بعد تأكيد فعلي")

    b3=Bus(); a3=mod.Atom(); await a3.initialize(b3.context()); await a3.start()
    await a3._on_ledger({"ledgers":[ledger(0,floating=999)]})
    assert not events(b3,mod.EVENT_PARTIAL)
    print("OK — الربح العائم وحده لا يطلق التخريج")

    b4=Bus(); a4=mod.Atom(); await a4.initialize(b4.context()); await a4.start()
    await a4._on_ledger({"ledgers":[ledger(300)]})
    req=events(b4,mod.EVENT_PARTIAL); assert [p["amount"] for p in req]==[25,50,100]
    await a4._on_ledger({"ledgers":[ledger(350)]})
    assert len(events(b4,mod.EVENT_PARTIAL))==3
    print("OK — التكرار/التراجع لا يعيدان مرحلة صُدرت")

    b5=Bus(); a5=mod.Atom(); await a5.initialize(b5.context({"milestone_mult":2,"extract_fraction":.25,"full_targets":{"A|X":300},"default_full_target":0})); await a5.start()
    await a5._on_ledger({"ledgers":[ledger(300)]})
    assert [p["amount"] for p in events(b5,mod.EVENT_PARTIAL)]==[12.5,25,50]
    assert len(events(b5,mod.EVENT_FULL))==1
    print("OK — مقابض R والتخريج الكامل الاختياري")

    b6=Bus(); a6=mod.Atom(); await a6.initialize(b6.context()); assert (await a6.health_check()).state==mod.HealthState.UNHEALTHY; await a6.start(); assert (await a6.health_check()).state==mod.HealthState.DEGRADED; await a6._on_ledger({"ledgers":[ledger(1)]}); assert (await a6.health_check()).state==mod.HealthState.HEALTHY
    print("OK — الصحة UNHEALTHY→DEGRADED→HEALTHY")

if __name__ == "__main__": asyncio.run(main())
