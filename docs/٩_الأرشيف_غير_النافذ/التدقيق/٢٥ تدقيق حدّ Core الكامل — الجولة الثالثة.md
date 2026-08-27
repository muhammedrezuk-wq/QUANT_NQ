# تدقيق حدّ Core الكامل — الجولة الثالثة

**التاريخ:** 2026-08-27  
**النطاق:** من أول عملية تشغيل حتى `Bootloader.boot()`، ثم من `Bootloader` إلى أول دورة ذرة.  
**النوع:** Evidence-only / لا إصلاح ولا ترقيع.  
**المراجع:**

- `التدقيق/٢٣ مسار إقلاع النواة واستقلالها.md`
- `التدقيق/٢٤ تدقيق حدود إقلاع النواة — الجولة الثانية.md`

---

## 1. الحكم التنفيذي

```text
Core + atoms directory فارغ → Bootloader → RC=0
```

هذا مثبت بالتجربة، ولذلك:

```text
Core requires atoms to boot = مرفوض
```

لكن حدود التشغيل المحيطة بها ليست نظيفة بعد:

```text
Unified Release gates       = قبل تشغيل Core
Execution preflight         = داخل run_core قبل run()
Execution checker scope     = لا يطابق عمق شجرة الذرات
API domain controls         = معرفة Crypto داخل core/api
Release boot expectation    = 212 في check_boot مقابل 233 في verify_unified
Process supervision         = غير موجود بعد spawn
```

هذه Findings تخص الحدود والمشغلات والحوكمة، ولا تبرر تعديل أي ذرة أو جعلها `auto`.

---

## 2. المسار الموثق من أول تشغيل إلى Core

### 2.1 مسار زر/ملف التشغيل الموحّد

```text
أداة/زر Windows
    ↓
scripts/launch_unified.bat:3
    ↓
إنشاء venv إن لم توجد: scripts/launch_unified.bat:6-18
    ↓
تثبيت requirements: scripts/launch_unified.bat:20-25
    ↓
scripts/launch_unified.py:132
    ↓
main():72-129
    ↓
prepare():81
    ├─ prepare_unified.py:26-32
    └─ verify_unified.py:33-38
    ↓
spawn run_forex.py / run_crypto.py:86-107
    ↓
run_core.main():407-430
    ↓
execution preflight:415-417
    ↓
seal preflight:418-421
    ↓
asyncio.run(run()):422-424
    ↓
Bootloader.boot():94
```

### 2.2 المسار المباشر للنواة

```text
python governance/scripts/run_core.py
    ↓
run_core.main():407-430
    ↓
_verify_execution_safety_at_startup():415-417
    ↓
_verify_seal_at_startup():418-421
    ↓
asyncio.run(run()):422-424
    ↓
Bootloader.boot():94
```

المسار المباشر لا يمر بـ`prepare_unified` أو `verify_unified`، لكنه ما زال يمر بفحص execution قبل `run()`.

---

## 3. ما يحدث بعد الوصول إلى Bootloader

```text
run_core.run():38-43
    ↓
load_core_config
    ↓
create Registry / EventBus / Journal / Metrics / Health / Snapshot
    ↓
Bootloader(...):89-92
    ↓
Bootloader.boot():94
    ├─ subscribe generic time event: bootloader.py:94-96
    ├─ scan atoms_root: bootloader.py:98
    ├─ report scan failures: bootloader.py:99-100
    ├─ filter manual/lazy: bootloader.py:104-114
    ├─ resolve dependencies: bootloader.py:115, 170-226
    ├─ instantiate/register: bootloader.py:117-133
    ├─ initialize/start: bootloader.py:135-152
    └─ BootReport: bootloader.py:155-161
    ↓
HotReloadService: run_core.py:107-117
    ↓
optional API: run_core.py:121-132
```

### الحكم

