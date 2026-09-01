"""اختبار كسور الأمس — آلة حالة PDH/PDL، والمسافة بصيغتيها.

٢٠٢٦-٠٩-٠٢: هذه الذرّة كانت **بلا أيّ ملفّ اختبار** — وهي واحدة من عشرٍ
تشكّل سلسلة قرار الكريبتو كاملة (2270…2277). الفوركس 233/233 له اختبارات؛
الكريبتو كان قلب قراره عاريًا.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os

from core.contracts.atom import AtomContext

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("breaks", os.path.join(HERE, "..", "atom.py"))
breaks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(breaks)


class Log:
    def __getattr__(self, _):
        return lambda *a, **k: None


class Bus:
    def __init__(self):
        self.out = []

    def ctx(self, cfg):
        async def pub(event, payload):
            self.out.append((event, payload))
        return AtomContext(atom_id=2272, config=cfg, logger=Log(),
                           publish=pub, subscribe=lambda *a, **k: None)


async def _armed(bus: Bus, *, pdh: float, pdl: float):
    atom = breaks.Atom()
    await atom.initialize(bus.ctx({"timeframe": "5m", "touch_tolerance_pct": 0.05,
                                   "max_age_s": 600}))
    await atom.start()
    await atom._on_prior({"symbol": "BTC_USDT", "prior_ready": True, "pdh": pdh, "pdl": pdl})
    return atom


def _candle(close: float, high: float | None = None, low: float | None = None):
    return {"symbol": "BTC_USDT", "timeframe": "5m", "provider": "MEXC",
            "high": high if high is not None else close,
            "low": low if low is not None else close,
            "close": close, "volume": 100.0}


def test_close_above_pdh_emits_broken():
    async def run():
        bus = Bus()
        atom = await _armed(bus, pdh=100.0, pdl=90.0)
        await atom._on_candle(_candle(100.5))
        events = [p for e, p in bus.out if e == "crypto.decision.breaks.state"]
        assert len(events) == 1
        assert events[0]["event"] == "broken" and events[0]["level"] == "pdh"
    asyncio.run(run())


def test_distance_is_published_in_both_absolute_and_relative_form():
    """المطلق والنسبيّ معًا — النسبيّ هو ما يُقارَن به عند 2274."""
    async def run():
        bus = Bus()
        atom = await _armed(bus, pdh=100.0, pdl=90.0)
        await atom._on_candle(_candle(100.5))
        event = [p for e, p in bus.out if e == "crypto.decision.breaks.state"][0]
        assert abs(event["distance_points"] - 0.5) < 1e-9
        # 0.5 من 100.0 = 50 نقطة أساس
        assert abs(event["distance_bps"] - 50.0) < 1e-6
    asyncio.run(run())


def test_relative_distance_is_scale_free_across_symbols():
    """نفس النسبة على رمزين تفصل بينهما أربعة أسس عشرية.

    هذا هو جوهر التحويل: 150 نقطة مطلقة كانت تعني 19 ن.أ على BTC
    و421 مليار ن.أ على PEPE — أي عتبةً تعمل على رمزٍ واحد من ١٩.
    """
    async def run():
        results = {}
        for label, level in (("BTC", 78650.0), ("PEPE", 0.00000356)):
            bus = Bus()
            atom = await _armed(bus, pdh=level, pdl=level * 0.9)
            await atom._on_candle(_candle(level * 1.002))     # 20 ن.أ فوق المستوى
            event = [p for e, p in bus.out if e == "crypto.decision.breaks.state"][0]
            results[label] = event["distance_bps"]
        assert abs(results["BTC"] - 20.0) < 0.01
        assert abs(results["PEPE"] - 20.0) < 0.01
        assert abs(results["BTC"] - results["PEPE"]) < 0.01
    asyncio.run(run())


def test_failed_break_resets_to_none():
    """فقدان الإغلاق خلف المستوى يعيد الحالة — لا يبقى مسلّحًا بالخطأ."""
    async def run():
        bus = Bus()
        atom = await _armed(bus, pdh=100.0, pdl=90.0)
        await atom._on_candle(_candle(100.5))
        await atom._on_candle(_candle(99.0))                  # عاد تحت المستوى
        health = await atom.health_check()
        assert health.details["stages"]["BTC_USDT"]["up"] == breaks.STAGE_NONE
    asyncio.run(run())


def test_other_timeframes_are_ignored():
    """إطار القرار الوحيد ٥د — ما عداه لا يحرّك الآلة."""
    async def run():
        bus = Bus()
        atom = await _armed(bus, pdh=100.0, pdl=90.0)
        candle = _candle(100.5)
        candle["timeframe"] = "1m"
        await atom._on_candle(candle)
        assert not [p for e, p in bus.out if e == "crypto.decision.breaks.state"]
    asyncio.run(run())
