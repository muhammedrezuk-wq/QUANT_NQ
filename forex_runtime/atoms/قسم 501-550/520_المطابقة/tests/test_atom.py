import asyncio
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[3]; folder=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root)); sys.path.insert(0,str(folder))
spec=importlib.util.spec_from_file_location("_atom520_work",folder/"atom.py"); mod=importlib.util.module_from_spec(spec); sys.modules["_atom520_work"]=mod; spec.loader.exec_module(mod)
class Log:
    def debug(self,*a,**k): pass
    def info(self,*a,**k): pass
    def warning(self,*a,**k): pass
    def error(self,*a,**k): pass
    def critical(self,*a,**k): pass
class Bus:
    def __init__(self): self.events=[]
    def subscribe(self,*a): pass
    async def publish(self,n,p): self.events.append((n,p))
    def ctx(self,p): return mod.AtomContext(520,{"state_path":p},Log(),self.publish,self.subscribe)
async def main():
    with tempfile.TemporaryDirectory() as t:
        p=str(Path(t)/"desired.json"); b=Bus(); a=mod.Atom(); await a.initialize(b.ctx(p)); await a.start()
        await a._on_desired({"account_id":"A","broker":"BR","symbol":"NQ","version":1,"timestamp":1,"legs":[{"ticket":"7","side":"BUY","volume":1,"stop_loss":99}]})
        assert json.loads(Path(p).read_text())["desired"]
        await a._on_actual({"source":"broker","timestamp":2,"positions":[{"account_id":"A","broker":"BR","symbol":"NQ","ticket":"7","side":"BUY","volume":2,"stop_loss":99}]})
        assert a.state(mod.scope("A","NQ","BR"))["classification_counts"]["MISMATCH"]==1
        # v3.2.0: a pending leg (no ticket) is intent, not loss -- gate stays open
        await a._on_desired({"account_id":"A","broker":"BR","symbol":"GC","version":1,"timestamp":3,"legs":[{"leg_id":"L1","request_id":"L1","side":"BUY","volume":1}]})
        await a._on_actual({"source":"broker","timestamp":4,"account_id":"A","broker":"BR","positions":[]})
        st=a.state(mod.scope("A","GC","BR"))
        assert st["status"]=="MATCH" and st["classification_counts"]["PENDING_OPEN"]==1 and st["warnings"]==["PENDING_OPEN_LEGS"]
        # the ack binds the broker ticket onto the desired leg
        await a._on_ack({"command_id":"L1","ticket":"55","account_id":"A","broker":"BR","symbol":"GC"})
        await a._on_actual({"source":"broker","timestamp":5,"account_id":"A","broker":"BR","positions":[{"account_id":"A","broker":"BR","symbol":"GC","ticket":"55","side":"BUY","volume":1}]})
        st=a.state(mod.scope("A","GC","BR"))
        assert st["status"]=="MATCH" and st["classification_counts"]["MATCH"]==1
        # a TICKETED leg vanishing at the broker still alarms
        await a._on_actual({"source":"broker","timestamp":6,"account_id":"A","broker":"BR","positions":[]})
        st=a.state(mod.scope("A","GC","BR"))
        assert st["status"]=="ATTENTION" and st["classification_counts"]["MISSING_AT_BROKER"]==1
        # binding survives persistence
        assert any(x.get("ticket")=="55" for rec in json.loads(Path(p).read_text())["desired"] for x in rec["legs"])
    print("520 P0 tests passed")
if __name__=="__main__": asyncio.run(main())
