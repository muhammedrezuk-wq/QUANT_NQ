from __future__ import annotations

import time
from typing import Any
import clock

from core.contracts.atom import AtomBase, AtomContext, HealthState, HealthStatus
from shared.financial_scope import financial_key, row_key, text
from spread_gate import spread_points, too_wide
from order_validation import _neutral_pair_contract, _validate
from shared.order_validator_state import (health as gate_health, restore as restore_gate,
                                          snapshot as snapshot_gate)

ATOM_VERSION = "5.4.2"
EVENT_BUILT = "execution.order.legal"
EVENT_HALT = "emergency.halt"
EVENT_RESET = "risk.kill_switch.reset_requested"
EVENT_WHITELIST = "allowed.symbols.state"
EVENT_FINAL = "trading.final_decision"
EVENT_REJECTED = "execution.order.rejected"
EVENT_GATE = "execution.gate.state"
EVENT_TICK = "feed.mt5.tick"
EVENT_SPECS = "market.symbol_specs"
EVENT_ACCOUNT = "platform.account.state"
EVENT_GATE_COMMAND = "execution.gate.command"
EVENT_RECONCILE = "execution.reconcile.state"
EVENT_REFERENCE = "reference.health.state"
EVENT_EXPOSURE = "risk.exposure.state"
EVENT_MARGIN_VERDICT = "risk.margin.validation.completed"
EVENT_SNAPSHOT = "execution.snapshot.state"
GATE_ID = "552"
ACTION_OPEN = "OPEN"
PROTECTION_PERPETUAL = "PERPETUAL_BUDGET"
ORIGIN_PERPETUAL = "perpetual-delta"
FAIL_CLOSED = "RESTORE_FAILED_FAIL_CLOSED"
MIN_SPREAD_AGE_S = 0.1

# NQ seal, item 22, package T (T3): every refusal names the refusing stage and
# carries the barrier quadruple {value, threshold, reason, measured_at} --
# value/threshold stay None where this gate genuinely has no measurement
# (never invented), same rule as the decision-chain barriers (454).
STAGE_FINAL = "FINAL_VALIDATION"
STAGE_ACTIVATION = "ASSET_ACTIVATION"
STAGE_PARENT = "PARENT_DECISION"
STAGE_MARGIN = "MARGIN_VERDICT"
STAGE_SNAPSHOT = "SNAPSHOT_VALIDITY"
# T1: the mandated identity pair threaded through the whole execution chain.
IDENTITY_FIELDS = ("decision_id", "gate_request_id")
# T3 (a): a directional entry must carry its parent decision or a documented
# owner authority -- the same authority fields 576 already publishes.
AUTHORITY_FIELDS = ("decision_id", "parent_decision_id", "owner_command_id")
WARNING_IDENTITY = "identity_incomplete"
# 583 grants usable_for_new_exposure only on READY (its own contract); the
# snapshot barrier reports that status as the threshold, nothing new.
SNAPSHOT_USABLE_STATUS = "READY"
# Memory bound only (same family as 467's tracked-decision bound): oldest
# record is evicted past this count. Not a trading value.
_MAX_TRACKED = 4096

_ORDER_FIELDS = (
    "account_id", "broker", "request_id", "action", "symbol", "side", "volume",
    "reference_price", "stop_loss", "take_profit", "cycle_id", "origin",
    "pair_id", "leg_role", "attempt", "pair_required", "protection_mode",
    "pair_volume", "purpose", "target_net", "current_net", "delta_net",
    "ticket", "params_json", "logical_symbol", "broker_symbol", "asset_canonical",
    "symbol_resolution_status", "symbol_spec", "snapshot_id",
    "risk_budget", "asset_stop_distance", "magic",
    "decision_id", "gate_request_id", "parent_decision_id", "owner_command_id",
)


