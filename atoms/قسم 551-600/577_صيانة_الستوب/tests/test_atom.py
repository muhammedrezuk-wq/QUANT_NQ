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
    "_atom577", _Path(__file__).resolve().parents[1] / "atom.py")
_mod = _ilu.module_from_spec(_spec)
sys.modules["_atom577"] = _mod
_spec.loader.exec_module(_mod)
Atom = _mod.Atom
EVENT_MANAGE = _mod.EVENT_MANAGE


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
        return AtomContext(atom_id=577, config=config, logger=_NullLogger(),
                           publish=self.publish, subscribe=self.subscribe)


async def _new():
    bus = FakeEventBus()
    atom = Atom()
    await atom.initialize(bus.make_context({}))
    await atom.start()
    return atom, bus


async def _positions(atom, legs, account="A1", symbol="XAUUSD"):
    rows = [{"account_id": account, "symbol": symbol, "ticket": t, "side": s} for t, s in legs]
    await atom._on_positions({"positions": rows})


async def _plan(atom, primary, stop_price, v_net, account="A1", symbol="XAUUSD"):
    await atom._on_plan({"plans": [{"account_id": account, "symbol": symbol,
                                    "primary_action": primary, "stop_price": stop_price,
                                    "v_net": v_net}]})


def _modifies(bus):
    return [p for n, p in bus.published if n == EVENT_MANAGE]


async def test_trail_lets_the_winner_run():
    """حكم المالك ٢٠٢٦-٠٩-٠٦: «آخر صفقة لازم تربح ٢٠٠ لا ٣٠٠، ربحانة ٣٥».

    المقيس الذي أثبت شكواه: الثماني الأخيرة أهدافها 78→142 نقطة (223$
    إلى 303$) ولا واحدة بلغت هدفها. والسبب رقمان في الزحف: بلا شرط ربح
    أدنى شُدّ الوقف إلى 1.47 نقطة من الدخول والسعر بعيد 9 فقط
    (1911362798 ⇒ −0.53$ بدل +303.08$)، ومجال التنفّس كان 7.71 أي
    بمقدار الضجيج المقيس نفسه (مئين ٨٠ = 7.54).
    """
    print("\n--- الزحف يترك الرابح يكمل ---")
    entry, stop = 80000.0, 79970.0           # شراء بمخاطرة ثلاثين نقطة
    original = entry - stop                  # 30.0
    atom, bus = await _new()
    atom._structure["XAUUSD"] = {"low": 79995.0, "high": 80100.0}
    pos = {"account_id": "A1", "symbol": "XAUUSD", "ticket": 7, "side": "BUY",
           "entry_price": entry, "current_price": entry + 9.0, "stop_loss": stop}

    # ربح ٩ نقاط على مخاطرة ٣٠ = 0.3R — دون العتبة، فلا يُمسّ الوقف.
    await atom._trail_structure(pos)
    assert not _modifies(bus), "زُحف الوقف قبل بلوغ الربح مخاطرته"

    # عند 1R بالضبط تُفتح البوّابة، لكن المرساة تحتاج مجال تنفّس كاملًا.
    pos["current_price"] = entry + original * _mod.TRAIL_MIN_PROFIT_R
    atom._structure["XAUUSD"] = {"low": entry + 5.0, "high": 80100.0}
    await atom._trail_structure(pos)
    assert not _modifies(bus), "زحف إلى مرساة داخل مجال التنفّس"

    # مرساة أبعد من مجال التنفّس (0.9 × 30 = 27) ⇒ تُقبل.
    pos["current_price"] = entry + 60.0
    atom._structure["XAUUSD"] = {"low": entry + 20.0, "high": 80200.0}
    await atom._trail_structure(pos)
    sent = _modifies(bus)
    assert len(sent) == 1, sent
    assert sent[0]["stop_loss"] == entry + 20.0, sent[0]
    print(f"  0.3R: لا زحف ✓ · 1R بمرساة لاصقة: لا زحف ✓ · "
          f"2R بمرساة على بعد 40: زحف إلى {sent[0]['stop_loss']} ✓")


