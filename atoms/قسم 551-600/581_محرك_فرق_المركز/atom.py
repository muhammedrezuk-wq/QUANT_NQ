from __future__ import annotations
import time
from typing import Any
from core.contracts.atom import AtomBase, AtomContext, HealthState, HealthStatus
from shared.decision_dials import (EVENT_COMMAND as EVENT_SETTINGS_COMMAND,
                                   EVENT_STATE as EVENT_SETTINGS_STATE,
                                   apply_command, effective_value)
from shared.horizon_profile import hysteresis_override
from shared.position_delta_recompute import recompute
from shared.trade_setup import (EVENT_SETUP, is_alive, is_broken, validate_setup,
                                OK as SETUP_OK)

ATOM_VERSION = "3.4.1"
EVENT_GATE = "decision.gate.passed"
EVENT_GATE_BLOCKED = "decision.gate.blocked"
EVENT_GATE_RECORDED = "decision.gate.recorded"
EVENT_CONTEXT = "decision.resolved.state"
EVENT_VERDICT = "decision.approved.state"
GATE_MARK = "_gate"
FILTER_PASSED = "FILTER_PASSED"
FILTER_BLOCKED = "FILTER_BLOCKED"
FILTER_PENDING = "FILTER_PENDING"
FAIL_CLOSED = "RESTORE_FAILED_FAIL_CLOSED"
EVENT_LEDGER = "risk.asset_ledger.state"
EVENT_PORTFOLIO = "asset.portfolio.state"
EVENT_DIAL = "dial.profile.state"
EVENT_SPECS = "market.symbol_specs"
EVENT_BROKER_TICK = "feed.mt5.tick"
PRICE_SOURCE = "mt5_broker_feed"
EVENT_TICK = EVENT_BROKER_TICK
EVENT_CANDLE = "market_data.candle_closed"
EVENT_POSITIONS = "platform.positions.state"
EVENT_STOP = "risk.asset_stop.state"
EVENT_OUT = "perpetual.target.state"
BUY = "buy"
SELL = "sell"
WAIT = "wait"
ADD = "ADD"
REDUCE = "REDUCE"
HEDGE = "HEDGE"
REBALANCE = "REBALANCE"
HOLD = "HOLD"
BLOCKED = "BLOCKED"
SEP = "\x1f"
DEFAULT_BANDS = {"0.0": 0.0, "0.2": 0.1, "0.4": 0.25, "0.6": 0.5}
DEFAULT_HEDGE_BANDS = {"0.0": 1.0, "0.2": 0.7, "0.4": 0.4, "0.6": 0.2}
REASON_NEUTRAL_KEEP = "NEUTRAL_KEEP_GROSS"


def real(value: Any) -> float | None:
    try: result = float(value)
    except (TypeError, ValueError): return None
    return result if result == result else None


def key(account: Any, symbol: Any) -> str: return str(account or "") + SEP + str(symbol or "")


def cycle_rank(cycle: Any) -> float | None:
    try: return float(str(cycle or "").rsplit("|", 1)[-1])
    except (TypeError, ValueError): return None


def is_stale(incoming: Any, accepted: float | None) -> bool:
    rank = cycle_rank(incoming)
    return rank is not None and accepted is not None and rank < accepted