- `manifest_loader.scan()` يعيد تقريرًا فارغًا إذا كان الجذر غير موجود: `core/manifest_loader.py:63-64`.
- لا يوجد في `Bootloader.boot()` مسار يجعل وجود ذرة شرطًا للرجوع؛ عند فراغ القائمة يبقى ترتيب الإقلاع فارغًا ويُعاد التقرير.
- `startup_mode` يُطبق بعد الاكتشاف داخل `bootloader.py:104-114`، لذلك هو قرار دورة حياة للذرة فقط.
- `HotReloadService` يبدأ بعد `Bootloader.boot()`، وليس قبله: `run_core.py:107-117`.

---

## 4. الأدلة المنفذة في الجولة

### 4.1 فحص صحة الملفات الموحّدة

```text
python scripts/verify_unified.py
```

النتيجة:

```text
Forex atoms: 233
Crypto atoms: 76
Crypto-specific atoms: 76
Shared links: 0
Core seal: OK
Unified release verification: OK
unified_verify_rc=0
```

هذا يثبت نجاح فحص الإصدار الموحّد وحده، ولا يثبت الإقلاع الكامل.

### 4.2 فحص `prepare --verify-only`

```text
python scripts/prepare_unified.py --verify-only
```

النتيجة:

```text
Unified-link preparation failed
```

والسبب المسجل هو أن روابط `forex_runtime/*` و`crypto_runtime/*` غير منشأة في checkout الحالي.

هذا ليس حكمًا بأن `prepare_unified.py` فشل عند الإنشاء؛ بل يثبت أن وضع `--verify-only` يفترض أن خطوة الإنشاء سبقتْه. لذلك لا يصنف كفشل Core Boot.

### 4.3 فحص التنفيذ المستقل

```text
python governance/checks/check_execution_safety.py
```

النتيجة:

```text
EXECUTION_SAFETY=BLOCKED
❌ ذرة 578 أو مانيفستها مفقود
```

لكن المسار المتكرر يجد:


```text
atoms/قسم 551-600/578_منفذ_التحوط
```

إذن يوجد تناقض مثبت بين شجرة المشروع ومسارات فحص execution.

### 4.4 فحص الإقلاع الفعلي

```text
python governance/checks/check_boot.py
```

النتيجة:

```text
بدأت فعليًا: 226
فشلت: لا شيء
استُبعدت: [107, 256, 257, 258, 625, 626, 630]
❌ الإقلاع لا يطابق البناء المطلوب 212
```

هذه ليست نتيجة تقول إن Core لم تقلع. بالعكس، التقرير وصل وبدأت 226 ذرة. هي نتيجة تقول إن فحص البناء نفسه لا يطابق الإصدار الحالي.

### 4.5 فحص Core بلا ذرات

النتيجة المسجلة من الجولة السابقة:

```text
Core empty atoms: RC=0
```

وتبقى هذه أقوى قرينة في هذا الملف على استقلال Core عن وجود atoms.

### 4.6 اختبارات Core

في البيئة الحالية:

- تحميل `tests/core` توقف عند غياب `fastapi` في اختبار WebSocket.
- عند استبعاد الاختبار، غاب `pytest-asyncio`، فأصبحت دوال `async` غير مدعومة وظهرت علامات `pytest.mark.asyncio` كمجهولة.

الحكم:

```text
نتيجة الاختبارات الحالية غير صالحة لتقدير عيوب Core قبل تجهيز بيئة dependencies.
```

---

## 5. فحص Boundary بين Core والوحدات الخارجية

### 5.1 Core التنفيذية لا تستورد Runner أو Governance

فحص الاستيرادات التنفيذية داخل `core/` أظهر imports من:

- مكتبات Python القياسية.
- `pydantic`.
- `yaml`.
- `jsonschema`.
- `packaging`.
- وحدات `core` نفسها.
- `fastapi` و`starlette` داخل `core/api/app.py`.

لم يظهر استيراد تنفيذي من:

```text
governance
transport
atoms
atoms_crypto
```

