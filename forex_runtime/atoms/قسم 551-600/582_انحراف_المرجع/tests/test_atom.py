import asyncio,importlib.util,sys
from pathlib import Path
root=Path(__file__).resolve().parents[4];folder=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));s=importlib.util.spec_from_file_location('a582',folder/'atom.py');m=importlib.util.module_from_spec(s);sys.modules['a582']=m;s.loader.exec_module(m)
CFG={'max_deviation_points':5,'max_age_s':5,'alignment_window_s':0.15}
# ٢٠٢٦-٠٩-٠١: الذرّة صارت تقرأ «الآن» من السلطة الزمنيّة `clock` مباشرة بدل
# حمولة النبضة (فصحّة المقارنة ما عادت تتبع جدولة صندوق البريد). فالاختبار
# يحقن ساعةً مضبوطة في **مساحة أسماء هذه الذرّة وحدها** (`m.clock`) ولا يمسّ
# الساعة العامّة: الطوابع تبقى صغيرة ودقيقة بتًّا ببت كما أراد حكم المالك —
# جمع 0.15 فوق طابعٍ بحجم زمن الحائط يفقد الدقّة عند الحدّ بالضبط.
class _Clock:
 value=1.0
 def now(self):return self.value
 def mono(self):return self.value
 def quality(self):return 'SYNCED'
 def state(self):return {'quality':'SYNCED'}
CLOCK=_Clock();m.clock=CLOCK
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
 CLOCK.value=1.0+max(0.0,gap)
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
 CLOCK.value=1.0
 a,b=await new();await a._on_pulse({'official_time':1.0});await a._on_ct({'symbol':'X','price':100});await a._on_mt({'symbol':'X','price':999,'timestamp':1.0})
 assert last(b)['status']=='STALE',last(b)
 # وبلا سعر تبقى WAITING كما كانت.
 CLOCK.value=1.0
 a,b=await new();await a._on_pulse({'official_time':1.0});await a._on_ct({'symbol':'X','timestamp':1.0});assert last(b)['status']=='WAITING',last(b)
 print('582 — التقادم ما زال يحجب، والزمن الغائب لا يكذب')

 a,b=await new();await judge(1.04,900,a,b)
 d=(await a.health_check()).details
 assert d['alignment_window_s']==0.15 and d['unaligned']==1 and d['max_deviation_points']==5.0
 assert last(b)['alignment_window_s']==0.15,'النافذة تُنشَر ليراها المالك'
 print('582 — النافذة معروضة بالصحّة وبالحدث')

 # ٢٠٢٦-٠٩-٠١ — حارس الانحدار المقيس حيًّا: حمولة ميتاتريدر تحمل
 # `exchange_timestamp` **موجودًا وقيمته None** (الجسر لا يعطي زمن بورصة).
 # `dict.get(k, default)` لا يستعمل البديل في هذه الحالة، فكان الطابع يخرج
 # None فتُصنَّف كل عيّنة STALE إلى الأبد: مقيس `compared=0 · stale=183843`.
 # كاشف التلاعب كان أعمى بلا أن يشتكي أحد. لا يمرّ هذا ثانيةً.
 CLOCK.value=1.0
 a,b=await new()
 await a._on_ct({'symbol':'X','price':100,'timestamp':1.0,'exchange_timestamp':1.0})
 await a._on_mt({'symbol':'X','price':110,'timestamp':1.0,'exchange_timestamp':None})
 r=last(b)
 assert r['status']!='STALE',('زمن البورصة None يجب أن يسقط إلى timestamp',r)
 assert r['status']=='DIVERGED',r
 assert r['sample_ages_s'][1] is not None,'عمر عيّنة الوسيط لا يجوز أن يبقى مجهولًا'
 print('582 — زمن بورصة None يسقط إلى زمن الوصول، والمقارنة تتمّ')
# ٢٠٢٦-٠٩-٠١: كان الملفّ سكربتًا بلا دالّة `test_`، فـpytest يجمع منه صفرًا
# ويعلن «no tests ran» — أي ذرّةٌ بلا تغطية فعليّة وهي تبدو مغطّاة. وكان
# `parents[3]` يشير إلى `atoms/` لا إلى جذر المشروع، فما إن استوردت الذرّة
# `clock` حتى انكسر الاستيراد. صار الملفّ اختبارًا حقيقيًّا بجذر صحيح.
def test_582_reference_divergence():asyncio.run(main())

if __name__=='__main__':asyncio.run(main())
