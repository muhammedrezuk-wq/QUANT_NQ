"""اختبار مُصنِّف الدخول — الصنف ③ وعتبة المسافة النسبيّة.

٢٠٢٦-٠٩-٠٢: هذه الذرّة كانت **بلا أيّ ملفّ اختبار**، وهي البوّابة التي
تُصدر مرشّح الدخول. التغطية هنا تبدأ من العتبة التي حُوِّلت من نقاطٍ
مطلقة إلى نقاط أساس — ولا تدّعي تغطية الأصناف الثلاثة كلّها.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import time

from core.contracts.atom import AtomContext

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("entry", os.path.join(HERE, "..", "atom.py"))
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class Log:
    def __getattr__(self, _):
        return lambda *a, **k: None


def _ctx(cfg):
    async def pub(_event, _payload):
        return None
    return AtomContext(atom_id=2274, config=cfg, logger=Log(),
                       publish=pub, subscribe=lambda *a, **k: None)


async def _atom(**cfg):
    atom = entry.Atom()
    await atom.initialize(_ctx(cfg))
    await atom.start()
    return atom


def _arm(atom, *, level_value: float, distance_bps: float | None,
         distance_points: float | None = None, volume_ratio: float = 1.2,
         age_s: float = 0.0):
    """يهيّئ كسرًا بوقودٍ موافقٍ لاتجاه الشراء. `age_s` عمر حدث الكسر."""
    symbol = "BTC_USDT"
    atom._breaks[symbol] = {"pdh": {"event": "broken", "level_value": level_value,
                                    "distance_points": distance_points,
                                    "distance_bps": distance_bps,
                                    "timestamp": time.time() - age_s}}
    atom._fuel[symbol] = {"fuel": "building_rise"}
    atom._volume_ma[symbol] = {"ratio": volume_ratio}
    return symbol


def test_break_within_relative_threshold_is_classified():
    """اختبار نجاح: مسافة 10 ن.أ تحت السقف 20 ⇒ الصنف ③."""
    async def run():
        atom = await _atom(filtered_break_max_bps=20.0)
        symbol = _arm(atom, level_value=78650.0, distance_bps=10.0)
        klass, evidence, _ = atom._classify(symbol, "long")
        assert klass == entry.CLASS_3
        assert evidence["distance_bps"] == 10.0
        assert evidence["max_bps"] == 20.0
    asyncio.run(run())


def test_break_beyond_relative_threshold_is_rejected():
    """اختبار فشل: 35 ن.أ فوق السقف ⇒ لا صنف."""
    async def run():
        atom = await _atom(filtered_break_max_bps=20.0)
        symbol = _arm(atom, level_value=78650.0, distance_bps=35.0)
        klass, _, _ = atom._classify(symbol, "long")
        assert klass is None
    asyncio.run(run())


def test_threshold_behaves_identically_across_price_scales():
    """جوهر التحويل: الحكم واحد على رمزين تفصل بينهما ثمانية أسس عشرية.

    بالعتبة المطلقة القديمة (150 نقطة) كان BTC يُحجب عند 19 ن.أ بينما
    PEPE يمرّ عند 421 مليار ن.أ — أي عتبة تعمل على رمزٍ واحد من ١٩.
    """
    async def run():
        verdicts = {}
        for label, level in (("BTC", 78650.0), ("PEPE", 0.00000356)):
            atom = await _atom(filtered_break_max_bps=20.0)
            symbol = _arm(atom, level_value=level, distance_bps=12.0)
            verdicts[label] = atom._classify(symbol, "long")[0]
        assert verdicts["BTC"] == entry.CLASS_3
        assert verdicts["PEPE"] == entry.CLASS_3
        assert verdicts["BTC"] == verdicts["PEPE"]
    asyncio.run(run())


def test_relative_distance_is_derived_when_publisher_is_old():
    """ناشرٌ لم يُرقَّ بعد لا يُسكت البوّابة — تُشتقّ النسبة من المطلق والمستوى."""
    async def run():
        atom = await _atom(filtered_break_max_bps=20.0)
        # 7.865 نقطة من 78,650 = 1 ن.أ — داخل السقف
        symbol = _arm(atom, level_value=78650.0, distance_bps=None, distance_points=7.865)
        klass, evidence, _ = atom._classify(symbol, "long")
        assert klass == entry.CLASS_3
        assert abs(evidence["distance_bps"] - 1.0) < 0.01
    asyncio.run(run())


def test_loud_break_is_excluded_regardless_of_distance():
    """الكسر الصاخب (≥×3 حجم) إقصاءٌ صريح — لا تنقضه المسافة القريبة."""
    async def run():
        atom = await _atom(filtered_break_max_bps=20.0, loud_break_ratio=3.0)
        symbol = _arm(atom, level_value=78650.0, distance_bps=5.0, volume_ratio=4.0)
        klass, _, _ = atom._classify(symbol, "long")
        assert klass is None
    asyncio.run(run())


def test_fuel_must_match_direction():
    """وقودٌ معاكس للاتجاه ⇒ لا صنف ③ مهما قربت المسافة."""
    async def run():
        atom = await _atom(filtered_break_max_bps=20.0)
        symbol = _arm(atom, level_value=78650.0, distance_bps=5.0)
        atom._fuel[symbol] = {"fuel": "building_decline"}     # هبوطيّ مع طلب شراء
        klass, _, _ = atom._classify(symbol, "long")
        assert klass is None
    asyncio.run(run())


def test_stale_break_event_no_longer_arms_an_entry():
    """اختبار فشل: حدث كسر عمره عشرون دقيقة لا يسلّح دخولًا.

    المقيس ٢٠٢٦-٠٩-٠١: `max_age_s` كان مقروءًا في `health_check()` حصرًا
    — شارةٌ لا بوّابة. فحدثٌ قديم يظلّ مسلَّحًا والسوق تحرّك منذ صدوره.
    """
    async def run():
        atom = await _atom(filtered_break_max_bps=20.0, input_max_age_s=120.0)
        symbol = _arm(atom, level_value=78650.0, distance_bps=5.0, age_s=1200.0)
        klass, _, _ = atom._classify(symbol, "long")
        assert klass is None
        health = await atom.health_check()
        assert health.details["stale_inputs"] == 1
        assert health.details["input_max_age_s"] == 120.0
    asyncio.run(run())


def test_fresh_break_event_within_budget_still_arms():
    """اختبار نجاح: داخل الميزانية الزمنيّة يبقى السلوك كما كان."""
    async def run():
        atom = await _atom(filtered_break_max_bps=20.0, input_max_age_s=120.0)
        symbol = _arm(atom, level_value=78650.0, distance_bps=5.0, age_s=30.0)
        klass, _, _ = atom._classify(symbol, "long")
        assert klass == entry.CLASS_3
        health = await atom.health_check()
        assert health.details["stale_inputs"] == 0
    asyncio.run(run())
