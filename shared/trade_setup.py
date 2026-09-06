# -*- coding: utf-8 -*-
"""عقد إعداد الصفقة — الكائن الوحيد الذي يملك فكرة الصفقة.

حكم المالك ٢٠٢٦-٠٩-٠٦: «مو تحطّ سقف يخنق غلطه — لازم من أساس ما يغلط»
ثم «حلّها من جذر لا ترقّع».

الجذر المقيس: النظام لم يملك يومًا كائنًا واحدًا يمثّل **فكرة الصفقة**.
كانت الفكرة موزّعة على ثلاثة لا يعرف بعضها بعضًا:

    لماذا ندخل؟  ← 404/408 (تقاطع متوسّطات · زخم حسابيّ)
    أين نخطئ؟    ← 581 يختار أقرب مستوى من خريطة عامّة
    إلى أين؟     ← 581 يختار أبعد مستوى من الخريطة نفسها

فلا أحد يستطيع الإجابة عن السؤال الأول: **لماذا هذه الصفقة موجودة؟**
ومن لا يملك جوابًا لا يملك وقفًا: تقاطعُ متوسّطين لا يُبطله سعرٌ معيّن
لأنه لا يدّعي شيئًا عن السعر. ولهذا كانت كل الحرّاس التي بُنيت — بوّابة
النسبة، سقف الخسارة، مجال تنفّس الزحف — تحسّن أرقامًا حول فراغ.

هذا الملفّ ينقل ملكية هندسة الصفقة إلى **صاحب الفكرة**:

    من يستطيع أن يقول «أنا مخطئ عند هذا السعر» — وحده يفتح صفقة.
    ومن لا يستطيع، يصوّت للسياق ولا يُنفَّذ.

وحين يملك الإعداد إبطاله وهدفه، تسقط الحرّاس من تلقائها: النسبة تخرج
من الفكرة نفسها، والوقف يعرف ما يحرس، والزحف يتبع إبطالًا يتطوّر لا
أقرب قاع عشوائيّ.

الأدوار بعد هذا العقد:
    الاستراتيجية البنيوية → تُنشئ إعدادًا كاملًا (اتجاه + إبطال + هدف)
    المحلّلات الأخرى      → سياق يقوّي الإعداد أو يضعفه، ولا يخلقه
    581                   → إدارة تعرّض وكمّية فقط — لا يخترع وقفًا ولا هدفًا
    551                   → حجم فقط
    584                   → شرعيّة فقط
    577                   → يدير إبطال الإعداد أثناء حياته
"""
from __future__ import annotations

import math
import time
from typing import Any

# حدث الإعداد — الاستراتيجية البنيوية تنشره، والغرفة تعتمده، و581 ينفّذه.
EVENT_SETUP = "strategy.setup.proposed"
SETUP_CONTRACT_VERSION = 1

BUY = "buy"
SELL = "sell"
SIDES = (BUY, SELL)

# أنواع الإعداد المعروفة — لكلٍّ إبطال طبيعيّ من بنيته هو، لا من خريطة عامّة.
SETUP_LIQUIDITY_RAID = "LIQUIDITY_RAID"      # كنس سيولة ثم استرداد
SETUP_BREAKOUT = "BREAKOUT_ACCEPTANCE"       # اختراق مستوى وقبولٌ خارجه
SETUP_TYPES = (SETUP_LIQUIDITY_RAID, SETUP_BREAKOUT)

# عمر الإعداد الافتراضيّ: فكرةٌ لا تُنفَّذ سريعًا تصف سوقًا مضى.
DEFAULT_TTL_S = 120.0

# حالات الإعداد (ورقة التنفيذ §٢٦): تُسجَّل كلّها ولو كان عدد الصفقات صفرًا،
# كي يقول النظام صراحةً **لماذا لم يتداول** بدل أن يبدو واقفًا بلا تفسير.
STATE_CREATED = "SETUP_CREATED"
STATE_APPROVED = "SETUP_APPROVED"
STATE_REJECTED = "SETUP_REJECTED"
STATE_INVALIDATED = "SETUP_INVALIDATED"
STATE_EXPIRED = "SETUP_EXPIRED"
# ٢٠٢٦-٠٩-٠٦ (حكم المالك): فكرةٌ بلغ السعرُ هدفَها قبل الدخول لم تُخطئ
# هندستها — **فاتت فرصتها**. الحالتان مختلفتان ولا يجوز خلطهما: الأولى
# عيبٌ في الإعداد، والثانية مضيُّ وقتٍ. والدخول بعد بلوغ الهدف مطاردة
# لا فكرة.
STATE_TARGET_REACHED = "SETUP_TARGET_REACHED"
LOG_STOP_FROM_SETUP = "STOP_DERIVED_FROM_SETUP"
LOG_TARGET_FROM_SETUP = "TARGET_DERIVED_FROM_SETUP"
LOG_EXEC_STOP_ADJUSTED = "EXECUTION_STOP_ADJUSTED"

