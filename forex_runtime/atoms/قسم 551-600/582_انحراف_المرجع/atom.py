from __future__ import annotations
from core.contracts.atom import AtomBase,AtomContext,HealthState,HealthStatus
ATOM_VERSION="1.4.0"
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
 def __init__(self):self._context=None;self._running=False;self._ct={};self._mt={};self._points={};self._max_dev=50.;self._max_age=5.;self._window=.15;self._updates=0;self._unaligned=0;self._now=0.
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
  for stamp in (a,b):
   ages.append(None if stamp is None or self._now<=0 else self._now-stamp)
  if cp is None or mp is None:status="WAITING"
  elif any(age is None or age<0 or age>self._max_age for age in ages):status="STALE"
  else:
   point=self._points.get(s,1.0);dev=(mp-cp)/point if point else mp-cp;gap=abs(a-b);status=UNALIGNED if gap>self._window else "DIVERGED" if abs(dev)>self._max_dev else "SYNCED"
  if status==UNALIGNED:self._unaligned+=1
  self._updates+=1;await self._context.publish(EVENT_OUT,{"symbol":s,"status":status,"reference_price":cp,"broker_price":mp,"deviation_points":dev,"timestamp_gap_s":gap,"sample_ages_s":ages,"max_deviation_points":self._max_dev,"alignment_window_s":self._window,"read_only":True})
 async def health_check(self):
  if not self._running:return HealthStatus(state=HealthState.UNHEALTHY,message="NOT_STARTED")
  return HealthStatus(state=HealthState.HEALTHY if self._updates else HealthState.DEGRADED,message="divergence_updates=%d unaligned=%d"%(self._updates,self._unaligned),details={"updates":self._updates,"unaligned":self._unaligned,"alignment_window_s":self._window,"max_deviation_points":self._max_dev,"max_age_s":self._max_age})