def side(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "BUY" if text in ("buy", "long", "1") else "SELL" if text in ("sell", "short", "-1") else ""


_LEVEL_HISTORY = 64
_LEVEL_EPSILON = 1e-9
# هامش دمج المستويات: نصف نقطة أساس (4 دولارات على 80,000) — أقلّ من
# سبريد البيتكوين المقيس (5.00)، فلا يدمج مستويين يمكن التمييز بينهما
# تداوليًّا، ويمنع امتلاء الخريطة بتوائم تطرد البعيد.
_LEVEL_MERGE_FRAC = 0.00005
# ٢٠٢٦-٠٩-٠٥ (حكم المالك، وهو ردّ على ما بنيتُه أنا): «عم تساوي قالب
# ثابت على سِستم تحليلي — ثلاث قوالب يعني ستوب مو دقيق جاي على تحليل
# مباشر». نوافذ المدى الزمنية (60/300/900 ثانية) كانت أرقامًا اخترعتها
# لا مستويات قالها التحليل، فحُذفت. المستويات تأتي من الذرّات التي
# تقيسها فعلًا، وهذه خريطة مصادرها المقيسة من مانيفستاتها وحمولاتها:
#
#   202 الهيكل الخارجي  structure.external.state  swing_high · swing_low
#   203 الهيكل الداخلي  structure.internal.state  swing_high · swing_low
#   204 كاشف BOS        structure.bos.state       level
#   205 كاشف CHoCH      structure.choch.state     level
#   206 تحوّل MSS        structure.mss.state       level
#   254 كنس السيولة     liquidity.sweep.state     level
#   255 الفجوة FVG      liquidity.fvg.state       gap_top · gap_bottom
#   157 الفجوات         analysis.gap.state        gap حسب حمولتها
#
# الهيكل الخارجي يعطي المسافات الواسعة (الوقف ٧٠)، والداخلي المتوسطة
# (٤٠)، والسوينغ والبرك الضيقة — فيختار الوقف مستوى حقيقيًّا بحسب ما
# تحرّك السوق، والحجم يتبعه لأنه محسوب منه.
LEVEL_FIELDS = ("swing_high", "swing_low", "level", "gap_top", "gap_bottom",
                "high", "low", "price")


def _push_level(bucket: dict, key: str, price: float) -> None:
    """يحفظ مستوى بنيويًّا في الخريطة بلا تكرار عمليّ وبسقف طول.

    ٢٠٢٦-٠٩-٠٦ (مقيس): المنع كان بالتطابق التامّ وحده (1e-9)، فامتلأت
    الخريطة بمستويات متلاصقة — قِيست ثلاثة تحت السعر تفصلها 0.11 و0.57
    دولار (79,853.07 · 79,853.18 · 79,853.75) وكلها على بعد نقطة واحدة
    من السعر. ومع سقف 24، كانت هذه التوائم **تطرد** المستويات البعيدة
    التي يحتاجها الهدف، فيُطلب هدف على بعد 30 ولا يوجد إلا ما بُعده 1.
    مستويان يفصلهما أقلّ من نصف نقطة أساس ليسا مستويين — يُدمجان،
    والسعة تتّسع لتبقى المسافات البعيدة حاضرة.
    """
    levels = bucket.setdefault(key, [])
    merge = max(price * _LEVEL_MERGE_FRAC, _LEVEL_EPSILON)
    if any(abs(x - price) < merge for x in levels):
        return
    levels.append(price)
    if len(levels) > _LEVEL_HISTORY:
        del levels[:-_LEVEL_HISTORY]


def side_of(payload: dict[str, Any]) -> str:
    raw = payload.get("decision_side") or payload.get("direction") or payload.get("signal") or WAIT
    return str(raw).strip().lower()


class Atom(AtomBase):
    def __init__(self) -> None:
        self._context = None
        self._running = False
        self._bands = DEFAULT_BANDS.copy()
        self._hedge_bands = DEFAULT_HEDGE_BANDS.copy()
        self._s_enter = 0.20
        self._s_exit = 0.15
        self._held_dir = {}
        self._last_strength = {}
        self._last_gross_target = {}
        self._pending_held = {}
        self._restore_error = ""
        self._cleared = set()
        self._held_restored = 0
        self._held_dropped = 0
        self._max_target = 20.0
        self._max_step = 1.0
        self._min_volume = 0.01
        self._hedge_cost_per_volume = 0.0
        self._spread_price = {}
        self._spread_cost = {}
        self._swings = {}
        self._liquidity_pools = {}
        self._level_sources = {}
        # إعداد الصفقة لكل رمز — مملوك لمن أنشأه، و581 حافظٌ لا مؤلّف.
        self._setups = {}
        self._setup_seen = self._setup_rejected = 0
        self._trend = {}
        self._sweep = {}
        self._decisions = {}
        self._ledgers = {}
        self._portfolios = {}
        self._dials = {}
        self._verdicts = {}
        self._blocked = 0
        self._cycle_rank = {}
        self._stale_decisions = 0
        self._stale_verdicts = 0
        self._vpu = {}
        self._price = {}
        self._sources = {}
        self._positions = {}
        self._stops = {}
        self._last = {}
        self._versions = {}
        self._seen = 0
        self._emitted = 0
        self._settings_applied = 0

    async def initialize(self, context: AtomContext) -> None:
        self._context = context
        cfg = context.config
        raw = cfg.get("bands") if isinstance(cfg.get("bands"), dict) else DEFAULT_BANDS
        self._bands = {str(k): float(v) for k, v in raw.items()}
        raw_h = cfg.get("hedge_bands") if isinstance(cfg.get("hedge_bands"), dict) else DEFAULT_HEDGE_BANDS
        self._hedge_bands = {str(k): float(v) for k, v in raw_h.items()}
        self._s_enter = float(cfg.get("s_enter", 0.20))
        self._s_exit = float(cfg.get("s_exit", 0.15))
        self._max_target = float(cfg.get("max_target_volume", 20.0))
        self._max_step = float(cfg.get("max_step_volume", 1.0))
        self._min_volume = float(cfg.get("min_volume", 0.01))
        self._hedge_cost_per_volume = max(0.0, float(cfg.get("hedge_cost_per_volume", 0.0)))
        context.subscribe(EVENT_GATE, self._on_gate_passed)
        context.subscribe(EVENT_GATE_BLOCKED, self._on_gate_blocked)
        context.subscribe(EVENT_GATE_RECORDED, self._on_gate_recorded)
        context.subscribe(EVENT_CONTEXT, self._on_context)
        context.subscribe(EVENT_VERDICT, self._on_verdict)
        context.subscribe(EVENT_LEDGER, self._on_ledger)
        context.subscribe(EVENT_PORTFOLIO, self._on_portfolio)
        context.subscribe(EVENT_DIAL, self._on_dial)
        context.subscribe(EVENT_SPECS, self._on_specs)
        context.subscribe(EVENT_STOP, self._on_stop)
        context.subscribe(EVENT_TICK, self._on_tick)
        context.subscribe(EVENT_CANDLE, self._on_candle)
        context.subscribe(EVENT_POSITIONS, self._on_positions)
        context.subscribe(EVENT_SETTINGS_COMMAND, self._on_setting)
        # ٢٠٢٦-٠٩-٠٥: هوية الوسيط لازمة لطلب الأمر (552 يرفض بلا وسيط).
        context.subscribe("platform.account.state", self._on_account_identity)
        # برك السيولة: عليها يُبنى الوقف والهدف بدل نسبة ثابتة.
        context.subscribe("liquidity.buyside.state", self._on_liquidity)
        context.subscribe("liquidity.sellside.state", self._on_liquidity)
        # السوينغ: أقرب حدّ بنيوي — عليه يقوم السكالبينغ.
        context.subscribe("structure.swing.state", self._on_swing)
        # مصادر المستويات التحليلية المباشرة — لا قوالب زمنية.
        for event in ("structure.external.state", "structure.internal.state",
                      "structure.bos.state", "structure.choch.state",
                      "structure.mss.state", "liquidity.sweep.state",
                      "liquidity.fvg.state", "analysis.gap.state"):
            context.subscribe(event, self._on_analysis_level)
        # فلتر الاتجاه: حالة الاتجاه من 207 وكنس السيولة من 254.
        context.subscribe("structure.trend.state", self._on_trend)
        context.subscribe("liquidity.sweep.state", self._on_sweep)
        # ٢٠٢٦-٠٩-٠٦ (حكم المالك: «حلّها من جذر لا ترقّع»): إعداد الصفقة
        # هو صاحب الفكرة، ومنه وحده يأتي الإبطال والهدف. 581 يسمعه ولا
        # يخترع بديلًا عنه.
        context.subscribe(EVENT_SETUP, self._on_setup)

    async def _on_trend(self, payload):
        """حالة الاتجاه من 207: uptrend · downtrend · range · transition."""
        if not isinstance(payload, dict):
            return
        symbol = str(payload.get("symbol") or "").strip().upper()
        signal = str(payload.get("signal") or "").strip().lower()
        if symbol and signal:
            self._trend[symbol] = (signal, time.time())

    async def _on_sweep(self, payload):
        """كنس السيولة من 254: قمّة أو قاع اختُرق كذبًا ثم ارتدّ.

        الكنس هو ما يميّز طرفًا يُباع منه من طرفٍ يُخترق فيُشترى — وهو
        الإذن الوحيد بصفقة عكس الاتجاه المعلن.
        """
        if not isinstance(payload, dict):
            return
        symbol = str(payload.get("symbol") or "").strip().upper()
        signal = str(payload.get("signal") or "").strip().lower()
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        direction = str(meta.get("direction") or payload.get("direction") or "").lower()
        if not symbol or signal in ("", "none"):
            return
        side = ("buyside" if "buy" in (signal + direction)
                else "sellside" if "sell" in (signal + direction) else "")
        if side:
            self._sweep[symbol] = (side, time.time())

    async def start(self): self._running = True
    async def stop(self): self._running = False
    async def shutdown(self): await self.stop()

    async def _on_decision(self, payload, side_override=None, gate_approved=None):
        if not self._running or not isinstance(payload, dict): return
        symbol = str(payload.get("symbol") or "")
        if not symbol: return
        account = str(payload.get("account_id") or "*")
        scope_key = key(account, symbol)
        cycle = str(payload.get("cycle_id") or "")
        if side_override == WAIT and gate_approved is None:
            held = self._decisions.get(scope_key) or self._decisions.get(key("*", symbol))
            if held is not None and held.get(GATE_MARK) and str(held.get("cycle_id") or "") == cycle: return
        if is_stale(payload.get("cycle_id"), self._cycle_rank.get(scope_key)):
            self._stale_decisions += 1
            return
        rank = cycle_rank(payload.get("cycle_id"))
        if rank is not None: self._cycle_rank[scope_key] = rank
        row = dict(payload)
        row["direction"] = side_override if side_override is not None else side_of(payload)
        row[GATE_MARK] = gate_approved is not None
        self._decisions[scope_key] = row
        if gate_approved is not None and cycle:
            self._verdicts[scope_key] = {"cycle_id": cycle, "approved": gate_approved}
        targets = [key(account, symbol)] if account != "*" else [k for k in self._ledgers if k.endswith(SEP + symbol)]
        for k in targets: await self._recompute(k)

    async def _on_gate_passed(self, payload): await self._on_decision(payload, None, True)

    async def _on_gate_blocked(self, payload): await self._on_decision(payload, None, False)

    async def _on_gate_recorded(self, payload): await self._on_decision(payload, WAIT, False)

    async def _on_context(self, payload): await self._on_decision(payload, WAIT, None)

    async def _on_verdict(self, payload):
        if not self._running or not isinstance(payload, dict): return
        symbol = str(payload.get("symbol") or "")
        if not symbol: return
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        cycle = str(payload.get("cycle_id") or "")
        account = str(payload.get("account_id") or "*")
        scope_key = key(account, symbol)
        if is_stale(cycle, self._cycle_rank.get(scope_key)):
            self._stale_verdicts += 1
            return
        flag = payload.get("approved")
        if not isinstance(flag, bool): flag = meta.get("approved")
        self._verdicts[scope_key] = {"cycle_id": cycle, "approved": flag is True}
        for k in [x for x in self._ledgers if x.endswith(SEP + symbol)]:
            held = self._decisions.get(k) or self._decisions.get(key("*", symbol))
            if held is not None and str(held.get("cycle_id") or "") == cycle: await self._recompute(k)

    def _filter_verdict(self, scope_key, decision):
        account, symbol = scope_key.split(SEP, 1)
        verdict = self._verdicts.get(scope_key) or self._verdicts.get(key("*", symbol))
        if verdict is None or verdict.get("cycle_id") != str(decision.get("cycle_id") or ""): return FILTER_PENDING
        return FILTER_PASSED if verdict.get("approved") else FILTER_BLOCKED

    async def _on_ledger(self, payload):
        if not self._running or not isinstance(payload, dict): return
        rows = payload.get("ledgers")
        rows = rows if isinstance(rows, list) else [payload]
        for row in rows:
            if isinstance(row, dict) and row.get("symbol"):
                k = key(row.get("account_id"), row.get("symbol"))
                self._ledgers[k] = dict(row)
                await self._recompute(k)

    async def _on_portfolio(self, payload):
        if not self._running or not isinstance(payload, dict): return
        rows = payload.get("portfolios")
        rows = rows if isinstance(rows, list) else ([payload] if payload.get("symbol") else [])
        for row in rows:
            if isinstance(row, dict) and row.get("symbol"):
                k = key(row.get("account_id"), row.get("symbol"))
                self._portfolios[k] = dict(row)
                await self._recompute(k)

    async def _on_dial(self, payload):
        if not self._running or not isinstance(payload, dict): return
        for row in payload.get("profiles", []) if isinstance(payload.get("profiles"), list) else []:
            if isinstance(row, dict) and row.get("symbol"):
                k = key(row.get("account_id"), row.get("symbol"))
                self._dials[k] = dict(row)
                await self._recompute(k)

    async def _on_specs(self, payload):
        if not self._running or not isinstance(payload, dict): return
        rows = payload.get("symbols")
        rows = [rows] if isinstance(rows, dict) else rows
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict): continue
            account = str(row.get("account_id") or payload.get("account_id") or "")
            symbol = str(row.get("symbol") or "")
            tv = real(row.get("tick_value"))
            ts = real(row.get("tick_size"))
            scope = key(account, symbol)
            if account and symbol and tv is not None and ts and ts > 0:
                self._vpu[scope] = tv / ts
                if scope in self._spread_price: self._spread_cost[scope] = self._spread_price[scope] * self._vpu[scope]
            # حدّ الوسيط الأدنى لمسافة الوقف/الهدف: مستوى تحليلي أقرب منه
            # يرفضه الوسيط، فيُزاح إليه بدل أن يُرسل ويُرفض.
            point = real(row.get("point")) or real(row.get("tick_size")) or 0.0
            stops_level = real(row.get("stops_level")) or 0.0
            if account and symbol:
                if not hasattr(self, "_broker_min_stop"):
                    self._broker_min_stop = {}
                self._broker_min_stop[scope] = stops_level * point

    async def _on_stop(self,payload):
        if not self._running or not isinstance(payload,dict): return
        rows=payload.get("stops") if isinstance(payload.get("stops"),list) else [payload]
        for row in rows:
            if isinstance(row,dict) and row.get("symbol"):
                self._stops[key(row.get("account_id"),row.get("symbol"))]=dict(row)
                await self._recompute(key(row.get("account_id"),row.get("symbol")))

    async def _on_tick(self, payload):
        if not self._running or not isinstance(payload, dict): return
        account = str(payload.get("account_id") or "")
        symbol = str(payload.get("symbol") or "")
        scope = key(account, symbol)
        price = real(payload.get("price"))
        bid = real(payload.get("bid"))
        ask = real(payload.get("ask"))
        if not account or not symbol: return
        if price is None and bid is not None and ask is not None: price = (bid + ask) / 2
        if bid is not None and ask is not None and bid > 0 and ask >= bid:
            self._spread_price[scope] = ask - bid
            if scope in self._vpu: self._spread_cost[scope] = (ask - bid) * self._vpu[scope]
        if price and price > 0:
            self._price[scope] = price

    async def _on_candle(self, payload):
        if not self._running or not isinstance(payload, dict): return
        account = str(payload.get("account_id") or "")
        symbol = str(payload.get("symbol") or "")
        price = real(payload.get("close"))
        if account and symbol and price and price > 0: self._price[key(account, symbol)] = price

    async def _on_swing(self, payload):
        """يلتقط آخر قمة/قاع سوينغ — أقرب مستوى بنيوي، وهو ما يلزم السكالبينغ.

        ٢٠٢٦-٠٩-٠٥ (حكم المالك: «لازم يتداول أسرع من هيك — سكالبينغ»):
        برك السيولة (251) تحتفظ بمستوى قد يبعد آلاف النقاط — قِيس وقف على
        بعد 7,156 — بينما السوينغ من 201 (fractal_center) هو أقرب حدّ
        بنيوي فعلي. كلاهما يُجمع، ويُختار الأنسب عند بناء الأمر.
        """
        if not isinstance(payload, dict):
            return
        symbol = str(payload.get("symbol") or "").strip().upper()
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        price = real(meta.get("price")) or real(payload.get("price"))
        signal = str(payload.get("signal") or "").lower()
        if not symbol or price is None or price <= 0:
            return
        if not hasattr(self, "_swings"):
            self._swings = {}
        bucket = self._swings.setdefault(symbol, {})
        # ٢٠٢٦-٠٩-٠٥ (مقيس): الاحتفاظ بآخر مستوى واحد لكل جهة جعل الهدف
        # دائمًا الجارَ الأقرب — بركتان تفصلهما 13 نقطة (79,724.87 و
        # 79,737.62) ⇒ كل أمر يسقط بـRR_BELOW_MIN (rr=0.18..0.35).
        # خريطة المستويات تحفظ آخر _LEVEL_HISTORY مستوى لكل جهة، فيصير
        # للهدف مدى حقيقي بدل نقطة واحدة، والوقف يبقى الأقرب.
        if signal == "swing_high":
            bucket["high"] = price
            _push_level(bucket, "highs", price)
        elif signal == "swing_low":
            bucket["low"] = price
            _push_level(bucket, "lows", price)
        bucket["seen_at"] = time.time()

    async def _on_setup(self, payload):
        """يحفظ آخر إعداد صالح لكل رمز — ولا يعدّله أبدًا.

        ورقة التنفيذ ٢٠٢٦-٠٩-٠٦ (§١٤): 581 مدير صفقة لا مؤلّفها. يستقبل
        الإعداد كما نطق به مالكه، ويرفض ما لا يصحّ، ولا يخترع بديلًا.
        """
        if not self._running or not isinstance(payload, dict):
            return
        reason = validate_setup(payload)
        if reason != SETUP_OK:
            self._setup_rejected += 1
            return
        symbol = str(payload.get("symbol") or "").strip().upper()
        if not symbol:
            return
        self._setups[symbol] = dict(payload)
        self._setup_seen += 1
        # ٢٠٢٦-٠٩-٠٦ (مقيس — خمسون إعدادًا ولا أمر): الفكرة تولد على
        # التِكّة بينما `recompute` كان يعمل على نبضة القرار وحدها، فحين
        # يُسأل الإعداد يكون قد انتهى أجله أو كسره السعر (SETUP_EXPIRED ·
        # SETUP_ALREADY_BROKEN). والإعداد صار **الفاتح**، فمن حقّه أن
        # يُطلق التقييم لحظة ولادته — أنضر ما تكون الفكرة.
        for key in [x for x in self._ledgers if x.endswith(SEP + symbol)]:
            await self._recompute(key)

    async def _on_analysis_level(self, payload):
        """يلتقط كل مستوى سعري تقوله ذرّات التحليل مباشرة.

        ٢٠٢٦-٠٩-٠٥ (حكم المالك): الوقف يجب أن يجيء «على تحليل مباشر» لا
        على قالب. كل ذرّة هنا تقيس مستواها بطريقتها — الهيكل الخارجي
        بقمم وقيعان أوسع، والداخلي بأضيق، وBOS بمستوى الاختراق، وFVG
        بحدّي الفجوة. المستوى يُقبل كما نُشر، ويُصنَّف قمّة أو قاعًا
        بموضعه من السعر الحالي، فتصير خريطة المستويات ذات مدى حقيقي
        مصدره التحليل وحده.
        """
        if not isinstance(payload, dict):
            return
        symbol = str(payload.get("symbol") or "").strip().upper()
        if not symbol:
            return
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        reference = real(meta.get("close")) or real(meta.get("price")) \
            or real(payload.get("price"))
        if reference is None or reference <= 0:
            return
        bucket = self._swings.setdefault(symbol, {})
        source = str(payload.get("id") or payload.get("signal") or "")
        found = 0
        for field in LEVEL_FIELDS:
            value = real(meta.get(field))
            if value is None or value <= 0 or value == reference:
                continue
            _push_level(bucket, "highs" if value > reference else "lows", value)
            found += 1
        if found:
            bucket["seen_at"] = time.time()
            self._level_sources[source] = self._level_sources.get(source, 0) + found

    async def _on_liquidity(self, payload):
        """يلتقط برك السيولة — عليها يُعلَّق الوقف والهدف.

        ٢٠٢٦-٠٩-٠٥ (حكم المالك): «ستوب وهدف ثابتين من رقم هندسي على
        ميزانية — هاد عيب، كل هالمحلّلات ما توصلك مكان ستوب من تحليل».
        252 ينشر سعر بركة الشراء (pool_high) و253 بركة البيع، وهما
        المستويان اللذان يُبنى عليهما الخروج بدل نسبة ثابتة.
        """
        if not isinstance(payload, dict):
            return
        symbol = str(payload.get("symbol") or "").strip().upper()
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        price = real(meta.get("price"))
        side = str(meta.get("side") or "").lower()
        if not symbol or price is None or price <= 0:
            return
        if not hasattr(self, "_liquidity_pools"):
            self._liquidity_pools = {}
        bucket = self._liquidity_pools.setdefault(symbol, {})
        if side == "high":
            bucket["buyside"] = price
            _push_level(bucket, "highs", price)
        elif side == "low":
            bucket["sellside"] = price
            _push_level(bucket, "lows", price)
        bucket["seen_at"] = time.time()

    async def _on_account_identity(self, payload):
        """يلتقط اسم الوسيط لكل حساب — يلزم طلب الأمر (552 يرفض بلا وسيط)."""
        if not isinstance(payload, dict):
            return
        account = str(payload.get("account_id") or "").strip()
        broker = str(payload.get("broker") or "").strip()
        if account and broker:
            if not hasattr(self, "_brokers"):
                self._brokers = {}
            self._brokers[account] = broker

    async def _on_positions(self, payload):
        if not self._running or not isinstance(payload, dict): return
        source = str(payload.get("source") or "broker")
        grouped = {}
        for pos in payload.get("positions", []) if isinstance(payload.get("positions"), list) else []:
            if not isinstance(pos, dict): continue
            symbol = str(pos.get("symbol") or pos.get("asset_canonical") or "")
            sd = side(pos.get("side"))
            volume = real(pos.get("volume"))
            if not symbol or not sd or volume is None or volume <= 0: continue
            account = str(pos.get("account_id") or payload.get("account_id") or "")
            k = key(account, symbol)
            grouped.setdefault(k, []).append({"ticket": pos.get("ticket"), "account_id": account, "symbol": symbol, "side": sd, "volume": abs(volume), "entry_price": real(pos.get("entry_price")), "current_price": real(pos.get("current_price")), "profit": real(pos.get("profit"))})
        old_keys = set(self._positions)
        self._sources[source] = grouped
        dedup: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {}
        for snap in self._sources.values():
            for k, legs in snap.items():
                bucket = dedup.setdefault(k, {})
                for leg in legs:
                    identity = (leg.get("account_id"), leg.get("ticket")) if leg.get("ticket") not in (None, "", 0) else (
                        leg.get("account_id"), leg.get("symbol"), leg.get("side"), leg.get("entry_price"), leg.get("volume"))
                    bucket[identity] = leg
        merged = {k: list(rows.values()) for k, rows in dedup.items()}
        self._positions = merged
        for k in old_keys | set(merged): await self._recompute(k)

    def _fraction(self, strength: float) -> float:
        result = 0.0
        for threshold, value in sorted((float(k), float(v)) for k, v in self._bands.items()):
            if strength >= threshold: result = value
        return max(0.0, min(1.0, result))

    def _hedge_fraction(self, strength: float) -> float:
        result = 1.0
        for threshold, value in sorted((float(k), float(v)) for k, v in self._hedge_bands.items()):
            if strength >= threshold: result = value
        return max(0.0, min(1.0, result))

    def _settle_pending(self, k, current_net):
        if k not in self._pending_held: return
        remembered = self._pending_held.pop(k)
        if abs(current_net) <= self._min_volume or (current_net > 0) == (remembered == BUY):
            self._held_dir[k] = remembered
            self._held_restored += 1
        else:
            self._held_dropped += 1

    def _held_direction(self, k, desired, strength, current_net):
        # امر المالك «فعل» (٢٦-٠٨): هستيريسيس الشخصية المولدة يسري عند
        # التفعيل، وقيم المانيفست المختومة هي الافتراض عند الظل/الاطفاء.
        s_enter, s_exit = hysteresis_override(self._s_enter, self._s_exit)
        self._settle_pending(k, current_net)
        if self._restore_error and k not in self._cleared:
            if abs(current_net) > self._min_volume: return None, FAIL_CLOSED
            self._cleared.add(k)
        held = self._held_dir.get(k)
        if held is None and abs(current_net) > self._min_volume:
            held = BUY if current_net > 0 else SELL
            self._held_dir[k] = held
        if held is None:
            if desired in (BUY, SELL) and strength >= s_enter:
                self._held_dir[k] = desired
                return desired, "CONTRACT_TARGET"
            return None, "NO_DIRECTION"
        if strength <= s_exit:
            self._held_dir.pop(k, None)
            return None, "EXIT_ZONE"
        if desired in (BUY, SELL) and desired != held:
            if abs(current_net) <= self._min_volume and strength >= s_enter:
                self._held_dir[k] = desired
                return desired, "REVERSED_AFTER_NEUTRAL"
            return None, "REVERSAL_VIA_NEUTRAL"
        return held, "CONTRACT_TARGET"

    def _risk_dial(self) -> float:
        """عيار RISK_DIAL الساري — المعتمد من المالك أو 100 (سلوك اليوم كاملًا).

        عقد المحورين v1.1 §3: بوابة نمو التعرض الجديد وحدها؛ تُقرأ حيًّا
        ببصمة قاعدة العيارات فيصل اعتماد المالك من اللوحة بلا إقلاع."""
        return effective_value("RISK_DIAL", 100.0)

    async def _on_setting(self, payload):
        if not self._running or not isinstance(payload, dict): return
        applied = apply_command(payload, atom_id="581")
        if applied is None: return
        self._settings_applied += 1
        await self._context.publish(EVENT_SETTINGS_STATE, {"atom": "581", **applied})
        for k in list(self._ledgers): await self._recompute(k)

    def _version(self, k): self._versions[k] = self._versions.get(k, 0) + 1; return self._versions[k]

    def _gross_cap(self, scope, budget, price, stop_frac, vpu):
        if budget is None or budget <= 0 or price is None or price <= 0 or stop_frac is None or stop_frac <= 0 or vpu is None or vpu <= 0:
            return self._max_target
        risk_cap = 2.0 * budget / (price * stop_frac * vpu)
        cost_per_volume = self._spread_cost.get(scope, 0.0) + self._hedge_cost_per_volume
        cost_cap = budget / cost_per_volume if cost_per_volume > 0 else self._max_target
        return min(self._max_target, risk_cap, cost_cap)

    async def _recompute(self, k):
        await recompute(self, k)

    async def snapshot(self):
        return {"version": ATOM_VERSION, "held_dir": {str(k): str(v) for k, v in self._held_dir.items()}}

    async def restore(self, state):
        held = state.get("held_dir") if isinstance(state, dict) else None
        ok = isinstance(held, dict) and all(
            isinstance(k, str) and v in (BUY, SELL) for k, v in held.items())
        if not ok:
            self._held_dir = {}
            self._pending_held = {}
            self._cleared = set()
            self._restore_error = FAIL_CLOSED
            raise ValueError(FAIL_CLOSED)
        self._held_dir = {}
        self._pending_held = dict(held)
        self._restore_error = ""
        self._cleared = set()

    async def health_check(self):
        if not self._running: return HealthStatus(state=HealthState.UNHEALTHY, message="NOT_STARTED")
        details = {"seen": self._seen, "emitted": self._emitted, "decisions": len(self._decisions), "ledgers": len(self._ledgers), "positions": len(self._positions), "filter_blocked": self._blocked, "verdicts": len(self._verdicts), "held_restored": self._held_restored, "held_dropped": self._held_dropped, "restore_error": self._restore_error, "risk_dial": self._risk_dial(), "settings_applied": self._settings_applied}
        if not self._decisions: return HealthStatus(state=HealthState.DEGRADED, message="NO_DECISION_YET", details=details)
        return HealthStatus(state=HealthState.HEALTHY, message="targets=%d" % self._emitted, details=details)
