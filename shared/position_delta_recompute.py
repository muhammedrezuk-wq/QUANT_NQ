from __future__ import annotations

import time
from typing import Any

# ٢٠٢٦-٠٩-٠٥ (حكم المالك: «مو سكالبينغ عصبي — أخفّ شوي من عصبي»):
# الكبح كان 60 ثانية فخُفّض إلى 10 للسكالبينغ، فصار القرار يتكرّر كل
# عشر ثوانٍ على تِكّات متلاصقة. 45 ثانية تترك للسوق مجالًا يتحرّك بين
# قرار وآخر بلا أن تعود إلى بطء الدقيقة الكاملة.
COOLDOWN_S = 45.0
REWARD_RISK = 2.0
MAX_STOP_FRAC = 0.02
MIN_STEP_FRAC = 0.20
MIN_RR = 1.5
# مضاعف السبريد كحدّ أدنى لمسافة الوقف والهدف: الدخول على جانب والخروج
# على الآخر يبتلع سبريدًا كاملًا، فوقف على بعد سبريد واحد يُضرب لحظة
# الفتح. مقيس على BTCUSD: سبريد 5.00 ووقف 2.20 ⇒ RETCODE_10016.
#
# ٢٠٢٦-٠٩-٠٦ — عودة إلى 4 بعد قياس انزلاق **تنفيذ الوقف** على ١٦ صفقة:
#   الوسيط −3.96 · المتوسط −4.45 (لصالحنا غالبًا) · لكن الذيل ثقيل
#   التذكرة 1911154141: وقف مرسل 10.00 ⇒ المسافة الفعلية 37.88 ⇒
#   انزلاق +27.88 وخسارة 15.15$ على مخاطرة محسوبة 4.00$
# الوقف الضيّق هو الأخطر: نسبة الانزلاق إليه بلغت ٢٧٩٪، بينما أوقاف
# 20→30 انزلقت +0.30 إلى +8.57 فقط. الحدّ الأدنى 20.00 يمنع الأوقاف
# الانتحارية، ولا يبطّئ النظام — البيتكوين يقطع عشرين نقطة في ثوانٍ،
# والقياس يشهد: صفقات كثيرة أُغلقت خلال دقائق بوقف 20.
#
# ٢٠٢٦-٠٩-٠٦ (مقيس — توقّف التداول عشرين مرّة من عشرين): الحدّ أعلاه
# **قياسه 20.00 مطلقًا**، لكنّه كُتب `spread × 4` لأن السبريد يوم القياس
# كان 5.00 بالضبط. فلمّا اتّسع السبريد إلى 7.25 (مقيس على ticks_v2:
# 5.00 و7.49) انزاح الحدّ تلقائيًّا إلى **29.00** — رقم لم يُقس قطّ.
# أثره المقيس في السجلّ: `NO_STRUCTURE_LEVEL missing=TARGET` عشرين مرّة
# من عشرين، لأن وقفًا مصنوعًا بـ29.00 يطلب هدفًا على بعد 43.50 والبنية
# الحقيقية تتباعد نقطةً أو اثنتين (79,918.95 · 79,919.79 · 79,921.65).
# وهو حرفيًّا ما رفضه المالك: «ما بصير يجي التحليل مع قالب مركّب».
#
# الحدّ يُكتب الآن كما قِيس: أرضية مطلقة، ونسبتها من السعر 20.00 ÷ 80,000
# كي تصحّ على أيّ سعر للرمز نفسه. ويبقى فوقها حارس قبول الوسيط —
# ومقياسه في `commands`: كل رفض RETCODE_10016 وقع بمسافة **دون سبريد
# واحد** (2.20 · 2.20 · 2.20 · 2.38 · 4.20 مقابل سبريد 5.00)، وأضيق
# وقفٍ قُبل كان 2.65 بسبريد أضيق. فالمضاعف المقيس واحد لا أربعة.
# ولا ينقص هذا حماية الوسيط شيئًا: `cost_pad` أدناه يزيح الوقف المرسل
# ثلاثة سبريدات أخرى للخارج، فالمسافة التي يراها الوسيط تبقى أربعة
# أضعاف السبريد كما هي اليوم — التحرير يمسّ وقف التحليل وحده.
MIN_STOP_PRICE_FRAC = 0.00025
SPREAD_STOP_MULT = 1.0
# احتياطي الانزلاق كمضاعف للسبريد — مقيس على ٢٤ صفقة منفَّذة: الانزلاق
# ضدّنا (وسيط 2.7 · متوسط 4.7 · أقصى 16.90) مقابل سبريد 5.00.
#
# ٢٠٢٦-٠٩-٠٦: احتياطي يغطّي انزلاق **الخروج** المرصود موجبًا (أقصاه
# +8.57 على الأوقاف السليمة 20→30) لا انزلاق الدخول وحده. المضاعف 1
# (5.00) كان يغطّي وسيط الدخول 2.7 ومتوسطه 4.7، لكنه لا يكفي للخروج.
# المضاعف 2 (10.00) يغطّي كليهما بهامش، وما زال دون القالب القديم الذي
# كان يبتلع نصف الميزانية على الأوقاف الصغيرة — وتلك الأوقاف صارت
# ممنوعة أصلًا بالحدّ الأدنى 20.00 أعلاه.
SLIPPAGE_SPREAD_MULT = 2.0
# صلاحية الكنس كإذنٍ بصفقة عكس الاتجاه: كنسٌ قديم لم يعد يصف السوق
# الحاضر. عشر دقائق — مدى يسع ارتدادًا بعد كنس على إطار التِكّة.
SWEEP_VALID_S = 600.0

SEP = "\x1f"
GATE_MARK = "_gate"
FILTER_PASSED = "FILTER_PASSED"
FILTER_BLOCKED = "FILTER_BLOCKED"
PRICE_SOURCE = "mt5_broker_feed"
BUY = "buy"
SELL = "sell"
WAIT = "wait"
ADD = "ADD"
REDUCE = "REDUCE"
HEDGE = "HEDGE"
REBALANCE = "REBALANCE"
HOLD = "HOLD"
BLOCKED = "BLOCKED"
EVENT_OUT = "perpetual.target.state"
REASON_NEUTRAL_KEEP = "NEUTRAL_KEEP_GROSS"


