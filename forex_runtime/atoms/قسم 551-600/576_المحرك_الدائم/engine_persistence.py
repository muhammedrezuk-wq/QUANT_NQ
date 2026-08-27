from __future__ import annotations
from typing import Any
from shared.snapshot_state import VALID,digest_of,grade

def snapshot(atom,version):
    body={"version":version,"active":sorted(atom._active),"actual_active":sorted(atom._actual_active),"pending":dict(atom._pending),"budget":dict(atom._budget),"counter":atom._counter,"gate_window":dict(getattr(atom,"_gate_window",{}))}
    return {"schema_version":1,"written_at":float(atom._epoch or 0),"session_epoch":atom._epoch,"payload":body,"digest":digest_of(body)}

def restore(atom,state:dict[str,Any],number,key_sep):
    verdict=grade(state);atom._restore_grade=verdict["grade"]
    if verdict["grade"]!=VALID:atom._restore_reason=verdict["reason"];return
    payload=state["payload"]
    for key in payload.get("active",[]):
        if isinstance(key,str) and key_sep in key:atom._active.add(key)
    for key in payload.get("actual_active",[]):
        if isinstance(key,str) and key_sep in key:atom._actual_active.add(key)
    pending=payload.get("pending")
    if isinstance(pending,dict):
        for key,request in pending.items():
            if isinstance(key,str) and isinstance(request,dict):atom._pending[key]=dict(request)
    budget=payload.get("budget")
    if isinstance(budget,dict):
        for key,value in budget.items():
            amount=number(value)
            if isinstance(key,str) and amount is not None:atom._budget[key]=amount
    counter=number(payload.get("counter"))
    if counter is not None:atom._counter=int(counter)
    window=payload.get("gate_window")
    if isinstance(window,dict):
        for decision_id,gate_request_id in window.items():
            if isinstance(decision_id,str) and decision_id and isinstance(gate_request_id,str) and gate_request_id:
                atom._gate_window[decision_id]=gate_request_id
