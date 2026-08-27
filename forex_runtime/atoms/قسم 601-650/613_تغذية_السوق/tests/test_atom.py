import asyncio
import inspect
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
from pathlib import Path as _AtomPath  # noqa: E402

_spec = _ilu.spec_from_file_location(
    "_atom613", _AtomPath(__file__).resolve().parents[1] / "atom.py")
_mod = _ilu.module_from_spec(_spec)
sys.modules["_atom613"] = _mod
_spec.loader.exec_module(_mod)
Atom = _mod.Atom
TICK = _mod.EVENT_MARKET_TICK
VOLUME = _mod.EVENT_MARKET_VOLUME

CFG = {
    "routes": {"feed.mt5.tick": "market.tick"},
    "provider_timeout_s": 30,
    "max_input_silence_seconds": 60,
}


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
        for handler in self._handlers.get(name, []):
            result = handler(payload)
            if inspect.isawaitable(result):
                await result

    def make_context(self, config):
        return AtomContext(atom_id=613, config=config, logger=_NullLogger(),
                           publish=self.publish, subscribe=self.subscribe)


async def _ready(bus):
    atom = Atom()
    await atom.initialize(bus.make_context(CFG))
    await atom.start()
    return atom


async def test_routes_source_tick_to_market_tick():
    print("\n--- test_routes_source_tick_to_market_tick ---")
    bus = FakeEventBus()
    await _ready(bus)
    await bus.publish("feed.mt5.tick",
                      {"provider": "MT5", "symbol": "NQ", "bid": 100.0, "ask": 100.5, "timestamp": 1000.0})
    ticks = [p for n, p in bus.published if n == TICK]
    assert len(ticks) == 1
    assert ticks[0]["symbol"] == "NQ" and ticks[0]["provider"] == "MT5"
    assert ticks[0]["timestamp"] == 1000.0, "وقت السوق من المصدر (قاعدة 13)"
    print(f"OK — وجّه feed.mt5.tick → market.tick: {ticks[0]['symbol']}")


async def test_propagates_account_id_identity_key():
    """قاعدة 22 — يمرّر account_id لو المصدر حطّه."""
    print("\n--- test_propagates_account_id_identity_key ---")
    bus = FakeEventBus()
    await _ready(bus)
    await bus.publish("feed.mt5.tick",
                      {"provider": "MT5", "symbol": "NQ", "bid": 1, "ask": 2, "timestamp": 5.0, "account_id": "ACC-1"})
    tick = [p for n, p in bus.published if n == TICK][-1]
    assert tick["account_id"] == "ACC-1", "لازم يمرّر account_id (قاعدة 22)"
    print("OK — مرّر account_id=ACC-1")


async def test_incomplete_payload_dropped_without_crash():
    """حالة فشل (قاعدة 9) — تكّة ناقصة تُسقَط بلا انهيار ولا نشر."""
    print("\n--- test_incomplete_payload_dropped_without_crash ---")
    bus = FakeEventBus()
    atom = await _ready(bus)
    await bus.publish("feed.mt5.tick", {"provider": "MT5", "symbol": "NQ", "timestamp": 1.0})  # لا bid/ask
    assert not [p for n, p in bus.published if n == TICK], "ما ينشر عند نقص"
    assert atom._dropped == 1
    print("OK — تكّة ناقصة أُسقطت (dropped=1) بلا انهيار")


