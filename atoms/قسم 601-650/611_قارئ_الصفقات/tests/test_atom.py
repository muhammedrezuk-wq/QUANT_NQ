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
    "_atom611", _AtomPath(__file__).resolve().parents[1] / "atom.py")
_mod = _ilu.module_from_spec(_spec)
sys.modules["_atom611"] = _mod
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

    def subscribe(self, name, handler):
        pass

    async def publish(self, name, payload):
        self.published.append((name, payload))

    def make_context(self, db_path):
        cfg = {"db_path": db_path, "table_name": "trade_events_v2", "poll_interval_s": 1.0, "batch_limit": 100}
        return AtomContext(atom_id=611, config=cfg, logger=_NullLogger(),
                           publish=self.publish, subscribe=self.subscribe)


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE trade_events_v2 (id INTEGER PRIMARY KEY, event_type TEXT, ticket INTEGER,"
                 " symbol TEXT, side TEXT, volume REAL, entry_price REAL, exit_price REAL,"
                 " open_time REAL, close_time REAL, reason TEXT, account_id TEXT)")
    conn.commit()
    conn.close()


def _add(path, row_id, account="ACC-1"):
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO trade_events_v2 (id, event_type, ticket, symbol, close_time, account_id)"
                 " VALUES (?, 'CLOSED', ?, 'NQ', ?, ?)", (row_id, 5000 + row_id, 100.0 + row_id, account))
    conn.commit()
    conn.close()


async def test_publishes_each_row_with_account_id():
    print("\n--- test_publishes_each_row_with_account_id ---")
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "b.db")
        _make_db(db); _add(db, 1); _add(db, 2)
        bus = FakeEventBus()
        atom = Atom()
        await atom.initialize(bus.make_context(db))
        await atom._drain_once()
        events = [p for n, p in bus.published if n == EVENT_OUT]
        assert len(events) == 2
        assert events[0]["account_id"] == "ACC-1" and events[0]["ticket"] == 5001
        print(f"OK — نشر {len(events)} حدث صفقة مع account_id")


async def test_cursor_does_not_republish():
    print("\n--- test_cursor_does_not_republish ---")
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "b.db")
        _make_db(db); _add(db, 1)
        bus = FakeEventBus()
        atom = Atom()
        await atom.initialize(bus.make_context(db))
        await atom._drain_once()
        await atom._drain_once()  # no new rows
        assert len([p for n, p in bus.published if n == EVENT_OUT]) == 1, "ما يعيد نشر القديم"
        _add(db, 2)
        await atom._drain_once()
        assert len([p for n, p in bus.published if n == EVENT_OUT]) == 2, "ينشر الجديد فقط"
        print("OK — المؤشّر ما يعيد نشر القديم، ينشر الجديد بس")


async def test_snapshot_restore_preserves_cursor():
    print("\n--- test_snapshot_restore_preserves_cursor ---")
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "b.db")
        _make_db(db); _add(db, 1); _add(db, 2)
        bus = FakeEventBus()
        atom = Atom()
        await atom.initialize(bus.make_context(db))
        await atom._drain_once()
        snap = await atom.snapshot()
        # new instance restores cursor -> must not republish 1,2
        bus2 = FakeEventBus()
        atom2 = Atom()
        await atom2.initialize(bus2.make_context(db))
        await atom2.restore(snap)
        await atom2._drain_once()
        assert not [p for n, p in bus2.published if n == EVENT_OUT], "المؤشّر المحفوظ يمنع إعادة التاريخ"
        print("OK — snapshot حفظ المؤشّر: ما أعاد نشر التاريخ")


async def test_unreadable_bridge_degraded():
    """حالة فشل (قاعدة 9)."""
    print("\n--- test_unreadable_bridge_degraded ---")
    bus = FakeEventBus()
    atom = Atom()
    await atom.initialize(bus.make_context(os.path.join("Z:\\", "no_such.db")))
    atom._running = True
    await atom._drain_once()
    h = await atom.health_check()
    assert h.state == HealthState.DEGRADED
    print("OK — جسر غير مقروء: DEGRADED بلا انهيار")


async def main():
    tests = [
        test_publishes_each_row_with_account_id,
        test_cursor_does_not_republish,
        test_snapshot_restore_preserves_cursor,
        test_unreadable_bridge_degraded,
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