داخل وحدات `core` التنفيذية في هذا الفحص.

الحكم الجزئي:

```text
core/ → runner/governance/ direct import = لم يثبت
core/ → external atom code direct import = لم يثبت
```

لكن `governance/scripts/run_core.py` خارج `core/` يستورد `transport.owned_event_bus`، ويستورد governance checks من مسار preflight. لذلك لا يجوز مساواة نظافة `core/` بنظافة Runner.

### 5.2 Runner هو الذي يجمع الطبقات

`governance/scripts/run_core.py:23-35` يستورد ويجمع:

```text
Core services
+ transport.owned_event_bus
+ security initializer
+ governance execution checker
+ governance seal checker
```

هذا مقبول فقط إذا بقي واضحًا أنه Runner خارجي. المشكلة المثبتة هي أن فحص التنفيذ موضوع داخل `main()` قبل Core Boot، كما هو موثق في `F-CORE-002`.

---

## 6. Findings الجديدة في حدّ الإقلاع

### F-CORE-009 — Domain Control Allowlist Inside Core API

**الموضع:** `core/api/app.py:255-267`.

يوجد داخل طبقة Core API:

```python
allowed = {
    "crypto.universe.override.command",
    "crypto.universe.scan.requested",
}
```

كما تصف docstring المسار بأنه خاص بلوحة كريبتو موحّدة.

**الحكم:**

هذا لا يثبت اعتماد Core على ذرة بعينها، لكنه يثبت معرفة نطاقية بـ`crypto` داخل `core/api`. إذا كان مبدأ Core هو الجهل الكامل بنوع المشروع/السوق، فهذا خرق لحدود المعرفة حتى لو لم يذكر رقم 1001.

**التصنيف:** مثبت بنيويًا، ويحتاج قرار حدود معماري قبل أي إصلاح.

### F-CORE-010 — Release Gate Count Contradiction

**المواضع:**

- `governance/checks/check_boot.py:22`: `EXPECTED_ATOMS = 212`.
- `scripts/verify_unified.py:23-27`: يتوقع 233 فوركس و76 كريبتو.
- `config/unified_release.json:4-6`: يعلن 233 فوركس و76 كريبتو.

**النتيجة الفعلية:**

```text
verify_unified = OK على 233/76
check_boot     = FAIL على 226/212 مع 7 مستبعدة
```

**الحكم:**

يوجد عقدان متعارضان لعدد البناء. هذا لا يثبت فشل Core Boot، لكنه يثبت أن بوابات الإصدار لا تتفق على ما هو «بناء صحيح».

### F-CORE-011 — No Process Supervisor After Spawn

**المواضع:**

- `scripts/launch_unified.py:41-60`: إنشاء child عبر `subprocess.Popen`.
- `scripts/launch_unified.py:85`: حفظ المراجع في قائمة `processes`.
- `scripts/launch_unified.py:117-129`: انتظار المنافذ ثم رجوع الدالة.

بعد أن تصبح المنافذ جاهزة، لا توجد حلقة تنتظر الأطفال أو تفحص موتهم أو تعيد تشغيلهم. لا توجد ملفات خدمة/مشرف/Guardian/Task Scheduler ضمن شجرة التسليم حسب الفحص.

**الحكم:**

المشغل الحالي Launcher وليس Supervisor دائمًا. هذا يفسر لماذا لا يوجد تشغيل ذاتي أو تعافٍ على مستوى العمليات. لا علاقة له بقدرة Core على الإقلاع بصفر ذرات.

### F-CORE-012 — Execution Checker Hard-Codes Atom Layout

**المواضع:**

- `governance/checks/check_execution_safety.py:15-18`: مسارات ثابتة مباشرة لـ578 وملفات الجسر.
- `governance/checks/check_execution_safety.py:29-32`: رفض إذا لم يوجد 578 في ذلك المسار.
- البنية الفعلية: `atoms/قسم 551-600/578_منفذ_التحوط`.