def real(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def key(account: Any, symbol: Any) -> str:
    return str(account or "") + SEP + str(symbol or "")


def cycle_rank(cycle: Any) -> float | None:
    try:
        return float(str(cycle or "").rsplit("|", 1)[-1])
    except (TypeError, ValueError):
        return None


def is_stale(incoming: Any, accepted: float | None) -> bool:
    rank = cycle_rank(incoming)
    return rank is not None and accepted is not None and rank < accepted


def finish_targets(
    atom: Any, out: dict[str, Any], target_net: float, gross: float,
    target_buy: float, target_sell: float, current_buy: float,
    current_sell: float, reason: str,
) -> None:
    raw_buy = target_buy - current_buy
    raw_sell = target_sell - current_sell
    delta_buy = max(-atom._max_step, min(atom._max_step, raw_buy))
    delta_sell = max(-atom._max_step, min(atom._max_step, raw_sell))
    active = (
        abs(delta_buy) >= atom._min_volume
        or abs(delta_sell) >= atom._min_volume
    )
    if not active:
        delta_buy = delta_sell = 0.0
        action = HOLD
    elif delta_buy < -atom._min_volume or delta_sell < -atom._min_volume:
        action = (
            REBALANCE
            if delta_buy > atom._min_volume or delta_sell > atom._min_volume
            else REDUCE
        )
    else:
        action = HEDGE if target_net * (out.get("current_net") or 0.0) < 0 else ADD
    out.update({
        "status": "READY",
        "target_net": round(target_net, 8),
        "target_gross": round(gross, 8),
        "target_buy": round(target_buy, 8),
        "target_sell": round(target_sell, 8),
        "delta_buy": round(delta_buy, 8),
        "delta_sell": round(delta_sell, 8),
        "delta_net": round(delta_buy - delta_sell, 8),
        "action": action,
        "reason": reason,
    })


async def recompute(atom: Any, scope_key: str) -> None:
    if atom._context is None:
        return
    account, symbol = scope_key.split(SEP, 1)
    decision = atom._decisions.get(scope_key)
    wildcard = atom._decisions.get(key("*", symbol))
    ledger = atom._ledgers.get(scope_key)
    if decision is None:
        decision = wildcard
    elif (
        wildcard is not None
        and wildcard.get(GATE_MARK)
        and not decision.get(GATE_MARK)
        and not is_stale(
            wildcard.get("cycle_id"), cycle_rank(decision.get("cycle_id"))
        )
    ):
        decision = wildcard
    if decision is None or ledger is None:
        return

    legs = list(atom._positions.get(scope_key, []))
    current_buy = sum(row["volume"] for row in legs if row["side"] == "BUY")
    current_sell = sum(row["volume"] for row in legs if row["side"] == "SELL")
    current_net = current_buy - current_sell
    current_gross = current_buy + current_sell
    direction = str(decision.get("direction") or decision.get("signal") or WAIT).lower()
    direction = (
        BUY if direction in ("buy", "up", "long")
        else SELL if direction in ("sell", "down", "short")
        else WAIT
    )
    strength = real(decision.get("strength"))
    fallback_strength = (real(decision.get("score")) or 0.0) / 100.0
    strength = max(0.0, min(1.0, strength if strength is not None else fallback_strength))
    budget = real(ledger.get("risk_budget", ledger.get("R", ledger.get("budget"))))
    filter_verdict = atom._filter_verdict(scope_key, decision)
    if filter_verdict != FILTER_PASSED:
        direction = WAIT
        if filter_verdict == FILTER_BLOCKED:
            atom._blocked += 1

    price = atom._price.get(scope_key)
    dial = atom._dials.get(scope_key, {})
    hard_stop = atom._stops.get(scope_key, {})
    stop_frac = real(dial.get("stop_distance_frac"))
    value_per_unit = atom._vpu.get(scope_key)
    portfolio = atom._portfolios.get(scope_key)
    state = str((portfolio or {}).get("state") or "UNKNOWN").upper()
    out = {
        "account_id": account, "symbol": symbol, "direction": direction,
        "strength": strength, "decision_id": decision.get("decision_id"),
        "gate_request_id": decision.get("gate_request_id"),
        "current_buy": round(current_buy, 8),
        "current_sell": round(current_sell, 8),
        "current_net": round(current_net, 8),
        "current_gross": round(current_gross, 8),
        "target_net": None, "target_gross": None,
        "target_buy": None, "target_sell": None,
        "delta_net": 0.0, "delta_buy": 0.0, "delta_sell": 0.0,
        "action": HOLD, "status": "WAITING", "reason": "",
        "current_legs": legs,
        "reference_price": round(price, 8) if price else None,
        "price_source": PRICE_SOURCE,
        "reference_is_broker_feed": True,
        "stop_distance_frac": stop_frac,
        "stop_state": (
            "FROZEN" if state in ("FROZEN", "PAUSED")
            else "REBALANCING" if state in ("WARNING", "HEDGING")
            else "READY"
        ),
        "state": state, "filter_verdict": filter_verdict,
        "version": atom._version(scope_key),
    }
    account_mode = str((portfolio or {}).get("account_mode") or "UNKNOWN").upper()
    system_alive = (portfolio or {}).get("system_alive") is True

    if portfolio is None:
        out.update(status="BLOCKED", action=BLOCKED, reason="PORTFOLIO_STATE_MISSING")
    elif not system_alive:
        out.update(status="BLOCKED", action=BLOCKED, reason="SYSTEM_NOT_ALIVE")
    elif account_mode != "HEDGING":
        reason = "NETTING_UNSUPPORTED" if account_mode == "NETTING" else "ACCOUNT_MODE_UNKNOWN"
        out.update(status="BLOCKED", action=BLOCKED, reason=reason)
    elif str(hard_stop.get("status") or "").upper() == "FROZEN":
        out.update(status="BLOCKED", action=BLOCKED, reason="HARD_STOP_FROZEN")
    elif state in ("FROZEN", "PAUSED"):
        out.update(status="BLOCKED", action=BLOCKED, reason="PORTFOLIO_FROZEN")
    elif state in ("WARNING", "HEDGING"):
        target_net = 0.0
        gross_cap = atom._gross_cap(scope_key, budget, price, stop_frac, value_per_unit)
        gross = min(current_gross, gross_cap)
        target_buy = target_sell = gross / 2.0
        finish_targets(
            atom, out, target_net, gross, target_buy, target_sell,
            current_buy, current_sell, "RISK_REBALANCE",
        )
        out["risk_gross_cap"] = round(gross_cap, 8)
    elif (
        budget is None or budget <= 0 or price is None or price <= 0
        or stop_frac is None or stop_frac <= 0
        or value_per_unit is None or value_per_unit <= 0
    ):
        if direction == WAIT:
            target_net = 0.0
            gross = current_gross
            target_buy = target_sell = gross / 2.0
            finish_targets(
                atom, out, target_net, gross, target_buy, target_sell,
                current_buy, current_sell, "NO_DIRECTION",
            )
        else:
            out.update(
                status="WAITING", action=BLOCKED,
                reason="MISSING_R_PRICE_DIAL_OR_SPECS",
            )
    else:
        capacity = min(atom._max_target, budget / (price * stop_frac * value_per_unit))
        gross_cap = atom._gross_cap(scope_key, budget, price, stop_frac, value_per_unit)
        held, reason = atom._held_direction(scope_key, direction, strength, current_net)
        # سؤال المالك ٢٠٢٦-٠٩-٠٥: «ليش بس عم يشتري». الجواب يجب أن يكون
        # رقمًا لا رأيًا: كلّما اختلف اتجاه القرار عن الاتجاه الممسوك،
        # يُسجَّل الاثنان مع الصافي والقوة — فيُعرف هل الروم لا يطلب بيعًا
        # أصلًا، أم يطلبه ويمنعه قفل «الانعكاس عبر الحياد».
        if direction in (BUY, SELL) and held != direction:
            last = getattr(atom, "_last_dir_block", None)
            if last is None:
                last = atom._last_dir_block = {}
            stamp = (direction, held or "NONE", reason)
            if last.get(scope_key) != stamp:
                last[scope_key] = stamp
                atom._context.logger.warning(
                    "581 direction blocked %s: decision=%s held=%s reason=%s "
                    "net=%.2f strength=%.2f",
                    symbol, direction, held or "NONE", reason, current_net, strength)
        exposure = atom._fraction(strength)
        hedge = atom._hedge_fraction(strength)
        if filter_verdict != FILTER_PASSED:
            exposure = 0.0
            hedge = 1.0
        previous_strength = atom._last_strength.get(scope_key)
        previous_gross = atom._last_gross_target.get(scope_key)
        # عقد المحورين v1.1 §3 — تحذير المالك اللفظي (نصّه الحرفي، مختوم NQ):
        #   RISK_DIAL
        #   = بوابة لنمو التعرض الجديد
        #   ≠ بوابة للبقاء
        #   ≠ عامل في E(S)
        #   ≠ عامل في gross_cap
        #   ≠ عامل في R_B
        dial_pct = real(getattr(atom, "_risk_dial", lambda: 100.0)())
        dial_factor = max(0.0, min(1.0, (dial_pct if dial_pct is not None else 0.0) / 100.0))
        u_float = real(ledger.get("u_float")) or 0.0
        u_realized = real(ledger.get("u_realized")) or 0.0
        consumed_budget = max(u_float, u_realized) * budget
        remaining_rb = budget - consumed_budget
        dial_add_budget = budget * dial_factor - consumed_budget
        remaining_add_budget = max(0.0, dial_add_budget)
        if exposure <= 0.0:
            gross = min(current_gross, gross_cap)
            base_target = gross
            allowed_increase = 0.0
            decrease = 0.0
            reason = REASON_NEUTRAL_KEEP
        else:
            base_target = min(capacity * exposure, gross_cap)
            if (
                previous_strength is not None and strength < previous_strength
                and previous_gross is not None
            ):
                base_target = min(base_target, previous_gross)
            increase = max(0.0, base_target - current_gross)
            allowed_increase = min(increase, capacity * exposure * dial_factor)
            if dial_add_budget <= 0.0:
                allowed_increase = 0.0
            # ٢٠٢٦-٠٩-٠٦ (حكم المالك: «إيمتى يعزّز على ربح؟»): التعزيز
            # كان مشروطًا بقوّة الإشارة وحدها، فيمكن أن يضيف إلى مركز
            # خاسر ويضاعف الخطأ — وهو أوّل ما يُنهى عنه المتداول. الإضافة
            # إلى مركز قائم تشترط أن يكون رابحًا: الشراء فوق متوسط دخوله
            # والبيع دونه. أمّا فتح مركز جديد (لا مركز قائم) فلا يشترط
            # شيئًا سوى ما سبقه من حرّاس.
            if allowed_increase > 0.0 and current_gross > atom._min_volume:
                legs_side = [row for row in legs
                             if row.get("side") == (BUY if held == BUY else SELL).upper()]
                entries = [real(row.get("entry_price")) for row in legs_side]
                entries = [x for x in entries if x is not None and x > 0]
                if entries and price:
                    avg_entry = sum(entries) / len(entries)
                    winning = (price > avg_entry) if held == BUY else (price < avg_entry)
                    if not winning:
                        allowed_increase = 0.0
                        reason = "ADD_ONLY_TO_WINNER"
            decrease = max(0.0, current_gross - base_target)
            gross = current_gross + allowed_increase - decrease
        target_net = (
            0.0 if held is None
            else gross * (1.0 - hedge) * (1.0 if held == BUY else -1.0)
        )
        target_buy = max(0.0, (gross + target_net) / 2.0)
        target_sell = max(0.0, (gross - target_net) / 2.0)
        atom._last_strength[scope_key] = strength
        atom._last_gross_target[scope_key] = gross
        finish_targets(
            atom, out, target_net, gross, target_buy, target_sell,
            current_buy, current_sell, reason,
        )
        unit_cost = atom._spread_cost.get(scope_key, 0.0) + atom._hedge_cost_per_volume
        out.update({
            "risk_dial": round(dial_factor * 100.0, 2),
            "base_target": round(base_target, 8),
            "allowed_increase": round(allowed_increase, 8),
            "decrease": round(decrease, 8),
            "consumed_budget": round(consumed_budget, 2),
            "remaining_RB": round(remaining_rb, 2),
            "dial_add_budget": round(dial_add_budget, 2),
            "remaining_add_budget": round(remaining_add_budget, 2),
            "max_target": round(capacity, 8),
            "risk_gross_cap": round(gross_cap, 8),
            "exposure_fraction": round(exposure, 8),
            "hedge_fraction": round(hedge, 8),
            "held_direction": held or WAIT,
            "hedge_cost_per_volume": round(unit_cost, 8),
            "projected_hedge_cost": round(gross * unit_cost, 8),
            "risk_budget": budget,
            "stop_distance_frac": stop_frac,
            "reference_price": round(price, 8),
            "vpu": value_per_unit,
        })

    atom._last[scope_key] = out
    atom._seen += 1
    atom._emitted += 1
    await atom._context.publish(EVENT_OUT, out)
    await request_orders(atom, scope_key, out)


EVENT_ORDER_REQUESTED = "execution.order.requested"
ACTION_OPEN = "OPEN"


async def request_orders(atom: Any, scope_key: str, out: dict[str, Any]) -> None:
    """يترجم الدلتا الموجبة إلى طلب أمر — الوصلة التي لم تُكتب قط.

    يُنشر فقط عند فتح تعرّض جديد (delta > 0). التقليص والإغلاق يحتاجان
    عقدًا بالتذكرة ويبقيان خارج هذه الوصلة.
    """
    if out.get("status") != "READY":
        return
    decision_id = out.get("decision_id")
    if not decision_id:
        return
    seen = getattr(atom, "_requested_decisions", None)
    if seen is None:
        seen = atom._requested_decisions = {}
    if seen.get(scope_key) == decision_id:
        return

    min_volume = float(getattr(atom, "_min_volume", 0.01) or 0.01)
    account = str(out.get("account_id") or "")
    symbol = str(out.get("symbol") or "")
    price = real(out.get("reference_price"))
    if not account or not symbol or price is None or price <= 0:
        return
    broker = ""
    brokers = getattr(atom, "_brokers", None)
    if isinstance(brokers, dict):
        broker = str(brokers.get(account) or "")

    # كبح: طلب واحد لكل نطاق كل COOLDOWN_S ثانية. بدونه يخرج طلب مع كل
    # تِكّة، ويحجز كلٌّ منها ميزانية لدى 516 فتُستهلك من أول طلب.
    now = time.time()
    last = getattr(atom, "_requested_at", None)
    if last is None:
        last = atom._requested_at = {}
    if now - float(last.get(scope_key) or 0.0) < COOLDOWN_S:
        return
    # ٢٠٢٦-٠٩-٠٦ (مقيس — سباق تزامن كلّف ستّ صفقات متراكمة): الفتحة
    # كانت تُحجز **بعد** النشر (`if published: last[...] = now`)، وبينهما
    # `await publish` يُسلّم التحكّم لحلقة الأحداث — فيدخل استدعاء آخر،
    # يجد الكبح كما هو، ويمرّ وينشر أيضًا. المقيس: ستّة أوامر بفواصل
    # 0.8 · 1.4 · 1.8 · 1.9 ثانية رغم كبح خمس وأربعين، وستّ مراكز بيع
    # مفتوحة معًا بمخاطرة مجمّعة ~160$ فوق سقف الواحد بالمئة.
    # الفتحة تُحجز الآن قبل أيّ await؛ وإن لم يُنشر شيء تُعاد أدناه كي
    # لا يُحرم النطاق من دورته التالية بلا سبب.
    previous_slot = last.get(scope_key)
    last[scope_key] = now

    budget = real(out.get("risk_budget")) or 0.0
    target_gross = real(out.get("target_gross")) or 0.0

    # ٢٠٢٦-٠٩-٠٥ (حكم المالك: «ما عم يتداول، عم يفتح هيدج جديد»): ننشر
    # الساق الاتجاهية وحدها. نشر الجهتين معًا كان ينتج زوجًا متعادلًا لأن
    # سقف الخطوة يقصّ الساقين إلى نفس الرقم فيمحو الاتجاه: الهدف المقيس
    # كان شراء 2.06 مقابل بيع 0.23 فخرجتا 0.05 و0.05. التحوّط شأن 576/578.
    target_net = real(out.get("target_net")) or 0.0
    if abs(target_net) < min_volume:
        # ٢٠٢٦-٠٩-٠٥: هذا الخروج كان صامتًا تمامًا — 581 targets=847 بلا
        # سطر واحد في السجلّ، فبدا النظام واقفًا بلا سبب. الأرقام التي
        # تصنع target_net تُسجَّل مرّة عند كل تغيّر في تركيبتها.
        stamp = (out.get("held_direction"), out.get("reason"),
                 round(real(out.get("strength")) or 0.0, 2),
                 round(real(out.get("target_gross")) or 0.0, 2))
        seen = getattr(atom, "_last_flat_stamp", None)
        if seen is None:
            seen = atom._last_flat_stamp = {}
        if seen.get(scope_key) != stamp:
            seen[scope_key] = stamp
            atom._context.logger.warning(
                "581 flat %s: target_net=%.4f held=%r reason=%r strength=%.3f "
                "gross=%.3f exposure=%r hedge=%r dir=%r state=%r",
                symbol, target_net, out.get("held_direction"), out.get("reason"),
                real(out.get("strength")) or 0.0, real(out.get("target_gross")) or 0.0,
                out.get("exposure_fraction"), out.get("hedge_fraction"),
                out.get("direction"), out.get("state"))
        return
    wanted_side = BUY if target_net > 0 else SELL

    published = False
    for side, field in ((BUY, "delta_buy"), (SELL, "delta_sell")):
        if side != wanted_side:
            continue
        delta = real(out.get(field)) or 0.0
        if delta < min_volume:
            continue
        # لا تنقيط: إضافة أصغر من MIN_STEP_FRAC من الهدف لا تستحق مركزًا
        # جديدًا. بدونها يفتح النظام مركزًا بحجم السقف كل دورة حتى يمتلئ
        # الحدّ — أربعة مراكز متطابقة قِيست، وهو ما سمّاه المالك «أعمى».
        # لكن الأرضية لا تتجاوز سقف الخطوة نفسه، وإلا جمد كل شيء: قِيس
        # هدف 5.7 وسقف خطوة 0.5، فصارت الأرضية 1.14 وتُخطّى كل طلب بصمت.
        floor = target_gross * MIN_STEP_FRAC if target_gross > 0 else 0.0
        floor = min(floor, float(getattr(atom, "_max_step", delta) or delta))
        if delta < floor:
            atom._context.logger.warning(
                "581 skip %s: STEP_BELOW_FLOOR delta=%s floor=%s", symbol, delta, floor)
            continue
        volume = round(delta / min_volume) * min_volume
        if volume < min_volume:
            continue
        # حصة هذا الطلب من الميزانية بنسبة حجمه إلى الهدف الإجمالي —
        # لا الميزانية كاملة، وإلا رفض 516 كل ما بعد الأول.
        share = budget
        step_fraction = 1.0
        if budget > 0 and target_gross > 0:
            step_fraction = min(1.0, volume / target_gross)
            share = round(budget * step_fraction, 2)
        # ٢٠٢٦-٠٩-٠٥ (حكم المالك): «ستوب وهدف ثابتين من رقم هندسي على
        # ميزانية — هاد عيب. كل هالمحلّلات ما توصلك مكان ستوب من تحليل،
        # وبنفس الوقت هدف ١/٢ بدون تحليل — عم تقفل باب بوجه التحليل».
        # الوقف والهدف يُعلَّقان الآن على برك السيولة: 200 ينشر السوينغ،
        # 251 يحوّله إلى بركة (METHOD=swing_as_pool)، و252/253 ينشران
        # سعرَي البركة العليا والسفلى. كلاهما مشتقّ من السعر وحده — صالح
        # لوسيط CFD الذي لا يقدّم حجمًا حقيقيًّا ولا CVD.
        sym = symbol.upper()
        pools = (getattr(atom, "_liquidity_pools", {}) or {}).get(sym, {})
        swings = (getattr(atom, "_swings", {}) or {}).get(sym, {})
        # ٢٠٢٦-٠٩-٠٥ (مقيس على رفض الوسيط RETCODE_10016 = INVALID_STOPS):
        # مواصفة BTCUSD تعلن stops_level = 0 وfreeze_level = 0، فالحارس
        # القديم (stops_level × point) كان صفرًا ولا يمنع شيئًا — ومع ذلك
        # رُفض أمرا الجسر 125 و126 عند التنفيذ. السبب المقيس: **السبريد
        # 5.00 دولار** (bid 79,721.64 / ask 79,726.64) بينما الوقف على
        # بعد 2.20 و2.38 — أي داخل السبريد. البيع يدخل على bid ويُوقَف
        # على ask، فالمسافة الفعلية تنكمش بمقدار سبريد كامل. الحدّ الأدنى
        # الحقيقي هو السبريد لا رقم الوسيط المعلن.
        spread = real(getattr(atom, "_spread_price", {}).get(scope_key)) or 0.0
        min_gap = max(
            real(getattr(atom, "_broker_min_stop", {}).get(scope_key)) or 0.0,
            price * MIN_STOP_PRICE_FRAC,
            spread * SPREAD_STOP_MULT,
        )

        # مرشّحو المستويات: السوينغ (أقرب حدّ بنيوي — سكالبينغ) وبرك
        # السيولة (أبعد — تحرّك أوسع). الوقف يأخذ الأقرب فالمخاطرة أصغر،
        # والهدف يأخذ أقرب مستوى يحقّق النسبة فالعائد ليس أصغر من المخاطرة.
        # خريطة المستويات: كل ما سجّلته 251/252/253 و201 من قمم وقيعان،
        # لا آخر واحد فقط — بها يجد الهدف مدى يحقّق النسبة بدل الجار
        # الملاصق (13 نقطة) الذي كان يُسقط كل أمر بـRR_BELOW_MIN.
        # ٢٠٢٦-٠٩-٠٥ (مقيس): المستوى كان يُصنَّف قمّةً أو قاعًا **وقت
        # نشره**، ثم يُقرأ من خانته وحدها. فمستوى نُشر فوق السعر وهبط
        # السعر دونه يبقى محبوسًا في «القمم» ولا يُرى كقاع — رغم أنه صار
        # قاعًا فعلًا. النتيجة خريطة فقيرة: قِيس `below` بعنصرين اثنين
        # (79,681.04 و79,696.97) بينما التحليل قدّم 27 مستوى خارجيًّا
        # و27 داخليًّا. فيُطلب هدف على بعد 32.46 وأبعد متاح 19.5 ⇒
        # NO_STRUCTURE_LEVEL على كل تِكّة، وتوقّف التداول.
        # المستوى سعرٌ لا لافتة: يُجمع الكل ثم يُصنَّف بموضعه من السعر
        # **الآن**، فيتضاعف المدى المتاح للوقف والهدف.
        levels = (list(pools.get("lows") or []) + list(pools.get("highs") or [])
                  + list(swings.get("lows") or []) + list(swings.get("highs") or [])
                  + [pools.get("sellside"), pools.get("buyside"),
                     swings.get("low"), swings.get("high")])
        seen_levels = {real(x) for x in levels if real(x) is not None and real(x) > 0}
        below = sorted(x for x in seen_levels if x < price)
        above = sorted(x for x in seen_levels if x > price)

        # ٢٠٢٦-٠٩-٠٥ (مقيس): اختيار «الأقرب مطلقًا» كان يوقف التداول
        # كلّيًّا — LEVEL_INSIDE_BROKER_MIN gap=20.0 مع مستويات تفصلها 13
        # نقطة (79,690.55 · 79,703.56 · 79,704.57). المستوى الملاصق ليس
        # الخيار الوحيد: يُؤخذ **أقرب مستوى يبلغ الحدّ الأدنى**، فيبقى
        # الوقف بنيويًّا حقيقيًّا ويُقبل عند الوسيط في آن.
        # ٢٠٢٦-٠٩-٠٦ (حكم المالك: «عم يشتري من قمة ويبيع من قاع»، وقياسه
        # الذي أكّده: البيع خسر ٧ من ٨ وصافيه −43.35$ بينما الشراء +6.86$،
        # ومتوسط دخول البيع من **منتصف** المدى — لا عند قمة تُباع منها):
        # خمس من ثماني استراتيجيات تتبع الزخم، فتدخل مع الحركة ولو كانت
        # عكس الاتجاه الأكبر. و207 (حالة الاتجاه) و254 (كنس السيولة)
        # تعملان وتنشران ولا أحد يمنع بهما صفقة عكسية.
        #
        # القاعدة: لا صفقة عكس الاتجاه المعلن إلا بكنسٍ حديث يبرّرها —
        # الكنس هو ما يميّز طرفًا يُباع منه (قمّة اختُرقت كذبًا فارتدّت)
        # من طرفٍ يُخترق فيُشترى. و`range`/`transition` لا اتجاه فيهما
        # فلا منع.
        trend_row = (getattr(atom, "_trend", {}) or {}).get(sym)
        trend = trend_row[0] if trend_row else ""
        # ٢٠٢٦-٠٩-٠٦ — سُحب هنا اشتقاقُ اتجاهٍ من موضع السعر بعتبتَي
        # 0.67/0.33: رقمان لم يُقاسا (حكم المالك: «حاج تخمين، اشتغل
        # صح»). الفلتر يبقى معلَّقًا على 207 وحده حتى يُقاس ما يميّز
        # الصفقة الرابحة من الخاسرة فعلًا — والقياس يُجمَع الآن مع كل
        # أمر (السطر أدناه) بدل أن يُخترع رقم ويُبنى عليه.
        if trend in ("uptrend", "downtrend"):
            against = (side == SELL) if trend == "uptrend" else (side == BUY)
            if against:
                sweep_row = (getattr(atom, "_sweep", {}) or {}).get(sym)
                want = "buyside" if side == SELL else "sellside"
                fresh = (sweep_row is not None and sweep_row[0] == want
                         and (time.time() - sweep_row[1]) <= SWEEP_VALID_S)
                if not fresh:
                    atom._context.logger.warning(
                        "581 skip %s %s: AGAINST_TREND trend=%s need_sweep=%s "
                        "have=%r", symbol, side, trend, want, sweep_row)
                    continue

        # الوقف: أقرب مستوى بنيوي يبلغ الحدّ الأدنى. وإن كان أبعد مستوى
        # متاح ما زال داخل الحدّ، يُزاح **إلى الخارج** إلى الحدّ بالضبط —
        # المستوى البنيوي يبقى محميًّا داخله، والإزاحة ضرورة وسيط لا
        # اختراع تحليل. اللوت يُعاد حسابه على المسافة الجديدة فتبقى
        # الخسارة تحت سقف المالك. (٢٠٢٦-٠٩-٠٥: بلا هذه الإزاحة توقّف
        # التداول كلّيًّا — LEVEL_INSIDE_BROKER_MIN على كل تِكّة.)
        # الهدف لا يُزاح أبدًا: يبقى مستوى بنيويًّا حقيقيًّا، وإن لم يبلغ
        # أيُّ مستوى الحدَّ والنسبة معًا فلا صفقة.
        shifted = False
        if side == BUY:
            stop_loss = next((s for s in reversed(below) if (price - s) >= min_gap),
                             below[0] if below else None)
            if stop_loss is not None and (price - stop_loss) < min_gap:
                stop_loss = price - min_gap
                shifted = True
            risk_gap = (price - stop_loss) if stop_loss else 0.0
            # ٢٠٢٦-٠٩-٠٦ (حكم المالك: «بين ستوب وهدف ليس محدود — إذا
            # اتجاه مدعوم يكمل مو يوقف»): كان يُختار **أقرب** مستوى يبلغ
            # النسبة، فيصير الهدف سقفًا يوقف الصفقة عند أوّل محطّة. صار
            # يُختار **أبعد** مستوى بنيوي متاح، فالصفقة تكمل ما دام
            # الهيكل يحملها، ووقفها المتحرّك هو من يقرّر الخروج لا رقم.
            # الشرط الأدنى يبقى: أن يبلغ الهدف النسبة وحدّ الوسيط.
            floor_t = max(risk_gap * MIN_RR, min_gap)
            reachable = [t for t in above if (t - price) >= floor_t]
            take_profit = reachable[-1] if reachable else None
        else:
            stop_loss = next((s for s in above if (s - price) >= min_gap),
                             above[-1] if above else None)
            if stop_loss is not None and (stop_loss - price) < min_gap:
                stop_loss = price + min_gap
                shifted = True
            risk_gap = (stop_loss - price) if stop_loss else 0.0
            floor_t = max(risk_gap * MIN_RR, min_gap)
            reachable = [t for t in below if (price - t) >= floor_t]
            take_profit = reachable[0] if reachable else None

        if stop_loss is None or take_profit is None:
            # لا مستوى تحليلي = لا صفقة. رقم هندسي بديل يكذب على القرار.
            # الرسالة تميّز غياب الوقف عن غياب الهدف، وتذكر مصادر
            # المستويات التي وصلت فعلًا — فيُعرف أيّ محلّل صامت.
            want = max((risk_gap * MIN_RR), min_gap)
            # ٢٠٢٦-٠٩-٠٦: الرسالة كانت تطبع الجيران الثلاثة فقط، وهم
            # الأقرب إلى السعر — فلا تُظهر هل المدى المطلوب غير موجود
            # أصلًا أم موجود وأبعد. المدى الكامل (الأقصى في كل جهة) هو
            # ما يفصل «البنية ضيّقة» عن «الحدّ الأدنى مبالغ».
            far_below = (price - below[0]) if below else 0.0
            far_above = (above[-1] - price) if above else 0.0
            atom._context.logger.warning(
                "581 skip %s: NO_STRUCTURE_LEVEL missing=%s price=%.2f "
                "stop=%r risk_gap=%.2f need_target_at=%.2f min_gap=%.2f "
                "spread=%.2f n_below=%d n_above=%d span_below=%.2f "
                "span_above=%.2f below=%s above=%s sources=%r",
                symbol, "STOP" if stop_loss is None else "TARGET", price,
                stop_loss, risk_gap, want, min_gap, spread,
                len(below), len(above), far_below, far_above,
                [round(x, 2) for x in below[-3:]],
                [round(x, 2) for x in above[:3]],
                getattr(atom, "_level_sources", {}))
            continue

        # الاتجاه لا يُفتح على مستويات مقلوبة (وقف فوق السعر لشراء مثلًا).
        if side == BUY and not (stop_loss < price < take_profit):
            atom._context.logger.warning(
                "581 skip BUY %s: LEVELS_INVERTED sl=%s price=%s tp=%s",
                symbol, stop_loss, price, take_profit)
            continue
        if side == SELL and not (take_profit < price < stop_loss):
            atom._context.logger.warning(
                "581 skip SELL %s: LEVELS_INVERTED tp=%s price=%s sl=%s",
                symbol, take_profit, price, stop_loss)
            continue

        # حدّ الوسيط الأدنى: مستوى أقرب منه يرفضه الوسيط.
        if min_gap > 0 and (abs(price - stop_loss) < min_gap
                            or abs(take_profit - price) < min_gap):
            atom._context.logger.warning(
                "581 skip %s: LEVEL_INSIDE_BROKER_MIN gap=%s sl=%s tp=%s",
                symbol, min_gap, stop_loss, take_profit)
            continue

        # سقف مخاطرة: مستوى أبعد من MAX_STOP_FRAC ليس خطأ في التحليل بل
        # مخاطرة أكبر من المسموح — تُترك الصفقة ولا يُزوَّر الوقف.
        if abs(price - stop_loss) / price > MAX_STOP_FRAC:
            atom._context.logger.warning(
                "581 skip %s: STOP_BEYOND_RISK_CAP dist=%.2f%% cap=%.2f%%",
                symbol, abs(price - stop_loss) / price * 100.0,
                MAX_STOP_FRAC * 100.0)
            continue

        # ٢٠٢٦-٠٩-٠٥ (حكم المالك على لقطة الحساب: «هدف أصغر من ستوب»):
        # المستويان صحيحان بنيويًّا لكن النسبة بينهما قد تكون مقلوبة —
        # مقيس على الحساب: مخاطرة 1,593 مقابل عائد 878 (نسبة 0.55)، وأسوأ
        # 7,156 مقابل 868 (نسبة 0.12). أي صفقة لا تبلغ MIN_RR تُترك.
        # النسبة تُحسب على ما يقبضه الحساب فعلًا: الدخول على الجانب
        # المعاكس والخروج على الآخر، فسبريد كامل يُضاف إلى المخاطرة
        # ويُطرح من العائد. مع سبريد 5.00 على وقف 8 نقاط، النسبة
        # المعلنة 5.8 حقيقتها 3.3 — والفرق ليس تفصيلًا على السكالبينغ.
        risk = abs(price - stop_loss) + spread
        reward = max(0.0, abs(take_profit - price) - spread)
        if risk <= 0 or reward / risk < MIN_RR:
            atom._context.logger.warning(
                "581 skip %s: RR_BELOW_MIN rr=%.2f risk=%.2f reward=%.2f min=%.2f "
                "| price=%.2f below=%s above=%s",
                symbol, (reward / risk if risk > 0 else 0.0), risk, reward, MIN_RR,
                price, [round(x, 2) for x in below[-4:]],
                [round(x, 2) for x in above[:4]])
            continue

        # ٢٠٢٦-٠٩-٠٦ (حكم المالك): «بدنا الستوب الحقيقي لتحليل الصفقة —
        # صفقة ستوبها 76 نقطة لازم تاخد مجال الـ76 بعد خصم السبريد
        # والانزلاق. ما بدنا نفشّل التحليل بالسبريد؛ نحن بنتحمّل تكاليفها
        # مو التحليل».
        #
        # كان الوقف يُرسل على مستوى التحليل نفسه، فيبتلع السبريد من
        # مجاله: شراء يدخل على ask ويُوقَف على bid، فوقف 76 نقطة يصير
        # 71 فعليًّا للتحليل. الآن يُزاح الوقف للخارج بمقدار التكاليف
        # (سبريد + احتياطي انزلاق)، فيبقى للتحليل مداه كاملًا، والتكلفة
        # تُدفع من فوقه لا منه. والحجم يُحسب على المسافة الموسَّعة —
        # فالخسارة تبقى تحت سقف المالك، ويصغر اللوت كلّما اتّسع الوقف.
        cost_pad = spread * (1.0 + SLIPPAGE_SPREAD_MULT)
        analysis_stop = stop_loss
        if cost_pad > 0:
            stop_loss = (stop_loss - cost_pad) if side == BUY else (stop_loss + cost_pad)
        stop_loss = round(stop_loss, 8)
        take_profit = round(take_profit, 8)
        body = {
            "request_id": "dir-%s-%s-%s" % (decision_id, side, atom._version(scope_key)),
            "account_id": account, "broker": broker,
            "action": ACTION_OPEN, "symbol": symbol, "side": side.upper(),
            "volume": round(volume, 8), "reference_price": round(price, 8),
            "stop_loss": stop_loss, "take_profit": take_profit,
            "origin": "directional", "attempt": 1,
            "risk_budget": share,
            # ٢٠٢٦-٠٩-٠٥ (مقيس على التذكرة 1911032162): 513 يستمع إلى
            # market.tick.validated وهو لا يحمل bid/ask، فوصلت تكاليف
            # العبور إلى 551 أصفارًا — فحسب لوتًا 0.5 على وقف 20 نقطة
            # (10.00$ بالضبط)، ثم انزلق التنفيذ 8.25 فصارت الخسارة 14.12
            # واضطُرّ 577 إلى تضييق الوقف بعد الفتح. السبريد يُقاس هنا
            # من تِكّة الوسيط نفسها، فيعبر مع الطلب إلى حاسب الحجم.
            # التكاليف صارت **داخل** مسافة الوقف المرسل أعلاه، فلا
            # تُضاف ثانيةً عند حساب الحجم — وإلا حُوسبت مرّتين فصغر
            # اللوت بلا سبب. الرقمان يعبران للتوثيق والقياس فقط.
            # ٢٠٢٦-٠٩-٠٦ (حكم المالك: «عم بيفتح 0.50 فرط حطّة ويأخذ ١٠
            # دولار بالصفقة — لازم يوزّع اللوتات ويديرها باحتراف»): بنية
            # التوزيع مبنيّة أصلًا في هذا المحرّك ومعطَّلة عمليًّا —
            #   capacity = الطاقة الكلية من الميزانية والوقف
            #   exposure = f(strength)  ⇒ الهدف يكبر بقوّة الإشارة
            #   delta    = الخطوة نحوه، مقصوصة بسقف الخطوة
            # فالهدف يكبر حين تقوى الإشارة، ويُبلَغ على **خطوات** — وهذا
            # هو التعزيز والتوزيع. لكن 551 كان يحسب الحجم على السقف
            # الكامل (١٠ دولارات) لكل خطوة، فألغى التوزيع: كل خطوة تأخذ
            # الميزانية كاملة وكأنها الصفقة الوحيدة.
            # النسبة تعبر الآن، فتأخذ كل خطوة حصّتها من السقف: خطوة تمثّل
            # ٤٠٪ من الهدف تخاطر بأربعة دولارات لا بعشرة، ويبقى للتعزيز
            # مجاله ضمن السقف نفسه.
            "step_fraction": round(step_fraction, 6),
            # ٢٠٢٦-٠٩-٠٦ (حكم المالك: «ليش هو عم يوصل لَسقف؟ لازم يتداول
            # بعيد عن السقف، مو كل مرّة ينضغط — في شي مو صحيح بالموضوع»):
            # وهو محقّ. السقف حدٌّ أقصى لا هدف، وكانت المعادلة تستهلكه
            # كاملًا في كل صفقة (قِيس 105.00 · 104.80 · 104.85 · 105.05).
            # وحِزَم التعرّض مبنيّة في هذا المحرّك وتقول العكس:
            #     قوّة <0.2 ⇒ 0.00   ·   0.2→0.4 ⇒ 0.10
            #     0.4→0.6  ⇒ 0.25   ·   ≥0.6     ⇒ 0.50
            # أي أن أقصى تعرّض مصمَّم هو **نصف** السقف، ولا يُبلغ إلا عند
            # إشارة قويّة. المخاطرة تتناسب مع الأفضلية: إعداد ضعيف يأخذ
            # عُشر السقف، وقويّ يأخذ نصفه — والسقف نفسه لا يُلامَس.
            "exposure_fraction": round(real(out.get("exposure_fraction")) or 0.0, 6),
            "costs_in_stop": True,
            "spread": round(spread, 8),
            "slippage_reserve": round(spread * SLIPPAGE_SPREAD_MULT, 8),
            "analysis_stop": round(analysis_stop, 8),
            "analysis_risk": round(abs(price - analysis_stop), 8),
            "parent_decision_id": decision_id,
            "gate_request_id": out.get("gate_request_id"),
        }
        await atom._context.publish(EVENT_ORDER_REQUESTED, body)
        # الوقف يُطبع بمسافته لا بسعره وحده: حكم المالك «كيف وقف ٢٠ نقطة
        # ما عم يتغيّر على تحليل؟». وقف مُزاح (shifted) يعني أن التحليل لم
        # يقدّم مستوى أبعد من الحدّ — إن تكرّر فالمصدر ضيّق لا القاعدة.
        # سجلّ ظروف كل أمر — أساس القياس الذي يميّز الرابح من الخاسر
        # لاحقًا بالأرقام لا بالظنّ: القوّة والتعرّض وموضع السعر من مدى
        # المستويات والاتجاه المعلن وعدد المستويات على الجهتين.
        span_lo = below[0] if below else None
        span_hi = above[-1] if above else None
        pos_in_range = ((price - span_lo) / (span_hi - span_lo)
                        if (span_lo is not None and span_hi is not None
                            and span_hi > span_lo) else None)
        atom._context.logger.warning(
            "581 order requested side=%s volume=%s price=%s stop_dist=%.2f "
            "target_dist=%.2f shifted=%s levels=%d/%d strength=%.3f "
            "exposure=%s pos_in_range=%s trend=%r decision=%s",
            side, body["volume"], body["reference_price"],
            abs(price - stop_loss), abs(take_profit - price), shifted,
            len(below), len(above), strength, out.get("exposure_fraction"),
            round(pos_in_range, 3) if pos_in_range is not None else None,
            trend or None, decision_id)
        published = True
    if published:
        seen[scope_key] = decision_id
    else:
        # لم يخرج أمر: تُعاد الفتحة كما كانت، فلا يُكبح النطاق بلا نشر.
        if previous_slot is None:
            last.pop(scope_key, None)
        else:
            last[scope_key] = previous_slot
