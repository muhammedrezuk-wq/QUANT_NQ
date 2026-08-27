import asyncio,importlib.util,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));s=importlib.util.spec_from_file_location('t560',folder/'atom.py');m=importlib.util.module_from_spec(s);sys.modules['t560']=m;s.loader.exec_module(m)
class L:
 def __getattr__(self,n):return lambda *a,**k:None
class B:
 def __init__(self):self.e=[]
 def subscribe(self,*a):pass
 async def publish(self,n,p):self.e.append((n,p))
async def main():
 b=B();a=m.Atom();await a.initialize(m.AtomContext(560,{'max_adverse_points':50,'max_reject_rate':.25,'min_samples':1},L(),b.publish,b.subscribe));await a.start();await a._on_account({'account_id':'A','broker':'BR'});await a._on_specs({'symbols':[{'account_id':'A','symbol':'BTCUSD','point':1}]});await a._on_request({'account_id':'A','broker':'BR','symbol':'BTCUSD','request_id':'r','side':'BUY','reference_price':100});await a._on_trade({'event_type':'OPENED','request_id':'r','entry_price':102});out=[p for n,p in b.e if n==m.EVENT_OUT][-1];assert out['adverse_max_points']==2 and out['broker']=='BR';await a._on_request({'account_id':'A','broker':'BR','symbol':'X','request_id':'x','side':'BUY','reference_price':100});await a._on_trade({'event_type':'OPENED','request_id':'x','entry_price':101});assert [p for n,p in b.e if n==m.EVENT_OUT][-1]['unmeasurable']==1;print('560 scoped point tests passed')
if __name__=='__main__':asyncio.run(main())