async def test_maintain_sets_sl_on_net_side():
    print("\n--- test_maintain_sets_sl_on_net_side ---")
    atom, bus = await _new()
    await _positions(atom, [(1, "BUY"), (2, "SELL")])
    await _plan(atom, "MAINTAIN_STOP", 4300.0, 0.02)
    mods = _modifies(bus)
    assert len(mods) == 1 and mods[0]["ticket"] == 1
    assert mods[0]["action"] == "MODIFY_SL" and mods[0]["stop_loss"] == 4300.0
    print("OK — صافي شراء → MODIFY_SL على الرِجل BUY فقط (تذكرة 1)")


async def test_dedup_then_change():
    print("\n--- test_dedup_then_change ---")
    atom, bus = await _new()
    await _positions(atom, [(1, "BUY")])
    await _plan(atom, "MAINTAIN_STOP", 4300.0, 0.02)
    await _plan(atom, "MAINTAIN_STOP", 4300.0, 0.02)
    assert len(_modifies(bus)) == 1, "نفس السعر → لا تكرار"
    await _plan(atom, "MAINTAIN_STOP", 4310.0, 0.02)
    assert len(_modifies(bus)) == 2 and _modifies(bus)[-1]["stop_loss"] == 4310.0
    print("OK — dedup: يرسل فقط عند تغيّر P_stop")


async def test_net_short():
    print("\n--- test_net_short ---")
    atom, bus = await _new()
    await _positions(atom, [(1, "BUY"), (2, "SELL")])
    await _plan(atom, "MAINTAIN_STOP", 4400.0, -0.03)
    mods = _modifies(bus)
    assert len(mods) == 1 and mods[0]["ticket"] == 2
    print("OK — صافي بيع → MODIFY_SL على الرِجل SELL (تذكرة 2)")


async def test_no_maintain_no_send():
    print("\n--- test_no_maintain_no_send ---")
    atom, bus = await _new()
    await _positions(atom, [(1, "BUY")])
    await _plan(atom, "HEDGE", 4300.0, 0.02)
    await _plan(atom, "FREEZE", 4300.0, 0.02)
    assert len(_modifies(bus)) == 0
    print("OK — HEDGE/FREEZE → لا MODIFY_SL")


async def test_ticket_cleanup():
    print("\n--- test_ticket_cleanup ---")
    atom, bus = await _new()
    await _positions(atom, [(1, "BUY")])
    await _plan(atom, "MAINTAIN_STOP", 4300.0, 0.02)
    await _positions(atom, [])
    await _positions(atom, [(1, "BUY")])
    await _plan(atom, "MAINTAIN_STOP", 4300.0, 0.02)
    assert len(_modifies(bus)) == 2, "تذكرة عادت بعد اختفاء → يعيد الإرسال (نُظّف last_sl)"
    print("OK — تنظيف تذاكر مختفية")


async def test_flat_no_send():
    print("\n--- test_flat_no_send ---")
    atom, bus = await _new()
    await _positions(atom, [(1, "BUY"), (2, "SELL")])
    await _plan(atom, "MAINTAIN_STOP", 4300.0, 0.0)
    assert len(_modifies(bus)) == 0
    print("OK — V_net=0 → لا صيانة ستوب")


async def test_health():
    print("\n--- test_health ---")
    bus = FakeEventBus()
    atom = Atom()
    await atom.initialize(bus.make_context({}))
    assert (await atom.health_check()).state == HealthState.UNHEALTHY
    await atom.start()
    assert (await atom.health_check()).state == HealthState.DEGRADED
    await _positions(atom, [(1, "BUY")])
    await _plan(atom, "MAINTAIN_STOP", 4300.0, 0.02)
    assert (await atom.health_check()).state == HealthState.HEALTHY
    print("OK — الصحة: UNHEALTHY→DEGRADED→HEALTHY")


async def main():
    tests = [test_trail_lets_the_winner_run, test_maintain_sets_sl_on_net_side, test_dedup_then_change, test_net_short,
             test_no_maintain_no_send, test_ticket_cleanup, test_flat_no_send, test_health]
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
