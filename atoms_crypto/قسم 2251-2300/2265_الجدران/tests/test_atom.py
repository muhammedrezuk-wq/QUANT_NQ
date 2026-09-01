"""اختبار الجدران — market.depth ⇒ sense.walls.state (نسبةٌ وأكبر الجدران).

٢٠٢٦-٠٩-٠١: كان هذا الملفّ يحمل `async def main()` بلا أيّ دالّة `test_`،
فلا يجمعه pytest إطلاقًا — يُشغَّل من `scripts/test_atoms.py` وحده. أي أنّ
أيّ كسرٍ هنا كان يمرّ من بوّابة `pytest` صامتًا. حُوّل إلى دوالّ `test_`
حقيقيّة، وأُضيفت تغطية بوّابة اللقطة الجديدة.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os

from core.contracts.atom import AtomContext

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("walls", os.path.join(HERE, "..", "atom.py"))
walls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(walls)


class Log:
    def __getattr__(self, _):
        return lambda *a, **k: None


class Bus:
    def __init__(self):
        self.out = []

    def ctx(self, cfg):
        async def pub(event, payload):
            self.out.append((event, payload))
        return AtomContext(atom_id=265, config=cfg, logger=Log(),
                           publish=pub, subscribe=lambda *a, **k: None)


def _book(levels: int, bid_size: float = 10.0, ask_size: float = 4.0):
    """دفترٌ اصطناعيّ بعدد مستويات محدَّد لكل جهة."""
    bids = [[100.0 - i * 0.1, bid_size] for i in range(levels)]
    asks = [[100.1 + i * 0.1, ask_size] for i in range(levels)]
    return bids, asks


async def _atom(bus: Bus, **overrides):
    cfg = {"levels": 20, "top_n": 3, "near_bps": 25, "max_age_s": 10}
    cfg.update(overrides)
    atom = walls.Atom()
    await atom.initialize(bus.ctx(cfg))
    await atom.start()
    return atom


def test_walls_ratio_follows_sizes_and_captures_largest():
    async def run():
        bus = Bus()
        atom = await _atom(bus, min_levels=3)
        # طلبٌ أثقل من العرض ⇒ نسبة > 1 وميلٌ موجب؛ أكبر جدار طلبٍ 50 عند 99.8.
        await atom._on_depth({"symbol": "BTC_USDT", "provider": "MEXC",
                              "bids": [[100.0, 10.0], [99.9, 5.0], [99.8, 50.0]],
                              "asks": [[100.1, 4.0], [100.2, 3.0], [100.3, 8.0]]})
        state = [p for e, p in bus.out if e == "sense.walls.state"][-1]
        assert state["role"] == "WITNESS"
        assert abs(state["bid_sum"] - 65.0) < 1e-9
        assert abs(state["ask_sum"] - 15.0) < 1e-9
        assert state["ratio"] > 1 and state["imbalance"] > 0
        assert state["bid_walls"][0] == [99.8, 50.0]
        assert state["ask_walls"][0] == [100.3, 8.0]
        assert len(state["bid_walls"]) == 3 and len(state["ask_walls"]) == 3
    asyncio.run(run())


def test_missing_side_is_not_published():
    async def run():
        bus = Bus()
        atom = await _atom(bus, min_levels=1)
        before = len(bus.out)
        await atom._on_depth({"symbol": "ETH_USDT", "bids": [], "asks": [[10.0, 1.0]]})
        assert len(bus.out) == before
    asyncio.run(run())


# ── بوّابة اللقطة — اختبار فشل لكل سبب رفض ──────────────────────────────

def test_incremental_delta_is_rejected():
    """اختبار فشل: رسالة موسومة `delta` لا تُقرأ دفترًا.

    السبب المقيس ٢٠٢٦-٠٩-٠١: `٢٦٢٠` يشترك على `sub.depth` وهي قناة
    تزايديّة، وكانت تُجمع هنا كأنّها الدفتر كلّه — فخرجت نسبٌ صفريّة
    قُرئت أصواتَ «شورت»: 55 من 80 = 69% أثرٌ من بيانات معطوبة.
    """
    async def run():
        bus = Bus()
        atom = await _atom(bus, min_levels=1)
        bids, asks = _book(10)
        await atom._on_depth({"symbol": "BTC_USDT", "depth_kind": "delta",
                              "bids": bids, "asks": asks})
        assert not [p for e, p in bus.out if e == "sense.walls.state"]
        health = await atom.health_check()
        assert health.details["rejected"]["delta"] == 1
    asyncio.run(run())


def test_snapshot_is_accepted():
    """اختبار نجاح: الموسوم `snapshot` يمرّ ويُنشر."""
    async def run():
        bus = Bus()
        atom = await _atom(bus, min_levels=5)
        bids, asks = _book(10)
        await atom._on_depth({"symbol": "BTC_USDT", "depth_kind": "snapshot",
                              "bids": bids, "asks": asks})
        assert len([p for e, p in bus.out if e == "sense.walls.state"]) == 1
        health = await atom.health_check()
        assert health.details["rejected_total"] == 0
        assert health.details["accept_pct"] == 100.0
    asyncio.run(run())


def test_too_few_levels_is_rejected():
    """اختبار فشل: دفترٌ بمستوًى واحد ليس لقطة — 20.8% من العيّنات كانت كذلك."""
    async def run():
        bus = Bus()
        atom = await _atom(bus, min_levels=5)
        await atom._on_depth({"symbol": "BTC_USDT",
                              "bids": [[100.0, 10.0]], "asks": [[100.1, 4.0]]})
        assert not [p for e, p in bus.out if e == "sense.walls.state"]
        health = await atom.health_check()
        assert health.details["rejected"]["few_levels"] == 1
    asyncio.run(run())


def test_zero_sum_side_is_rejected():
    """اختبار فشل: جهةٌ مجموعها صفر تعطي `ratio = 0.000` — صوت شورت زائف."""
    async def run():
        bus = Bus()
        atom = await _atom(bus, min_levels=5)
        bids, asks = _book(10, bid_size=0.0)      # كل أحجام الشراء صفر (حذف مستويات)
        await atom._on_depth({"symbol": "BTC_USDT", "bids": bids, "asks": asks})
        assert not [p for e, p in bus.out if e == "sense.walls.state"]
        health = await atom.health_check()
        assert health.details["rejected"]["empty_side"] == 1
    asyncio.run(run())


def test_crossed_book_is_rejected_and_counted():
    """اختبار فشل: أفضل عرضٍ دون أفضل طلب = بيانات فاسدة، وتُعَدّ باسمها."""
    async def run():
        bus = Bus()
        atom = await _atom(bus, min_levels=1)
        await atom._on_depth({"symbol": "BTC_USDT",
                              "bids": [[100.0, 10.0], [99.9, 9.0]],
                              "asks": [[99.0, 4.0], [99.5, 3.0]]})
        assert not [p for e, p in bus.out if e == "sense.walls.state"]
        health = await atom.health_check()
        assert health.details["rejected"]["crossed"] == 1
    asyncio.run(run())


def test_delta_passes_when_snapshot_not_required():
    """اختبار نجاح: العيار قابل للإطفاء صراحةً — لا سلوك مخفيّ."""
    async def run():
        bus = Bus()
        atom = await _atom(bus, min_levels=1, require_snapshot=False)
        bids, asks = _book(10)
        await atom._on_depth({"symbol": "BTC_USDT", "depth_kind": "delta",
                              "bids": bids, "asks": asks})
        assert len([p for e, p in bus.out if e == "sense.walls.state"]) == 1
    asyncio.run(run())
