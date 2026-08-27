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
    "_atom576", _Path(__file__).resolve().parents[1] / "atom.py")
_mod = _ilu.module_from_spec(_spec)
sys.modules["_atom576"] = _mod
_spec.loader.exec_module(_mod)
Atom = _mod.Atom
EVENT_REQUEST = _mod.EVENT_REQUEST
EVENT_STATE = _mod.EVENT_STATE
EVENT_REJECTED = _mod.EVENT_REJECTED


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
        return AtomContext(atom_id=576, config=config, logger=_NullLogger(),
                           publish=self.publish, subscribe=self.subscribe)


async def _new(config=None):
    bus = FakeEventBus()
    atom = Atom()
    await atom.initialize(bus.make_context(config if config is not None else {}))
    await atom.start()
    return atom, bus


async def _setup(atom, symbol="XAUUSD", tv=1.0, ts=1.0, price=100.0, stop_frac=0.05, account="A1"):
    await atom._on_account({"account_id": account, "broker": "BR"})
    await atom._on_specs({"account_id": account, "broker": "BR", "symbols": [{"account_id": account, "symbol": symbol, "contract_size": 100.0,
                                       "tick_value": tv, "tick_size": ts}]})
    await atom._on_candle({"account_id": account, "broker": "BR", "symbol": symbol, "close": price, "timeframe": "60s"})
    await atom._on_dial({"profiles": [{"account_id": account, "broker": "BR", "symbol": symbol,
                                       "stop_distance_frac": stop_frac}]})


def _activate(**extra):
    """بند ب٥ (ق٩ §١٥-١٦): أمر التفعيل الحي يصل من 901 حاملًا command_id
    (معرّف أمر المالك الموثق) — الاختبارات تحاكي الشكل الحقيقي نفسه."""
    body = {"account_id": "A1", "broker": "BR", "symbol": "XAUUSD", "budget": 50.0,
            "command_id": 7, "origin": "901", "reason": "OWNER_COMMAND"}
    body.update(extra)
    return body


def _decisions(bus):
    return [p for n, p in bus.published if n == EVENT_REQUEST]


def _states(bus):
    return [p for n, p in bus.published if n == EVENT_STATE]


def _rejections(bus):
    return [p for n, p in bus.published if n == EVENT_REJECTED]


async def test_entry_opens_two_hedged_legs():
    print("\n--- test_entry_opens_two_hedged_legs ---")
    atom, bus = await _new()
    await _setup(atom, stop_frac=0.05)  # stop_distance=5, vpu=1 → lot=50/5=10
    await atom._on_activate(_activate())
    dec = _decisions(bus)
    assert len(dec) == 2, len(dec)
    buy = [d for d in dec if d["side"] == "BUY"][0]
    sell = [d for d in dec if d["side"] == "SELL"][0]
    assert buy["volume"] == 10.0 and sell["volume"] == 10.0
    assert buy["stop_loss"] is None and buy["account_id"] == "A1" and buy["symbol"] == "XAUUSD"
    assert buy["request_id"] != sell["request_id"]
    # ب٥: كل أمر يحمل أصله الأب الصريح — معرف أمر المالك من 901
    assert buy["owner_command_id"] == "7" and sell["owner_command_id"] == "7"
    opened = _states(bus)[-1]
    assert opened["status"] == "OPENED" and opened["owner_command_id"] == "7"
    print("OK — تفعيل بأمر مالك → صفقتان (BUY+SELL) وكل أمر يحمل owner_command_id")


async def test_no_parent_authority_rejected():
    """قبول ق٩ (٤/أ): تفعيل بلا أصل (لا قرار أب ولا أمر مالك) → مرفوض صراحة."""
    print("\n--- test_no_parent_authority_rejected ---")
    atom, bus = await _new()
    await _setup(atom)
    await atom._on_activate({"account_id": "A1", "broker": "BR", "symbol": "XAUUSD",
                             "budget": 50.0})
    assert len(_decisions(bus)) == 0, "order without parent authority escaped"
    rej = _rejections(bus)
    assert len(rej) == 1 and rej[0]["reason"] == "NO_PARENT_AUTHORITY", rej
    assert rej[0]["status"] == "REJECTED" and rej[0]["symbol"] == "XAUUSD"
    h = await atom.health_check()
    assert h.details["rejected_no_authority"] == 1, h.details
    # ولا زناد شمعة لاحق: لا معلق محفوظ يفتح عند اكتمال المدخلات
    await atom._on_candle({"account_id": "A1", "broker": "BR", "symbol": "XAUUSD",
                           "close": 100.0, "timeframe": "60s"})
    assert len(_decisions(bus)) == 0
    print("OK — بلا أصل أب → NO_PARENT_AUTHORITY وعداد صحة، ولا دخول بشمعة لاحقة")


