from __future__ import annotations

from typing import Any

from core.contracts.atom import AtomBase, AtomContext, HealthState, HealthStatus
from shared.trade_setup import EVENT_SETUP

ATOM_VERSION = "1.1.0"
# v1.1.0 (2026-08-25): the manage command carries the leg's magic. Measured
# on the live orphan leg: 577's MODIFY_SL reached 575 without a magic field
# and died there as MISSING_OR_FOREIGN_MAGIC -- the only path that places a
# hard stop on a position was broken at its last meter. The magic rides
# from the broker's own position row (609 passes it through), so a foreign
# position still gets refused by 575's ownership checks, never adopted.

EVENT_PLAN = "perpetual.plan.state"
EVENT_POSITIONS = "platform.positions.state"
EVENT_MANAGE = "execution.manage.command"
EVENT_SIZE = "risk.position_size.state"

# آلية المالك اليدوية NQ_Manual v5.5 (أرسلها ٢٠٢٦-٠٩-٠٥) تحمل الفكرة
# الناقصة هنا: بعد التعبئة يُعاد ضبط الوقف على **سعر الدخول الفعلي**
# بحيث تبقى الخسارة مساوية للميزانية مهما كان الانزلاق:
#     exactSL = floor(SavedRisk / (lot × valuePerPoint))
#     إن كان الانزلاق ضدّنا: SL يُضيَّق بمقدار خسارة الانزلاق
# لا تقدير مسبق للانزلاق — قياس بعدي على ما نُفِّذ فعلًا. مقيس على ٢٤
# صفقة: الانزلاق ضدّنا دائمًا (وسيط 2.7 · أقصى 16.90 دولار).
#
# الفرق عن آلية المالك: وقفه من الميزانية وحدها، ووقفي من التحليل —
# فالميزانية هنا **سقف** لا مصدر. الوقف البنيوي يبقى ما دامت خسارته
# ضمن السقف، ويُضيَّق فقط إذا تجاوزته بعد الانزلاق (اللوت حينها منفَّذ
# ولا يمكن تصغيره).
# ٢٠٢٦-٠٩-٠٦ (مقيس على التذكرة 1911165380): هذا الثابت بقي ١٠ دولارات
# بعد أن صار السقف ١٪ من الرصيد (105.13$)، فخنق الحارسُ صفقةً سليمة:
# فُتحت 01:37:23 بوقف ٣٥ نقطة، وبعد **ثانيتين** أُرسل MODIFY_SL يقرّبه
# إلى 12.82 نقطة (79,800.24) كي تصير الخسارة عشرة — فماتت على أوّل
# تذبذب بـ−17.21. السقف يُقرأ الآن من 513 مع كل تحجيم (metadata
# max_trade_loss)، فيتبع الرصيد والنسبة بدل رقم متحجّر.
DEFAULT_MAX_TRADE_LOSS = 10.0
LOSS_TOLERANCE = 1.02
# مسافة التنفّس التي يجب أن تفصل الوقف الزاحف عن السعر الحالي، كنسبة من
# المسافة الأصلية للوقف. وقفٌ يلتصق بالسعر يُغلق الصفقة بدل أن يحميها.
#
# ٢٠٢٦-٠٩-٠٦ (حكم المالك: «آخر صفقة لازم تربح ٢٠٠ لا ٣٠٠ دولار، ربحانة
# ٣٥»). القياس يشهد له: أهداف الصفقات الثماني الأخيرة كانت على بعد
# 78→142 نقطة (تساوي 223$ إلى 303$ بلوتاتها)، و**لا واحدة بلغت هدفها**
# — الثمانية كلّها خرجت بـSL. ومقارنة الأربعين المزحوفة بالإحدى
# والثلاثين غير المزحوفة:
#     زُحف وقفها : ن=40 · رابحة 60% · صافي +89.05$ · أفضل صفقة +21.84$
#     بلا زحف    : ن=31 · رابحة  6% · صافي −866.68$ · أسوأ −125.07$
# فالزحف هو ما يُبقي الحساب حيًّا، لكنه سقفٌ على كل رابح عند +21.84$.
#
# الرقمان اللذان يخنقانه:
#   ١) التنفّس 0.25 من وقف 30.84 = 7.71 — وهو **مساوٍ** للضجيج المقيس
#      (الزيادة على المسافة المخطَّطة: مئين ٨٠ = 7.54، أقصى = 27.88).
#      أي أن الضجيج وحده يكفي لضرب الوقف الزاحف في خُمس الحالات.
#      يصير 0.9 ⇒ ~27.8 على وقف ثلاثين، أي بقدر أقصى ضجيج مرصود.
#   ٢) لا شرط ربح أدنى: مقيس على 1911362798 — شُدّ الوقف إلى 1.47 نقطة
#      من الدخول والسعر بعيد 9 نقاط فقط، فخرجت الصفقة بـ−0.53$ وهدفها
#      يساوي +303.08$. الزحف يبدأ الآن بعد ربح يعادل المخاطرة الأصلية
#      (1R)، فلا يُقفل رابحٌ على لا شيء، ويبقى للاتجاه مجال يكمل فيه.
TRAIL_BREATHING_FRAC = 0.9
TRAIL_MIN_PROFIT_R = 1.0