# أسباب الرفض — تُعلَن ولا تُبتلع، فالإعداد المرفوض يُقاس لا يُخمَّن.
REJECT_SIDE = "SIDE_NOT_BUY_OR_SELL"
REJECT_TYPE = "UNKNOWN_SETUP_TYPE"
REJECT_OWNER = "OWNER_MISSING"
REJECT_PRICES = "PRICE_NOT_FINITE_OR_POSITIVE"
REJECT_GEOMETRY = "GEOMETRY_INVERTED"
REJECT_WHY = "INVALIDATION_WITHOUT_REASON"
REJECT_TARGET_WHY = "TARGET_WITHOUT_REASON"
REJECT_EXPIRY = "EXPIRY_NOT_AFTER_CREATION"
OK = ""


def _real(value: Any) -> float | None:
    """رقم حقيقيّ موجب أو لا شيء — لا صفر ولا لانهاية ولا نصّ."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_setup(
    *,
    owner: Any,
    setup_type: str,
    side: str,
    entry_reference: Any,
    invalidation_price: Any,
    invalidation_source: str,
    invalidation_reason: str,
    target_price: Any,
    target_source: str,
    target_reason: str,
    account_id: str = "",
    broker: str = "",
    symbol: str = "",
    cycle_id: str = "",
    period_start: Any = None,
    structure_id: str = "",
    strength: Any = 0.0,
    confidence: Any = 0.0,
    evidence: dict[str, Any] | None = None,
    created_at: float | None = None,
    ttl_s: float = DEFAULT_TTL_S,
) -> dict[str, Any]:
    """يبني حمولة الإعداد كما تنطق بها الاستراتيجية — بلا تحقّق هنا.

    التحقّق مسؤولية `validate_setup` كي يبقى البناء وصفًا خالصًا،
    والرفض قرارًا معلنًا بسببه.
    """
    now = float(created_at if created_at is not None else time.time())
    symbol = _text(symbol).upper()
    return {
        "contract_version": SETUP_CONTRACT_VERSION,
        "setup_id": "%s:%s:%s:%s" % (_text(owner), setup_type, symbol, round(now, 3)),
        "setup_owner": _text(owner),
        "setup_type": _text(setup_type).upper(),
        "side": _text(side).lower(),
        "account_id": _text(account_id),
        "broker": _text(broker),
        "symbol": symbol,
        "cycle_id": _text(cycle_id),
        "period_start": period_start,
        "setup_state": STATE_CREATED,
        "entry_reference": _real(entry_reference),
        # الإبطال: السعر الذي يُثبت أن الفكرة ماتت — ومصدره وسببه معه،
        # فلا يُقبل رقمٌ بلا نسب.
        "invalidation_price": _real(invalidation_price),
        "invalidation_source": _text(invalidation_source),
        "invalidation_reason": _text(invalidation_reason),
        # الهدف: إلى أين تقصد الحركة، بنسبه أيضًا.
        "target_price": _real(target_price),
        "target_source": _text(target_source),
        "target_reason": _text(target_reason),
        "structure_id": _text(structure_id),
        "strength": _real(strength) or 0.0,
        "confidence": _real(confidence) or 0.0,
        "evidence": dict(evidence or {}),
        "created_at": now,
        "expires_at": now + max(1.0, float(ttl_s or DEFAULT_TTL_S)),
    }


def validate_setup(setup: Any) -> str:
    """يعيد `OK` إن صحّ الإعداد، أو سبب الرفض صريحًا.

    الشروط ليست تجميلًا: كلٌّ منها يمنع صفقةً بلا فكرة.
      · الجانب معروف، والنوع من الأنواع المعلنة، وله مالك.
      · الأسعار الثلاثة حقيقية موجبة.
      · الهندسة غير مقلوبة: الإبطال خلف الدخول، والهدف أمامه.
      · للإبطال مصدر وسبب — رقمٌ بلا نسب ليس إبطالًا بل تخمين.
      · للهدف مصدر وسبب — للسبب نفسه.
      · للإعداد أجلٌ: فكرةٌ لا تُنفَّذ تصف سوقًا مضى.
    """
    if not isinstance(setup, dict):
        return REJECT_TYPE
    side = _text(setup.get("side")).lower()
    if side not in SIDES:
        return REJECT_SIDE
    if _text(setup.get("setup_type")).upper() not in SETUP_TYPES:
        return REJECT_TYPE
    if not _text(setup.get("setup_owner")):
        return REJECT_OWNER
    entry = _real(setup.get("entry_reference"))
    stop = _real(setup.get("invalidation_price"))
    target = _real(setup.get("target_price"))
    if entry is None or stop is None or target is None:
        return REJECT_PRICES
    if entry <= 0 or stop <= 0 or target <= 0:
        return REJECT_PRICES
    if side == BUY and not (stop < entry < target):
        return REJECT_GEOMETRY
    if side == SELL and not (target < entry < stop):
        return REJECT_GEOMETRY
    if not (_text(setup.get("invalidation_source"))
            and _text(setup.get("invalidation_reason"))):
        return REJECT_WHY
    if not (_text(setup.get("target_source")) and _text(setup.get("target_reason"))):
        return REJECT_TARGET_WHY
    created = _real(setup.get("created_at")) or 0.0
    expires = _real(setup.get("expires_at")) or 0.0
    if expires <= created:
        return REJECT_EXPIRY
    return OK


def setup_risk(setup: dict[str, Any]) -> float:
    """مسافة الإبطال — ما يخسره الحساب إن ماتت الفكرة."""
    entry = _real(setup.get("entry_reference")) or 0.0
    stop = _real(setup.get("invalidation_price")) or 0.0
    return abs(entry - stop)


def setup_reward(setup: dict[str, Any]) -> float:
    """مسافة الهدف — ما تقصده الفكرة."""
    entry = _real(setup.get("entry_reference")) or 0.0
    target = _real(setup.get("target_price")) or 0.0
    return abs(target - entry)


def setup_ratio(setup: dict[str, Any]) -> float:
    """نسبة الإعداد — **خاصّية للفكرة** لا بوّابة تُطبَّق عليها لاحقًا.

    هذا الفرق هو كل الفرق: نسبةٌ تخرج من الفكرة تُعاير إحصائيًّا، ونسبةٌ
    تُحسب بين رقمين اختارتهما طبقتان مختلفتان لا تعني شيئًا.
    """
    risk = setup_risk(setup)
    return (setup_reward(setup) / risk) if risk > 0 else 0.0


def is_alive(setup: dict[str, Any], now: float | None = None) -> bool:
    """هل الإعداد ما زال يصف السوق الحاضر؟"""
    stamp = float(now if now is not None else time.time())
    return stamp < (_real(setup.get("expires_at")) or 0.0)


def is_target_reached(setup: dict[str, Any], price: Any) -> bool:
    """هل بلغ السعرُ هدفَ الفكرة قبل الدخول؟

    سؤالٌ عن **فوات الفرصة**، لا عن صحّة الهندسة. الدخول بعد بلوغ الهدف
    مطاردةٌ للحركة لا تنفيذٌ لفكرة، ولا عائد يبقى فيها.
    """
    current = _real(price)
    target = _real(setup.get("target_price"))
    if current is None or target is None:
        return False
    return current >= target if _text(setup.get("side")) == BUY else current <= target


def geometry_matches_entry(setup: dict[str, Any]) -> bool:
    """هل الإبطال والهدف متّسقان مع **مرجع الدخول**؟

    حكم المالك ٢٠٢٦-٠٩-٠٦: الهندسة تُقاس على `entry_reference` لا على
    السعر الحاليّ. السعر الحاليّ يجيب سؤالًا آخر تمامًا — «هل فاتت
    الفكرة؟» — وخلط السؤالين كان يُصنّف مئةً وواحدًا وعشرين إعدادًا
    سليمًا بأنه «هندسة مقلوبة» لمجرّد أن السعر تحرّك بعد ولادته.
    """
    entry = _real(setup.get("entry_reference"))
    stop = _real(setup.get("invalidation_price"))
    target = _real(setup.get("target_price"))
    if entry is None or stop is None or target is None:
        return False
    if _text(setup.get("side")) == BUY:
        return stop < entry < target
    return target < entry < stop


def is_broken(setup: dict[str, Any], price: Any) -> bool:
    """هل تجاوز السعرُ الإبطال فماتت الفكرة؟

    يُستعمل قبل الدخول (فلا يُفتح إعداد مات) وبعده (فيعرف 577 ما يحرس).
    """
    current = _real(price)
    stop = _real(setup.get("invalidation_price"))
    if current is None or stop is None:
        return False
    return current <= stop if _text(setup.get("side")) == BUY else current >= stop
