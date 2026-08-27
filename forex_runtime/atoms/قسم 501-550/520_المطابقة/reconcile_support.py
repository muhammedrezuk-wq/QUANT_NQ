from __future__ import annotations
import math
from typing import Any

DEFAULT_ACCOUNT="__unknown__"; DEFAULT_BROKER="__unknown__"; SEP="\x1f"; SRC_SEP="\x1e"
PRICE_FIELDS=("stop_loss","take_profit")

def num(v):
    try:r=float(v)
    except (TypeError,ValueError):return None
    return r if math.isfinite(r) else None

def text(v,default=""):
    r=str(v or "").strip();return r or default

def scope(account,symbol,broker=""):return SEP.join((text(account,DEFAULT_ACCOUNT),text(broker,DEFAULT_BROKER),text(symbol)))
def parts(k):
    values=str(k).split(SEP,2)
    return tuple(values) if len(values)==3 else (DEFAULT_ACCOUNT,DEFAULT_BROKER,str(k))
def stamp(d):
    for k in ("timestamp","stamp","updated_at","read_at"):
        v=num(d.get(k))
        if v is not None:return v
    return None

def identity(leg):
    ticket=text(leg.get("ticket"),text(leg.get("broker_ticket")))
    if ticket:return "ticket:"+ticket
    leg_id=text(leg.get("leg_id"))
    if leg_id:return "leg:"+leg_id
    return "sig:"+SEP.join(text(leg.get(k)) for k in ("account_id","broker","symbol","side","entry_price"))
def normalize(raw,account,broker,symbol,source=""):
    out=dict(raw);out["account_id"]=text(raw.get("account_id"),account);out["broker"]=text(raw.get("broker"),broker);out["symbol"]=text(raw.get("asset_canonical"),text(raw.get("symbol"),symbol));out["ticket"]=text(raw.get("ticket"),text(raw.get("broker_ticket")));out["volume"]=num(raw.get("volume"));out["entry_price"]=num(raw.get("entry_price"))
    for k in PRICE_FIELDS:out[k]=num(raw.get(k))
    out["_identity"]=identity(out)
    if source:out["_source_scope"]=source
    return out
def desired_records(payload):
    top_a=text(payload.get("account_id"),DEFAULT_ACCOUNT);top_b=text(payload.get("broker"),DEFAULT_BROKER);top_s=text(payload.get("asset_canonical"),text(payload.get("symbol")));raw_list=payload.get("desired")
    if not isinstance(raw_list,list) or not any(isinstance(x,dict) and ("legs" in x or "positions" in x) for x in raw_list):raw_list=[payload]
    out=[]
    for raw in raw_list:
        if not isinstance(raw,dict):continue
        a=text(raw.get("account_id"),top_a);b=text(raw.get("broker"),top_b);s=text(raw.get("asset_canonical"),text(raw.get("symbol"),top_s))
        if not s:continue
        legs=raw.get("legs",raw.get("positions",[]));legs=legs if isinstance(legs,list) else ([raw] if raw.get("ticket") or raw.get("leg_id") else [])
        out.append({"account_id":a,"broker":b,"asset_canonical":s,"symbol":s,"version":int(num(raw.get("version",payload.get("version",0))) or 0),"stamp":stamp(raw) or stamp(payload),"legs":[normalize(x,a,b,s) for x in legs if isinstance(x,dict)]})
    return out
def stale(candidate,previous):
    if previous is None:return False
    # v3.4.0 (2026-08-25): سجلٌّ سابق كل سيقانه بلا تذاكر = نيّة لم تُنفَّذ
    # قط — لا يتقدّم على نيّة أحدث ختمًا مهما علا رقم إصداره. المقيس: زوج
    # ميت v18 ظل يحجب سجلات الأزواج الجديدة (v1) فبقي «المرغوب» كاذبًا
    # وامتنع ربط التذاكر. الإصدار يبقى الحكم بين السجلات المؤكَّدة (ذات
    # التذاكر) كما كان حرفيًّا.
    prev_legs=previous.get("legs") or []
    prev_pure_intent=bool(prev_legs) and not any(text(x.get("ticket")) for x in prev_legs if isinstance(x,dict))
    cs,ps=candidate.get("stamp"),previous.get("stamp")
    if prev_pure_intent and cs is not None and (ps is None or cs>ps):return False
    cv=int(candidate.get("version",0));pv=int(previous.get("version",0))
    if cv!=pv:return cv<pv
    return cs is not None and ps is not None and cs<=ps
