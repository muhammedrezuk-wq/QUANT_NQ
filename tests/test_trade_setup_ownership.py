# -*- coding: utf-8 -*-
"""ملكية الصفقة — اختبارات القبول لورقة التنفيذ ٢٠٢٦-٠٩-٠٦.

حكم المالك: «إذا كان بإمكان النظام بعد التعديل فتح صفقة من 404/408
وحدهما، فالإصلاح فاشل، مهما كانت نتائج الاختبارات الأخرى».

هذه الاختبارات تحرس الأربعة التي جعلها المالك معيار النجاح (§٢٥):
    ١. لا يمكن فتح OPEN بلا إعداد.
    ٢. لا يمكن تغيير إبطال الإعداد من طبقة لاحقة.
    ٣. لا يضيع `setup_id` أثناء العبور بين الطبقات.
    ٤. لا يوجد مسار فتح ثانٍ يلتفّ حول العقد.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared import position_delta_recompute as pdr  # noqa: E402
from shared.trade_setup import (  # noqa: E402
    OK, REJECT_GEOMETRY, REJECT_PRICES, REJECT_WHY, SETUP_LIQUIDITY_RAID,
    build_setup, geometry_matches_entry, is_alive, is_broken, is_target_reached,
    net_ratio as pdr_net, round_trip_cost, setup_ratio, validate_setup)


def _setup(side="sell", entry=79986.0, stop=80012.0, target=79850.0, **kw):
    return build_setup(
        owner="410", setup_type=SETUP_LIQUIDITY_RAID, side=side,
        entry_reference=entry, invalidation_price=stop,
        invalidation_source="410:sweep_edge",
        invalidation_reason="عودة السعر فوق طرف الكنس تُبطل الاسترداد",
        target_price=target, target_source="410:opposite_liquidity",
        target_reason="السيولة المقابلة", symbol="BTCUSD", **kw)


# ─────────── العقد نفسه: الهندسة والنسب والحياة ───────────

def test_setup_geometry_must_be_sane() -> None:
    """اختبارا ١١ و١٠: إبطال مقلوب أو ناقص = رفض، لا اختراع بديل."""
    assert validate_setup(_setup()) == OK
    # بيع بإبطال تحت الدخول = هندسة مقلوبة.
    assert validate_setup(_setup(stop=79900.0)) == REJECT_GEOMETRY
    # بلا إبطال أصلًا.
    assert validate_setup(_setup(stop=None)) == REJECT_PRICES
    # بلا هدف.
    assert validate_setup(_setup(target=None)) == REJECT_PRICES
    # إبطال بلا سبب = رقم بلا نسب، ليس إبطالًا.
    bare = _setup()
    bare["invalidation_reason"] = ""
    assert validate_setup(bare) == REJECT_WHY


def test_ratio_is_a_property_of_the_idea() -> None:
    """النسبة تخرج من الفكرة لا من بوّابة تُطبَّق عليها لاحقًا."""
    setup = _setup(entry=79986.0, stop=80012.0, target=79850.0)
    assert abs(setup_ratio(setup) - (136.0 / 26.0)) < 1e-9


def test_setup_dies_by_price_and_by_time() -> None:
    """§١٧: فكرةٌ ماتت لا تُفتح — لا بتجاوز الإبطال ولا بانقضاء الأجل."""
    setup = _setup(ttl_s=10.0)
    assert is_alive(setup, setup["created_at"] + 5.0)
    assert not is_alive(setup, setup["created_at"] + 11.0)
    assert not is_broken(setup, 79990.0)
    assert is_broken(setup, 80013.0)          # بيع: تجاوز الإبطال فوقه


# ─────────── البوّابة: لا صفقة بلا إعداد مملوك ───────────

def test_direction_alone_cannot_open_a_trade() -> None:
    """اختبار ١ و§٢١ — انحدار الصفقة 1911362798.

    404 = SELL و408 = SELL، ولا إعداد مملوك ⇒ **لا صفقة**.
    هذا الاختبار يجب أن يفشل على النظام القديم وينجح بعد الإصلاح.
    """
    now = time.time()
    assert pdr._setup_gate(None, "sell", 79986.0, now) == pdr.NO_SETUP
    assert pdr._setup_gate({}, "sell", 79986.0, now) == pdr.NO_SETUP


def test_context_cannot_flip_the_owner_side() -> None:
    """اختبار ٨: سياق معاكس لا يسرق ملكية الإبطال ولا يقلب الإعداد."""
    now = time.time()
    sell_setup = _setup(side="sell")
    assert pdr._setup_gate(sell_setup, "buy", 79986.0, now) == pdr.SETUP_SIDE_MISMATCH


def test_stale_or_broken_setup_is_refused() -> None:
    """اختبارا ١٢ و١٧: إعداد منتهٍ أو ميت لا يفتح صفقة."""
    setup = _setup(ttl_s=5.0)
    assert pdr._setup_gate(setup, "sell", 79986.0,
                           setup["created_at"] + 9.0) == pdr.SETUP_EXPIRED
    alive = setup["created_at"] + 1.0
    assert pdr._setup_gate(setup, "sell", 80013.0, alive) == pdr.SETUP_ALREADY_BROKEN


def test_a_complete_setup_passes_the_gate() -> None:
    """اختبار ٢: إعداد كامل من 410 ⇒ يُسمح بالفتح."""
    setup = _setup()
    assert pdr._setup_gate(setup, "sell", 79986.0, setup["created_at"] + 1.0) == ""


# ─────────── قطع المسار القديم: لا باب ثانٍ ───────────

def test_no_second_door_to_open() -> None:
    """§٩ و§١٠: 581 لم يعد يملك اختيار الوقف والهدف من خريطة عامّة.

    القياس على الكود نفسه لا على النيّة: الأسطر التي كانت تختار المستوى
    (`reachable[-1]` و`reachable[0]`) محذوفة، والإبطال والهدف يُقرآن من
    الإعداد. أيّ عودة لها تكسر هذا الحارس.
    """
    source = Path(pdr.__file__).read_text(encoding="utf-8")
    assert "reachable = [t for t in above" not in source, "عاد اختيار الهدف إلى 581"
    assert "reachable = [t for t in below" not in source, "عاد اختيار الهدف إلى 581"
    assert 'setup.get("invalidation_price")' in source, "581 لا يقرأ إبطال الإعداد"
    assert 'setup.get("target_price")' in source, "581 لا يقرأ هدف الإعداد"
    # وهوية الفكرة تعبر مع الأمر ولا تضيع (§٢٢).
    for field in ("setup_id", "setup_owner", "analysis_invalidation",
                  "analysis_target", "invalidation_source", "target_source"):
        assert f'"{field}"' in source, f"حقل الهوية مفقود من الأمر: {field}"


def test_551_carries_ownership_and_never_edits_it() -> None:
    """اختبار ٤ (المرحلة هـ): 551 يحسب الحجم ولا يبدّل إبطال الإعداد."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "atoms/قسم 551-600/551_باني_الأمر/atom.py").read_text(
        encoding="utf-8")
    for field in ("setup_id", "setup_owner", "analysis_invalidation",
                  "analysis_target", "invalidation_source", "target_source"):
        assert f'"{field}"' in source, f"551 لا يحمل حقل الملكية: {field}"
    # ولا يُسند إليها قيمة جديدة في أيّ موضع.
    for field in ("analysis_invalidation", "analysis_target", "setup_id"):
        assert f'["{field}"] =' not in source, f"551 يعدّل حقلًا مملوكًا: {field}"


