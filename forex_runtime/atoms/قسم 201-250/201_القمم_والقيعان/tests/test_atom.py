import asyncio
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.contracts.atom import AtomContext, HealthState  # noqa: E402
import importlib.util as _ilu  # noqa: E402

_spec = _ilu.spec_from_file_location(
    "_atom201", _Path(__file__).resolve().parents[1] / "atom.py")
_mod = _ilu.module_from_spec(_spec)
sys.modules["_atom201"] = _mod
_spec.loader.exec_module(_mod)
Atom = _mod.Atom
EVENT_OUT = _mod.EVENT_OUT


class _NullLogger:
    def debug(self, *a): pass
    def info(self, *a): pass
    def warning(self, *a): pass
    def error(self, *a): pass
    def critical(self, *a): pass


class FakeEventBus:
    def __init__(self):
        self.published = []
        self._handlers = {}

    def subscribe(self, name, handler):
        self._handlers.setdefault(name, []).append(handler)

    async def publish(self, name, payload):
        self.published.append((name, payload))

    def make_context(self, config):
        return AtomContext(atom_id=201, config=config, logger=_NullLogger(),
                           publish=self.publish, subscribe=self.subscribe)


CFG = {"lookback": 2}  # window = 5


async def _run(bars, cfg=None):
    bus = FakeEventBus()
    atom = Atom()
    await atom.initialize(bus.make_context(cfg or dict(CFG)))
    await atom.start()
    for i, (h, l) in enumerate(bars):
        c = (h + l) / 2
        await atom._on_candle({"symbol": "NQ100", "open": c, "high": h, "low": l,
                               "close": c, "volume": 1, "timeframe": "60s",
                               "period_start": float(i), "timestamp": float(i)})
    swings = [p for n, p in bus.published if n == EVENT_OUT]
    return atom, bus, swings


async def test_warmup_insufficient():
    print("\n--- test_warmup_insufficient ---")
    _atom, _bus, swings = await _run([(10, 9), (11, 10), (12, 11)])  # < window(5)
    assert swings, "لازم ينشر حتى وقت الإحماء"
    last = swings[-1]
    assert last["status"] == "insufficient_data", last["status"]
    assert last["signal"] == "none"
    assert "insufficient_candles" in last["warnings"]
    print("OK — الإحماء: insufficient_data + none")


async def test_detect_swing_high():
    print("\n--- test_detect_swing_high ---")
    # center (index 2) high=15 towers over its 2 neighbours each side
    bars = [(10, 9), (11, 10), (15, 14), (11, 10), (10, 9)]
    _atom, _bus, swings = await _run(bars)
    last = swings[-1]
    assert last["status"] == "ok", last
    assert last["signal"] == "swing_high", last["signal"]
    assert last["metadata"]["price"] == 15, last["metadata"]
    assert last["metadata"]["swing_time"] == 2.0, last["metadata"]["swing_time"]
    assert last["confidence"] == 1.0
    assert last["score"] > 0
    print(f"OK — قمة: price={last['metadata']['price']} "
          f"time={last['metadata']['swing_time']} score={last['score']}")


async def test_detect_swing_low():
    print("\n--- test_detect_swing_low ---")
    # center (index 2) low=3 dips below its 2 neighbours each side
    bars = [(10, 9), (11, 8), (9, 3), (11, 8), (10, 9)]
    _atom, _bus, swings = await _run(bars)
    last = swings[-1]
    assert last["signal"] == "swing_low", last["signal"]
    assert last["metadata"]["price"] == 3, last["metadata"]
    assert last["metadata"]["swing_time"] == 2.0
    print(f"OK — قاع: price={last['metadata']['price']} score={last['score']}")


async def test_monotonic_no_swing():
    print("\n--- test_monotonic_no_swing ---")
    bars = [(10 + i, 9 + i) for i in range(7)]  # steadily rising → no center peak/trough
    _atom, _bus, swings = await _run(bars)
    kinds = {s["signal"] for s in swings}
    assert "swing_high" not in kinds and "swing_low" not in kinds, kinds
    print("OK — صعود رتيب: صفر قمم/قيعان (بحقّ)")


async def test_contract_shape_complete():
    print("\n--- test_contract_shape_complete ---")
    bars = [(10, 9), (11, 10), (15, 14), (11, 10), (10, 9)]
    _atom, _bus, swings = await _run(bars)
    last = swings[-1]
    for field in ("symbol", "id", "cycle_id", "status", "signal", "score",
                  "confidence", "quality", "warnings", "metadata"):
        assert field in last, f"حقل ناقص بالعقد: {field}"
    for field in ("method", "timeframe", "lookback", "close", "price",
                  "swing_time", "prominence"):
        assert field in last["metadata"], f"حقل metadata ناقص: {field}"
    assert last["id"] == "swing"
    assert last["metadata"]["method"] == "fractal_center"
    assert 0.0 <= last["confidence"] <= 1.0
    print("OK — العقد الموحّد كامل الحقول")


async def test_health_states():
    print("\n--- test_health_states ---")
    bus = FakeEventBus()
    atom = Atom()
    await atom.initialize(bus.make_context(dict(CFG)))
    h0 = await atom.health_check()
    assert h0.state == HealthState.UNHEALTHY, "قبل start"
    await atom.start()
    h1 = await atom.health_check()
    assert h1.state == HealthState.DEGRADED, "بعد start بلا شموع"
    await atom._on_candle({"symbol": "NQ100", "open": 10, "high": 10, "low": 9,
                           "close": 10, "volume": 1, "timeframe": "60s",
                           "period_start": 0.0, "timestamp": 0.0})
    h2 = await atom.health_check()
    assert h2.state == HealthState.HEALTHY, "بعد وصول شمعة"
    print("OK — الصحة: UNHEALTHY→DEGRADED→HEALTHY")


async def main():
    tests = [
        test_warmup_insufficient,
        test_detect_swing_high,
        test_detect_swing_low,
        test_monotonic_no_swing,
        test_contract_shape_complete,
        test_health_states,
    ]
    failed = []
    for t in tests:
        try:
            await t()
        except AssertionError as e:
            failed.append((t.__name__, str(e)))
            print(f"FAILED: {t.__name__}: {e}")
        except Exception as e:
            failed.append((t.__name__, repr(e)))
            print(f"ERROR: {t.__name__}: {e!r}")
    print("\n" + "=" * 60)
    if failed:
        print(f"فشل {len(failed)} من أصل {len(tests)}")
        sys.exit(1)
    print(f"نجح كل الاختبارات ({len(tests)}/{len(tests)})")


if __name__ == "__main__":
    asyncio.run(main())