ACTION_MODIFY = "MODIFY_SL"
ACT_MAINTAIN = "MAINTAIN_STOP"

REASON_NOT_STARTED = "NOT_STARTED"
REASON_NO_DATA = "NO_PLAN_YET"

_KEY_SEP = "|"


def _to_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _norm_side(side: Any) -> str:
    text = str(side).strip().lower()
    if text in ("sell", "short", "1"):
        return "SELL"
    if text in ("buy", "long", "0"):
        return "BUY"
    return ""


class Atom(AtomBase):
    def __init__(self) -> None:
        self._context: AtomContext | None = None
        self._running = False
        self._min_change = 1e-9
        self._legs: dict[str, list[dict[str, Any]]] = {}
        self._last_sl: dict[int, float] = {}
        self._vpp: dict[str, float] = {}
        self._capped: set[int] = set()
        self._risk_capped = 0
        self._structure: dict[str, dict[str, float]] = {}
        self._loss_cap: dict[str, float] = {}
        self._trailed = 0
        # إبطال الإعداد لكل رمز: (setup_id, side, price) — مرجع الملكية.
        self._setup_stop: dict[str, tuple[str, str, float]] = {}
        self._sent = 0
        self._updates = 0
        self._seen_plan = False

    async def initialize(self, context: AtomContext) -> None:
        self._context = context
        self._min_change = float(context.config.get("min_sl_change", 1e-9))
        context.subscribe(EVENT_POSITIONS, self._on_positions)
        context.subscribe(EVENT_PLAN, self._on_plan)
        context.subscribe(EVENT_SIZE, self._on_size)
        # مصادر التتبّع البنيوي: القمم والقيعان من 201 والهيكل الداخلي
        # من 203 — خلفها يزحف الوقف بينما الصفقة تكمل.
        # ٢٠٢٦-٠٩-٠٦ (مقيس): المصدران وحدهما نشرا سوينغين اثنين فقط
        # (201 swings=2 · 203 events=3)، فلم يجد الوقف الزاحف قاعًا يزحف
        # خلفه ولا مرّة. تُضاف كل الذرّات التي تقيس مستوى بنيويًّا —
        # هي نفسها التي تغذّي خريطة 581 — فيصير للتتبّع ما يمسك به.
        for event in ("structure.swing.state", "structure.internal.state",
                      "structure.external.state", "structure.bos.state",
                      "structure.choch.state", "structure.mss.state",
                      "liquidity.sweep.state", "liquidity.fvg.state",
                      "liquidity.buyside.state", "liquidity.sellside.state"):
            context.subscribe(event, self._on_structure)
        # ٢٠٢٦-٠٩-٠٦ — ورقة ملكية الصفقة (المرحلة ز · §١٥): الزحف كان
        # يبدأ من «أقرب قاع» في خريطة عامّة، فيستطيع أن يستبدل إبطال
        # الإعداد بمنطق لا ينتمي إليه — أي تعود المشكلة نفسها بعد الدخول.
        # 577 يسمع الإعداد الآن، ويحرس حدًّا لا يتجاوزه: لا يشدّ الوقف
        # إلى ما هو **أضيق من إبطال الفكرة** إلا إن كان الربح قد تجاوزه،
        # ولا يوسّعه أبدًا.
        context.subscribe(EVENT_SETUP, self._on_setup)

    async def _on_setup(self, payload: dict[str, Any]) -> None:
        """يحفظ إبطال الإعداد لكل رمز — مرجعًا لا يُستبدل بمنطق آخر."""
        if not self._running or not isinstance(payload, dict):
            return
        symbol = str(payload.get("symbol") or "").strip().upper()
        stop = _to_float(payload.get("invalidation_price"))
        side = str(payload.get("side") or "").upper()
        setup_id = str(payload.get("setup_id") or "")
        if not symbol or stop is None or side not in ("BUY", "SELL") or not setup_id:
            return
        self._setup_stop[symbol] = (setup_id, side, stop)

    async def _on_structure(self, payload: dict[str, Any]) -> None:
        """يحفظ آخر قاع وآخر قمّة بنيويّين — مرساتا الوقف الزاحف."""
        if not self._running or not isinstance(payload, dict):
            return
        symbol = str(payload.get("symbol") or "").strip().upper()
        if not symbol:
            return
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        signal = str(payload.get("signal") or "").lower()
        book = self._structure.setdefault(symbol, {})
        # المرجع الذي يُصنَّف به المستوى: سعر إغلاق الدورة التي نشرته.
        reference = (_to_float(meta.get("close")) or _to_float(meta.get("price"))
                     or _to_float(payload.get("price")))
        low = _to_float(meta.get("swing_low"))
        high = _to_float(meta.get("swing_high"))
        if low is None and signal == "swing_low":
            low = _to_float(meta.get("price")) or _to_float(payload.get("price"))
        if high is None and signal == "swing_high":
            high = _to_float(meta.get("price")) or _to_float(payload.get("price"))
        # مستويات الذرّات الأخرى: مستوى الاختراق وحدّا الفجوة وسعر البركة
        # — تُصنَّف قاعًا أو قمّةً بموضعها من مرجع دورتها.
        if reference and reference > 0:
            for field in ("level", "gap_bottom", "gap_top", "price"):
                value = _to_float(meta.get(field))
                if value is None or value <= 0 or value == reference:
                    continue
                if value < reference and (low is None or value > low):
                    low = value
                elif value > reference and (high is None or value < high):
                    high = value
        if low and low > 0:
            book["low"] = low
        if high and high > 0:
            book["high"] = high

    async def _trail_structure(self, pos: dict[str, Any]) -> None:
        """يزحف بالوقف خلف آخر مستوى بنيوي في اتجاه الربح.

        حكم المالك ٢٠٢٦-٠٩-٠٦: «يدير صفقة على تحليل بين ستوب وهدف ليس
        محدود — إذا اتجاه مدعوم يكمل مو يوقف». فالخروج لا يقرّره رقم
        مُسبق بل انكسارُ الهيكل: ما دام السعر يصنع قيعانًا أعلى (لشراء)
        يزحف الوقف خلف آخرها، وتبقى الصفقة مفتوحة تجمع ما يعطيه الاتجاه.
        الوقف يُشدّ ولا يُوسَّع أبدًا، ولا يتحرّك إلا والصفقة رابحة —
        فلا يُقرَّب وقفٌ على مركز خاسر فيُخنَق قبل أوانه.
        """
        ticket = _to_int(pos.get("ticket"))
        symbol = str(pos.get("symbol") or "")
        side = _norm_side(pos.get("side"))
        entry = _to_float(pos.get("entry_price"))
        current = _to_float(pos.get("current_price"))
        stop = _to_float(pos.get("stop_loss"))
        book = self._structure.get(symbol.upper()) or {}
        if ticket is None or not side or not entry or not current:
            return
        anchor = book.get("low") if side == "BUY" else book.get("high")
        if not anchor:
            return
        in_profit = (current > entry) if side == "BUY" else (current < entry)
        if not in_profit:
            return
        # ٢٠٢٦-٠٩-٠٦ (مقيس على التذكرة 1911168352): المرساة كانت تُقبل
        # لمجرّد وقوعها بين الدخول والسعر، فزحف الوقف إلى 79,783.69
        # بينما السعر 79,782.55 — **1.14 نقطة** فقط. وقفٌ بهذا اللصوق
        # ليس حمايةً بل إغلاقٌ فوريّ: ضُرب بعد ثوانٍ بـ−1.46 على صفقة
        # وقفها الأصلي ٣٥ نقطة. المرساة تحتاج مسافة تنفّس من السعر — لا
        # تقلّ عن رُبع المسافة الأصلية للوقف — وإلا تُركت الصفقة تتنفّس
        # بوقفها الحالي حتى يصنع الهيكل مرساةً أبعد.
        original = abs(entry - stop) if (stop and stop > 0) else 0.0
        # ربحٌ أدنى قبل أوّل زحف: بلا هذا الشرط يُشدّ الوقف إلى جوار
        # الدخول عند أوّل حركة، فيتحوّل رابحٌ محتمل بمئات الدولارات إلى
        # صفر. المقياس هو المخاطرة نفسها: لا يُمسّ الوقف قبل أن يبلغ
        # الربح مثلها (1R).
        if original > 0 and abs(current - entry) < original * TRAIL_MIN_PROFIT_R:
            return
        breathing = original * TRAIL_BREATHING_FRAC
        if breathing > 0 and abs(current - anchor) < breathing:
            return
        # ملكية الإبطال (§١٥ و§١٦): المرساة لا تُستبدل بإبطال الإعداد إلا
        # حين يكون الربح قد تجاوزه فعلًا — عندها الزحف يقفل ربحًا، لا
        # يستبدل فكرة. وقبل ذلك يبقى إبطال الإعداد هو الحدّ.
        owned = self._setup_stop.get(symbol.upper())
        if owned is not None:
            _, owned_side, owned_stop = owned
            if owned_side == side:
                beyond = (current > owned_stop) if side == "BUY" else (current < owned_stop)
                inside = (anchor < owned_stop) if side == "BUY" else (anchor > owned_stop)
                if inside and not beyond:
                    return
        # المرساة يجب أن تقع بين الدخول والسعر: خلف الربح المحقَّق، لا
        # أمامه (فتُضرب فورًا) ولا خلف الدخول (فلا تضيف حماية).
        if side == "BUY":
            if not (entry <= anchor < current):
                return
            better = stop is None or stop <= 0.0 or anchor > stop + self._min_change
        else:
            if not (current < anchor <= entry):
                return
            better = stop is None or stop <= 0.0 or anchor < stop - self._min_change
        if not better:
            return
        self._last_sl[ticket] = anchor
        self._sent += 1
        self._trailed += 1
        self._context.logger.warning(
            "577 trail %s ticket=%s: %s -> %s (entry=%s price=%s side=%s)",
            symbol, ticket, stop, round(anchor, 6), entry, current, side)
        await self._context.publish(EVENT_MANAGE, {
            "account_id": str(pos.get("account_id") or ""),
            "action": ACTION_MODIFY, "ticket": ticket, "symbol": symbol,
            "side": side, "stop_loss": round(anchor, 6),
            "magic": _to_int(pos.get("magic")), "origin": "structure_trail"})

    async def _on_size(self, payload: dict[str, Any]) -> None:
        """قيمة النقطة لكل لوت — من مواصفة الوسيط التي ينشرها 513."""
        if not self._running or not isinstance(payload, dict):
            return
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        tick_value = _to_float(meta.get("tick_value"))
        tick_size = _to_float(meta.get("tick_size"))
        symbol = str(payload.get("symbol") or "")
        if symbol and tick_value and tick_size:
            self._vpp[symbol] = tick_value / tick_size
        # سقف الخسارة الساري كما يحسبه 513 من الرصيد والنسبة — لا رقم
        # ثابت هنا يتحجّر ويخنق الصفقات حين تتغيّر المعايرة.
        cap = _to_float(meta.get("max_trade_loss"))
        if symbol and cap and cap > 0:
            self._loss_cap[symbol] = cap

    async def _cap_risk(self, pos: dict[str, Any]) -> None:
        """يضبط وقف مركز منفَّذ كي لا تتجاوز خسارته سقف المالك.

        يُحسب على سعر الدخول **الفعلي**، فيدخل الانزلاق في الحساب بلا
        تقدير: خسارة الوقف الحالي = اللوت × (الدخول − الوقف) × قيمة
        النقطة. إن تجاوزت السقف، يُقرَّب الوقف إلى المسافة القصوى التي
        تُبقيها عنده بالضبط. الوقف يُضيَّق فقط — لا يُوسَّع أبدًا.
        """
        ticket = _to_int(pos.get("ticket"))
        symbol = str(pos.get("symbol") or "")
        side = _norm_side(pos.get("side"))
        volume = _to_float(pos.get("volume"))
        entry = _to_float(pos.get("entry_price"))
        stop = _to_float(pos.get("stop_loss"))
        vpp = self._vpp.get(symbol)
        if (ticket is None or not side or not volume or not entry
                or not stop or stop <= 0.0 or not vpp or vpp <= 0.0):
            return
        distance = (entry - stop) if side == "BUY" else (stop - entry)
        if distance <= 0.0:
            return
        cap = self._loss_cap.get(symbol) or DEFAULT_MAX_TRADE_LOSS
        loss = volume * distance * vpp
        if loss <= cap * LOSS_TOLERANCE:
            self._capped.discard(ticket)
            return
        if ticket in self._capped:
            return
        max_distance = cap / (volume * vpp)
        capped = (entry - max_distance) if side == "BUY" else (entry + max_distance)
        self._capped.add(ticket)
        self._risk_capped += 1
        self._last_sl[ticket] = capped
        self._sent += 1
        self._context.logger.warning(
            "577 risk cap %s ticket=%s: loss=%.2f > cap=%.2f | entry=%s "
            "stop=%s -> %s (lot=%s vpp=%.4f)",
            symbol, ticket, loss, cap, entry, stop,
            round(capped, 6), volume, vpp)
        await self._context.publish(EVENT_MANAGE, {
            "account_id": str(pos.get("account_id") or ""),
            "action": ACTION_MODIFY, "ticket": ticket, "symbol": symbol,
            "side": side, "stop_loss": round(capped, 6),
            "magic": _to_int(pos.get("magic")), "origin": "risk_cap"})

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def shutdown(self) -> None:
        await self.stop()

    async def _on_positions(self, payload: dict[str, Any]) -> None:
        if not self._running or not isinstance(payload, dict):
            return
        positions = payload.get("positions")
        if not isinstance(positions, list):
            return
        legs: dict[str, list[dict[str, Any]]] = {}
        live_tickets: set[int] = set()
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            symbol = str(pos.get("symbol") or "")
            ticket = _to_int(pos.get("ticket"))
            side = _norm_side(pos.get("side"))
            if not symbol or ticket is None or not side:
                continue
            key = str(pos.get("account_id") or "") + _KEY_SEP + symbol
            legs.setdefault(key, []).append({
                "ticket": ticket, "side": side,
                "magic": _to_int(pos.get("magic")),
                # الوقف القائم على المركز نفسه — مرجع «لا توسيع».
                "sl": _to_float(pos.get("stop_loss")),
                "entry": _to_float(pos.get("entry_price")),
            })
            live_tickets.add(ticket)
        self._legs = legs
        for ticket in [t for t in self._last_sl if t not in live_tickets]:
            del self._last_sl[ticket]
        self._capped &= live_tickets
        if self._context is not None:
            for pos in positions:
                if not isinstance(pos, dict):
                    continue
                # الأمان أوّلًا (سقف الخسارة)، ثم التتبّع البنيوي الذي
                # يترك الصفقة تكمل ما دام الهيكل يحملها.
                await self._cap_risk(pos)
                await self._trail_structure(pos)

    async def _on_plan(self, payload: dict[str, Any]) -> None:
        if not self._running or self._context is None or not isinstance(payload, dict):
            return
        plans = payload.get("plans")
        if not isinstance(plans, list):
            return
        self._seen_plan = True
        self._updates += 1
        for plan in plans:
            if isinstance(plan, dict):
                await self._maintain(plan)

    async def _maintain(self, plan: dict[str, Any]) -> None:
        if str(plan.get("primary_action") or "") != ACT_MAINTAIN:
            return
        stop_price = _to_float(plan.get("stop_price"))
        v_net = _to_float(plan.get("v_net"))
        symbol = str(plan.get("symbol") or "")
        if stop_price is None or v_net is None or v_net == 0.0 or not symbol:
            return
        net_side = "BUY" if v_net > 0.0 else "SELL"
        key = str(plan.get("account_id") or "") + _KEY_SEP + symbol
        for leg in self._legs.get(key, []):
            if leg["side"] != net_side:
                continue
            ticket = leg["ticket"]
            prev = self._last_sl.get(ticket)
            if prev is not None and abs(prev - stop_price) < self._min_change:
                continue
            # ٢٠٢٦-٠٩-٠٥ (مقيس على أمرَي الجسر 116 و117): الوقف المحفظيّ
            # للخطة الدائمة (72,957.55) طُبِّق على صفقة سكالبينغ دخلت عند
            # 79,685 بوقف بنيوي 79,679 — فتحوّلت مخاطرة 6 نقاط إلى 6,728
            # نقطة بأمر MODIFY_SL واحد بعد الفتح. الوقف يُشدّ ولا يُوسَّع:
            # للشراء لا ينزل تحت الوقف القائم، وللبيع لا يصعد فوقه.
            current = leg.get("sl") if leg.get("sl") else None
            anchor = prev if prev is not None else current
            if anchor is not None:
                widening = (stop_price < anchor) if leg["side"] == "BUY" \
                    else (stop_price > anchor)
                if widening:
                    self._context.logger.warning(
                        "577 skip %s ticket=%s: STOP_WIDENING_REFUSED "
                        "new=%s current=%s side=%s",
                        symbol, ticket, stop_price, anchor, leg["side"])
                    continue
            self._last_sl[ticket] = stop_price
            self._sent += 1
            await self._context.publish(EVENT_MANAGE, {
                "account_id": key.split(_KEY_SEP, 1)[0],
                "action": ACTION_MODIFY, "ticket": ticket, "symbol": symbol,
                "side": leg["side"], "stop_loss": stop_price,
                "magic": leg.get("magic"), "origin": "perpetual"})

    async def health_check(self) -> HealthStatus:
        if not self._running:
            return HealthStatus(state=HealthState.UNHEALTHY, message=REASON_NOT_STARTED)
        details = {"updates": self._updates, "sent": self._sent,
                   "tracked_legs": sum(len(v) for v in self._legs.values())}
        if not self._seen_plan:
            return HealthStatus(state=HealthState.DEGRADED, message=REASON_NO_DATA, details=details)
        return HealthStatus(state=HealthState.HEALTHY,
                            message="modify_sent=%d" % self._sent, details=details)
