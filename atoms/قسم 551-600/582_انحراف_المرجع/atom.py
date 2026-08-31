from __future__ import annotations
import clock
from core.contracts.atom import AtomBase,AtomContext,HealthState,HealthStatus
# ٢٠٢٦-٠٨-٣١ (ختم NQ): «الآن» كان يُؤخذ من حمولة نبضة SYS_SECOND المخزَّنة،
# فصارت صحّة المقارنة تابعة لجدولة صندوق البريد. مقاس: النبضة تُنتَج 1.000/ث
# و`dropped=0`، ومع ذلك يتأخّر طابعها تأخّرًا تراكميًّا (‏3.97ث ← 60.56ث ←
# 97.87ث خلال ستّ عشرة دقيقة). فتخرج أعمار العيّنات سالبة/خارج النافذة
# فيُصنَّف كلّ شيء STALE ولا تتمّ مقارنة واحدة. القراءة الآن من السلطة
# الزمنيّة مباشرة (`clock`) بلا طابور — والنافذة `_max_age` لم تُمسّ.
# النبضة تبقى إشارة مراقبة: تأخّرها يُعلَن في تفاصيل الصحّة.
ATOM_VERSION="1.5.0"
EVENT_CTRADER="feed.ctrader.tick"
EVENT_MT5="feed.mt5.tick"
EVENT_SPECS="market.symbol_specs"
EVENT_PULSE="SYS_SECOND"
EVENT_OUT="execution.reference_divergence.state"
UNALIGNED="UNALIGNED"
def num(v):
 try:r=float(v)
 except (TypeError,ValueError):return None
 return r if r==r else None
class Atom(AtomBase):
 def __init__(self):self._context=None;self._running=False;self._ct={};self._mt={};self._points={};self._max_dev=50.;self._max_age=5.;self._window=.15;self._updates=0;self._unaligned=0;self._now=0.;self._compared=0;self._waiting=0;self._stale=0
 async def initialize(self,c):
  self._context=c
  cfg=c.config
  self._max_dev=float(cfg.get("max_deviation_points",50))
  self._max_age=float(cfg.get("max_age_s",5))
  self._window=float(cfg["alignment_window_s"])
  c.subscribe(EVENT_CTRADER,self._on_ct)
  c.subscribe(EVENT_MT5,self._on_mt)
  c.subscribe(EVENT_SPECS,self._on_specs)
  c.subscribe(EVENT_PULSE,self._on_pulse)
 async def start(self):self._running=True
 async def stop(self):self._running=False
 async def shutdown(self):await self.stop()
 async def _on_pulse(self,p):
  if not self._running or not isinstance(p,dict):return
  try:self._now=float(p.get("official_time"))
  except (TypeError,ValueError):return
  for symbol in set(self._ct)|set(self._mt):await self._publish(symbol)
 async def _on_specs(self,p):
  if self._running and isinstance(p,dict):
   for r in p.get("symbols",[]) if isinstance(p.get("symbols"),list) else []:
    if isinstance(r,dict) and r.get("symbol") and num(r.get("point")):self._points[str(r["symbol"])]=num(r["point"])
 async def _on_ct(self,p):
  if self._running and isinstance(p,dict) and p.get("symbol"):self._ct[str(p["symbol"])]=dict(p);await self._publish(str(p["symbol"]))
 async def _on_mt(self,p):
  if self._running and isinstance(p,dict) and p.get("symbol"):self._mt[str(p["symbol"])]=dict(p);await self._publish(str(p["symbol"]))
 async def _publish(self,s):
  if self._context is None:return
  ct=self._ct.get(s);mt=self._mt.get(s);a=num((ct or {}).get("exchange_timestamp",(ct or {}).get("timestamp")));b=num((mt or {}).get("exchange_timestamp",(mt or {}).get("timestamp")));cp=num((ct or {}).get("price"));mp=num((mt or {}).get("price"));dev=None;gap=None;ages=[]
  now=clock.now()
  for stamp in (a,b):
   ages.append(None if stamp is None else now-stamp)
  if cp is None or mp is None:status="WAITING"
  elif any(age is None or age<0 or age>self._max_age for age in ages):status="STALE"
  else:
   point=self._points.get(s,1.0);dev=(mp-cp)/point if point else mp-cp;gap=abs(a-b);status=UNALIGNED if gap>self._window else "DIVERGED" if abs(dev)>self._max_dev else "SYNCED"
  if status==UNALIGNED:self._unaligned+=1
  # ٢٠٢٦-٠٨-٣١ (ختم NQ): `_updates` كان يُزاد على كل وصول — حتى حالة WAITING
  # (سعر المرجع غائب). و`health_check` يعلن HEALTHY لمجرّد أنّ العدّاد > 0،
  # فكانت الذرّة تقول «divergence_updates=50496 unaligned=0» وهي **لم تقارن
  # ولا مرّة** (سي‑تريدر مقفول، `622 t=0`). `unaligned=0` تعني «لم نقِس» لا
  # «لا تلاعب» — وهذا أخطر من العطل نفسه: كاشف التلاعب يعلن السلامة وهو أعمى.
  # الآن يُفصل عدّاد المقارنات الحقيقيّة عن عدّاد الاستقبال.
  if status=="WAITING":self._waiting+=1
  elif status=="STALE":self._stale+=1
  else:self._compared+=1
  self._updates+=1;await self._context.publish(EVENT_OUT,{"symbol":s,"status":status,"reference_price":cp,"broker_price":mp,"deviation_points":dev,"timestamp_gap_s":gap,"sample_ages_s":ages,"max_deviation_points":self._max_dev,"alignment_window_s":self._window,"read_only":True})
 async def health_check(self):
  if not self._running:return HealthStatus(state=HealthState.UNHEALTHY,message="NOT_STARTED")
  d={"updates":self._updates,"compared":self._compared,"waiting":self._waiting,"stale":self._stale,"unaligned":self._unaligned,"alignment_window_s":self._window,"max_deviation_points":self._max_dev,"max_age_s":self._max_age,
     # مراقبة فقط: تأخّر آخر نبضة عن السلطة الزمنيّة — لا يدخل أي حكم.
     "pulse_lag_s":(None if not self._now else round(clock.now()-self._now,3))}
  if not self._compared:
   return HealthStatus(state=HealthState.DEGRADED,message="NO_COMPARISON_YET: compared=0 waiting=%d stale=%d — لا مقارنة تمّت؛ سعر المرجع (سي‑تريدر) لم يصل، فلا حكم على التلاعب"%(self._waiting,self._stale),details=d)
  return HealthStatus(state=HealthState.HEALTHY,message="compared=%d unaligned=%d waiting=%d"%(self._compared,self._unaligned,self._waiting),details=d)
