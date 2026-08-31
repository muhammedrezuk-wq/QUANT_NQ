# ١٨-A · التصميم المستهدف — Event Ownership Architecture
**الحالة:** `TARGET DESIGN` — مقترح، **غير معتمد للتنفيذ** · لا تعديل منطق تداول · لا ذرات جديدة
**التاريخ:** ٢٦-٠٨-٢٠٢٦ · **المرجع:** ورقة ١٨ §٠-ح · **يليها:** `١٨-B` تنفيذية **بعد ختم الاعتماد فقط**

> **القرار الجذري: لا نوزّع النسخ. نوزّع الملكية.**

المسار الحالي:
```text
TICK → Central Bus → COPY × Subscribers → Queues → Analysis
```
يُستبدل بـ:
```text
TICK
 ↓ INGEST
 ↓ NORMALIZE ONCE
 ↓ ROUTE BY OWNERSHIP
┌──────────┬──────────┬──────────┬──────────┐
│ Worker 0 │ Worker 1 │ Worker 2 │ Worker N │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┘
     ↓          ↓          ↓          ↓
 owned state owned state owned state owned state
     ↓          ↓          ↓          ↓
 analysis    analysis    analysis    analysis
     └──────────┴──────────┴──────────┘
                    ↓
             RESULT / CONTROL
                    ↓
              COLD OUTPUT
```

**القاعدة الأساسية:** كل `ACCOUNT × SYMBOL` له **Owner واحد في لحظة معينة**. الـWorker المالك هو الوحيد الذي يعدّل `mutable state`. أما التكة الداخلة فهي `immutable / read-only payload` تُمرَّر **كمرجع، لا تُنسخ لكل مستهلك**.

---

## ٢ · ماذا نزيل من Hot Path؟

نزيل جذريًا:
```text
pickle per subscriber · _fast_copy المتكرر · isolated_copy
نسخ last_event غير الضرورية · نسخ إعادة التسليم · Central fan-out
Central subscriber execution
```
والـUUID لا يُولَّد لكل مرحلة داخلية؛ هوية الحدث تُنشأ **مرة واحدة عند دخوله النظام** إن لزمت للتتبع.

## ٣ · الملكية

`Ownership Registry` وظيفته فقط: `ACCOUNT × SYMBOL → WORKER`.
```text
A×NQ → W0 · A×ES → W1 · B×NQ → W2 · B×ES → W2 · C×GC → W3
```
**لا نعتمد عدد العمال النهائي الآن** (`1 · 2 · 4 · 6`) — الاختبار يحدّد الأفضل.

## ٤ · أهم نقطة: ترتيب الأحداث

لنفس `ACCOUNT × SYMBOL` لا يُسمح `Tick 101 → W1 · Tick 102 → W2` إن كان ترتيب الحالة مهمًا. بل:
```text
A×NQ → Owner Worker 2 → 101 → 102 → 103 → 104
```
> **Parallelism بين وحدات الملكية، لا داخل سلسلة الحالة نفسها.**

وهذا يحافظ على semantics الموجودة بدل تغيير منطق التداول.

## ٥ · ماذا يصبح مركزيًا؟

يبقى مركزيًا فقط ما يحتاج مركزًا فعلًا: `INGESTION · OWNERSHIP MAP · SYSTEM CONTROL · HEALTH · WORKER SUPERVISION · FINAL CONTROL/OUTPUT`. لكن ممنوع أن يصبح `Central Control` مكانَ تنفيذ التحليل:
```text
CONTROL ≠ COMPUTE
```

## ٦ · الـBus الجديد

بدل `Central Bus → copy → copy → copy`:
```text
Router → Owner Queue → Owner Worker
```
الحمولة `one immutable payload`، والـqueue تحتوي **references** لا نسخ payload كامل.

## ٧ · حالة العامل

كل Worker يملك state وحداته (`Account×Symbol …`)، ولا يوجد `Shared Mutable Analysis State` بين العمال في Hot Path — كي لا نستبدل `Central Serialization` بـ`Global Lock Serialization`.

## ٨ · الأقفال

الأقفال الحالية (`parameter_registry._lock · live_analysis._schema_lock · metrics._lock …`) لا تُنقل ببساطة للعمال. في التصميم:
- **Hot Path:** `Lock-free where possible` أو `Worker-local state`.
- **Shared state (إن لزم):** `read-only · snapshot · atomic/safe publication`.

الهدف: **لا Global Lock يوقف جميع العمال.**

## ٩ · العيارات

