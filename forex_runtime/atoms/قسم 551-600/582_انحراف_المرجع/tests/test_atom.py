import asyncio,importlib.util,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));s=importlib.util.spec_from_file_location('a582',folder/'atom.py');m=importlib.util.module_from_spec(s);sys.modules['a582']=m;s.loader.exec_module(m)
CFG={'max_deviation_points':5,'max_age_s':5,'alignment_window_s':0.15}
class L:
 def __getattr__(self,n):return lambda *a,**k:None
class B:
 def __init__(self):self.e=[]
 def subscribe(self,*a):pass
 async def publish(self,n,p):self.e.append((n,p))
async def new(cfg=None):
 b=B();a=m.Atom();await a.initialize(m.AtomContext(582,dict(cfg or CFG),L(),b.publish,b.subscribe));await a.start()
 await a._on_specs({'symbols':[{'symbol':'X','point':1}]});return a,b
def last(b):return [p for n,p in b.e if n==m.EVENT_OUT][-1]
async def judge(gap,dev,a=None,b=None):
 # الطابع الأوّل صفر عمدًا: الجمع يفقد الدقّة عند الحدّ، والحدّ يجب أن يُختبر
 # بقيمته الحقيقيّة بت ببت (حكم المالك: لا اعتماد على >/>= بالحدس).
 if a is None:a,b=await new()
 await a._on_pulse({'official_time': 1.0 + max(0.0, gap)})
 await a._on_ct({'symbol':'X','price':100,'timestamp':0.0});await a._on_mt({'symbol':'X','price':100+dev,'timestamp':gap});return last(b)
async def main():
 # حكم المالك ٢٠٢٦-٠٨-١٤ (البند ٢١): لا حكم انحراف إلّا من عيّنتين متزامنتين.
 # الرقم 0.15 مشتقّ من ٢٠٣٥ عيّنة حيّة: حتى 0.15 يبقى أثر الفجوة p95 ≤ ٣ نقاط،
 # وعند 0.15–0.20 يقفز إلى ١٠٣ — ضِعف العتبة.
 r=await judge(0.0,10);assert r['status']=='DIVERGED',r
 r=await judge(0.05,10);assert r['status']=='DIVERGED',r
 r=await judge(0.05,1);assert r['status']=='SYNCED',r
 print('582 — داخل النافذة: الانحراف الحقيقيّ ما زال يُكشف')

 r=await judge(0.15,10)
 assert r['timestamp_gap_s']==0.15 and r['status']=='DIVERGED',r   # الحدّ داخل النافذة
 r=await judge(0.1500001,10);assert r['status']=='UNALIGNED',r
 r=await judge(1.04,10);assert r['status']=='UNALIGNED',r
 print('582 — الحدّ 0.15 داخل النافذة بالضبط، وما بعده UNALIGNED')

 # التقادم يُحسم أوّلًا: موت مغذٍّ حماية قائمة لا أثر عيّنة.
 r=await judge(10.0,10);assert r['status']=='STALE',r
 r=await judge(10.0,0);assert r['status']=='STALE',r
 # وزمن غائب لا يصير انحرافًا كذبًا.
 a,b=await new();await a._on_pulse({'official_time':1.0});await a._on_ct({'symbol':'X','price':100});await a._on_mt({'symbol':'X','price':999,'timestamp':1.0})
 assert last(b)['status']=='STALE',last(b)
 # وبلا سعر تبقى WAITING كما كانت.
 a,b=await new();await a._on_pulse({'official_time':1.0});await a._on_ct({'symbol':'X','timestamp':1.0});assert last(b)['status']=='WAITING',last(b)
 print('582 — التقادم ما زال يحجب، والزمن الغائب لا يكذب')

 a,b=await new();await judge(1.04,900,a,b)
 d=(await a.health_check()).details
 assert d['alignment_window_s']==0.15 and d['unaligned']==1 and d['max_deviation_points']==5.0
 assert last(b)['alignment_window_s']==0.15,'النافذة تُنشَر ليراها المالك'
 print('582 — النافذة معروضة بالصحّة وبالحدث')
if __name__=='__main__':asyncio.run(main())
