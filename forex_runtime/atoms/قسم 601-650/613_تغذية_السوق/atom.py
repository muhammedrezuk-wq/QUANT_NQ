from __future__ import annotations

import time
import math
from typing import Any

from core.contracts.atom import AtomBase, AtomContext, HealthState, HealthStatus

ATOM_VERSION = "2.5.0"

SUBSECOND_CLOCK_REASON = "feed silence is measured below one second"

EVENT_HEARTBEAT = "kernel.clock.heartbeat"
EVENT_MARKET_TICK = "market.tick"
EVENT_MARKET_VOLUME = "market.volume"
EVENT_PROVIDER_DOWN = "market.feed.provider_down"
EVENT_PROVIDER_RECOVERED = "market.feed.provider_recovered"

_SIDES = 2.0
_IDENTITY_KEYS = ("account_id", "broker", "symbol", "provider", "sequence", "tick_id")


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Atom(AtomBase):
    def __init__(self) -> None:
        self._context: AtomContext | None = None
        self._running = False
        self._routes: dict[str, str] = {}
        self._provider_timeout_s = 0.0
        self._max_input_silence_s = 0.0
        self._preferred_provider = ""
        self._official_time = 0.0
        self._last_input_at = 0.0
        self._forwarded = 0
        self._dropped = 0
        self._suppressed_secondary = 0
        self._symbols: set[str] = set()
        self._providers: dict[str, dict[str, Any]] = {}

    async def initialize(self, context: AtomContext) -> None:
        self._context = context
        cfg = context.config
        self._provider_timeout_s = float(cfg["provider_timeout_s"])
        self._max_input_silence_s = float(cfg["max_input_silence_seconds"])
        self._preferred_provider = str(cfg.get("preferred_provider", "")).strip().upper()
        self._routes = dict(cfg["routes"])
        for source_event, destination in self._routes.items():
            context.subscribe(source_event, self._make_router(str(destination)))
        context.subscribe(EVENT_HEARTBEAT, self._on_heartbeat)

    async def start(self) -> None:
        self._running = True
        self._last_input_at = time.time()

    async def stop(self) -> None:
        self._running = False

    async def shutdown(self) -> None:
        self._providers.clear()

    async def health_check(self) -> HealthStatus:
        if self._context is None:
            return HealthStatus(state=HealthState.UNKNOWN, message="not initialized")
        if not self._running:
            return HealthStatus(state=HealthState.UNHEALTHY, message="NOT_STARTED")
        silent_for = time.time() - self._last_input_at
        if self._last_input_at and silent_for > self._max_input_silence_s:
            return HealthStatus(
                state=HealthState.DEGRADED,
                message=f"INPUT_STARVED: no feed for {int(silent_for)}s",
                details={"forwarded": self._forwarded, "dropped": self._dropped, "providers": self._stats()})
        # self._last_input_at is one shared clock touched by EITHER source (line ~97) --
        # it only starves once BOTH providers go silent, so a single dead provider (e.g.
        # MT5) hid completely behind a live preferred provider (e.g. cTrader) and the
        # top-level state/message stayed HEALTHY forever. _on_heartbeat already computes a
        # per-provider "down" flag from the same provider_timeout_s used above -- promote
        # it to the top-level answer instead of leaving it buried only in details.
        down_providers = sorted(name for name, info in self._providers.items() if info["down"])
        details = {"forwarded": self._forwarded, "dropped": self._dropped,
                   "suppressed_secondary": self._suppressed_secondary,
                   "preferred_provider": self._preferred_provider or None,
                   "symbols": len(self._symbols), "providers": self._stats()}
        if down_providers:
            return HealthStatus(state=HealthState.DEGRADED,
                message=f"PROVIDER_DOWN: {','.join(down_providers)}", details=details)
        return HealthStatus(
            state=HealthState.HEALTHY,
            message=f"forwarding {len(self._symbols)} symbols via {len(self._routes)} routes",
            details=details)

    def _stats(self) -> dict[str, Any]:
        return {name: {"ticks": info["ticks"], "down": info["down"]} for name, info in self._providers.items()}

    def _make_router(self, destination: str):
        async def handler(payload: dict[str, Any]) -> None:
            await self._on_source_tick(payload, destination)
        return handler

    async def _on_source_tick(self, payload: dict[str, Any], destination: str) -> None:
        if not self._running or self._context is None:
            return
        provider = payload.get("provider")
        symbol = payload.get("symbol")
        bid = _to_float(payload.get("bid"))
        ask = _to_float(payload.get("ask"))
        if (not provider or not symbol or bid is None or ask is None
                or not math.isfinite(bid) or not math.isfinite(ask)
                or bid <= 0 or ask <= 0 or ask < bid):
            self._dropped += 1
            self._context.logger.warning("incomplete feed payload dropped")
            return
        exchange_ts = _to_float(payload.get("exchange_timestamp")) or _to_float(payload.get("timestamp"))
        if exchange_ts is None or not math.isfinite(exchange_ts) or exchange_ts <= 0:
            self._dropped += 1
            self._context.logger.warning("feed tick without timestamp from %s dropped", provider)
            return
        # v2.5.0: the staleness clock now advances only on a genuinely
        # VALID tick -- moved past both validation blocks above. A feed
        # sending nothing but malformed packets used to touch this on
        # every arrival regardless, so INPUT_STARVED could never trip
        # (dropped=100%, forwarded=0, health still HEALTHY) as long as
        # SOMETHING kept arriving on the wire.
        self._last_input_at = time.time()
        self._touch(str(provider))
        if self._secondary_suppressed(str(provider)):
            self._suppressed_secondary += 1
            return
        await self._forward(payload, str(provider), str(symbol), bid, ask, exchange_ts, destination)

    def _secondary_suppressed(self, provider: str) -> bool:
        preferred = self._preferred_provider
        if not preferred or provider.upper() == preferred:
            return False
        info = self._providers.get(preferred)
        if info is None or not info.get("last_seen"):
            return False
        if info.get("down"):
            return False
        silent = self._official_time - float(info["last_seen"])
        return silent <= self._provider_timeout_s

    def _touch(self, provider: str) -> None:
        info = self._providers.setdefault(provider, {"ticks": 0, "down": False, "last_seen": 0.0})
        info["ticks"] += 1
        info["last_seen"] = self._official_time

    async def _forward(self, payload: dict[str, Any], provider: str, symbol: str,
                       bid: float, ask: float, exchange_ts: float, destination: str) -> None:
        if self._context is None:
            return
        volume = _to_float(payload.get("volume"))
        tick = {
            "symbol": symbol,
            "bid": bid,
            "ask": ask,
            "price": _to_float(payload.get("price")) or (bid + ask) / _SIDES,
            "volume": volume,
            "provider": provider,
            "timestamp": exchange_ts,
            "exchange_timestamp": exchange_ts,
            "received_at": _to_float(payload.get("received_at")),
        }
        for key in _IDENTITY_KEYS:
            if key in payload and key not in tick:
                tick[key] = payload[key]
        self._symbols.add(symbol)
        await self._context.publish(destination, tick)
        self._forwarded += 1
        if volume is not None:
            vol_event = {"symbol": symbol, "volume": volume, "provider": provider, "timestamp": exchange_ts}
            if "account_id" in payload:
                vol_event["account_id"] = payload["account_id"]
            await self._context.publish(EVENT_MARKET_VOLUME, vol_event)

    async def _on_heartbeat(self, payload: dict[str, Any]) -> None:
        official = _to_float(payload.get("official_time"))
        if not self._running or official is None or self._context is None:
            return
        # م-37/613 (ورقة ٤١، 2026-08-28): بوابة سلامة للساعة الرسمية — رفض
        # القيم السالبة/غير المنتهية قبل أي استخدام. مرجع زمني غير سليم كان
        # يُقبل كما هو فتفسد كل حسابات الصمت (silent) بعده.
        if not (official > 0.0) or official == float("inf"):
            return
        self._official_time = official
        for name, info in self._providers.items():
            if not info["last_seen"]:
                continue
            silent = official - info["last_seen"]
            if not info["down"] and silent > self._provider_timeout_s:
                info["down"] = True
                self._context.logger.warning("provider %s down, silent %ds", name, int(silent))
                await self._context.publish(EVENT_PROVIDER_DOWN,
                    {"provider": name, "silent_seconds": silent, "timestamp": official})
            elif info["down"] and silent <= self._provider_timeout_s:
                info["down"] = False
                await self._context.publish(EVENT_PROVIDER_RECOVERED,
                    {"provider": name, "silent_seconds": silent, "timestamp": official})