def actual_records(payload):
    source=text(payload.get("source"),"broker");top_a=text(payload.get("account_id"),DEFAULT_ACCOUNT);top_b=text(payload.get("broker"),DEFAULT_BROKER);rows=payload.get("positions");rows=rows if isinstance(rows,list) else [];grouped={}
    for raw in rows:
        if not isinstance(raw,dict):continue
        a=text(raw.get("account_id"),top_a);b=text(raw.get("broker"),top_b);s=text(raw.get("asset_canonical"),text(raw.get("symbol")))
        if s:
            source_scope=SRC_SEP.join((source,a,b));grouped.setdefault(source_scope,[]).append(normalize(raw,a,b,s,source_scope))
    if not grouped and top_a!=DEFAULT_ACCOUNT and top_b!=DEFAULT_BROKER:grouped[SRC_SEP.join((source,top_a,top_b))]=[]
    return grouped,stamp(payload)
def compare(key,desired,actual,actual_seen,vol_tol,price_tol,ack_count):
    a,b,s=parts(key)
    if desired is None:return {"account_id":a,"broker":b,"asset_canonical":s,"symbol":s,"status":"NO_DESIRED_STATE","items":[],"classification_counts":{},"escalate":bool(actual),"auto_adopted":False,"actual_snapshot":actual_seen}
    dm={x["_identity"]:x for x in desired.get("legs",[])};am={x["_identity"]:x for x in actual};items=[];counts={}
    for ident in sorted(set(dm)|set(am)):
        d=dm.get(ident);x=am.get(ident);dif=[]
        if d is None:kind="EXTRA_AT_BROKER"
        # A desired leg with no broker ticket is intent that has not executed
        # yet -- 551 writes desired state at BUILD time, so before the fill the
        # broker cannot show it. Only a TICKETED leg missing at the broker is
        # a real loss alarm.
        elif x is None:kind="MISSING_AT_BROKER" if text(d.get("ticket")) else "PENDING_OPEN"
        else:
            if d.get("volume") is not None and x.get("volume") is not None and abs(d["volume"]-x["volume"])>vol_tol:dif.append("volume")
            for f in PRICE_FIELDS:
                if d.get(f) is not None and (x.get(f) is None or abs(d[f]-x[f])>price_tol):dif.append(f)
            kind="MISMATCH" if dif else "MATCH"
        counts[kind]=counts.get(kind,0)+1;items.append({"identity":ident,"classification":kind,"differences":dif,"desired":d,"actual":x})
    if not actual_seen:status="WAITING_FOR_ACTUAL";warnings=["NO_ACTUAL_SNAPSHOT"]
    elif not items:status="MATCH";warnings=[]
    else:
        status="MATCH" if all(x["classification"] in ("MATCH","PENDING_OPEN") for x in items) else "ATTENTION"
        warnings=(["PENDING_OPEN_LEGS"] if counts.get("PENDING_OPEN") else []) if status=="MATCH" else ["RECONCILIATION_REQUIRED"]
    return {"account_id":a,"broker":b,"asset_canonical":s,"symbol":s,"status":status,"items":items,"classification_counts":counts,"desired_version":desired.get("version",0),"desired_stamp":desired.get("stamp"),"actual_snapshot":actual_seen,"warnings":warnings,"escalate":status=="ATTENTION","auto_adopted":False,"protocol":{"desired_persisted":True,"ack_count":ack_count}}