def test_584_separates_execution_stop_from_the_idea() -> None:
    """اختبار ٥ (المرحلة و): إزاحة وقف التنفيذ تُسجَّل، والهدف لا يُخترع."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "atoms/قسم 551-600/584_شرعية_الستوب/atom.py").read_text(
        encoding="utf-8")
    assert "execution_stop" in source, "584 لا يفصل وقف التنفيذ"
    assert "EXECUTION_STOP_ADJUSTED" in source, "الإزاحة لا تُسجَّل"
    assert 'num(payload.get("analysis_target"))' in source, \
        "584 ما زال يخترع هدفًا بدل هدف الإعداد"
    assert '"analysis_invalidation"' not in source.split("out.update")[-1], \
        "584 يكتب فوق الإبطال التحليليّ"


def test_577_respects_the_owned_invalidation() -> None:
    """اختبار ٦ (المرحلة ز): الزحف لا يستبدل إبطال الإعداد بمنطق آخر."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "atoms/قسم 551-600/577_صيانة_الستوب/atom.py").read_text(
        encoding="utf-8")
    assert "EVENT_SETUP" in source and "_setup_stop" in source, \
        "577 لا يسمع الإعداد"
    assert "_on_setup" in source, "577 بلا مستقبِل للإعداد"


def test_missed_opportunity_is_named_by_its_own_name() -> None:
    """الاختبار الحاسم بأرقام المالك ٢٠٢٦-٠٩-٠٦.

        entry=79693 · invalidation=79699 · target=79682 · current=79680
        ⇒ SETUP_TARGET_REACHED  (لا LEVELS_INVERTED)

    الفكرة سليمة الهندسة عند ولادتها؛ ما جرى أن السعر بلغ هدفها قبل
    الدخول — أي **فاتت الفرصة**. وخلط الحالتين كان يصنّف مئةً وواحدًا
    وعشرين إعدادًا سليمًا بأنه مقلوب الهندسة.
    """
    setup = _setup(side="sell", entry=79693.0, stop=79699.0, target=79682.0)
    assert validate_setup(setup) == OK, "الإعداد سليم عند ولادته"
    assert geometry_matches_entry(setup), "الهندسة متّسقة مع مرجع الدخول"
    now = setup["created_at"] + 1.0
    direction, _, reason = pdr._direction_from_setup(setup, 79680.0, now)
    assert reason == pdr.SETUP_TARGET_REACHED, reason
    assert direction == "wait"
    # وقبل بلوغ الهدف: الفكرة حيّة وتفتح المسار.
    direction, _, reason = pdr._direction_from_setup(setup, 79690.0, now)
    assert reason == "" and direction == "sell", (reason, direction)


