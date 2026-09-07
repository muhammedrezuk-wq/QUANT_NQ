# TASK 5 — إصلاح جميع الحالات الحرجة المتبقية
## Summary of All Critical Fixes (2026-08-27)

---

## Critical #1 ✅ — SyncEventBus async handlers never executed

**الذرة:** `backtest/sync_event_bus.py`

**المشكلة:**
عند إضافة handler من نوع `async def`، يُستدعى بدون `await`. النتيجة: coroutine يُنشأ ولا يُنفّذ، ويُبلع `RuntimeWarning` صامت.

**الحل:**
- اكتشاف `asyncio.iscoroutine(result)` بعد الاستدعاء
- تنفيذ عبر `_run_coro()` (يستخدم `asyncio.run` بأمان في thread منفصل)
- عدم بلع الأخطاء — `except Exception` يسجل الخطأ بدون `pass`

---

## Critical #2 ✅ — Decision bridge bypasses atom 552

**الملف:** `backtest/runner.py`

**المشكلة:**
`_make_context()` كان يبني `bus.publish` مباشرة يتجاوز البوابة 552. القرارات تُنفَّذ بدون فحص التنفيذ.

**الحل:**
- إزالة الـ decision bridge بالكامل
- الذرات 551 و 552 تُحمّل بشكل طبيعي عبر governance runner
- القرارات تمر عبر المسار الكامل

---

## Critical #3 ✅ — Backtest engine falls back to synthetic data silently

**الملفات:** `backtest/engine.py`, `backtest/models.py`

**المشكلة:**
عند فشل تحميل البيانات من الملف أو WebSocket، المحرك ينتقل صامتاً إلى `generate_synthetic_data()` — بيانات وهمية بلا علامة `source=synthetic`.

**الحل:**
- `_load_data()` الآن:
  1. يحاول الملف إذا `data_file` محدد
  2. يحاول WebSocket
  3. `generate_synthetic_data()` فقط إذا `allow_synthetic=True`
  4. يرمي `RuntimeError` إذا لا شيء متاح
- `BacktestConfig` جديد: `data_file`, `allow_synthetic`
- `BacktestResult` جديد: `data_source` field
- Synthetic data يحمل `source=synthetic` ولا يصل Product Gate

---

## Critical #4 ✅ — Trade counter never allows second trade

**الملف:** `backtest/engine.py`

**المشكلة:**
`self._trade_counter` يزيد مع كل صفقة ولا ينقص. بعد `max_open_trades` صفقات، المحرك يرفض الكل حتى لو لا صفقات مفتوحة.

**الحل:**
- استبدال `self._trade_counter >= self.config.max_open_trades` بـ:
  ```python
  open_count = 1 if self._open_trade is not None else 0
  if open_count >= self.config.max_open_trades:
      return
  ```
- التحقق من الصفقات المفتوحة فعلياً بدلاً من العدّاد التراكمي

---

## Critical #5 ✅ — Daily loss limit fails open on storage error

**الذرة:** `atoms/قسم 501-550/516_قاطع_الأمان/atom.py` (sealed)

**المشكلة:**
1. `_on_loss()` كان `return` مبكراً عند `_storage_error` — لا حساب خسارة
2. `_reject_reason()` لم يتحقق من `_storage_error` — يرفض فقط إذا kill=True في الذاكرة

**النتيجة:** فقدان journal = قاطع معطّل = أوامر تُنفَّذ بدون فحص حد الخسارة.

**الحل:**
1. `_reject_reason()` — أول سطر:
   ```python
   if self._storage_error: return "RISK_LEDGER_UNAVAILABLE"
   ```
   → fail-closed: كل الأوامر مرفوضة عند خطأ تخزين

2. `_on_loss()` — إزالة `return` المبكر:
   - يحسب الخسارة في الذاكرة دائماً
   - فشل التخزين → `kill=True` + `reason="RISK_LEDGER_UNAVAILABLE"`
   - لا journal → نفس السلوك fail-closed

---

## Finding 06 ✅ — Windows stop button doesn't write snapshots

**الملفات:** `scripts/stop_all.py`, `scripts/launch_market.py`, `governance/scripts/run_core.py`

**المشكلة:**
- `stop_all.py`: `terminate()` على Windows يقتل فوراً بدون `CTRL_BREAK_EVENT`
- `launch_market.py`: الأبناء يرثون Ctrl+C من الأب
- `run_core.py`: snapshot واحد فقط عند البدء

**الحل:**
- `stop_all.py`: `CTRL_BREAK_EVENT` قبل `terminate()` (Windows فقط)
- `launch_market.py`: `CREATE_NEW_PROCESS_GROUP` (Windows فقط)
- `run_core.py`: periodic snapshot كل 60 ثانية

---

## Verification

| # | الحالة | Status |
|---|--------|--------|
| 1 | SyncEventBus async handlers | ✅ Fixed |
| 2 | Decision bridge bypass | ✅ Fixed |
| 3 | Synthetic fallback | ✅ Fixed |
| 4 | Trade counter | ✅ Fixed |
| 5 | Daily loss fail-open | ✅ Fixed |
| 6 | Windows stop snapshots | ✅ Fixed |

All syntax verified ✅