**الحكم:**

حتى بعد فصل الفحص عن Core، الفحص نفسه لا يتبع قاعدة اكتشاف المانيفست المتكرر التي يتبعها `manifest_loader`. هذا سبب مستقل لنتيجة «578 مفقودة» الكاذبة.

### F-CORE-013 — API Default Path Not Covered by Zero-Atom Evidence

**المواضع:**

- `config/core.yaml:21-24`: API مفعّلة افتراضيًا.
- `run_core.py:121-132`: استدعاء `_start_api` عند التفعيل.
- `core/api/app.py:26`: تحميل FastAPI عند استيراد API.
- `pyproject.toml`: FastAPI/Uvicorn في optional extra اسمه `api`.

اختبار الصفر ذرات مرّ باستخدام `--no-api`. لذلك:

```text
Core no-atom internal boot = مثبت
Core no-atom default API boot in a bare package environment = غير مثبت
```

هذا Finding توزيع/بيئة، وليس اعتمادًا على atoms.

---

## 7. ما هو مثبت وما هو غير مثبت

| السؤال | النتيجة |
|---|---|
| هل Core تحتاج atoms كي تقلع؟ | لا؛ عكسه مثبت |
| هل `manual` يمنع Core Boot؟ | لا دليل؛ غير صحيح معماريًا |
| هل HotReload يسبق Bootloader؟ | لا؛ الكود يضعه بعده |
| هل `launch_unified` يضع بوابات قبل الأغلفة؟ | نعم؛ مثبت |
| هل `run_core` يضع execution preflight قبل Core؟ | نعم؛ مثبت |
| هل execution preflight يطابق عمق الشجرة؟ | لا؛ مثبت أنه يفوّت 578 الحالية |
| هل إصدار الإصدار وفحص الإقلاع يتفقان على العدد؟ | لا؛ 233 مقابل 212 |
| هل يوجد Supervisor دائم؟ | غير موجود في التسليم المفحوص |
| هل يوجد دليل أن API الافتراضية تعمل في بيئة ناقصة؟ | لا |
| هل كل فشل الاختبارات عيوب Core؟ | لا؛ البيئة ناقصة |

---

## 8. قرارات ممنوعة في هذه المرحلة

لا يتم قبل قرار Boundary صريح:

- جعل 74 كريبتو `auto`.
- جعل 578 `auto`.
- حذف execution safety.
- تعديل `CORE.lock`.
- تعديل `HotReloadService`.
- نقل الذرات أو إعادة ترقيمها.
- إنشاء Supervisor.
- تسجيل Windows Service.
- حذف النسخة القديمة.
- ربط حساب حقيقي.

---

## 9. الحالة النهائية للجولة

```text
F-CORE-003  Zero-atom Core boot                     PROVEN
F-CORE-001  Unified pre-core gates                  PROVEN
F-CORE-002  Execution preflight before Core         PROVEN
F-CORE-004  Non-recursive execution preflight       PROVEN
F-CORE-005  Full crypto auto-start disabled         PROVEN
F-CORE-006  Dual atom-root sources                  STRUCTURALLY PROVEN
F-CORE-007  Optional API dependency                 STRUCTURALLY PROVEN
F-CORE-008  Test environment not provisioned        PROVEN
F-CORE-009  Crypto domain allowlist in Core API     STRUCTURALLY PROVEN
F-CORE-010  Release count contradiction             PROVEN
F-CORE-011  No process supervisor after spawn        PROVEN
F-CORE-012  Hard-coded execution atom layout         PROVEN
F-CORE-013  Default API path not evidenced           PROVEN AS GAP
```

**الخلاصة:**

```text
Core Boot boundary itself: independent from atoms — proven.
Runner/Unified boundary: contains pre-Core gates — proven.
Execution preflight: both misplaced before Core and structurally stale — proven.
Release supervision: not present — proven.
No code was changed during this round.
```
