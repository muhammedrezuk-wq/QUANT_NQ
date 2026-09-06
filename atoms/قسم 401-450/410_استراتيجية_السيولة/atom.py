from __future__ import annotations
from typing import Any
from core.contracts.atom import AtomBase, AtomContext, HealthState, HealthStatus
from shared.section_contract import section_atom
from shared.strategy_contract import StrategyRuntime, clip
from shared.tick_contract import VALIDATED_TICK_EVENT
from shared.trade_setup import (EVENT_SETUP, SETUP_LIQUIDITY_RAID, build_setup,
                                meets_scale, net_ratio, round_trip_cost, validate_setup,
                                OK as SETUP_OK)

ATOM_VERSION = "2.4.0"
# ٢٠٢٦-٠٩-٠٦: المالك لا يقترح فكرة لا يُطاق اقتصادها، ولا ينتظر حارسًا
# يقصّها. والحدّ يبقى كما هو (1.5) كي يُقاس أثر رفع شرط السبريد وحده.
MIN_SETUP_RATIO = 1.5
EVENT_TICK = VALIDATED_TICK_EVENT
EVENT_OUT = "strategy.liquidity.state"
STRATEGY_ID = "liquidity_raid"
EPSILON = 1e-9
CONFIDENCE_BASE = 55.0
CONFIDENCE_FACTOR = 0.45


