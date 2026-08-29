# ترحيل Governance إلى Registry — قبل HotReload

**التاريخ:** 2026-08-27  
**الحالة:** ترحيل مسارات الاكتشاف فقط؛ لا HotReload.  
**قاعدة الجولة:** لا تعديل Core أو Atom أو Manifest أو `startup_mode`.

---

## 1. ما تغير

أضيفت واجهة توافق خارج Core:

```text
build_registry/paths.py
```

`RegistryAtomRoot` يحافظ على الصيغة القديمة في أدوات الحوكمة، لكنه يحل:

```text
ATOMS / "578_منفذ_التحوط"
```

عبر:

```text
BuildRegistry → atom_id → path الفعلي مهما كان العمق
```

كما يدعم:

```text
iterdir
rglob
glob
```

مع نتائج مبنية على الاكتشاف المتكرر، لا على تخمين القسم.

تم ترحيل طبقة مسارات أدوات Governance والـproofs إلى الواجهة المركزية، بما فيها المسارات التي كانت تستخدم:

```text
ROOT / "atoms" / ...
ATOMS / A...
ATOMS.glob("578_*")
```

ما عدا استخدام `ROOT / "atoms"` داخل fixture لإنشاء شجرة اختبار مؤقتة؛ هذا ليس lookup لشجرة التشغيل.

---

## 2. الإثبات

```text
578_منفذ_التحوط
→ /atoms/قسم 551-600/578_منفذ_التحوط
```

```text
552_مدقق_الأمر
→ /atoms/قسم 551-600/552_مدقق_الأمر
```

```text
584_شرعية_الستوب
→ /atoms/قسم 551-600/584_شرعية_الستوب
```

```text
708_سجل_الرموز
→ /atoms/قسم 701-750/708_سجل_الرموز
```

```text
516_قاطع_الأمان
→ /atoms/قسم 501-550/516_قاطع_الأمان
```

لم يعد عمق القسم يؤثر على lookup.

---

## 3. نتائج الفحوص

```text
Python compile لجميع Governance checks/scripts = PASS
Core seal = PASS
Core unchanged منذ الختم الأخير = PASS
Registry + Boundary + Boot tests = 50 passed
```

فحوص رئيسية:

```text
check_execution_safety = PASS
check_execution_state_truth = PASS
check_hedge_contract = PASS
check_safety_gate_scope = PASS
check_versions = PASS
```

توجد فحوص أخرى تعيد فشلًا بسبب عقود منطقية قديمة أو حالات تشغيلية معلنة، وليس بسبب عدم العثور على مسار Atom. هذه الجولة لا تصلح منطق التداول أو عقود الذرات.

---

## 4. ما لم يُعتبر نجاحًا

```text
Full Governance suite = ليس PASS كاملًا
check_files = FAIL بسبب الشروحات الناقصة
check_events = FAIL بسبب أحداث بلا ناشر
validate_atoms = FAIL بسبب مخالفات الذرات الموجودة مسبقًا
```

هذه ليست أعطالًا عالجتها الجولة، ولا يتم تحويلها إلى ترقيع Atom.

---

## 5. Build Contract

ما زال:

```text
BUILD_CONTRACT = CONFLICT
BUILD_ID = null
Release = BLOCKED
```

المصادر لم تُحسم:

```text
QUANT_NQ_FULL_212
QUANT_NQ_COMPLETE_FULL
```

لا اختيار تلقائي.

---

## 6. check_files Contract

النتيجة الحالية:

```text
manifests المكتشفة = 309
الشروحات الناقصة = 32
```

لم تُنشأ أي شروحات، لأن القرار لم يُحسم بعد:

```text
شرط Release
أم
فحص توثيق مستقل غير حاجب
```

---

## 7. Core وAtoms

```text
core/ = لم يُعدّل في هذه الجولة
atoms/ = لم يُعدّل
atoms_crypto/ = لم يُعدّل
startup_mode = لم يُعدّل
Trading/Decision/Execution logic = لم يُعدّل
HotReload = لم يُعدّل
```

---

## 8. الحالة

```text
Governance path migration = منفذ
Registry lookup = منفذ
Hard-coded Atom path lookup = أزيل من طبقة الترحيل
Functional Governance contracts = بعضها ما زال FAIL ويحتاج جولات منطق مستقلة
Build Contract = غير محسوم
check_files Contract = غير محسوم
Full dependencies = غير مكتملة
HotReload Gate = مغلقة
```

**توقفت هنا. لا فتح لـGate 15 قبل قرار Build وقرار check_files وتجهيز dependencies للاختبار الكامل.**