القياس حسم: `approved_value = 0.6%` — ليست مشكلة الآن. لكن في التصميم:
```text
Configuration → immutable/read-mostly snapshot → Workers
```
بدل قراءة Registry مشتركة لكل عملية، إن أثبت القياس ضرورته.

## ١٠ · Persistence

التخزين `12%` كبير، فلا يدخل `TICK → DB → wait → Analysis`. بل:
```text
HOT: Tick → Analysis → Decision → Result
وبالتوازي: Result ─→ { Persistence · Logging · Dashboard · Historical }
```
`HOT ≠ COLD`.

## ١١ · Dashboard

لا يشارك في Fan-out التكة. بدل `Tick → Dashboard subscriber → JSON`:
```text
Worker Result → Telemetry Snapshot → Dashboard  (بمعدل مناسب)
```
اللوحة لا تملك حق تعطيل التحليل.

## ١٢ · الفشل

```text
Worker 2 FAILED → isolate → restart/recover → restore owned state
```
ولا يحدث `Worker FAILED → CORE FAILED → SYSTEM FAILED`. أحد معايير اعتماد التصميم.

## ١٣ · Backpressure

لكل Worker حدود واضحة (`queue depth · processing rate · overload state`). عند `input > processing` **لا نرمي بصمت**، بل حالة معلنة: `NORMAL · DEGRADED · OVERLOAD · RECOVERY · FAILED`. وسياسة كل نوع event تُحسم في ورقة التنفيذ، لا في ١٨-A.

## ١٤ · استغلال الـ6 Cores

لا `6 Cores = 6 Workers`. نختبر `1 · 2 · 4 · 6` ونقيس `CPU/core · throughput · p99 · queue depth · RAM · worker imbalance`. النتيجة قد تكون `4 Compute + 1 I/O + 1 Control` أو `6 Compute` أو غيره. **القياس يحكم.**

## ١٥ · نقطة مهمة جدًا: Python / GIL

إذا بقي الحساب الثقيل داخل `Python threads` فلن نحصل تلقائيًا على توازي CPU حقيقي. لذلك ١٨-A **لا تقول «استخدم Threads»**، بل: **استخدم Parallel Execution حقيقي حيث يستحق.** وطريقة التنفيذ (`processes · native execution · multiprocessing · optimized libraries · threads for I/O`) تُحسم في ١٨-B حسب طبيعة الحمل الفعلية.

## ١٦ · الشكل النهائي

```text
                         MARKET
                           ▼
                    ┌─────────────┐
                    │  INGESTION  │
                    └──────┬──────┘
                    normalize once
                           ▼
                    ┌─────────────┐
                    │   ROUTER    │
                    └──────┬──────┘
                    ownership lookup
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
     ┌─────────┐      ┌─────────┐      ┌─────────┐
     │ Worker 0│      │ Worker 1│ ...  │ Worker N│
     ├─────────┤      ├─────────┤      ├─────────┤
     │ A×NQ    │      │ A×ES    │      │ B×NQ    │
     │ C×GC    │      │ B×ES    │      │ C×NQ    │
     └────┬────┘      └────┬────┘      └────┬────┘
          ▼                ▼                ▼
       ANALYSIS         ANALYSIS         ANALYSIS
          └────────────────┼────────────────┘
                           ▼
                    RESULT / CONTROL
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          Dashboard   Persistence    Telemetry
              └──────── COLD PATH ─────┘
```

## الحكم

| المشكلة الحالية | التصميم الجديد |
|---|---|
| Copy لكل Subscriber | Payload واحد |
| Central Fan-out | Ownership Routing |
| Central Compute | Worker-local Compute |
| Shared mutable state | Owned state |
| Central serialization | Partition serialization |
| Dashboard داخل المسار | Cold/Telemetry path |
| Persistence داخل الحمل | Cold path |
| Threads عشوائيًا | Workers حسب القياس |
| فشل عامل = خطر النظام | Local failure |

والأهم:
> **ما عم نحاول نخلي الـpickle أسرع. عم نلغي الحاجة إليه في Hot Path.**

هذا التصميم يستحق الانتقال من `OPEN STUDY` إلى `TARGET ARCHITECTURE`. **لكنه غير معتمد للتنفيذ بكلام المصمّم — الاعتماد الرسمي يظل للمالك.** بعد ختم الاعتماد فقط، تُكتب `١٨-B` تنفيذية ناشفة: الملفات · الملكية · الـqueues · شكل الـpayload · lifecycle العامل · نقل الـstate · إزالة الـcopy · الـprocess/thread model · الفشل والاسترداد · اختبارات 100→2000.