def test_the_three_time_states_stay_separate() -> None:
    """ثلاث حالات زمنية مستقلّة لا تُخلط، وبالترتيب الذي أمر به المالك."""
    base = _setup(side="sell", entry=79693.0, stop=79699.0, target=79682.0,
                  ttl_s=10.0)
    born = base["created_at"]
    # بلوغ الهدف يسبق انتهاء الأجل في الترتيب — الفرصة فاتت لا الوقت.
    assert pdr._direction_from_setup(base, 79680.0, born + 99.0)[2] \
        == pdr.SETUP_TARGET_REACHED
    # ولو لم يُبلَغ الهدف، فالأجل هو الحكم.
    assert pdr._direction_from_setup(base, 79690.0, born + 99.0)[2] \
        == pdr.SETUP_EXPIRED
    # ولو كان حيًّا ولم يُبلَغ الهدف، فالإبطال.
    assert pdr._direction_from_setup(base, 79700.0, born + 1.0)[2] \
        == pdr.SETUP_ALREADY_BROKEN
    # وهندسة مقلوبة عند مرجع الدخول تُسمّى باسمها لا بأسمائهم.
    bad = dict(base, target_price=79800.0)
    assert pdr._direction_from_setup(bad, 79693.0, born + 1.0)[2] \
        == pdr.SETUP_GEOMETRY_INVALID


def test_setup_opens_even_when_the_vote_is_neutral() -> None:
    """الاختبار الحاسم (نصّ المالك): 410 = SELL_SETUP و404/408 محايدان
    ⇒ يجب أن يصل إلى OPEN، بتعرّض مخفَّض لا كامل."""
    setup = _setup(side="sell")
    now = setup["created_at"] + 1.0
    direction, _, block = pdr._direction_from_setup(setup, 79986.0, now)
    assert block == "" and direction == "sell", (block, direction)
    # التصويت محايد ⇒ موقف محايد ⇒ تعرّض مخفَّض، لا صفر ولا كامل.
    stance = pdr._vote_stance("wait", "sell", pdr.FILTER_PASSED)
    assert stance == pdr.STANCE_NEUTRAL
    assert 0.0 < pdr.NEUTRAL_EXPOSURE_FACTOR < 1.0, "المحايد صار صفقة كاملة"


def test_bare_direction_still_yields_no_trade() -> None:
    """وبالمقابل: 404/408 = SELL بلا إعداد ⇒ لا اتجاه أصلًا ⇒ NO TRADE."""
    direction, _, block = pdr._direction_from_setup(None, 79986.0, time.time())
    assert direction == "wait" and block == pdr.NO_SETUP


def test_opposing_context_refuses_rather_than_shrinks() -> None:
    """سياقٌ معارض لا يُصغَّر بل يُرفض — ولا يقلب اتجاه الفكرة أبدًا."""
    assert pdr._vote_stance("buy", "sell", pdr.FILTER_PASSED) == pdr.STANCE_AGAINST
    assert pdr._vote_stance("sell", "sell", pdr.FILTER_PASSED) == pdr.STANCE_SUPPORT
    # وحكم البوّابة المانع يُعامَل معارضةً مهما كان اتجاه التصويت.
    assert pdr._vote_stance("sell", "sell", pdr.FILTER_BLOCKED) == pdr.STANCE_AGAINST


def test_economics_judge_the_idea_not_the_spread() -> None:
    """اختبارا المالك الإلزاميّان ٢٠٢٦-٠٩-٠٦.

    قِيس أن ٢٢ من ٢٧ فكرة تُرفض لأن إبطالها أضيق من سبريد — «حكم على
    جودة الفكرة من معيار واحد، بدل أن يكون جزءًا من حساب الاقتصاد
    الكامل». الحكم صار اقتصاديًّا بتكلفة الجهتين.
    """
    cost = 5.0
    # مخاطرة ٣ · هدف ٤٠ · تكلفة ٥ ⇒ (40−5)/(3+5) = 4.38 — تُقبل رغم 3 < 5.
    tight = _setup(side="sell", entry=79624.75, stop=79627.75, target=79584.75)
    assert abs(pdr_net(tight, cost) - (35.0 / 8.0)) < 1e-9, pdr_net(tight, cost)
    assert pdr_net(tight, cost) >= 1.5, "رُفضت فكرة ضيّقة اقتصادها ممتاز"
    # مخاطرة ٢٠ · هدف ٢٥ ⇒ (25−5)/(20+5) = 0.80 — تُرفض اقتصاديًّا.
    wide = _setup(side="sell", entry=79600.0, stop=79620.0, target=79575.0)
    assert abs(pdr_net(wide, cost) - 0.8) < 1e-9, pdr_net(wide, cost)
    assert pdr_net(wide, cost) < 1.5, "قُبلت فكرة واسعة اقتصادها خاسر"
    # وتكلفة العبور تُحسب مرّة واحدة للدورة كاملة، لا مرّتين.
    assert round_trip_cost(79995.0, 80000.0) == 5.0


