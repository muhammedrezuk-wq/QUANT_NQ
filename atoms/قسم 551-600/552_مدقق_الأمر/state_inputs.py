from __future__ import annotations

from typing import Any

from shared.financial_scope import text

# Campaign 450-901 batch B: state-input handlers (margin verdicts, snapshots,
# reconciliation, exposure, reference feeds) extracted verbatim.

import time


def _remember(registry: dict, key: Any, record: dict) -> None:
    registry[key] = record


async def on_margin_verdict(atom, payload: dict[str, Any]) -> None:
    """T3 (c): remember 585's margin verdict per (account, request)."""
    if not atom._running or not isinstance(payload, dict): return
    account = text(payload.get("account_id")); request_id = text(payload.get("request_id"))
    if not account or not request_id: return
    _remember(atom._margin_verdicts, (account, request_id), {
        "approved": payload.get("approved") is True,
        "reason": text(payload.get("reason")),
        "required_margin": payload.get("required_margin"),
        "free_margin": payload.get("free_margin"),
        "measured_at": time.time()})


async def on_snapshot(atom, payload: dict[str, Any]) -> None:
    """T3 (d) + T1: remember 583's snapshot verdict keyed by snapshot_id."""
    if not atom._running or not isinstance(payload, dict): return
    snapshot_id = text(payload.get("snapshot_id"))
    if not snapshot_id: return
    _remember(atom._snapshots, snapshot_id, {
        "decision_id": payload.get("decision_id"),
        "gate_request_id": payload.get("gate_request_id"),
        "snapshot_status": text(payload.get("snapshot_status")),
        "usable_for_new_exposure": payload.get("usable_for_new_exposure") is True,
        "usable_for_protection": payload.get("usable_for_protection") is True,
        "produced_at": payload.get("produced_at"),
        "measured_at": time.time()})


async def on_reconcile(atom, payload: dict[str, Any]) -> None:
    if not atom._running or not isinstance(payload, dict): return
    account = text(payload.get("account_id")); broker = text(payload.get("broker")) or atom._broker_by_account.get(account, "")
    symbol = text(payload.get("asset_canonical") or payload.get("symbol"))
    if account and broker and symbol:
        atom._reconcile[(account, broker, symbol)] = text(payload.get("status")).upper()


async def on_exposure(atom, payload: dict[str, Any]) -> None:
    if not atom._running or not isinstance(payload, dict): return
    account=text(payload.get("account_id"));broker=text(payload.get("broker")) or atom._broker_by_account.get(account,"")
    if account and broker:atom._exposure[(account,broker)]=dict(payload)


async def on_reference(atom, payload: dict[str, Any]) -> None:
    if not atom._running or not isinstance(payload, dict): return
    symbol = text(payload.get("symbol"))
    if symbol: atom._reference[symbol] = text(payload.get("state") or payload.get("status")).upper()
