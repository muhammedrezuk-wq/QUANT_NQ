import asyncio,importlib.util,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));spec=importlib.util.spec_from_file_location('_t516',folder/'atom.py');m=importlib.util.module_from_spec(spec);sys.modules['_t516']=m;spec.loader.exec_module(m)
class L:
 def __getattr__(self,n):return lambda *a,**k:None
class B:
 def __init__(self):self.e=[]
 def subscribe(self,*a):pass
 async def publish(self,n,p):self.e.append((n,p))
async def main():
 b=B();a=m.Atom();td=tempfile.TemporaryDirectory();cfg={'max_daily_loss_pct':5,'max_consecutive_losses':3,'max_daily_trades':20,'max_open_trades':5,'consumer_db_path':td.name+'/c.db'};await a.initialize(m.AtomContext(516,cfg,L(),b.publish,b.subscribe));await a.start();await a._on_truth_equity({'account_id':'A','broker':'BR','equity':1000});await a._on_account({'account_id':'A','broker':'BR'});await a._on_terminal({'account_id':'A','connected':True,'trade_allowed':True,'expert_allowed':True});await a._on_ledger({'ledgers':[{'account_id':'A','broker':'BR','symbol':'NQ','R':100}]});await a._on_validate({'account_id':'A','broker':'BR','request_id':'r1','symbol':'NQ','action':'OPEN','risk_budget':60,'approved':True});await a._on_validate({'account_id':'A','broker':'BR','request_id':'r2','symbol':'NQ','action':'OPEN','risk_budget':60,'approved':True});rows=[p for n,p in b.e if n==m.EVENT_VALIDATED];assert rows[-2]['approved'] and rows[-1]['reason']=='RISK_BUDGET_EXCEEDED';before=dict(a.book('A'));await a._on_loss({'event_id':'loss:incomplete','account_id':'A','completeness':'INCOMPLETE','loss_pct':99});assert a.book('A')==before;await a._on_loss({'event_id':'loss:complete','account_id':'A','completeness':'COMPLETE','loss_pct':6,'is_loss':True});assert a.book('A')['kill'];await a._on_day({'pulse_id':'SYS_DAY|1','bucket_start':1});assert a.book('A')['kill'];await a._on_reset({'account_id':'A'});assert not a.book('A')['kill'];snap=await a.snapshot();c=m.Atom();await c.restore(snap);assert 'A' in c._books;print('516 scoped risk authority tests passed')
if __name__=='__main__':asyncio.run(main())