def test_spread_is_no_longer_a_verdict_on_the_idea() -> None:
    """`RISK_INSIDE_SPREAD` لم يعد سببًا مستقلًّا عند أيّ مالك."""
    root = Path(__file__).resolve().parents[1]
    for rel in ("atoms/قسم 401-450/410_استراتيجية_السيولة/atom.py",
                "atoms/قسم 401-450/406_استراتيجية_الاختراق/atom.py"):
        source = (root / rel).read_text(encoding="utf-8")
        # الذكر في تعليق يوثّق التاريخ مسموح؛ الممنوع أن يعود **حكمًا**.
        assert 'reason = "RISK_INSIDE_SPREAD"' not in source, \
            f"{rel}: السبريد ما زال حكمًا على الفكرة"
        assert "NET_RR_REJECTED" in source, f"{rel}: بلا حكم اقتصاديّ"
        assert "INVALIDATION_NOT_STRUCTURAL" in source, \
            f"{rel}: حُذف الحارس بلا بديل بنيويّ"
        assert "round_trip_cost" in source, f"{rel}: لا يحسب تكلفة الجهتين"


def test_owners_refuse_ideas_they_cannot_afford() -> None:
    """المالك يصمت بدل أن يقترح فكرة لا يُطاق اقتصادها.

    الشرطان خاصّيتان للفكرة عند صاحبها لا حارسًا لاحقًا يقصّها (حكم
    المالك: «لازم من أساس ما يغلط»)، وقد صارا بعد تصحيحه ٢٠٢٦-٠٩-٠٦:
    صلاحية بنيوية للإبطال، ثم حكم اقتصاديّ بتكاليف الجهتين — لا مقارنة
    بالسبريد وحده.
    """
    root = Path(__file__).resolve().parents[1]
    for rel in ("atoms/قسم 401-450/410_استراتيجية_السيولة/atom.py",
                "atoms/قسم 401-450/406_استراتيجية_الاختراق/atom.py"):
        source = (root / rel).read_text(encoding="utf-8")
        assert "INVALIDATION_NOT_STRUCTURAL" in source, \
            f"{rel}: بلا فحص بنيويّ للإبطال"
        assert "NET_RR_REJECTED" in source, f"{rel}: بلا حكم اقتصاديّ"
        assert "MIN_SETUP_RATIO = 1.5" in source, f"{rel}: تغيّر الحدّ 1.5"


def test_406_is_the_second_owner() -> None:
    """§١٢: 406 لا يكتفي بـ«bearish_breakout» بل يقول أين يموت وإلى أين."""
    root = Path(__file__).resolve().parents[1]
    atom = (root / "atoms/قسم 401-450/406_استراتيجية_الاختراق/atom.py").read_text(
        encoding="utf-8")
    manifest = (root / "atoms/قسم 401-450/406_استراتيجية_الاختراق/manifest.yaml").read_text(
        encoding="utf-8")
    assert "SETUP_BREAKOUT" in atom and "build_setup" in atom
    assert "406:range_edge" in atom, "الإبطال ليس حدّ المدى"
    assert "406:measured_move" in atom, "الهدف ليس حركة مقيسة"
    assert "strategy.setup.proposed" in manifest


def test_410_owns_a_real_setup_contract() -> None:
    """§١٣: 410 هو أوّل مالك — يعلن الإعداد ويصفه في مانيفستِه."""
    root = Path(__file__).resolve().parents[1]
    atom = (root / "atoms/قسم 401-450/410_استراتيجية_السيولة/atom.py").read_text(
        encoding="utf-8")
    manifest = (root / "atoms/قسم 401-450/410_استراتيجية_السيولة/manifest.yaml").read_text(
        encoding="utf-8")
    assert "EVENT_SETUP" in atom and "build_setup" in atom
    assert "invalidation_reason" in atom, "410 ينشر إبطالًا بلا سبب"
    assert "strategy.setup.proposed" in manifest, "الإعداد غير معلن في المانيفست"