@section_atom("400", "410")
class Atom(AtomBase):
    def __init__(self):
        self._context = None
        self._running = False
        self._rt = StrategyRuntime(STRATEGY_ID)
        self._window = 24
        self._seen = self._emitted = 0
        self._setups = self._rejected = 0

    async def initialize(self, c):
        self._context = c
        self._rt.configure(c.config)
        self._window = int(c.config.get("tick_window", 24))
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
        reference = prices[-self._window - 2 : -2]
        if len(reference) < self._window:
            card = self._rt.card(
                tick,
                s,
                direction=0,
                strength=0,
                confidence=0,
                signal="liquidity_context_unformed",
                status="insufficient_data",
            )
        else:
            low = min(reference)
            high = max(reference)
            previous = prices[-2]
            current = prices[-1]
            bullish = previous < low and current >= low
            bearish = previous > high and current <= high
            direction = 100.0 if bullish else -100.0 if bearish else 0.0
            raid = low - previous if bullish else previous - high if bearish else 0
            span = max(high - low, current * EPSILON)
            strength = clip(raid / span * 100)
            confidence = clip(CONFIDENCE_BASE + strength * CONFIDENCE_FACTOR)
            card = self._rt.card(
                tick,
                s,
                direction=direction,
                strength=strength,
                confidence=confidence,
                signal=(
                    "bullish_liquidity_reclaim"
                    if bullish
                    else "bearish_liquidity_reclaim" if bearish else "no_confirmed_raid"
                ),
                evidence={
                    "reference_low": low,
                    "reference_high": high,
                    "raid_distance": raid,
                },
            )
        await self._context.publish(EVENT_OUT, card)
        self._emitted += 1
        await self._propose_setup(tick, card)

    async def _propose_setup(self, tick: dict[str, Any], card: dict[str, Any]) -> None:
        """ينشر **إعداد صفقة مملوكًا** حين يكتمل الكنس والاسترداد.

        ورقة التنفيذ ٢٠٢٦-٠٩-٠٦ (§١٣): 410 هو أوّل مالك لعقد الإعداد،
        لأنه الوحيد الذي يملك أدلّة بنيوية حقيقية — طرفا النافذة وسعر
        الكنس. والإبطال هنا ليس رقمًا مستعارًا من خريطة عامّة بل **معنى
        الفكرة نفسها**: الاسترداد يموت إذا عاد السعر خلف طرف الكنس.
        والهدف هو السيولة المقابلة التي تقصدها الحركة.

        بطاقة الاستراتيجية أعلاه تبقى كما هي — سياقٌ يصوّت. الجديد أن
        الفكرة صارت تملك هندستها، فلا يخترعها 581 من بعدُ.
        """
        meta = card.get("metadata") or {}
        low, high = meta.get("reference_low"), meta.get("reference_high")
        direction = card.get("direction") or 0.0
        entry = card.get("price") or tick.get("price")
        raid = meta.get("raid_distance")
        if not direction or low is None or high is None or not entry:
            return
        buy = direction > 0
        # طرف الكنس: السعر الذي تجاوز الحدّ قبل الاسترداد. هو نفسه حدّ
        # الإبطال — تجاوزه ثانيةً يعني أن الاسترداد لم يكن استردادًا.
        sweep_edge = (low - raid) if buy else (high + raid)
        setup = build_setup(
            owner="410",
            setup_type=SETUP_LIQUIDITY_RAID,
            side="buy" if buy else "sell",
            entry_reference=entry,
            invalidation_price=sweep_edge,
            invalidation_source="410:sweep_edge",
            invalidation_reason=("عودة السعر تحت طرف الكنس تُبطل الاسترداد"
                                 if buy else
                                 "عودة السعر فوق طرف الكنس تُبطل الاسترداد"),
            target_price=high if buy else low,
            target_source="410:opposite_liquidity",
            target_reason="السيولة المقابلة في الطرف الآخر من النافذة",
            account_id=tick.get("account_id") or "",
            broker=tick.get("broker") or "",
            symbol=tick.get("symbol") or "",
            cycle_id=tick.get("cycle_id") or "",
            period_start=tick.get("period_start"),
            structure_id="raid:%s:%s" % (round(float(low), 8), round(float(high), 8)),
            strength=card.get("strength") or 0.0,
            confidence=card.get("confidence") or 0.0,
            evidence={"reference_low": low, "reference_high": high,
                      "raid_distance": raid, "signal": card.get("signal")},
        )
        reason = validate_setup(setup)
        if reason == SETUP_OK:
            # ٢٠٢٦-٠٩-٠٦ (حكم المالك بعد القياس: ٢٢ رفضًا من ٢٧ بسبب
            # RISK_INSIDE_SPREAD): كان الإبطال يُحاكَم بالسبريد وحده —
            # «حكمًا على جودة الفكرة من معيار واحد، بدل أن يكون جزءًا من
            # حساب الاقتصاد الكامل». والسبريد ليس تعريفًا لصلاحية
            # الإبطال. الفحصان مستقلّان الآن:
            #
            #   ١) صلاحية الإبطال **بنيويًّا**: أن يكون طرفَ كنسٍ وقع
            #      فعلًا — سعرًا طبعه السوق، لا رقمًا مشتقًّا. كنسٌ
            #      مسافته صفر ليس كنسًا، وإبطالٌ ملاصق للدخول ليس مستوًى.
            #   ٢) الاقتصاد: النسبة **بعد** تكاليف الجهتين تبلغ الحدّ.
            #      فكرةٌ إبطالها ٣ وهدفها ٤٠ تُقبل، وأخرى إبطالها ٢٠
            #      وهدفها ٢٥ تُرفض — والضيق ليس عيبًا بذاته.
            raid_distance = abs(float(raid or 0.0))
            gap = abs(float(entry) - float(sweep_edge))
            cost = round_trip_cost(tick.get("bid"), tick.get("ask"))
            if raid_distance <= 0.0 or gap <= 0.0:
                reason = "INVALIDATION_NOT_STRUCTURAL"
            elif not meets_scale(setup):
                reason = "SCALE_TOO_SMALL"
            elif net_ratio(setup, cost) < MIN_SETUP_RATIO:
                reason = "NET_RR_REJECTED"
        if reason != SETUP_OK:
            # الرفض يُعلن ولا يُبتلع (§٢٦): النظام يقول لماذا لم يتداول.
            self._rejected += 1
            if self._rejected <= 20:
                self._context.logger.warning(
                    "410 إعداد مرفوض %s: %s (دخول=%s إبطال=%s هدف=%s)",
                    setup.get("symbol"), reason, setup.get("entry_reference"),
                    setup.get("invalidation_price"), setup.get("target_price"))
            return
        self._setups += 1
        self._context.logger.warning(
            "410 إعداد %s %s: دخول=%.2f إبطال=%.2f هدف=%.2f setup_id=%s",
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
                "setups": self._setups,
                "setups_rejected": self._rejected,
            },
        )
