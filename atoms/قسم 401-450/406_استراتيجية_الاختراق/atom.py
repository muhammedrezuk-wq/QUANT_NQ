from __future__ import annotations
from typing import Any
from core.contracts.atom import AtomBase, AtomContext, HealthState, HealthStatus
from shared.section_contract import section_atom
from shared.strategy_contract import StrategyRuntime, clip
from shared.tick_contract import VALIDATED_TICK_EVENT
from shared.trade_setup import (EVENT_SETUP, SETUP_BREAKOUT, build_setup,
                                net_ratio, round_trip_cost, validate_setup,
                                OK as SETUP_OK)

ATOM_VERSION = "2.2.0"
# الحدّ يبقى 1.5 بلا تغيير، كي يُقاس أثر رفع شرط السبريد وحده.
MIN_SETUP_RATIO = 1.5
EVENT_TICK = VALIDATED_TICK_EVENT
EVENT_OUT = "strategy.breakout.state"
STRATEGY_ID = "breakout_acceptance"
EPSILON = 1e-9
CONFIDENCE_BASE = 50.0
CONFIDENCE_FACTOR = 0.5


@section_atom("400", "406")
class Atom(AtomBase):
    def __init__(self):
        self._context = None
        self._running = False
        self._rt = StrategyRuntime(STRATEGY_ID)
        self._window = 32
        self._seen = self._emitted = 0
        self._setups = self._rejected = 0

    async def initialize(self, c):
        self._context = c
        self._rt.configure(c.config)
        self._window = int(c.config.get("tick_window", 32))
        c.subscribe(EVENT_TICK, self._on_tick)

    async def start(self):
        self._running = True

    async def stop(self):
        self._running = False

    async def shutdown(self):
        await self.stop()

    async def _on_tick(self, p: dict[str, Any]):
        if not self._running or self._context is None or not isinstance(p, dict):
            return
        item = self._rt.ingest(p)
        if item is None:
            return
        tick, s = item
        prices = list(s.prices)
        self._seen += 1
        prior = prices[-self._window - 1 : -1]
        if len(prior) < self._window:
            card = self._rt.card(
                tick,
                s,
                direction=0,
                strength=0,
                confidence=0,
                signal="breakout_unformed",
                status="insufficient_data",
            )
        else:
            price = prices[-1]
            high = max(prior)
            low = min(prior)
            width = max(high - low, price * EPSILON)
            direction = 100.0 if price > high else -100.0 if price < low else 0.0
            distance = (
                price - high if direction > 0 else low - price if direction < 0 else 0.0
            )
            strength = clip(distance / width * 100)
            confidence = clip(CONFIDENCE_BASE + strength * CONFIDENCE_FACTOR)
            card = self._rt.card(
                tick,
                s,
                direction=direction,
                strength=strength,
                confidence=confidence,
                signal=(
                    "bullish_breakout_acceptance"
                    if direction > 0
                    else (
                        "bearish_breakout_acceptance"
                        if direction < 0
                        else "inside_reference_range"
                    )
                ),
                evidence={"range_high": high, "range_low": low, "distance": distance},
            )
        await self._context.publish(EVENT_OUT, card)
        self._emitted += 1
        await self._propose_setup(tick, card)

    async def _propose_setup(self, tick: dict[str, Any], card: dict[str, Any]) -> None:
        """ينشر إعداد اختراق مملوكًا — المالك الثاني بعد 410.

        ورقة التنفيذ ٢٠٢٦-٠٩-٠٦ (§١٢): لا يكفي أن يقول 406
        «bearish_breakout»؛ عليه أن يقول أين تموت فكرته وإلى أين تقصد.
        وكلاهما من بنيته هو: الاختراق يُبطله **العودة داخل المدى**،
        وهدفه حركة مقيسة بعرض المدى نفسه مسقطة من نقطة الكسر.
        """
        meta = card.get("metadata") or {}
        high, low = meta.get("range_high"), meta.get("range_low")
        direction = card.get("direction") or 0.0
        entry = card.get("price") or tick.get("price")
        if not direction or high is None or low is None or not entry:
            return
        buy = direction > 0
        width = float(high) - float(low)
        break_level = float(high) if buy else float(low)
        setup = build_setup(
            owner="406",
            setup_type=SETUP_BREAKOUT,
            side="buy" if buy else "sell",
            entry_reference=entry,
            invalidation_price=break_level,
            invalidation_source="406:range_edge",
            invalidation_reason=("عودة السعر داخل المدى تُبطل قبول الاختراق"),
            target_price=(break_level + width) if buy else (break_level - width),
            target_source="406:measured_move",
            target_reason="حركة مقيسة بعرض المدى مسقطة من نقطة الكسر",
            account_id=tick.get("account_id") or "",
            broker=tick.get("broker") or "",
            symbol=tick.get("symbol") or "",
            cycle_id=tick.get("cycle_id") or "",
            period_start=tick.get("period_start"),
            structure_id="range:%s:%s" % (round(float(low), 8), round(float(high), 8)),
            strength=card.get("strength") or 0.0,
            confidence=card.get("confidence") or 0.0,
            evidence={"range_high": high, "range_low": low,
                      "distance": meta.get("distance"), "signal": card.get("signal")},
        )
        reason = validate_setup(setup)
        if reason == SETUP_OK:
            # كما في 410 (حكم المالك ٢٠٢٦-٠٩-٠٦): السبريد ليس تعريفًا
            # لصلاحية الإبطال. فحصان مستقلّان — بنيويّ ثم اقتصاديّ:
            #   ١) حدّ المدى مستوًى حقيقيّ: مدى بعرض موجب واختراق فعليّ.
            #   ٢) النسبة بعد تكاليف الجهتين تبلغ الحدّ.
            cost = round_trip_cost(tick.get("bid"), tick.get("ask"))
            if width <= 0.0 or abs(float(entry) - break_level) <= 0.0:
                reason = "INVALIDATION_NOT_STRUCTURAL"
            elif net_ratio(setup, cost) < MIN_SETUP_RATIO:
                reason = "NET_RR_REJECTED"
        if reason != SETUP_OK:
            self._rejected += 1
            if self._rejected <= 20:
                self._context.logger.warning(
                    "406 إعداد مرفوض %s: %s (دخول=%s إبطال=%s هدف=%s)",
                    setup.get("symbol"), reason, setup.get("entry_reference"),
                    setup.get("invalidation_price"), setup.get("target_price"))
            return
        self._setups += 1
        self._context.logger.warning(
            "406 إعداد %s %s: دخول=%.2f إبطال=%.2f هدف=%.2f setup_id=%s",
            setup["symbol"], setup["side"], setup["entry_reference"],
            setup["invalidation_price"], setup["target_price"], setup["setup_id"])
        await self._context.publish(EVENT_SETUP, setup)

    async def snapshot(self):
        return {
            "runtime": self._rt.snapshot(),
            "seen": self._seen,
            "emitted": self._emitted,
        }

    async def restore(self, x):
        if isinstance(x, dict):
            self._rt.restore(x.get("runtime"))
            self._seen = int(x.get("seen", 0))
            self._emitted = int(x.get("emitted", 0))

    async def health_check(self):
        if not self._running:
            return HealthStatus(state=HealthState.UNHEALTHY, message="NOT_STARTED")
        return HealthStatus(
            state=HealthState.HEALTHY if self._seen else HealthState.DEGRADED,
            message="ticks=%d emitted=%d" % (self._seen, self._emitted),
            details={
                "ticks": self._seen,
                "emitted": self._emitted,
                "invalid": self._rt.invalid,
            },
        )
