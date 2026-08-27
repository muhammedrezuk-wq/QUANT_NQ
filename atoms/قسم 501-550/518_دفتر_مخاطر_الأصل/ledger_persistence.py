from __future__ import annotations
from typing import Any
from ledger_support import POS_SEP, num, scope, text


def snapshot(atom) -> dict[str, Any]:
    return {"version": atom.__class__.__module__,
            "realized": [{"scope": k, "value": v} for k,v in atom._realized.items()],
            "realized_gross": [{"scope": k, "value": v} for k,v in atom._realized_gross.items()],
            "realized_costs": [{"scope": k, "value": v} for k,v in atom._realized_costs.items()],
            "extracted": [{"scope": k, "value": v} for k,v in atom._extracted.items()],
            "budgets": [{"scope": k, "value": v} for k,v in atom._budgets.items()],
            "positions": list(atom._positions.values()), "specs": atom._specs,
            "last_snapshot": atom._last_snapshot, "seen_trade_ids": list(atom._seen_order),
            "extraction_tickets": atom._extraction_tickets, "brokers": atom._brokers,
            "reservations": [{"account_id": a, "request_id": r, **v}
                             for (a,r),v in atom._reservations.items()]}


def restore(atom, state: dict[str, Any]) -> None:
    if not isinstance(state, dict):
        return
    for name,target in (("realized",atom._realized),("realized_gross",atom._realized_gross),
                        ("realized_costs",atom._realized_costs),("extracted",atom._extracted),
                        ("budgets",atom._budgets)):
        for item in state.get(name,[]):
            if isinstance(item,dict) and item.get("scope") and num(item.get("value")) is not None:
                target[str(item["scope"])]=num(item["value"]);atom._known.add(str(item["scope"]))
    for item in state.get("positions",[]):
        if isinstance(item,dict) and item.get("ticket"):
            key=f"{item.get('source_scope','restored')}{POS_SEP}{item['ticket']}";atom._positions[key]=item
            atom._known.add(scope(text(item.get("account_id")),text(item.get("symbol")),text(item.get("broker"))))
    if isinstance(state.get("specs"),dict):atom._specs.update(state["specs"])
    if isinstance(state.get("last_snapshot"),dict):atom._last_snapshot.update(state["last_snapshot"])
    for item in state.get("seen_trade_ids",[]):atom._remember(text(item))
    if isinstance(state.get("brokers"),dict):atom._brokers={str(k):str(v) for k,v in state["brokers"].items()}
    for item in state.get("reservations",[]):
        if isinstance(item,dict) and item.get("account_id") and item.get("request_id") and item.get("scope") and num(item.get("amount")) is not None:
            atom._reservations[(str(item["account_id"]),str(item["request_id"]))]={"scope":str(item["scope"]),"amount":num(item["amount"])}
    if isinstance(state.get("extraction_tickets"),dict):
        atom._extraction_tickets={str(k):str(v) for k,v in state["extraction_tickets"].items()}
