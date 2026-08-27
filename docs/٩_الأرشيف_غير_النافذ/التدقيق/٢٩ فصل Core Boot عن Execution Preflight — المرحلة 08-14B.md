# فصل Core Boot عن Execution Preflight — المرحلة 08 → 14B

**التاريخ:** 2026-08-27  
**الحالة:** تنفيذ إضافي لمعالجة `F-CORE-002` فقط.  
**النطاق:** فصل مرحلتي الإقلاع دون تغيير أي Atom أو `startup_mode` أو منطق تداول.

---

## 1. التغيير المعماري

أصبح المسار:

```text
Core services
    ↓
Bootloader — auto atoms غير التنفيذية
    ↓
Core Boot reached
    ↓
Execution Safety عبر Registry
    ↓
Bootloader — execution targets فقط
```

وليس:

```text
Execution Safety
    ↓
Core Boot
```

### التنفيذ

- `core/bootloader.py`: أضيف `boot(include_ids=...)` عام، لا يحتوي مفردات تنفيذ أو Domain.
- `core/bootloader.py`: يمنع إعادة اشتراك ساعة Core عند المرحلتين.
- `governance/scripts/run_core.py`: يحسب مجموعتي auto والتنفيذ من Build Registry.
- تُحسب closure للاعتماديات العكسية حتى لا تبدأ ذرة تعتمد على مكوّن مؤجل.
- إذا فشل Safety بعد Core Boot، تبقى Core والطبقة غير التنفيذية عاملة، ولا تبدأ execution.
- تقارير المرحلتين تُدمج في تقرير نهائي واحد.

تم تحديث الإصدار المعماري وختم Core:

```text
Core version: 1.26.0
Core seal: PASS
```

---

## 2. أدلة التشغيل

### الفوركس

```text
مرحلة Core/Atom غير التنفيذية = PASS
Execution Safety بعد Core Boot = PASS
مرحلة execution = PASS
التقرير النهائي = PASS
CORE_PHASE_RC=0
```

الأعداد في هذه الجولة ناتجة من Registry؛ لا يوجد شرط `212`.

### الكريبتو

```text
Core/Atom phase = PASS
لا أهداف execution auto في نطاق crypto = معلن
التقرير النهائي = PASS
CRYPTO_PHASE_RC=0
```

بقيت ذرّات Crypto المصدر الكامل `manual` كما هي.

### فحص الإقلاع

```text
Registry auto set: 226
Actually started: 226
Failed: 0
Excluded: 7 manual
BOOT_RC=0
```

`check_boot.py` ينتظر التقرير النهائي المدمج، لا تقرير المرحلة الأولى فقط.

### نطاق Safety

```text
لا ذرات تنفيذ: التخطّي معلن = PASS
مع ذرات تنفيذ: Safety يعمل بعد Core = PASS
مع ذرة معطوبة: يرفض execution، ولا يسقط Core = PASS
SCOPE_RC=0
```

---

## 3. نتيجة `F-CORE-002`

```text
Execution preflight before Core Boot = removed
Execution Safety after Core Boot = proven
```

الحالة:

```text
F-CORE-002 = RESOLVED FOR RUNNER LIFECYCLE
```

فحص سلامة التنفيذ بقي موجودًا ولم يُحذف؛ تغيّر موضعه فقط.

---

## 4. الاختبارات

```text
Boundary + Registry + Boot phase + Core seal tests: 50 passed
Python compile: PASS
Core seal verification: PASS
```

التحذير الوحيد بيئي:

```text
Unknown config option: asyncio_mode
```

لأن بيئة التدقيق الحالية لا تحتوي إعداد pytest-asyncio الكامل.

---

## 5. بوابة الإصدار الحالية

```text
verify_unified:
  Build contract = CONFLICT
  Release = BLOCKED
  RC = 1
```

هذا الرفض صحيح ولا يختار Build من نفسه.

```text
check_files:
  manifests = 309
  missing explanations = 32
  RC = 1
```

لا تُنشأ الشروحات ضمن هذه الجولة.

---

## 6. ما لم يتغير

```text
atoms/
atoms_crypto/
startup_mode
Trading logic
Decision logic
Execution logic
```

ولا تم:

```text
اختيار 212
اختيار 233/76 كـBuild ID
إنشاء Supervisor
تسجيل Windows Service
بدء HotReload migration
ربط حساب حقيقي
```

---

## 7. الحالة

```text
Gate 01 → 07 = PASS
Gate 08 → 10 = PASS
F-CORE-002 = RESOLVED
Gate 11 → 14 = PASS وظيفيًا، لكن Release BLOCKED تعاقديًا
Gate 15 = STOP
```

### المتبقي قبل فتح HotReload

```text
قرار رسمي لـBuild Contract
قرار رسمي: هل الشروحات شرط Release أم فحص توثيق مستقل؟
تدقيق/ترحيل بقية Governance checkers ذات المسارات القديمة
تجهيز dependencies ثم Full test suite
```

**لا يجوز فتح Gate 15 قبل حسم أول بندين على الأقل.**
