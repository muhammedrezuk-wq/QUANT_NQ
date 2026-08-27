import asyncio,importlib.util,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));s=importlib.util.spec_from_file_location('t563',folder/'atom.py');m=importlib.util.module_from_spec(s);sys.modules['t563']=m;s.loader.exec_module(m)
class L:
 def __getattr__(self,n):return lambda *a,**k:None
class B:
 def __init__(self):self.e=[]
 def subscribe(self,*a):pass
 async def publish(self,n,p):self.e.append((n,p))
async def main():
 with tempfile.TemporaryDirectory() as td:
  b=B();a=m.Atom();await a.initialize(m.AtomContext(563,{'dedupe_db_path':str(Path(td)/'j.db')},L(),b.publish,b.subscribe));await a.start();await a._on_account({'account_id':'A','broker':'BR'});await a._on_specs({'symbols':[{'account_id':'A','symbol':'NQ','point':.25,'tick_value':5,'tick_size':.25}]});await a._on_requested({'account_id':'A','broker':'BR','request_id':'r','symbol':'NQ','side':'BUY','reference_price':100});event={'account_id':'A','broker':'BR','request_id':'r','event_type':'OPENED','source_row_id':1,'symbol':'NQ','entry_price':101,'volume':1};await a._on_event(event);assert [p for n,p in b.e if n==m.EVENT_ACK][-1]['slippage_points']==4;await a._on_event(event);assert a._duplicates==1;await a._on_event({'account_id':'A','broker':'BR','event_type':'CLOSED','source_row_id':2,'symbol':'NQ','profit':10,'commission':0,'swap':0,'fee':0});assert [p for n,p in b.e if n==m.EVENT_OUT][-1]['profit']==10;await a._on_event({'account_id':'A','broker':'BR','event_type':'OPENED'});assert [p for n,p in b.e if n==m.EVENT_REJECTED][-1]['reason']=='MISSING_DURABLE_EVENT_ID_OR_SCOPE'
  # بند 22 حزمة ت (ت١): حدث الوسيط لا يحمل الهوية — تُستَرجَع من سجل الطلب
  # الدائم (قرار→طلب→أمر→نتيجة صامد على أي إقلاع)، والغائب None + إنذار.
  await a._on_requested({'account_id':'A','broker':'BR','request_id':'r2','symbol':'NQ','side':'BUY','reference_price':100,'decision_id':'D-5','gate_request_id':'G-5'})
  await a._on_event({'account_id':'A','broker':'BR','request_id':'r2','event_type':'OPENED','source_row_id':3,'symbol':'NQ','entry_price':100,'volume':1})
  ack=[p for n,p in b.e if n==m.EVENT_ACK][-1];assert ack['decision_id']=='D-5' and ack['gate_request_id']=='G-5' and 'identity_warnings' not in ack,ack
  await a._on_event({'account_id':'A','broker':'BR','request_id':'r2','event_type':'CLOSED','source_row_id':4,'symbol':'NQ','profit':-5,'commission':0,'swap':0,'fee':0})
  out=[p for n,p in b.e if n==m.EVENT_OUT][-1];assert out['decision_id']=='D-5' and out['gate_request_id']=='G-5' and 'identity_warnings' not in out,out
  # الحدث المغلق الأول (بلا request_id) خرج بهوية None ومُعلَنة — لا اختراع
  first_out=[p for n,p in b.e if n==m.EVENT_OUT][0]
  assert first_out['decision_id'] is None and first_out['identity_warnings']==['identity_incomplete'],first_out
  print('563 durable confirmation tests passed')
if __name__=='__main__':asyncio.run(main())