async def test_parent_decision_origin_passes():
    """قبول ق٩ (٤/ب): أصل قرار معتمد مرّ بالبوابة يمر ويُختم على الأوامر.

    الوحدة 1 (3.3.1): النسب وحده لا يكفي — يلزم أن تكون بوابة 467 قد نشرت
    decision.gate.passed لهذا القرار فعلًا. نغذي البوابة أولًا ثم نفعّل."""
    print("\n--- test_parent_decision_origin_passes ---")
    atom, bus = await _new()
    await _setup(atom)
    await atom._on_gate_passed({"decision_id": "dec-9", "gate_request_id": "dec-9:req1"})
    await atom._on_activate({"account_id": "A1", "broker": "BR", "symbol": "XAUUSD",
                             "budget": 50.0, "parent_decision_id": "dec-9"})
    dec = _decisions(bus)
    assert len(dec) == 2, len(dec)
    assert all(d["parent_decision_id"] == "dec-9" for d in dec), dec
    assert not _rejections(bus)
    # والقرار الذي لم يعبر البوابة يُرفض صراحة بعدّاد ظاهر — لا نشر بأي حال.
    atom2, bus2 = await _new()
    await _setup(atom2, symbol="XAUUSD")
    await atom2._on_activate({"account_id": "A1", "broker": "BR", "symbol": "XAUUSD",
                              "budget": 50.0, "parent_decision_id": "dec-forged"})
    assert len(_decisions(bus2)) == 0, "forged parent decision opened a pair"
    rej2 = _rejections(bus2)
    assert len(rej2) == 1 and rej2[0]["reason"] == "DECISION_NOT_IN_GATE_WINDOW", rej2
    h2 = await atom2.health_check()
    assert h2.details["rejected_unverified_decision"] == 1, h2.details
    print("OK — النافذ عبر البوابة يمر ويُختم، والملفّق يُرفض بDECISION_NOT_IN_GATE_WINDOW")


async def test_stale_pending_without_authority_rejected_on_retry():
    """معلق قديم (ما قبل ب٥) بلا أصل: الشمعة لا تفتح — يُرفض ويُمسح."""
    print("\n--- test_stale_pending_without_authority_rejected_on_retry ---")
    atom, bus = await _new()
    atom._pending["A1|BR|XAUUSD"] = {"account_id": "A1", "broker": "BR",
                                     "symbol": "XAUUSD", "budget": 50.0}
    await _setup(atom)  # candle arrives → retry path
    assert len(_decisions(bus)) == 0
    assert len(_rejections(bus)) == 1 and _rejections(bus)[0]["reason"] == "NO_PARENT_AUTHORITY"
    assert "A1|BR|XAUUSD" not in atom._pending
    print("OK — الحارس الثاني عند التنفيذ: معلق بلا أصل يُرفض ويُنسى")


async def test_inverse_lot_via_dial():
    print("\n--- test_inverse_lot_via_dial ---")
    atom, bus = await _new()
    await _setup(atom, stop_frac=0.05)
    await atom._on_activate(_activate())
    wide = _decisions(bus)[0]["volume"]
    await atom._on_deactivate({"account_id": "A1", "broker": "BR", "symbol": "XAUUSD"})
    await atom._on_dial({"profiles": [{"account_id": "A1", "broker": "BR", "symbol": "XAUUSD",
                                       "stop_distance_frac": 0.025}]})
    await atom._on_activate(_activate(command_id=8))
    tight = _decisions(bus)[-1]["volume"]
    assert tight > wide and tight == 20.0 and wide == 10.0
    print("OK — عيار أضيق (stop_frac 0.025) → لوت أكبر 20 (عكسيّ تلقائيّ)")


async def test_idempotent():
    print("\n--- test_idempotent ---")
    atom, bus = await _new()
    await _setup(atom)
    await atom._on_activate(_activate())
    await atom._on_activate(_activate(command_id=8))
    assert len(_decisions(bus)) == 2, "لا فتح مكرّر"
    assert _states(bus)[-1]["status"] == "ALREADY_ACTIVE"
    print("OK — تفعيل مكرّر → لا فتح مكرّر (ALREADY_ACTIVE)")