async def test_preferred_provider_failover():
    """الدستور §20-21: المرجع (CTRADER) يقود التحليل؛ MT5 احتياط عند صمته فقط."""
    print("\n--- test_preferred_provider_failover ---")
    bus = FakeEventBus()
    atom = Atom()
    cfg = {"routes": {"feed.mt5.tick": "market.tick", "feed.ctrader.tick": "market.tick"},
           "provider_timeout_s": 30, "max_input_silence_seconds": 60,
           "preferred_provider": "CTRADER"}
    await atom.initialize(bus.make_context(cfg))
    await atom.start()
    await bus.publish("kernel.clock.heartbeat", {"official_time": 100.0})
    # قبل أول تكّة مرجعية: MT5 يمرّ (لا هواء ميت)
    await bus.publish("feed.mt5.tick",
                      {"provider": "MT5", "symbol": "NQ", "bid": 1, "ask": 2, "timestamp": 100.0})
    assert len([p for n, p in bus.published if n == TICK]) == 1
    # المرجع وصل: تكّته تمرّ وتكّة MT5 التالية تنكتم
    await bus.publish("feed.ctrader.tick",
                      {"provider": "CTRADER", "symbol": "NQ", "bid": 1.1, "ask": 2.1, "timestamp": 101.0})
    await bus.publish("feed.mt5.tick",
                      {"provider": "MT5", "symbol": "NQ", "bid": 1.2, "ask": 2.2, "timestamp": 102.0})
    ticks = [p for n, p in bus.published if n == TICK]
    assert len(ticks) == 2 and ticks[-1]["provider"] == "CTRADER"
    assert atom._suppressed_secondary == 1
    # المرجع صمت فوق المهلة: MT5 يرجع يتدفّق
    await bus.publish("kernel.clock.heartbeat", {"official_time": 200.0})
    await bus.publish("feed.mt5.tick",
                      {"provider": "MT5", "symbol": "NQ", "bid": 1.3, "ask": 2.3, "timestamp": 200.0})
    ticks = [p for n, p in bus.published if n == TICK]
    assert len(ticks) == 3 and ticks[-1]["provider"] == "MT5"
    print("OK — أفضلية المرجع مع تحويل تلقائي عند صمته")


async def test_health_check_surfaces_single_dead_provider():
    """عطل حي مقيس 2026-08-19: health_check() كانت تراقب ساعة صمت واحدة
    مشتركة (self._last_input_at) بلا تمييز مصدر — MT5 ممكن يموت كلياً
    وcTrader يبقى حيّ، فتستمر الحالة العليا 'سليمة' بلا أي إشارة، رغم أن
    العلم down لكل مصدر محسوب فعلاً بـ_on_heartbeat ولم يكن يُقرأ هون."""
    print("\n--- test_health_check_surfaces_single_dead_provider ---")
    bus = FakeEventBus()
    atom = Atom()
    cfg = {"routes": {"feed.mt5.tick": "market.tick", "feed.ctrader.tick": "market.tick"},
           "provider_timeout_s": 30, "max_input_silence_seconds": 60,
           "preferred_provider": "CTRADER"}
    await atom.initialize(bus.make_context(cfg))
    await atom.start()
    await bus.publish("kernel.clock.heartbeat", {"official_time": 100.0})
    await bus.publish("feed.mt5.tick",
                      {"provider": "MT5", "symbol": "NQ", "bid": 1, "ask": 2, "timestamp": 100.0})
    await bus.publish("feed.ctrader.tick",
                      {"provider": "CTRADER", "symbol": "NQ", "bid": 1.1, "ask": 2.1, "timestamp": 100.0})
    healthy = await atom.health_check()
    assert healthy.state == HealthState.HEALTHY
    # MT5 يصمت فوق provider_timeout_s بينما cTrader يستمر يتدفّق بلا انقطاع.
    for t in range(101, 140):
        await bus.publish("kernel.clock.heartbeat", {"official_time": float(t)})
        await bus.publish("feed.ctrader.tick",
                          {"provider": "CTRADER", "symbol": "NQ", "bid": 1.1, "ask": 2.1, "timestamp": float(t)})
    status = await atom.health_check()
    assert status.state == HealthState.DEGRADED, (
        f"MT5 صامت 39 ثانية رغم أن cTrader حيّ تماماً — يجب أن تُبلَّغ متعثّرة لا سليمة، "
        f"الحالة الفعلية: {status.state} / {status.message}"
    )
    assert "MT5" in status.message, f"الرسالة يجب أن تسمّي المصدر الميت صراحة: {status.message}"
    print(f"OK — health_check سمّت المصدر الميت: {status.message}")


async def test_volume_published_when_present():
    print("\n--- test_volume_published_when_present ---")
    bus = FakeEventBus()
    await _ready(bus)
    await bus.publish("feed.mt5.tick",
                      {"provider": "MT5", "symbol": "ES", "bid": 1, "ask": 2, "timestamp": 3.0, "volume": 500})
    vols = [p for n, p in bus.published if n == VOLUME]
    assert len(vols) == 1 and vols[0]["volume"] == 500
    print("OK — نشر market.volume عند وجود حجم")


async def main():
    tests = [
        test_routes_source_tick_to_market_tick,
        test_propagates_account_id_identity_key,
        test_incomplete_payload_dropped_without_crash,
        test_preferred_provider_failover,
        test_health_check_surfaces_single_dead_provider,
        test_volume_published_when_present,
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
