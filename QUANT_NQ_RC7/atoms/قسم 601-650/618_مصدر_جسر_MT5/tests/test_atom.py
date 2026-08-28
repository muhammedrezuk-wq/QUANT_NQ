import asyncio
import os
import sqlite3
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.pop("NQ_BRIDGE_DB", None)  # اختبار محكم: لا يتأثّر بمتغيّر جسر الإنتاج NQ_BRIDGE_DB

from core.contracts.atom import AtomContext, HealthState  # noqa: E402
import importlib.util as _ilu  # noqa: E402
from pathlib import Path as _AtomPath  # noqa: E402

_spec = _ilu.spec_from_file_location(
    "_atom618", _AtomPath(__file__).resolve().parents[1] / "atom.py")
_mod = _ilu.module_from_spec(_spec)
sys.modules["_atom618"] = _mod
_spec.loader.exec_module(_mod)
Atom = _mod.Atom
EVENT_TICK = _mod.EVENT_TICK
EVENT_SPECS = _mod.EVENT_SPECS


class _NullLogger:
    def debug(self, *a): pass
    def info(self, *a): pass
    def warning(self, *a): pass
    def error(self, *a): pass
    def critical(self, *a): pass


class FakeEventBus:
    def __init__(self):
        self.published = []

    def subscribe(self, name, handler):
        pass

    async def publish(self, name, payload):
        self.published.append((name, payload))

    def make_context(self, db_path):
        cfg = {"db_path": db_path, "table_name": "ticks_v2", "spec_table": "symbol_specs_v2",
               "spec_refresh_s": 300, "poll_interval_s": 0.1, "batch_limit": 500,
               "delete_consumed": True}
        return AtomContext(atom_id=618, config=cfg, logger=_NullLogger(),
                           publish=self.publish, subscribe=self.subscribe)


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE ticks_v2 (id INTEGER PRIMARY KEY, account_id TEXT, symbol TEXT, bid REAL, ask REAL,"
                 " last REAL, volume REAL, tick_ms REAL)")
    conn.execute("CREATE TABLE symbol_specs_v2 (account_id TEXT, symbol TEXT, contract_size REAL, tick_value REAL, tick_size REAL)")
    conn.commit()
    conn.close()


def _add_tick(path, row_id, symbol="NQ", bid=100.0, ask=100.5, tick_ms=1700000000000.0):
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO ticks_v2 (id, account_id, symbol, bid, ask, tick_ms) VALUES (?, ?, ?, ?, ?, ?)",
                 (row_id, "A", symbol, bid, ask, tick_ms))
    conn.commit()
    conn.close()


def _pending_ticks(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT count(*) FROM ticks_v2").fetchone()[0]
    finally:
        conn.close()


async def test_publishes_feed_tick_from_bridge():
    print("\n--- test_publishes_feed_tick_from_bridge ---")
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "b.db")
        _make_db(db); _add_tick(db, 1)
        bus = FakeEventBus()
        atom = Atom()
        await atom.initialize(bus.make_context(db))
        await atom._drain_once()
        ticks = [p for n, p in bus.published if n == EVENT_TICK]
        assert len(ticks) == 1
        assert ticks[0]["symbol"] == "NQ" and ticks[0]["provider"] == "MT5"
        # البند ٧٨: ساعة الوسيط تُنشر باسمها، والانحراف مقيس، ولا ختم UTC كاذب
        assert ticks[0]["broker_timestamp"] == 1700000000.0, "ساعة الوسيط الخام"
        assert ticks[0]["broker_clock_offset_s"] is not None, "الانحراف يُقاس ويُعلَن"
        assert ticks[0]["exchange_timestamp"] is None, "ساعة لا توافق الاستلام لا تُقدَّم ختمًا"
        print(f"OK — نشر feed.mt5.tick محليًا من الجسر (بلا شبكة): {ticks[0]['symbol']}")


async def test_deletes_consumed_ticks():
    print("\n--- test_deletes_consumed_ticks ---")
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "b.db")
        _make_db(db); _add_tick(db, 1); _add_tick(db, 2)
        bus = FakeEventBus()
        atom = Atom()
        await atom.initialize(bus.make_context(db))
        await atom._drain_once()
        assert _pending_ticks(db) == 0, "الطابور يتنظّف بعد النشر"
        print("OK — حذف التكّات المقروءة (طابور مو مخزن)")


async def test_drops_incomplete_tick():
    """حالة فشل (قاعدة 9) — تكّة ناقصة تُسقَط بلا انهيار."""
    print("\n--- test_drops_incomplete_tick ---")
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "b.db")
        _make_db(db)
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO ticks_v2 (id, account_id, symbol, tick_ms) VALUES (1, 'A', 'NQ', 1700000000000.0)")  # لا bid/ask
        conn.commit(); conn.close()
        bus = FakeEventBus()
        atom = Atom()
        await atom.initialize(bus.make_context(db))
        await atom._drain_once()
        assert not [p for n, p in bus.published if n == EVENT_TICK]
        assert atom.dropped_count == 1
        print("OK — تكّة ناقصة أُسقطت بلا انهيار")


async def test_publishes_symbol_specs():
    print("\n--- test_publishes_symbol_specs ---")
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "b.db")
        _make_db(db)
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO symbol_specs_v2 VALUES ('A', 'NQ', 20.0, 0.5, 0.25)")
        conn.commit(); conn.close()
        bus = FakeEventBus()
        atom = Atom()
        await atom.initialize(bus.make_context(db))
        await atom._refresh_specs()
        specs = [p for n, p in bus.published if n == EVENT_SPECS]
        assert specs and specs[0]["symbols"][0]["contract_size"] == 20.0
        assert specs[0]["published_at"] and specs[0]["symbols"][0]["spec_observed_monotonic"] > 0
        print("OK — نشر مواصفات الرموز (contract_size)")


async def main():
    tests = [
        test_publishes_feed_tick_from_bridge,
        test_deletes_consumed_ticks,
        test_drops_incomplete_tick,
        test_publishes_symbol_specs,
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