async def test_deactivate_reopen():
    print("\n--- test_deactivate_reopen ---")
    atom, bus = await _new()
    await _setup(atom)
    await atom._on_activate(_activate())
    await atom._on_deactivate({"account_id": "A1", "broker": "BR", "symbol": "XAUUSD"})
    await atom._on_activate(_activate(command_id=8))
    assert len(_decisions(bus)) == 4
    print("OK — deactivate ثمّ تفعيل → يفتح جديد")


async def test_missing_inputs():
    print("\n--- test_missing_inputs ---")
    atom, bus = await _new()
    await atom._on_activate(_activate())
    assert len(_decisions(bus)) == 0
    assert _states(bus)[-1]["status"] == "MISSING_INPUTS"
    print("OK — بلا سعر/مواصفات → MISSING_INPUTS (صادق، ما يرسل)")


async def test_budget_from_ledger():
    print("\n--- test_budget_from_ledger ---")
    atom, bus = await _new()
    await _setup(atom, stop_frac=0.05)
    await atom._on_ledger({"ledgers": [{"account_id": "A1", "broker": "BR", "symbol": "XAUUSD", "budget": 50.0}]})
    await atom._on_activate(_activate(budget=None))
    assert len(_decisions(bus)) == 2 and _decisions(bus)[0]["volume"] == 10.0
    print("OK — بلا ميزانيّة بالأمر → يأخذها من دفتر 518")


async def test_lot_clamped_to_max():
    print("\n--- test_lot_clamped_to_max ---")
    atom, bus = await _new({"max_lot": 5.0})
    await _setup(atom, stop_frac=0.05)  # would be 10 → clamped to 5
    await atom._on_activate(_activate())
    assert _decisions(bus)[0]["volume"] == 5.0
    print("OK — اللوت محصور بالسقف max_lot")


async def test_survives_restart():
    """انقطاع كهربا أو إعادة تشغيل لا يُلغي تفعيل الأصل."""
    print("\n--- test_survives_restart ---")
    before, bus1 = await _new()
    await _setup(before)
    await before._on_activate(_activate())
    assert len(_decisions(bus1)) == 2, "الزوج المحايد فُتح"
    saved = await before.snapshot()
    # عقد اللقطة 2026-08-16: الجسم صار داخل payload ومختومًا بـdigest
    assert "A1|BR|XAUUSD" in saved["payload"]["active"], "التفعيل يُحفظ"

    # ذرّة جديدة تمامًا — كأنّ الجهاز أُطفئ ثمّ عاد
    after, bus2 = await _new()
    await after.restore(saved)
    await _setup(after)
    await after._on_activate(_activate())
    assert len(_decisions(bus2)) == 0, "لا يُعاد فتح زوج جديد بعد الرجوع"
    assert _states(bus2)[-1]["status"] == "ALREADY_ACTIVE", "الأصل يعود مفعّلًا بلا طقس"
    print("OK — التفعيل ينجو من إعادة التشغيل (ALREADY_ACTIVE بلا فتح جديد)")


async def test_restore_ignores_garbage():
    print("\n--- test_restore_ignores_garbage ---")
    atom, _ = await _new()
    await atom.restore({"active": ["بلا فاصل", 7, None], "budget": {"A1|X": "نص"},
                        "pending": "مو قاموس", "counter": "س"})
    assert not atom._active and not atom._budget and not atom._pending
    await atom.restore(None)
    print("OK — استرجاع فاسد يُتجاهل بلا انهيار")


async def test_health():
    print("\n--- test_health ---")
    bus = FakeEventBus()
    atom = Atom()
    await atom.initialize(bus.make_context({}))
    assert (await atom.health_check()).state == HealthState.UNHEALTHY
    await atom.start()
    assert (await atom.health_check()).state == HealthState.HEALTHY
    print("OK — الصحة: UNHEALTHY→HEALTHY")


async def main():
    tests = [test_entry_opens_two_hedged_legs, test_no_parent_authority_rejected,
             test_parent_decision_origin_passes,
             test_stale_pending_without_authority_rejected_on_retry,
             test_inverse_lot_via_dial, test_idempotent,
             test_deactivate_reopen, test_missing_inputs, test_budget_from_ledger,
             test_lot_clamped_to_max, test_survives_restart,
             test_restore_ignores_garbage, test_health]
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
