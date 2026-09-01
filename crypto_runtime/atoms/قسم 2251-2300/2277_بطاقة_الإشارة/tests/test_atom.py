"""اختبار بطاقة الإشارة — وبوّابتا العمر والمرساة.

٢٠٢٦-٠٩-٠٢: كانت الذرّة بلا أيّ ملفّ اختبار. والحادثة التي استدعت
البوّابتين مقيسة: `LINK_USDT` صدرت بطاقتها بمرساة `11.488` ووقف
`11.4547` والسعر وقتها `11.333` — أي **106 نقاط تحت الوقف نفسه** —
و«معتمَدة» بلا علم واحد. الوقف يُشتقّ من المرساة لا من السعر، فلم يكن
شيء يربط الاثنين.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import time

from core.contracts.atom import AtomContext

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("card", os.path.join(HERE, "..", "atom.py"))
card = importlib.util.module_from_spec(spec)
spec.loader.exec_module(card)


class Log:
    def __getattr__(self, _):
        return lambda *a, **k: None


class Bus:
    def __init__(self):
        self.out = []

    def ctx(self, cfg):
        async def pub(event, payload):
            self.out.append((event, payload))
        return AtomContext(atom_id=2277, config=cfg, logger=Log(),
                           publish=pub, subscribe=lambda *a, **k: None)


async def _atom(bus: Bus, **cfg):
    atom = card.Atom()
    await atom.initialize(bus.ctx(cfg))
    await atom.start()
    return atom


def _sized(*, anchor: float, price: float, direction: str = "long",
           age_s: float = 0.0, approved: bool = True):
    return {"approved": approved, "symbol": "LINK_USDT", "direction": direction,
            "price": price, "grade": "A", "entry_class": "②break_retest",
            "evidence": {"level_value": anchor},
            "timestamp": time.time() - age_s}


def _cards(bus: Bus):
    return [p for e, p in bus.out if e == "crypto.decision.signal_card.state"]


def test_card_is_published_when_price_is_on_the_right_side():
    """اختبار نجاح: سعرٌ فوق الوقف لشراءٍ ⇒ بطاقة تصدر."""
    async def run():
        bus = Bus()
        atom = await _atom(bus)
        await atom._on_sized(_sized(anchor=11.488, price=11.488))
        assert len(_cards(bus)) == 1
        published = _cards(bus)[0]
        assert published["stop_loss"] < published["entry_price"]
        # 11.488 − 29 ن.أ = 11.4547 — أرقام حادثة LINK حرفيًّا
        assert abs(published["stop_loss"] - 11.4547) < 1e-4
    asyncio.run(run())


def test_long_card_is_rejected_when_price_already_below_stop():
    """اختبار فشل — حادثة LINK حرفيًّا: 11.333 تحت وقف 11.4547 ⇒ لا بطاقة."""
    async def run():
        bus = Bus()
        atom = await _atom(bus)
        await atom._on_sized(_sized(anchor=11.488, price=11.333))
        assert _cards(bus) == []
        health = await atom.health_check()
        assert health.details["rejected"]["price_beyond_stop"] == 1
    asyncio.run(run())


def test_short_card_is_rejected_when_price_already_above_stop():
    """اختبار فشل: الجهة المعاكسة تُفحَص بنفس الصرامة."""
    async def run():
        bus = Bus()
        atom = await _atom(bus)
        await atom._on_sized(_sized(anchor=11.488, price=11.60, direction="short"))
        assert _cards(bus) == []
        health = await atom.health_check()
        assert health.details["rejected"]["price_beyond_stop"] == 1
    asyncio.run(run())


def test_stale_sized_entry_is_rejected():
    """اختبار فشل: مدخلٌ أقدم من `input_max_age_s` لا يُبنى عليه.

    كان `max_age_s` مقروءًا في `health_check()` حصرًا — شارةٌ لا بوّابة.
    """
    async def run():
        bus = Bus()
        atom = await _atom(bus, input_max_age_s=30.0)
        await atom._on_sized(_sized(anchor=11.488, price=11.488, age_s=120.0))
        assert _cards(bus) == []
        health = await atom.health_check()
        assert health.details["rejected"]["stale_input"] == 1
    asyncio.run(run())


def test_fresh_input_within_budget_passes():
    """اختبار نجاح: داخل الميزانية الزمنيّة ⇒ يمرّ."""
    async def run():
        bus = Bus()
        atom = await _atom(bus, input_max_age_s=30.0)
        await atom._on_sized(_sized(anchor=11.488, price=11.488, age_s=5.0))
        assert len(_cards(bus)) == 1
    asyncio.run(run())


def test_unapproved_entry_never_becomes_a_card():
    """اختبار فشل: ما لم يُعتمَد لا يصير بطاقة."""
    async def run():
        bus = Bus()
        atom = await _atom(bus)
        await atom._on_sized(_sized(anchor=11.488, price=11.488, approved=False))
        assert _cards(bus) == []
    asyncio.run(run())


def test_health_exposes_both_rejection_reasons():
    """الرفض معدودٌ بسببه — رفضٌ صامت يعيد المشكلة بشكل آخر."""
    async def run():
        bus = Bus()
        atom = await _atom(bus, input_max_age_s=30.0)
        await atom._on_sized(_sized(anchor=11.488, price=11.333))        # تجاوز الوقف
        await atom._on_sized(_sized(anchor=11.488, price=11.488, age_s=90.0))  # قديم
        health = await atom.health_check()
        assert health.details["rejected"] == {"stale_input": 1, "price_beyond_stop": 1}
    asyncio.run(run())