class Atom(AtomBase):
    def __init__(self) -> None:
        self._context: AtomContext | None = None
        self._running = False
        self._enabled = False
        self._global_halted = False
        self._halted_accounts: dict[str, str] = {}
        self._restore_error = ""
        self._rehydrated = False
        self._allowed: set[str] = set()
        self._allowed_by_account: dict[str, set[str]] = {}
        self._whitelist_seen = False
        self._broker_by_account: dict[str, str] = {}
        self._pending_specs: list[dict[str, Any]] = []
        self._max_spread_points = 0.0
        self._spread_ttl_s = 5.0
        self._spread: dict[tuple[str, str, str], tuple[float, float]] = {}
        self._specs: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._reconcile: dict[tuple[str, str, str], str] = {}
        self._reference: dict[str, str] = {}
        self._exposure: dict[tuple[str, str], dict[str, Any]] = {}
        self._margin_verdicts: dict[tuple[str, str], dict[str, Any]] = {}
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._seen = self._decisions_finalized = self._rejected = 0
        self._whitelist_blocked = self._clock_blocked = self._spread_blocked = 0
        self._reconcile_blocked = self._reference_blocked = self._identity_blocked = 0
        self._exposure_blocked = 0
        self._parent_decision_blocked = self._margin_verdict_blocked = 0
        self._snapshot_validity_blocked = 0
        self._identity_recovered = self._identity_incomplete = 0

    async def initialize(self, context: AtomContext) -> None:
        self._context = context
        self._enabled = bool(context.config["enabled"])
        self._max_spread_points = float(context.config.get("max_spread_points", 0.0))
        self._spread_ttl_s = max(MIN_SPREAD_AGE_S, float(context.config.get("spread_ttl_s", 5.0)))
        for event, handler in (
            (EVENT_TICK, self._on_tick), (EVENT_SPECS, self._on_specs),
            (EVENT_ACCOUNT, self._on_account), (EVENT_BUILT, self._on_built),
            (EVENT_GATE_COMMAND, self._on_gate_command), (EVENT_GATE, self._rehydrate),
            (EVENT_HALT, self._on_halt), (EVENT_RESET, self._on_reset),
            (EVENT_WHITELIST, self._on_whitelist),
            (EVENT_RECONCILE, self._on_reconcile), (EVENT_REFERENCE, self._on_reference),
            (EVENT_EXPOSURE, self._on_exposure),
            (EVENT_MARGIN_VERDICT, self._on_margin_verdict),
            (EVENT_SNAPSHOT, self._on_snapshot)):
            context.subscribe(event, handler)

    async def start(self) -> None:
        self._running = True
        await self._publish_gate()
    async def stop(self) -> None: self._running = False
    async def shutdown(self) -> None: await self.stop()

    async def _on_account(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict): return  # state handler: no running gate (v5.4.1)
        account = text(payload.get("account_id")); broker = text(payload.get("broker"))
        if account and broker:
            self._broker_by_account[account] = broker
            pending, self._pending_specs = self._pending_specs, []
            for item in pending: await self._on_specs(item)

    async def _on_halt(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict): return  # state handler: no running gate (v5.4.1)
        self._rehydrated = True
        account = text(payload.get("account_id"))
        if account:
            self._halted_accounts[account] = text(payload.get("reason")) or "RISK_HALT"
        elif str(payload.get("scope") or "").upper() == "SYSTEM":
            self._global_halted = True
        else:
            self._identity_blocked += 1
            return
        await self._publish_gate()

    async def _on_reset(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict): return  # state handler: no running gate (v5.4.1)
        self._rehydrated = True
        account = text(payload.get("account_id"))
        if account: self._halted_accounts.pop(account, None)
        elif str(payload.get("scope") or "").upper() == "SYSTEM": self._global_halted = False
        else: return
        await self._publish_gate()

    async def _publish_gate(self) -> None:
        if self._context is None: return
        status = "HALTED" if self._global_halted else "PARTIAL_HALT" if self._halted_accounts else "LIVE" if self._enabled else "STOPPED"
        await self._context.publish(EVENT_GATE, {
            "enabled": self._enabled, "halted": self._global_halted,
            # v5.4.2 (nq seal 2026-08-25): "open" -- the field the dashboard
            # banner reads (gate?.open) never existed on the wire, so the
            # banner said "closed" forever (documented display lie). The wire
            # now states it: open = enabled and not halted.
            "open": bool(self._enabled and not self._global_halted),
            "halted_accounts": dict(self._halted_accounts), "status": status,
            "seen": self._seen})

    async def _rehydrate(self, payload: dict[str, Any]) -> None:
        if self._rehydrated: return
        self._rehydrated = True
        if not isinstance(payload, dict):
            self._global_halted = True
            self._restore_error = FAIL_CLOSED
            return
        halted = payload.get("halted")
        accounts = payload.get("halted_accounts", {})
        if not isinstance(halted, bool) or not isinstance(accounts, dict):
            self._global_halted = True
            self._restore_error = FAIL_CLOSED
            return
        self._global_halted = halted
        self._halted_accounts = {str(k): str(v) for k,v in accounts.items() if str(k)}

    async def _on_gate_command(self, payload: dict[str, Any]) -> None:
        if not self._running or not isinstance(payload, dict): return
        if str(payload.get("gate") or "") not in (GATE_ID, "both"): return
        wanted = payload.get("enabled")
        if isinstance(wanted, bool) and wanted != self._enabled:
            self._enabled = wanted; await self._publish_gate()

    async def _on_whitelist(self, payload: dict[str, Any]) -> None:
        # v5.4.0 (nq seal 2026-08-25, measured live): NO _running gate on a
        # STATE handler. 468 publishes the whitelist at ITS start -- before
        # this atom's start in boot order -- so the guard swallowed the only
        # whitelist this boot and every order died SYMBOL_NOT_ALLOWED while
        # the list plainly said BTCUSD allowed. Storing state is always safe;
        # the running gate belongs to command/decision handlers only.
        if not isinstance(payload, dict): return
        allowed = payload.get("allowed")
        if isinstance(allowed, list):
            self._allowed = {text(x) for x in allowed if text(x)}; self._whitelist_seen = True
        scoped = payload.get("allowed_by_account")
        if isinstance(scoped, dict):
            self._allowed_by_account = {str(a): {text(x) for x in values if text(x)}
                                        for a,values in scoped.items() if isinstance(values,list)}
            self._whitelist_seen = True

    async def _on_specs(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict): return  # state handler: no running gate (v5.4.1)
        rows = payload.get("symbols")
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict): continue
            key = row_key(payload, row, self._broker_by_account)
            if key is not None: self._specs[key] = dict(row)
            elif text(row.get("account_id") or payload.get("account_id")) and payload not in self._pending_specs: self._pending_specs.append(dict(payload))

    async def _on_tick(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict): return  # state handler: no running gate (v5.4.1)
        key = financial_key(payload, payload.get("symbol"), self._broker_by_account)
        if key is None: return
        points = spread_points(payload, self._specs.get(key))
        if points is not None: self._spread[key] = (points, time.monotonic(), time.time())

    @staticmethod
    def _remember(registry: dict, key: Any, record: dict[str, Any]) -> None:
        if key not in registry and len(registry) >= _MAX_TRACKED:
            registry.pop(next(iter(registry)))
        registry[key] = record

    async def _on_margin_verdict(self, payload: dict[str, Any]) -> None:
        """T3 (c): remember 585's margin verdict per (account, request)."""
        if not isinstance(payload, dict): return  # state handler: no running gate (v5.4.1)
        account = text(payload.get("account_id")); request_id = text(payload.get("request_id"))
        if not account or not request_id: return
        self._remember(self._margin_verdicts, (account, request_id), {
            "approved": payload.get("approved") is True,
            "reason": text(payload.get("reason")),
            "required_margin": payload.get("required_margin"),
            "free_margin": payload.get("free_margin"),
            "measured_at": time.time()})

    async def _on_snapshot(self, payload: dict[str, Any]) -> None:
        """T3 (d) + T1: remember 583's snapshot verdict and the decision
        identity it carried, keyed by the immutable snapshot_id."""
        if not isinstance(payload, dict): return  # state handler: no running gate (v5.4.1)
        snapshot_id = text(payload.get("snapshot_id"))
        if not snapshot_id: return
        self._remember(self._snapshots, snapshot_id, {
            "decision_id": payload.get("decision_id"),
            "gate_request_id": payload.get("gate_request_id"),
            "snapshot_status": text(payload.get("snapshot_status")),
            "usable_for_new_exposure": payload.get("usable_for_new_exposure") is True,
            "usable_for_protection": payload.get("usable_for_protection") is True,
            "produced_at": payload.get("produced_at"),
            "measured_at": time.time()})

    async def _on_reconcile(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict): return  # state handler: no running gate (v5.4.1)
        account = text(payload.get("account_id")); broker = text(payload.get("broker")) or self._broker_by_account.get(account, "")
        symbol = text(payload.get("asset_canonical") or payload.get("symbol"))
        if account and broker and symbol:
            self._reconcile[(account, broker, symbol)] = text(payload.get("status")).upper()

    async def _on_exposure(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict): return  # state handler: no running gate (v5.4.1)
        account=text(payload.get("account_id"));broker=text(payload.get("broker")) or self._broker_by_account.get(account,"")
        if account and broker:self._exposure[(account,broker)]=dict(payload)

    async def _on_reference(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict): return  # state handler: no running gate (v5.4.1)
        symbol = text(payload.get("symbol"))
        if symbol: self._reference[symbol] = text(payload.get("state") or payload.get("status")).upper()

    @staticmethod
    def _opens_new_exposure(order: dict[str, Any]) -> bool:
        if str(order.get("action") or ACTION_OPEN).upper() != ACTION_OPEN: return False
        return not (str(order.get("protection_mode") or "").upper() == PROTECTION_PERPETUAL
                    and str(order.get("origin") or "") == ORIGIN_PERPETUAL)

    def _symbol_allowed(self, order: dict[str, Any]) -> bool:
        if str(order.get("action") or ACTION_OPEN).upper() != ACTION_OPEN: return True
        if not self._whitelist_seen: return False
        account = text(order.get("account_id")); allowed = self._allowed_by_account.get(account, self._allowed)
        names = {text(order.get(field)) for field in ("symbol","logical_symbol","asset_canonical","broker_symbol")}
        return bool(allowed and names & allowed)

    def _reconcile_status(self, key: tuple[str,str,str]) -> str:
        return self._reconcile.get(key) or self._reconcile.get((key[0], key[1], "*"), "UNKNOWN")

    async def _refuse(self, payload: dict[str, Any], reason: str,
                      stage: str = STAGE_FINAL, value: Any = None,
                      threshold: Any = None, measured_at: Any = None) -> None:
        self._rejected += 1
        if self._context is not None:
            await self._context.publish(EVENT_REJECTED, {
                **{key: payload.get(key) for key in _ORDER_FIELDS},
                "request_id": text(payload.get("request_id")),
                "symbol": text(payload.get("symbol")), "side": text(payload.get("side")),
                "reason": reason, "stage": stage,
                "barrier": {"name": stage, "value": value, "threshold": threshold,
                            "reason": reason, "measured_at": measured_at}})

    def _resolve_identity(self, body: dict[str, Any]) -> None:
        """T1: the identity pair rides the order when the builder kept it; a
        value the builder dropped is recovered from the exact snapshot the
        order itself names (snapshot_id is immutable, so this is the recorded
        value of that very snapshot -- not a guess). Whatever remains absent
        passes as None and is declared."""
        record = self._snapshots.get(text(body.get("snapshot_id")))
        recovered = False
        for field in IDENTITY_FIELDS:
            if not body.get(field) and record is not None and record.get(field):
                body[field] = record[field]; recovered = True
        if recovered:
            self._identity_recovered += 1
            body["identity_from_snapshot"] = True
        missing = [field for field in IDENTITY_FIELDS if not body.get(field)]
        if missing:
            self._identity_incomplete += 1
            body["identity_missing"] = missing
            body["identity_warnings"] = [WARNING_IDENTITY]

    async def _on_built(self, payload: dict[str, Any]) -> None:
        if not self._running or self._context is None or not isinstance(payload, dict): return
        self._seen += 1
        reason = _validate(payload)
        account = text(payload.get("account_id")); broker = text(payload.get("broker")) or self._broker_by_account.get(account, "")
        symbol = text(payload.get("symbol")); scoped = financial_key({"account_id":account,"broker":broker}, symbol, self._broker_by_account)
        if not reason and scoped is None:
            reason = "MISSING_ACCOUNT_BROKER_OR_SYMBOL"; self._identity_blocked += 1
        try:magic=int(payload.get("magic"))
        except (TypeError,ValueError):magic=0
        if not reason and magic<=0:reason="MISSING_MAGIC"
        if reason: await self._refuse(payload, reason); return
        if not self._symbol_allowed(payload):
            self._whitelist_blocked += 1
            allowed = sorted(self._allowed_by_account.get(account, self._allowed))
            await self._refuse(payload, "SYMBOL_NOT_ALLOWED", STAGE_ACTIVATION,
                               value=symbol, threshold=allowed or None,
                               measured_at=time.time()); return
        if self._max_spread_points > 0 and str(payload.get("action") or ACTION_OPEN).upper() == ACTION_OPEN:
            record = self._spread.get(scoped) if scoped is not None else None
            fresh = record if record and time.monotonic()-record[1] <= self._spread_ttl_s else None
            spread = fresh[0] if fresh else None
            if too_wide(spread, self._max_spread_points):
                self._spread_blocked += 1
                await self._refuse(payload, "SPREAD_TOO_WIDE", STAGE_FINAL,
                                   value=spread, threshold=self._max_spread_points,
                                   measured_at=fresh[2] if fresh else None); return
        assert scoped is not None
        body = {key: payload.get(key) for key in _ORDER_FIELDS}
        body.update({"account_id": account, "broker": broker, "symbol": symbol,
                     "action": str(payload.get("action") or ACTION_OPEN).upper()})
        self._resolve_identity(body)
        if not self._enabled: await self._refuse(body, "disabled"); return
        if self._global_halted or account in self._halted_accounts:
            await self._refuse(body, "halted"); return
        if body["action"] == ACTION_OPEN:
            # T3 (a): a directional entry (any OPEN that is not the declared
            # neutral-pair contract) must carry its parent decision or a
            # documented owner authority. Management/close orders never enter
            # this branch, exactly as the existing code separates them.
            if not _neutral_pair_contract(body) \
                    and not any(text(body.get(field)) for field in AUTHORITY_FIELDS):
                self._parent_decision_blocked += 1
                await self._refuse(body, "PARENT_DECISION_MISSING", STAGE_PARENT,
                                   measured_at=time.time()); return
            # T3 (c): the margin stage (585) must have ruled on this very
            # request and approved it -- the gate verifies the verdict
            # happened, it does not recompute margin.
            verdict = self._margin_verdicts.get((account, text(body.get("request_id"))))
            if verdict is None:
                self._margin_verdict_blocked += 1
                await self._refuse(body, "MARGIN_VERDICT_MISSING", STAGE_MARGIN,
                                   measured_at=time.time()); return
            if not verdict.get("approved"):
                self._margin_verdict_blocked += 1
                await self._refuse(body, "MARGIN_VERDICT_REJECTED", STAGE_MARGIN,
                                   value=verdict.get("required_margin"),
                                   threshold=verdict.get("free_margin"),
                                   measured_at=verdict.get("measured_at")); return
            # T3 (d): an order that names its snapshot is held to it -- the
            # snapshot must be known here and usable for new exposure (583
            # grants that only on READY). Flows that never carry a snapshot
            # (the owner-authorized initial pairs from 576) are not given an
            # invented requirement.
            snapshot_id = text(body.get("snapshot_id"))
            if snapshot_id:
                record = self._snapshots.get(snapshot_id)
                if record is None:
                    self._snapshot_validity_blocked += 1
                    await self._refuse(body, "SNAPSHOT_UNKNOWN", STAGE_SNAPSHOT,
                                       measured_at=time.time()); return
                if not record.get("usable_for_new_exposure"):
                    self._snapshot_validity_blocked += 1
                    await self._refuse(body, "SNAPSHOT_NOT_USABLE", STAGE_SNAPSHOT,
                                       value=record.get("snapshot_status"),
                                       threshold=SNAPSHOT_USABLE_STATUS,
                                       measured_at=record.get("measured_at")); return
        if self._opens_new_exposure(body) and clock.quality() != clock.SYNCED:
            self._clock_blocked += 1
            await self._refuse(body, "CLOCK_NOT_SYNCED")
            return
        if self._opens_new_exposure(body):
            reconcile = self._reconcile_status(scoped)
            if reconcile not in {"MATCH", "MATCH_EMPTY_ACCOUNT"}:
                self._reconcile_blocked += 1
                await self._refuse(body, "RECONCILIATION_NOT_MATCHED")
                return
            reference = self._reference.get(symbol, "UNKNOWN")
            if reference not in {"HEALTHY", "FALLBACK"}:
                self._reference_blocked += 1
                await self._refuse(body, "REFERENCE_NOT_USABLE")
                return
            exposure = self._exposure.get((account, broker))
            if exposure is None or exposure.get("usable_for_new_exposure") is not True:
                self._exposure_blocked += 1
                await self._refuse(body, "EXPOSURE_STATE_NOT_USABLE")
                return
        self._decisions_finalized += 1; await self._context.publish(EVENT_FINAL, body)

    async def snapshot(self) -> dict[str, Any]:
        return snapshot_gate(self, ATOM_VERSION)

    async def restore(self, state: dict[str, Any]) -> None:
        await restore_gate(self, state, FAIL_CLOSED)

    async def health_check(self) -> HealthStatus:
        return gate_health(self)
