# قياس: الحاجز ٣٦ · منفذ `/gov/parameters` · زرّ «حفظ»

**التاريخ:** 2026-09-03 · **على:** `9e4f254` (مطابق لـ `origin/master`) · **المنفِّذ:** قياس آليّ على الكود، لا قراءة ورق

> القاعدة فوق كل شيء: الحقيقة في `atom.py`. ما يلي كلّه مخرَج أوامر فعلية.

---

## ١) خريطة المسارات — الجذر الحقيقي لكل الأعراض

| المكوِّن | الملفّ الذي يقرأه فعليًا | يوجد؟ |
|---|---|---|
| محرّك القرار — `shared/parameter_registry.py:109-112` | `var/store/analysis_settings.db` (افتراضي) أو `QUANT_ANALYSIS_SETTINGS_DB` | ✅ موجود |
| محرّك القرار عند إقلاع الزرّ الرسميّ (`scripts/run_forex.py:21`) | `var/forex/analysis_settings.db` | ✅ موجود |
| **اللوحة** — `governance/server.py:60` `ANALYSIS_SETTINGS_DB = DATA_ROOT / "analysis_settings.db"`، `DATA_ROOT = ROOT.parent/forex_runtime/var` | `forex_runtime/var/analysis_settings.db` | ❌ **لا يوجد أبدًا** |

قِيس في الحالتين الحقيقيّتين للإقلاع (`measure_real.py`):

```
── ١) غرفة القيادة.bat → governance/app.py → governance/scripts/run_core.py (بلا متغيّر بيئة)
   قاعدة المحرّك (ParameterRegistry): .../QUANT_NQ/var/store/analysis_settings.db        [موجودة]
   قاعدة اللوحة  (ANALYSIS_SETTINGS_DB): .../QUANT_NQ/forex_runtime/var/analysis_settings.db [لا توجد]
   بعد declare(): صفوف المحرّك=36 | الحاجز يرى=36
   /gov/parameters → available=False | عدد=0 | بطاقات اعتماد تُبنى=0
   نفس الملف؟ False

── ٢) أزرار التشغيل/تشغيل الفوركس الموحد.bat → launch_market.py → run_forex.py
   قاعدة المحرّك: .../QUANT_NQ/var/forex/analysis_settings.db                            [موجودة]
   قاعدة اللوحة : .../QUANT_NQ/forex_runtime/var/analysis_settings.db                     [لا توجد]
   /gov/parameters → available=False | عدد=0 | بطاقات اعتماد تُبنى=0
```

**لا يوجد إقلاع يُوَفِّق المسارَين.** `parameters_rows()` (`server.py:1744`) لا يقرأ
`QUANT_ANALYSIS_SETTINGS_DB` إطلاقًا — المسار محفور من `DATA_ROOT`. قِيس أنّ ضبط
المتغيّر على قاعدة المحرّك الموجودة **لا يغيّر شيئًا**: `available=False · عدد=0`.

⇒ فرضيّة «`DATA_ROOT` اختلف بعد آخر إقلاع» ليست السبب: **الخادم لا يشتقّ المسار من
المتغيّر أصلًا**، فيبقى فارقًا ثابتًا بين ملفّين لا متغيّرًا في الجلسة.

---

## ٢) المنفذان في نفس الخادم يقرآن ملفّين مختلفين (انقسام دماخ)

| المنفذ | مصدر القراءة | النتيجة |
|---|---|---|
| `/gov/decision/dials` (`server.py:2196`) | `from shared.decision_dials import declare` → `ParameterRegistry()` = **قاعدة المحرّك**، ثمّ **يكتب فيها** `INSERT OR IGNORE` لثلاثين صفًا | يعرض الثلاثين «غير معتمد — قيمة المانيفست» ✓ |
| `/gov/parameters` (`server.py:2216 → 1744`) | `ANALYSIS_SETTINGS_DB` = **`forex_runtime/var/…`** | `available=False · عدد=0` |

⇒ **زيارة تبويب الإعدادات تُنشئ صفوف العيارات في قاعدة المحرّك**، أي تُنقل البوابة من
«٦ صفوف كلها معلّقة» إلى «٣٦ صفا كلها معلّقة». البوابة تُغلَق أكثر بمجرّد فتح اللوحة.

---

## ٣) تصحيحان على ما قِيل

### أ. «زرّ حفظ يغيّر القيمة، مش بيعتمد» — **غير صحيح**
`Settings.tsx:204` يبعت `decision_setting`، لكن الطريق ينتهي باعتماد كامل:

```
901 atom.py:78   ACTION_DECISION_SETTINGS → "decision.settings.command"
453 atom.py:117  applied = apply_command(payload, atom_id="453")
decision_dials.py:317  row = registry.approve(name, value=value, source=SOURCE_OWNER,
                                               approved_by=operator, ...)
```

قِيس مباشرة (`measure_gate36.py`، السيناريو ٥):
```
apply_command(«حفظ») أعاد: {'name':'DECISION_CONTEXT_WEIGHT','value':0.42,'version':2,'scope':'global'}
بعد الحفظ: {'status':'APPROVED','source':'OWNER','version':2}
```
فالزرّ يغيّر القيمة **ويعتمد الصّفّ** — «ضبط عيار» و«اعتماد مالك» فعلٌ واحد بالكود.
هذه ثغرة حوكمة مستقلة عن كل ما سبق: `parameter_registry.approve()` يرفض
`source=UNSET` بلا هوية، ولا يرفضه هنا لأن الأمر يمرّ باسم المشغّل.

### ب. «اعتماد الستّة لا يفتح البوابة» — **شرطيّ، وليس مطلقًا**

| حالة القاعدة | `الحاجز` | `state` | `weight_effect` |
|---|---|---|---|
| ٦ صفوف، ٠ اعتماد (قبل `declare()`) | 6 | NOT_READY | 0.00 |
| **٦ صفوف، الستّة معتمدة** | **0** | **READY** | **40.00** ← فتحت |
| ٣٦ صفا، الستّة معتمدة (بعد `declare()`) | 30 | NOT_READY | 0.00 |
| ٣٦ صفا، عيار واحد فقط معتمد | 35 | NOT_READY | 0.00 |
| ٣٦ صفا، الكل معتمد | 0 | READY | 40.00 |

قِيس في `probe_gate.py` (صفوف `declare()` لم تُنشأ بعد) مقابل `measure_final.py`
(٣٦ صفا). **عدد ما يراه الحاجز يتوقّف على عمر القاعدة، لا على الإعدادات.**

### ج. ما قيل عني
«**بكودك**»: الكود ليس لي — هو `muhammedrezuk-wq/QUANT_NQ` عند `9e4f254`، وأنا قِستُه
فقط. ولم أُصلح شيئًا في المستودع: **رقعة `_flush_news` ما زالت غير مطبَّقة**، فلا توجد
«حالة بعد الرقعة» تُعرض. الأرقام الثلاثة (1131/11، `5edb4df2…` مقابل `b74a9efd…`،
ذرّة ٥٨٢) باقية كما هي، وقد أُعيد التأكيد عليها في هذه الجولة.

---

## ٤) الأزرار — موجودة، ثلاثة منها، واثنتان تختفيان

| العنصر | الموضع | السلوك |
|---|---|---|
| زرّ **«حفظ»** على `DialRow` | `Settings.tsx:236` | `confirmedCommand('decision_setting', …)` — للعيارات الثلاثين + يعتمد الصّفّ (انظر ٣أ) |
| حقل رقمي + زرّ **«اعتماد»** على `ParameterRow` | `Settings.tsx:580` | `confirmedCommand('parameter_approve', …)` — للستّة |
| بطاقة **«المُعامِلات المعلنة»** | `Settings.tsx:608` `DeclaredParametersCard` | تُفلتر `filter(p => p.approvable)` على مخرَج `/gov/parameters` |

لأن `parameters_rows()` يرجع صففرًا، `params = []` فتُطبع البطاقة هكذا:
```
«سجلّ المُعامِلات غير متاح بعد — يتكوّن مع أول تشغيل للنواة»   ← السطر 623
«ما وصل أي مُعامِل معلن — سجلّ المُعامِلات فاضي.»                ← السطر 645
```
**زرّ «اعتماد» موجود بالكود، ولا يُعرض** — لا لأنه مدفون، بل لأن مصدر بياناته ملفّ لا
يكتبه أحد. وفوق ذلك: لا يوجد أيّ مسار اعتماد للعيارات الثلاثين من `/gov/parameters`
بوصفه اعتمادًا (`approvable = name in DECLARED`، `server.py:1758`)؛ اعتمادها الجانبيّ
يمرّ من زرّ «حفظ» وحده.

---

## ٥) الإصلاح المقترح (لم يُطبَّق شيء بعد)

1. **توحيد مصدر الحقيقة** — `governance/server.py:60`:
   ```python
   ANALYSIS_SETTINGS_DB = (Path(os.environ["QUANT_ANALYSIS_SETTINGS_DB"])
                           if os.environ.get("QUANT_ANALYSIS_SETTINGS_DB")
                           else DATA_ROOT / "analysis_settings.db")
   ```
   والأصحّ: أن يُشتقّ من `shared.parameter_registry.ParameterRegistry().path` بدل تكرار
   المنطق — وإلّا بقي مصدران يتباعدان (نمط «حدّ واحد لا ثلاثة تتباعد»، §٥٢).
2. **فصل «ضبط قيمة» عن «اعتماد مالك»** — `decision_dials.apply_command` يجب ألّا
   يستدعي `registry.approve(source=SOURCE_OWNER)`؛ وإلّا بقي زرّ «حفظ» يفتح البوابة.
3. **فحص حوكمة يمسك الانقسام** — `governance/checks/check_parameters_endpoint.py`
   يمرّ اليوم (`rc=0`) لأنّه يبني قاعدته المؤقّتة بيده ولا يختبر مسار الإنتاج. فحص
   «مسار المنفذ = مسار المحرّك» كان سيقبض هذا من أول بناء.
4. **ورقة في `١٤_الأعطال_المعروفة/فوركس/`** تسمّي الملفّات الثلاثة قبل أن يُعاد
   تشخيصها مرّة رابعة.

### تصحيحات علىّ أنا (الجولة السابقة)
- قلتُ «الحاجز بيفحص ٦ معاملات» — ناقص: `unapproved()` يستعرد الجدول كلّه
  (`shared/parameter_registry.py:154-158`: `status != 'APPROVED'`)، فالـ٣٦ رقم صحيح،
  و«٦» كان ما ترونه القاعدة قبل `declare()`.
- لم أُنبّه أنّ الحاجر **لا يفتح** بمجرّد اعتماد الستّة بعد أن تُنشأ صفوف العيارات.

---

## ٦) الملحق — بعد قياس المالك على النسخة الحيّة (2026-09-03)

**صحّ من التقرير:** انقسام المسارين · `forex_runtime` مجلّد مستقلّ لا رابط · «حفظ` بيعتمد` · الحاجز يستعرض الجدول كلّه (٣٦).

**صحّ من قياس المالك:** الأرشيف لا يحوي اعتمادًا (0 صفوف في `parameters_audit` بالنسختين) — فالفرضيّة الأولى ساقطة · الانقسام أوسع من المعاملات (١٦ اسمًا على `DATA_ROOT`).

**تصحيحان:**

1. **التقرير حصر الانقسام بمنفذ واحد** — الحقيقة أن `DATA_ROOT` يبني ١٦ اسمًا (`server.py:57-369,688,861,869,1159,1164,2126,2299`).
2. **لكنّ «٤ قواعد مكسورة بنفس السبب» تتوقّف على الزرّ المُقْلِع**:
   - `أزرار التشغيل/تشغيل الفوركس الموحد.bat → launch_market.py → scripts/run_forex.py:17` فيه `os.chdir(ROOT/"forex_runtime")` ⇒ `Path.cwd()` (ذرّة ٩٠١، `atom.py:183`) = `forex_runtime/` ⇒ `var\…` النسبي **يقع تحت `forex_runtime/var/`** = مسار اللوحة ✓
   - `غرفة القيادة.bat:32 → governance/app.py → governance/scripts/run_core.py` **بلا chdir** (`_spawn` بـ`cwd=ROOT`) ⇒ `Path.cwd()` = الجذر ⇒ كل المسارات النسبية خارج `DATA_ROOT` ✗
   - `ANALYSIS_SETTINGS_DB` **مكسور في الحالتين**: `run_forex.py:21` يضبط `QUANT_ANALYSIS_SETTINGS_DB = var/forex/analysis_settings.db` (خارج الـruntime) بينما `run_crypto.py:24` بختم NQ 2026‑09‑01 يضعه داخله؛ و`server.py:60` محفور على `DATA_ROOT/analysis_settings.db` (بلا `store/`) ولا يقرأ متغيّر البيئة. قاعدة المالك المقاسة `QUANT_NQ\var\store\analysis_settings.db` = فرع «غرفة القيادة» بالضبط.
3. **الإصلاح ليس سطرًا بـ`server.py:56`** — `governance/checks/check_crypto_isolation.py:100-106` يفحص عمدًا أن `forex_runtime/var ≠ crypto_runtime/var` («فخّ الوصلات»)، و`server.py:393-397` يوثّق نموّ اللقطة 7.72 GB/5د من جعل `var` رابطًا للجذر. توحيدهما يعيد العطل المختوم.
   **الإصلاح سطرين:** (أ) `ANALYSIS_SETTINGS_DB = ParameterRegistry().path` في `server.py:60` — يلغي ازدواج `var/` و`var/store/` ويلغي تجاهل متغيّر البيئة؛ (ب) حذف/تصحيح `run_forex.py:21` ليطابق ختم الكريبتو (تحت `forex_runtime/var/`).
4. **نمط «مفتاح بلا سلك» رابع (بجانب البند ٤٧):** `QUANT_ATOMS_ROOT` مضبوط في `run_forex.py:19`/`run_crypto.py:21` ولا مستهلِك له في المستودع (grep = 6 مواضع، كلها `setdefault`)؛ الجذر الحقيقي من `run_core.py:51` = `PROJECT_ROOT / core_config["atoms_root"]`. ازدواج الأساس (cwd مقابل PROJECT_ROOT) هو جذر العرض كله.

**لم يُطبَّق أي تعديل** — `git diff` فارغ، ولا ختم NQ بعد.

---

# الملحق ٧ — فحص جذر المسارات (ممنوع أي تعديل؛ لا شيء عُدِّل)

**طريقة القياس:** لا نتيجة مبنية على اسم مجلّد. كل مسار أدناه هو `resolve()`/`Path.cwd()`
الحقيقي لسطر كود مُعيّن، قِيس في وضعَي الإقلاع الفعليّين بـ`/home/user/audit_paths_live.py`.

## A) خريطة المسارات الفعلية (المُخرَج المطلق وقت التشغيل)

`R = جذر المستودع`. اللوحة = `governance/server.py` (الجذر؛ النسخة داخل الـmirror مطابقة بايت-ببايت).

| المورد | سطر تعريف اللوحة | اللوحة تقرأ/تكتب | المحرّك/الذرّة يقرأ/يكتب | mode ① (غرفة القيادة) | mode ② (زرّ الفوركس) |
|---|---|---|---|---|---|
| commands.db | `server.py:59` | `R/forex_runtime/var/governance/commands.db` | `atoms/…901/atom.py:183` `Path.cwd()/raw` | `R/var/governance/…` **✗** | `R/forex_runtime/var/governance/…` **✓** |
| market_data.db | `:58` | `…/forex_runtime/var/store/market_data.db` | 701/714/716/717 + 625/630 عبر `cwd` | `R/var/store/…` **✗** | `R/forex_runtime/var/store/…` **✓** |
| decisions.db | `:62` | `…/forex_runtime/var/store/decisions.db` | `atoms/…707/manifest.yaml:43` عبر `cwd` | `R/var/store/…` **✗** | **✓** |
| logs | `:82` | `…/forex_runtime/var/logs` | `atoms/…719 · 720` عبر `cwd` | `R/var/logs` **✗** | **✓** |
| backups | `:369` | `…/forex_runtime/var/backups` | **اللوحة هي الكاتبة الوحيدة** (`make_backup:443`) | `R/var/backups` | `R/forex_runtime/var/backups` |
| tilt_rules.db | `:61` | `…/forex_runtime/var/store/tilt_rules.db` | `atoms/…580/atom.py:233-234` **`Path(__file__).parents[2]`** | `R/atoms/var/store/tilt_rules.db` **✗✗** | `R/atoms/var/store/…` **✗✗** |
| analysis_settings.db | `:60` | `…/forex_runtime/var/analysis_settings.db` | `shared/parameter_registry.py:110-112` `__file__/parent.parent` = `R/var/store/…`؛ و`scripts/run_forex.py:21` يفرض `QUANT_ANALYSIS_SETTINGS_DB = R/var/forex/analysis_settings.db` | `R/var/store/…` **✗** | `R/var/forex/…` **✗** |

**النتيجة:** لا يوجد وضع إقلاع واحد تُطبَق فيه الصفّ السبعة. في الوضع الرسميّ (②) تتطابق
خمسة موارد، وينفرد **اثنان بالكسر في الوضعَين معًا**:
`tilt_rules.db` (ذرّة ٥٨0 — الوحيدة في المستودع التي تحلّ `var/` عبر `parents[2]`، فتنتج
`R/atoms/var/store/…` وهو مسار لا يمكن أن يوجد) و`analysis_settings.db`
(كسرُه **سببه متغيّر البيئة لا اللوحة**).

## B) مالك كل مورد (من يكتب / من يقرأ)

| المورد | كاتب | قارئ | اللوحة كاتبة؟ |
|---|---|---|---|
| `var/store/market_data.db` | الذرّات 701·716 · المصادر 625/630 | الذرّات + اللوحة (`candles:922`, `:925`) | **لا** — قراءة فقط |
| `var/store/decisions.db` | 707 (·714 أرشفة) | 717 + اللوحة | **لا** |
| `var/logs` | 719 · 720 | اللوحة (`:582`) | **لا** |
| `var/store/tilt_rules.db` | **580 فقط** | اللوحة (`:1771`، `mode=ro`) | **لا** — لا تكتب أبدًا |
| `var/forex/journal.jsonl` · `var/forex/snapshots/` | النواة: `run_core.py:77` و`:80` (`PROJECT_ROOT`-join)؛ `SnapshotEngine.__init__` يعمل `mkdir` | الاستعادة عند الإقلاع | **لا** |
| `var/store/analysis_settings.db` (أو `var/forex/`) | النواة (`approve`) + `/gov/decision/dials` **عبر `shared` العام** (`server.py:2196`) | اللوحة `parameters_rows:1744` — **من ملفّ آخر** | نعم للوحة، لا لنفس الملفّ |
| `var/governance/commands.db` | **اللوحة** (`queue_command:901-910`، يعمل `mkdir` وينشئ القاعدة) | 901 (`_on_pulse:228`) | **نعم — الكاتبة الوحيدة** |
| `var/backups` | **اللوحة** (`make_backup:443-446`) | قائمة اللقطات `:501`، `:2416` | **نعم** |

**القاعدة:** اللوحة **لا تكتب** في مخازن الذرّات؛ تكتب في مكانَين فقط — جسر الأوامر
ولقطة النسخ الاحتياطي. فكل «انقسام» في الخمسة هو عرض فارغ لا إفساد بيانات؛ لكن
الانقسام في `commands.db` **يفصل يد المالك عن ٩٠١** (في mode ①)، والانقسام في
`analysis_settings.db` يفصل شاشة العيارات عن السجلّ الذي يعتمد.

## C) الجذر القانوني (المُعلَن، المُقاس من مواضع التعريف لا من الأسماء)

المُعلَن في المستودع — والاتّفاق بينه وبين الكريبتو:
1. `config/unified_release.json`: `"crypto_data_root": "crypto_runtime/var"` (وليس مقابل فوركسي له).
2. `tools/build_architecture_atlas.py:609`: «كريبتو: الجذر الوحيد `crypto_runtime/var`. فوركس: `forex_runtime/var`».
3. `run_crypto.py:22-24` + ختم NQ 2026‑09‑01: «كل قراءة وكتابة خاصة بالكريبتو تعيش تحت runtime نفسه».
4. `scripts/run_forex.py:17` `os.chdir(ROOT/"forex_runtime")` — أي أن الـcwd المخطَّط هو الـruntime.
5. `governance/checks/check_crypto_isolation.py:100-106` يفرض `forex_runtime/var ≠ crypto_runtime/var`.

⇒ **الجذر القانوني للفوركس = `<PROJECT_ROOT>/forex_runtime/var/`**، بشرط أن تكون
`forex_runtime/` **مجموعة وصلات** (`prepare_unified.py`) لا نسخة ملفات — وعندئذٍ
`forex_runtime/var` مجلّد حقيقيّ مستقلّ (مُستثنًى من قائمة الوصلات عمدًا)، فيبقى
العزل وتحصل المطابقة مع `Path.cwd()` للذرّات.

موارد **لا** ينطبق عليها هذا الجذر ولا يجوز زجّها فيه: `journal` و`snapshots`
(`run_core.py:77,80` — `PROJECT_ROOT`-join = `R/var/forex/…`)؛ وهما وحدهما السبب في
أن `var/store/analysis_settings.db` ظهر عندك بالجذر: **`shared/parameter_registry.py:110`
يشتقّ من `__file__`**، فيوضع `shared/` في `R/shared/` (الوضع ①) أو في الـmirror.

⇒ **جذر قانوني واحد لكل الموارد غير ممكن**: هناك **طبقتان** — طبقة البيانات الحيّة
(`<runtime>/var`) للذرّات واللوحة، وطبقة الحالة التشغيلية للنواة (`<PROJECT_ROOT>/var/forex`)
لليورنال واللقطات والخزنة (`../runtime/secrets.enc`). الإصلاح يجب أن يوحّد **الطبقة الأولى فقط**.

## D) الملفات التي يجب تعديلها لاحقًا (مرحلة التنفيذ — لا شيء عُدِّل الآن)

| # | الملفّ | السطر |Nature |
|---|---|---|---|
| ١ | `scripts/run_forex.py` | 21 | احذف/صحّح فرض `QUANT_ANALYSIS_SETTINGS_DB` إلى `forex_runtime/var/store/analysis_settings.db` ليطابق `run_crypto.py:24` — **هذا هو إصلاح `analysis_settings.db`، وليس `server.py:56`** |
| ٢ | `atoms/قسم 551-600/580_منفذ_الترجيح/atom.py` | 233-234 | وحده يستخدم `parents[2]` فينتج `R/atoms/var/…` — اجعله `Path.cwd()` كذرّة ٩٠١، أو مرّر مسارًا مطلقًا في المانيفست |
| ٣ | `governance/server.py` (+ نسختا الـmirror) | 60 | وحّد مصدر القراءة: `ANALYSIS_SETTINGS_DB = ParameterRegistry().path` بدل `DATA_ROOT/…`، وإلّا بقي `/gov/parameters` يقرأ ملفًّا لا يكتبه أحد |
| ٤ | `config/core_forex.yaml` | 8,12-13 | `journal.path` و`snapshot_root` تُحلّان من `PROJECT_ROOT` بينما `secrets` من cwd — وثّق/وحّد الأساس في سطر واحد |
| ٥ | `scripts/prepare_unified.py` | 90-96 | قائمة `runtime_common` تُنشئ وصلات لكن **لا تزيل النسخ الحقيقية** (`_make_link` يرجع "kept" ولا يتحقّق أنه link) — فهناك 1564 ملفًّا مكرَّرًا بلا ختم |
| ٦ | `atoms/قسم 001-050/007_سلامة_الملفات/manifest.yaml` | `watched_dirs` | `forex_runtime/` و`crypto_runtime/` خارج المراقبة تمامًا؛ و`SHA256SUMS.txt` يغطي `forex_runtime/` بمداخِلِ ٢ فقط |
| ٧ | `scripts/launch_market.py` / `governance/app.py` | — | `app.py` لا يعمل `chdir` ولا يضبط المتغيّرات ⇒ الوضع ① غير مدعوم ويجب أن يفشل بصوت عالٍ لا بصمت |

## E) لماذا لا يكفي تعديل السطر ٥٦ (مثبت بالقياس، لا بالاسم)

1. **٥ من ٧ موارد تتطابق فعلًا في الوضع الرسميّ** بدون أي تغيير في `:56` (جدول A، عمود ②).
   فموحّدها مع `R/var` **يكسر** ما يعمل: الذرّات تُحلّ عبر `Path.cwd()`، وتغيير `:56` لا يغيّر `cwd`.
2. **الكسران الحقيقيّان لا يمرّان بـ`:56`**: `tilt_rules.db` مكسور من **داخل الذرّة** (`atom.py:234`)
   — لا علاقة له بجذر اللوحة؛ و`analysis_settings.db` مكسور من **متغيّر بيئة يفرضه `run_forex.py:21`**
   — وأي `RUNTIME_ROOT` تختاره يبقى المحرّك على `R/var/forex/`.
3. **`server.py:2196` (`/gov/decision/dials`) يستورد `shared` من `ROOT.parent`** = الـshared العام،
   بينما `parameters_rows` (`:1744`) يقرأ `ANALYSIS_SETTINGS_DB`. حتى لو وحّدت `:56` يبقى
   المنفذان في نفس الخادم على ملفّين مختلفين — والدليل المقيس: بعد فرض المتغيّر على قاعدة المحرّك
   الموجودة ظلّ `/gov/parameters` `available=False · عدد=0`.
4. `RUNTIME_ROOT` **مُستهلَك أيضًا من فحص العزل**: `check_crypto_isolation.py:102-106` يقارن
   `forex_runtime/var` مع `crypto_runtime/var`. توجيهه إلى `R/var` يجعلهما… لا شيء، ويسقط الحاجز.

## F) هل `forex_runtime/` نسخة تشغيل مستقلة؟ — **كلا: mirror جزئي متقادم، لا يحدّثه أحد**

| الدليل | القياس |
|---|---|
| هل هي نسخة كاملة؟ | **نعم**: 1564 ملفًّا مُتتبَّعًا في git (1199 atoms · 237 governance · 41 scripts · 29 shared · 24 core · 9 config · 8 tools…)، **كلها `100644` عاديّة — صفر symlink** |
| هل تتطابق مع الجذر؟ | **1535/1535 مطابق بايت-ببايت**؛ و`governance/server.py` مطابق ✓ |
| ما الفرق؟ | 27 ملفًا **موجودة داخل الـmirror فقط**: `forex_runtime/governance/ui/built/assets/*.{woff,woff2}` — **بناء الواجهة موجود داخل الـmirror وغير موجود في الجذر** (الجذر: `governance/ui/built/assets` = ٠ ملف) |
| هل تُحدَّث؟ | **لا**: المولّد الوحيد هو `tools/baseline_regen.py:53-55` (يولّد `forex_runtime/integrity_baseline.json` بنفس منطق ٠٠٧). لا `copytree` ولا rsync في المستودع |
| هل تُختم؟ | **لا**: `SHA256SUMS.txt` = 2778 مدخلًا، منها **٢ فقط** لـ`forex_runtime/` (`e3b0c442…`= `.gitkeep` — أي **ملفّ فارغ**، و`066ee903…`= `integrity_baseline.json`) |
| هل يراقبها الحارس؟ | **لا**: `watched_dirs` في ٠٠٧ = `atoms/ transport/ security/ clock/ catchup/ scripts/ tools/ shared/ governance/ config/ mt5/ ctrader/ core/` — لا `forex_runtime/` ولا `crypto_runtime/` |
| هل هي متقادمة؟ | **نعم، مُثبت**: `forex_runtime/integrity_baseline.json` يحمل **نفس `scope_digest` للجذر** (`6017027da724ee74…`) أي نسخته الخاصة من ٠٠٧ ✓، **1300 مدخل بدل 1310** (نقص 10 = ملفات أُضيفت للجذر بعد النسخ: `ui/src/components/AccountsBar.tsx`, `FeedLeds.tsx`, `ui/src/sections/Backtest.tsx`, `Lab.tsx`, `scripts/e2e_runner.py`, `financial_validation.py`, `product_gate.py`…)، و**٣٩ قيمة لا تطابق الملفّات الفعلية** |
| أمثلة على تقادُم الـbaseline الداخلي | `dir:mt5/::QUANT_NQ.mq5`: داخلي `92955b85925f…` · جذر `b74a9efd7600…` · **الملفّ الفعلي في الموضعَين `5edb4df2ff7f…`** — أي أن baseline الجذر أيضًا يكذب على هذا الملفّ (وهو عطل `test_device_contract` المعروف) |
| هل الوصلات المفروضة موجودة؟ | **لا** — `python scripts/prepare_unified.py --verify-only` يرجع **rc=2** بقائمة 26 فشلًا (`forex_runtime/atoms -> atoms`, `…/shared -> shared`, …) لأن النسخ حقيقية لا وصلت. ومجرّد أن المحتوى مطابق يجعل `_make_link` يرجع `"kept"` **دون أن يحوّلها إلى وصلات** |

**الحُكم:** `forex_runtime/` = **بقايا بناء/تجميع** (شجرة كاملة مُنسخة زمن النشر) تُستخدَم
ـcwd وdata root للذرّات واللوحة، لكنها **ليست مستقلة قانونيًّا**: لا ختم خارجي لها، لا مراقبة
من ٠٠٧، ومولّدها الوحيد هو `baseline_regen.py`. وعلى نسخة المالك (حيث `forex_runtime/`
وصلات فقط، كما يولّده `prepare_unified.py` بـ**استثناء `var`**) يختلف السلوك اختلاقًا كليًّا —
وهذا يفسّر لماذا عندك «جوّاته governance وبس»: عندك الوصلات قائمة، وعندنا نحن النسخة الكاملة.

## G) حالة المستودع بعد التنفيذ (حُدِّث هذا القسم — لم يعد «لم يُمسّ» شيئًا)

مرحلة التنفيذ **مأذونة** (١٩ بندًا)، فالتعديلات مطبَّقة على الشجرة. القيد الوحيد الباقي:
**لا commit، لا push، لا إعادة ختم** — وكلّها محترَمة.

| البند | الحالة |
|---|---|
| لا commit / لا push | ✓ `git log -1` = `9e4f254` (لا جديد) · `origin/master` لم يُمسّ |
| لا إعادة ختم (`SHA256SUMS.txt`, `integrity_baseline.json`) | ✓ لم يُكتب في أيّ منهما ملفّ — انظر «ما يُعرف عن الختم» أدناه |
| `git status --porcelain` | ٦٥ سطرًا: ٥٦ تعديلًا + ٩ ملفات جديدة (المالك + الجسر + الفحص الجديد) + هذا التقرير |
| قواعد البيانات الحيّة | ✓ لا كتابة في `forex_runtime/var` ولا `R/var` من هذا التنفيذ (القياسات جرت في `/tmp`)؛ `forex_runtime/var/store/analysis_settings.db` (٦ صفوف) من **اختبار سابق** للسجلّ حين أُنشئ المرسى الجديد |
| `venv/`, `__pycache__`, `governance/ui/node_modules`, `governance/ui/built/` | مستبعدات `.gitignore` — أثار بناء/اختبارات (مبنية من `Settings.tsx` المعدَّل) |

## H) التنفيذ — ما تغيّر، وبِمَ قِيست صحّته

### ح/١ المالك الجديد: `shared/runtime_paths.py`

ملفّ واحد يملك اشتقاق الجذور (لا «حساب في كل ملفّ»). العقد:

```
runtime_root(code_root=…, market=…)      → <runtime>  أو RuntimeError — ⛔ بلا <root>/var
runtime_var(*parts, …)                   → <runtime>/var/…      (كل مورد تشغيليّ)
settings_db_path(code_root=…, market=… ) → QUANT_ANALYSIS_SETTINGS_DB، ثم
                                           <runtime>/var/store/analysis_settings.db
core_state_root(code_root=…, market=…)   → QUANT_CORE_STATE_ROOT، ثم <runtime>/var،
                                           ثم <root> (السلوك التراثيّ حرفيًا عند بلا مُقلِع)
```

* أولوية `QUANT_RUNTIME_ROOT` **مطلقة** (لا يُعاد اشتقاق شيء بعدها)؛ مرفوض إن لم يكن مطلقًا وموجودًا.
* قاعدة `governance/` **لا تُنقص طبقة** (`server.py` يمرّر `ROOT.parent` جاهزًا) — هذا كان يولّد
  `governance/forex_runtime` الكاذب. نسخة الـruntime تُخدم من نفسها (لا نسخة تخدم سوقين).
* سوقٌ غير معروف (`equities`) ⇒ **خطأ**، لا إسقاط على الفوركس (قِيس: كان `runtime_var(market="crypto")`
  يرجع `forex_runtime/var` لأنّ المقارنة كانت بحرفيّة `"crypto_runtime"`).
* جسر خفيف `governance/runtime_paths.py` لملفات الحوكمة القائمة بذاتها
  (`check_telegram.py`, `start_asset.py`, `verdict_cycle.py`, `live_probe.py`, `app.py`) — يعيد
  الاستدعاء إلى المالك، **لا يكرّر منطقًا**.

### ح/٢ جدول المسارات — قبل ⇄ بعد (كلّها مقيَسة، لا مُستنتَجة)

| المُستهلِك | قبل (مقيَس) | بعد (مقيَس) |
|---|---|---|
| `server.py:DATA_ROOT` | `RUNTIME_ROOT/"var"` من `ROOT.parent/<runtime>` **بلا تحقّق** | `<runtime>/var` — من المالك، ومعروف بالاسم من داخل النسخة |
| `server.py:ANALYSIS_SETTINGS_DB` | `DATA_ROOT/"analysis_settings.db"` (بلا `store/`) — **⊄** لا يطابق السجلّ | `settings_db_path()` = عقد السجلّ حرفيًا: `<runtime>/var/store/analysis_settings.db` |
| `server.py` (16 موردًا: MARKET_DB · COMMANDS_DB · TILT_RULES_DB · DECISIONS_DB · LOGS_DIR · BACKUPS_DIR · MEXC_KEYS · TRADE_DB · …) | مشتقّة يدويًا من `DATA_ROOT` | كلّها `_resolve_runtime_var(…)` — **صفر** استخدام لـ`DATA_ROOT /` |
| `shared/parameter_registry.py` | `Path(__file__).parent.parent/"var"/"store"` = `R/var/store` | `settings_db_path()` ⇒ **نفس ملفّ اللوحة** ✓ |
| `scripts/run_forex.py:21` | يدوس `QUANT_ANALYSIS_SETTINGS_DB=R/var/forex/analysis_settings.db` | يرسو على `QUANT_RUNTIME_ROOT=<runtime>` + `QUANT_CORE_STATE_ROOT=<runtime>/var` + السجلّ تحت `var/store/` |
| `scripts/run_forex.py:19` (`QUANT_ATOMS_ROOT`) | **مفتاح بلا سلك** — لا قارئ له | السلك موصول: `run_core.py` يقرأه أوّلًا، والقيمة صارت `<runtime>/atoms` |
| `scripts/run_crypto.py` | `CRYPTO_DATA_ROOT/analysis_settings.db` (بلا `store/`) + `QUANT_ATOMS_ROOT=R/atoms_crypto` | `…/var/store/analysis_settings.db` + `QUANT_ATOMS_ROOT=<crypto_runtime>/atoms_crypto` (مع احتياط `…/atoms`) |
| `governance/scripts/run_core.py:77,80` | `PROJECT_ROOT / journal_path` · `PROJECT_ROOT / snapshot_path` (يكتب `R/var/forex/…`) | `state_root / …` حيث `state_root = core_state_root()` — **تراثي تمامًا** عند بلا بيئة، وتحت `<runtime>/var` مع عقد المُقلِع |
| `scripts/run_governance.py` | لا جذر ولا chdir | يضبط `QUANT_RUNTIME_ROOT/QUANT_CORE_STATE_ROOT/QUANT_ANALYSIS_SETTINGS_DB` بحسب `--market` (setdefault — يد المالك تتقدّم) |
| `governance/app.py` (غرفة القيادة) | يُقِلع `governance/server.py` + `run_core.py` من جذر المشروع **بلا بيئة** | يضبط العقد الثلاثة + `QUANT_CORE_CONFIG/DOMAIN` قبل الإقلاع؛ و`SNAPSHOTS_DIR` صار مرسى النواة الفعليّ (كان `R/var/snapshots` ⇒ عدّاد `--stop` كان «يكذب بلا لقطات») |
| `atoms/…/580_منفذ_الترجيح/atom.py:232-235` | `parents[2]/raw` = **`atoms/var/store/tilt_rules.db`** (لا يوجد — مقيَس: `exists R/atoms/var = False`) | `Path.cwd()/raw` = عقد المُقلِع ⇒ `<runtime>/var/store/tilt_rules.db` = ما تقرأه اللوحة ✓ |
| `governance/telegram.py:45-46` | `R/var/governance/telegram{,_beat}.json` (⊄ ما تكتبه اللوحة) | المالك ⇒ `<runtime>/var/governance/…` ✓ |
| `governance/vault_ops.py:52` | `R/var/governance/vault_audit.log` | المالك ⇒ `<runtime>/var/governance/vault_audit.log` ✓ |
| `conftest.py` | يعزل السجلّ فقط | يعزل **الجذر كلّه** (`QUANT_RUNTIME_ROOT` + `QUANT_CORE_STATE_ROOT` على قرص مؤقت) |

**برهان «لا `R/atoms/var`»:** `Path("/home/user/QUANT_NQ/atoms/var").exists() = False` بعد كل
القياسات؛ وحيث جرى تشغيل الذرّة بعقد المُقلِع نشأ `…/var/store/tilt_rules.db` تحت مجلّد العمل.

### ح/٣ «حفظ» ≠ «اعتماد» (البنود ٥–٦)

* `ParameterRegistry.write_value()` الجديد: يكتب القيمة، **يبقي `UNAPPROVED`**، لا `source` إطلاقًا
  (`source=OWNER` حقّ الاعتماد لا حقّ الكتابة)، يرفع `version` ويسجّل في `parameters_audit`، ويرفض
  `PARAMETER_NOT_DECLARED`/`PARAMETER_VALUE_INVALID` (رقمية وNaN).
* `decision_dials.apply_command(…, confirm=…)`: الحاكم حقل **`confirm` في الحِمل** — `true` وحده
  يعتمد؛ الغياب/`"true"` النصّي/أي شيء آخر = مسودة. أُعِيد الترتيب ليُكتب الحفظ **بعد** تأمين صفّ
  النطاق (`scoped`) وإلا ضاع على عيار مقيَّد بحساب/رمز.
* `Settings.tsx`: زرّ «حفظ» يرسل `confirm:false` ورسالته صريحة («مسودة — اعتماد بالزرّ المجاور»)،
  وأضيف زرّ **«اعتماد ✓»** منفصل يمرّر `confirm:true` (كلاهما بخطوات بوّابة ٩٠١)؛ وبطاقة سرعة
  التحليل تُرسل `confirm:true` لأن غرضها النصّي «تطبيق».
* المقلِع البرمجيّ الوحيد لهذا المسار كان `/gov/decision/dials` (الذي لا وجود له فعلًا) — المسار
  الحقيقي `/gov/decision/settings` **قراءة فقط**، ولم يُمسّ عقده.

**القياس الحيّ (خادم حوكمة حقيقيّ على قرص مؤقت، PUT عبر `/gov/command` بثلاث خطوات، وتطبيق من ذرّة ٤٥٣):**

| الخطوة | ما وصل للوحة (`/gov/decision/settings`) |
|---|---|
| حفظ (`confirm` غائب) | `value=0.37 · status=UNAPPROVED · source=UNSET · v1` — **والساري يبقى المانيفست** (`effective_value=50.0`) |
| اعتماد المالك (`confirm=true`) | `value=0.37 · status=APPROVED · source=OWNER · v2` |
| تكرار نفس `command_id` | idempotent — بلا نسخة ثالثة |

### ح/٤ اختبار الوصلة الحقيقيّة: `/gov/parameters` يقرأ قاعدة المُحرّك (البند ٤)

```
وضع ① (غرفة القيادة، cwd=root، بلا قولبات):  RUNTIME_ROOT=<R>/forex_runtime · DATA_ROOT=<R>/forex_runtime/var
   SETTINGS_DB=<R>/forex_runtime/var/store/analysis_settings.db · before declare(): available=True rows=6
وضع ② (زرّ الفوركس):  لوحة = محرّك = /tmp/…/forex_runtime/var/store/analysis_settings.db  (✓ متّحدان)
   بعد declare(): available=True rows=36 · بطاقات اعتماد=6 · عدّاد الحاجز=36   ← تطابق، لا «36 مقابل ٦»
   GET /gov/parameters → 200 rows=36 ; GET /gov/decision/settings → 200 dials=30 · معتمدة=0
```

أي: **لا «6» في اللوحة مقابل «36» عند الإقلاع** حين يتّحد الجذر — الفارقان كانا أثرًا لجذرَين لا لحاجزَين.

### ح/٥ الفحص الجديد: `governance/checks/check_path_authority.py`

خمس دقاقات، لا نصًّا منسوخًا: **أ** مالكٌ وحيد (قواعد محرَّمة على: `ROOT/"var"` · `ROOT.parent/"forex_runtime"`
· `parents[n]/var` · دوس السجلّ على `var/forex` · `runtime_paths` غائب عند من يشتقّ الجذور ·
`QUANT_ATOMS_ROOT` مفتاح-بلا-سلك)، **ب** تطابق النسخ (`forex_runtime` صارم، وانحراف `crypto_runtime`
المُعلَن في `decision_dials/parameter_registry` يُطبع ولا يُحسب خرقًا)، **ج** نقاط اللقاء (لوحة=سجلّ=عيارات،
لا `DATA_ROOT /` في server، لا `parents[n]` في ٥٨٠، journal/snapshots عبر `state_root`، فوركس ⊥ كريبتو)،
**د** الحفظ ≠ الاعتماد، **هـ** عقد الوصلات (يرفض `kept` لمجلّد حقيقيّ محلّ وصلة).

```
$ python3 governance/checks/check_path_authority.py     # من الجذر      → rc=0 🟢 (أ ب ج د هـ كلها 🟢)
$ cd forex_runtime  && … check_path_authority.py        → rc=0 🟢
$ cd crypto_runtime && … check_path_authority.py        → rc=0 🟢
```

### ح/٦ عقد الوصلات في `scripts/prepare_unified.py`

* `_make_link` صار **يرفض** مجلّدًا حقيقيًّا محلّ وصلة («real directory where a link is contracted») —
  لا يمرّ «kept» لمحتوى مطابق بينما العقد وصلة؛ **وهذا كان ثغرة الصمت** في `--verify-only` (rc=2 فقط،
  والباقي kept).
* `--convert-identical`: **لا-تخريبيّ** — يقارن الشجرة بايت-ببايت، ولا يحوّل إلا عند المطابقة الكاملة،
  وينقل النسخة القديمة إلى `<name>.pre-junction-backup/` (لا حذف، ولا لمس لـ`var/`).
* القياس هنا: ٢٤ من ٢٦ وصلًا «مطابقة تمامًا» (بما فيها `shared` و`atoms` و`config` في النسختين)،
  و`forex_runtime/governance` + `scripts` منحرِفة **بسبب تعديلات هذا التنفيذ** — لذا **لم يُشغَّل**
  `--convert-identical` (سيُبقي النسخة القديمة بلا فائدة، وقد يبتلع فروقًا لاحقًا). `--verify-only` rc=2
  بالرسائل المُشخَّصة = النتيجة الصحيحة لشجرة نسخ كاملة مثل شجرة هذا Sandbox.

### ح/٧ ما لم يُفعَّل (قرار موثِّق، البند ٢٤)

* `007`: **لم تُضف** `forex_runtime/`/`crypto_runtime/` إلى `watched_dirs` — أُضيف تعليقًا في المانيفست
  يشرح أن النطاق «شجرة الكود التي تعمل منها الذرّة»، وأن إضافة نسختَي runtime كانت ستجعل الختم يشمّ
  حالة حيّة (`var/`) — وهذا محرَّم. (المسح الفعليّ: `watched_items=1313` · `scan_ms≈41`.)
* **لم تُعَدّ** `integrity_baseline.json` ولا `SHA256SUMS.txt` (حظر إعادة الختم). **أثر معروف:**
  `tests/test_device_contract.py::test_28` يفشل الآن لأن ختم ٠٠٧ قديم مقابل ملفات عدّلناها
  (`run_forex.py` · `run_governance.py` · …) — **كان يفشل قبل التعديل أيضًا** (ملف `.mq5`؛ مقيَس في §أ)،
  وزاد عدد صفوف الانحراف. إعادة الختم خطوة لاحقة مطلوبة من المالك: `tools/baseline_regen.py` (ثلاثة نطاقات).
* `queue_command` ما زال يحصر `operator` بـ`{dashboard, telegram}` — تركته كما هو (عقده)، وهو سببُ
  ظهور أوامر القياس باسم «dashboard» رغم إرسال اسم آخر.

### ح/٨ نتائج الفحوص الكاملة (لا إخفاء للأخضر)

| الفحص | النتيجة | مقابل HEAD (شجرة عمل HEAD في `/tmp/base_chk`) |
|---|---|---|
| `pytest -q` (كامل) | **11 failed · 1132 passed · 1 skipped** (140s) | **11 failed · 1131 passed · 2 skipped** — لا فشل جديد؛ `test_device_contract::test_28` انتقل من skipped إلى failed (تقادُم الختم — ح/٧) |
| `tests/test_analysis_speed.py` | 7 passed | — |
| `tests/test_release_contract.py` | 8 passed | — |
| ذرّة ٥٨٠ (الجذر + `forex_runtime`) | 19 + 19 passed | — |
| ذرّة ٩٠١ | 15 passed | — |
| `shared/` | 5 passed | — |
| `check_path_authority.py` | 🟢 rc=0 في الشجرات الثلاث | غير موجود في HEAD |
| `check_parameters_endpoint.py` | rc=0 (`declared=6 dials=30`) | rc=0 |
| `check_crypto_isolation.py` | rc=1 — **نفس سبب HEAD**: «نواة الكريبتو (8020) غير قابلة للوصول»؛ و«مجلّدا البيانات مساران مختلفان فعلًا» 🟢 | rc=1، نفس السطر |
| `check_project.py` | «١ فحص فشل» | «٢ فحص فشل» (الزيادة عند HEAD: `governance/ui/built/index.html` مفقود — بنيته هنا) |
| `validate_atoms.py` | 233 ذرّة · مخالفات 1 · تحذيرات 20 | مطابق (الخطأ نفسه: 582 «أرقام سحرية») |
| `prepare_unified.py --verify-only` | rc=2 + تشخيص ٢٦ وصلًا | rc=2 بلا تشخيص |
| `npm run build` (لوحة React) | ✓ built (لا أخطاء TS) | — |

**اختبارات عُدِّلَت (مطلوب لعقد البند ٥/١٠، لا لإخفاء فشل):**
`tests/test_analysis_speed.py::test_scoped_apply_command` كان يثبّت أن الأمر **يعتمد** مباشرة (هذا
بالضبط العطل المُبلَّغ: «الحفظ يعتمِد») — صار يقيس: مسودة `UNAPPROVED` ثم اعتماد `APPROVED/OWNER`.
`tests/test_release_contract.py::test_crypto_data_paths_stay_under_crypto_runtime_var` كان يطابق
سطور `server.py` الحرفية (وهو ما صنع انضباط النصّ لا العقد) — صار يمنع الحساب اليدويّ بالـregex
**ويقيس** `runtime_var(market="crypto") == crypto_runtime/var` فعليًا.

### ح/٩ الملفات

| جديدة (٩) | معدَّلة (٦٥) |
|---|---|
| `shared/runtime_paths.py` (المالك) · `governance/runtime_paths.py` (جسر) · `governance/checks/check_path_authority.py` (الفحص) — **لكلٍّ منها نسخة في `forex_runtime/` و`crypto_runtime/` مطابقة بايت-ببايت** | `governance/server.py` · `app.py` · `telegram.py` · `vault_ops.py` · `checks/check_telegram.py` · `scripts/{run_core,start_asset,verdict_cycle,live_probe}.py` · `ui/src/sections/Settings.tsx` (＋بناء `built/`) — **وفي النسختين**؛ `shared/{parameter_registry,decision_dials}.py` (＋نسخة forex؛ نسخة crypto فيها فرقها الخاص فلا فُرِض عليها)؛ `scripts/{run_forex,run_crypto,run_governance,prepare_unified}.py` (＋نسختين)؛ `atoms/…/580…/atom.py` (＋نسخة forex)؛ `atoms/…/007…/manifest.yaml` (＋نسختين)؛ `conftest.py` · `tests/test_analysis_speed.py` · `tests/test_release_contract.py` |

### ح/١١ الشحنة الثانية — ما بقي خارج القائمة الأولى (وليس «شغلاً ثانوياً»)

بعد الحصر الذي طلبه المالك تبيّن أنّ **ثلاثة مواضع** كانت خارج لائحة البنود، وأحدها هو
جذر «الحفظ ينجح ولا يصل» بعينه:

| الملفّ | العطل المقيَس | ما صار |
|---|---|---|
| `shared/live_analysis.py:162-172` | `AnalysisSettingsStore.__init__` يحسب `_root = Path(__file__).parent.parent` ثم `_root/var/store/analysis_settings.db` ⇒ المحرّك (ذرّتا ١٥٠ و١٥٠-القسم) يقرأ من **جذر المشروع** بينما اللوحة والسجلّ تحت `<runtime>/var/store` — نفس عطل «ملفّ الظلّ» الموثّق بورقة ٩٩ بند ٤ رجع بصيغة أخرى بعد توحيد الجذر | المسار من `settings_db_path()` وحده، مع سوق من `QUANT_CORE_DOMAIN`؛ القياس: المحرّك = السجلّ = اللوحة على ملفّ واحد، وكتابة `set_weights` بـ`updated_by=قياس`/`revision=1` قُرئت من كائن آخر فورًا |
| `tools/approve_scalp_params.py:31` | الافتراضيّ `ROOT/var/forex/analysis_settings.db` — مسار **متقاعِد** لا يقرأه أحد بعد التوحيد (الأداة «تنجح» وتكتب في الهواء) | `settings_db_path(code_root=ROOT, market="forex")` |
| `tools/set_scalp_weights.py:71-75,212` | نفس المسار المتقاعِد + قرص لقطات `ROOT/var/forex/snapshots` + كشّاف «الملفات الظلّ» يمشي على جذر واحد | المالك للمسار، و`core_state_root()` للقطات، والكشّاف يمرّ على الجذور الثلاثة (المشروع + `forex_runtime` + `crypto_runtime`) |
| `governance/app.py` · `governance/scripts/verdict_cycle.py` | كانا يحملان **مرسىً تراثيًّا محليًّا** في `except` (`ROOT/"var"/"forex"/…`) — أي حدسٌ بلا مالك بالضبط ما يحرّمه العقد | حُذف الحدس: بلا `shared/` يُلقى `RuntimeError` صريح بدل قراءة جذر متقاعِد |
| `shared/section_live.py` | يفحص فقط (لا حساب فيه) — أُدرج في قائمة الفحص | — |

وتوسّع `check_path_authority.py` ليُغطّي هذه المواضع بقاعدتَين جديدتين:
`_root / "var" / "store"` (مرسى محلّي داخل الملفّ) و`ROOT / "var" / "forex"` (قراءة متقاعِدة).
**إثبات أنّ الحارس ليس زرّية:** أُعيدت سطور العطل القديمة إلى `shared/live_analysis.py` مؤقتًا ⇒
`rc=1` مع السطر: `⛔ shared/live_analysis.py:173 — مرسى محلّي لقاعدة المعايرة داخل الملفّ نفسه
(ملفّ ظلّ لا يقرأه أحد)`؛ ثم أُرجعت ⇒ `rc=0`. و`check_analysis_dials_contract.py` 🟢، و
`pytest -q` الكامل: **11 failed · 1132 passed · 1 skipped** — لا جديد مقابل HEAD.


### ح/١٠ ما يترتّب على المالك بعد (لا شيء نُفِّذ منه)

1. **إعادة ختم** `tools/baseline_regen.py` ثم `SHA256SUMS.txt` (وإلّا بقي `test_device_contract` أحمر).
2. `git add` + commit — **لم يُفعَّل**: كل شيء في الشجرة غير مُودَع.
3. عند نسخة المالك (وصلات حقيقية): لا شيء — `server.py` يعمل بالاكتشاف، وعند الحاجة
   `python scripts/prepare_unified.py --convert-identical` بعد نسخة احتياطية.
4. على ويندوز: «غرفة القيادة.bat» الآن يُقلِع العقد نفسها التي يُقلعها زرّ الفوركس — لا حاجة لضبط بيئة يدويّ.


---

## §ح/١٢ — سجلّ جولة «تجديد خط الأساس فقط» (٢٠٢٦-٠٩-٠٣ ١٠:٤٠)

* المنفَّذ: `python tools/baseline_regen.py` (لا شيء غيره). ما لمسه: `integrity_baseline.json`
  + `forex_runtime/integrity_baseline.json` + `crypto_runtime/integrity_baseline.json` — وهي الملفات
  الثلاثة التي صمَّم السكربت لكتابتها («ما لا تفعله: لا تلمس أي ملفّ خارج ملفات خط الأساس الثلاثة»).
* الأرقام: 1313 عنصر حرس · متقادم 23→0 · مزال 0 · مضاف 3 · `scope_digest=6017027da724…` (الجذر/الفوركس)
  و655 عنصر · 42→0 · `b93860072fdd…` (الكريبتو). الوضع الجديد مطابق للشجرة: `--check` ⇒ «0/0/0» في الثلاث.
* `pytest -q`: **10 failed · 1133 passed · 1 skipped** (كان 11/1132/1 قبل التجديد؛ الأخضر الجديد
  `test_device_contract::test_28`). `tests/test_device_contract.py`: **28 passed** في 3.27 ث.
* `check_path_authority.py`: 🟢 rc=0 (الجذر + المرآتان). `validate_atoms.py`: 233 ذرّة · 1 ERROR (582
  أرقام سحرية `[0.95,0.99,20,400]`) · 20 تحذيرات · rc=1 (كما في HEAD). `check_crypto_isolation.py`:
  rc=1 والسبب `8020` مغلق في هذا الصندوق (لا تسرّب مسارات). `scripts/check_project.py`: rc=1 وفحصه
  الفاشل الوحيد هو الـERROR(582) نفسه.
* البناء: `cd governance/ui && npm run build` ✓ في 610ms (`built/index.html` = `dd8bac83eef6b4d9…`).
  `forex_runtime/governance/ui/built` **لم يُمسَّ** (`6469e075bc86e49c…`)؛ هو مجلّد متتبَّع في المرآة،
  وبناءُه قرارُ نشر من المالك لا قرار هذه الجولة.
* `SHA256SUMS.txt`: لم يُمسَّ — بصمته `f0fe09aa6d84904af200aec489873782ce01e9a9e34871e06f2443fa2c01e8f7`
  قبل وبعد، و`git status --short -- SHA256SUMS.txt` فارغ (0 أسطر). الختم النهائيّ لم يُعمل.
* لا commit ولا push: `git log -1` = `9e4f254` = `origin/master`، `git log origin/master..HEAD` فارغ (0)،
  والـreflog سطرُه الوحيد `clone: from https://github.com/muhammedrezuk-wq/QUANT_NQ.git`.

---

## §ح/١٣ — جولة `582` (أمر المالك: أصلح 582 أولًا، ثم أعد القياس)

**العطل:** المادة 9/ملف 4 رفضت أربعة أرقام بلا ملكية معلَنة في `atoms/قسم 551-600/582_انحراف_المرجع/atom.py`:
`_caps:222 → 20` · `_caps:224 → 0.95` · `_caps:225 → 0.99` · `_classify:309 → 400`
(الـ400 الثاني في `[-400:]` غير محسوب: الشرائح/Fetch مستثناة صراحةً في `literal_numbers`).

**الإصلاح (ملكٌ معلَن، لا ترخيص في العقد):** أربعة مفاتيح في `manifest.yaml` →
`cap_min_samples: 20` · `expected_percentile: 95` · `suspicious_percentile: 99` · `ratio_history_cap: 400`
(كلُّها `type: integer` بحدود دنيا/قصوى)، تُقرأ مرّة في `initialize` عبر `cfg.get(…، default)`
وتُخزَّن في `self._cap_min_samples/_expected_pct/_suspicious_pct/_ratio_history_cap`
(المئويّات مقسومة على 100 في `initialize` — لا قسمة في منطق العمل، ولا رقم حيّ في `_caps`).
`config/atom_quality_contract.json` **لم يُمسَّ**: لم تُشترَ خضرة بإضافة الأرقام إلى قائمة الإعفاء.

**لا تغيّر سلوكي مقيَس:** `95/100.0 == 0.95` و`99/100.0 == 0.99` ⇒ True؛ وقيم المانيفست تساوي
الافتراضيات القديمة (20/20/400) فلا انزياح؛ والاختبار الذاتي للذرّة (9 اختبارات) ومرّ.

**القياس بعد الإصلاح:**

| الفحص | قبل | بعد |
|---|---|---|
| `validate_atoms.py` | 233 ذرّة · **1 ERROR** · 20 تحذيرات · rc=1 | 233 ذرّة · **0 مخالفات** · 20 تحذيرات · **rc=0** |
| `scripts/check_project.py` | rc=1 (الفشل = validate_atoms) | **rc=0** «فحص المشروع البنيوي ناجح» |
| `tests/test_atom_quality_contract.py` | FAILED | **3 passed** |
| `pytest -q` | 10 failed · 1133 passed · 1 skipped | 10 failed · 1133 passed · 1 skipped (العدد ثابت، والتشكيلة تغيّرت) |
| `check_path_authority.py` | rc=0 | rc=0 في الأشجار الثلاث (نسختا 582 متطابقتان) |
| `check_crypto_isolation.py` | rc=1، الاختلافات=1 (نواة 8020) | rc=1، الاختلافات=1 (نواة 8020) — لا علاقة له بالإصلاح |
| `test_device_contract::test_28` | PASSED | **FAILED** — الحارس يسمّي ملفَّي 582 نفسيهما: «متقادم: 2، مزال: 0، مضاف: 0» |

**ملاحظة صريحة:** الفشل الوحيد الجديد هو حارس خطّ الأساس، وهو يعمل كما صُمّم (كل تعديل على ملفّ
مُراقَب يُسقِطه حتى يُعاد توليد الخطّ بـ`tools/baseline_regen.py`). لم أشغّله في هذه الجولة؛ إعادة
التوليد **ليست** إعادة ختم — الختم `SHA256SUMS.txt` لم يُلمَس (بصمته ما زالت `f0fe09aa6d84904a…`).


---

## §ح/١٤ — جولة «السلسلة الميتة لم تكن ميتة: كانت غير محمولة» (٢٠٢٦‑٠٩‑٠٣ مساءً، Bursa)

أمر المالك: إصلاح جذري حتى التشغيل الفعلي، لا تجاوز الاختبارات. هذا سجلّ ما قِيس وما عولج.

### ١) السبب الجذري الأول: مُحَمِّل الاختبار الخلفي كان يحمّل ١٢٤ من ١٣١
القياس: `loaded=124` مقابل ١٣١ مجلّدًا في المدى المطلوب، والناقص
`560, 563, 586, 601, 618, 620, 317, 403, 514, 515` — منها **موجود على القرص ولم يُذكر قطّ**
في `key_atoms` (٥٦٠/٥٦٣/٥٨٦/٦٠١)، ومنها **لا مجلّد له أصلًا** (٣١٧/٤٠٣/٥١٤/٥١٥).
عولج بإضافة الموجودة؛ صار `loaded=136`.

### ٢) سُلَّم القرار كان مقطوعًا لا معطوبًا
٤٥٠ و٤٦٠‑٤٦٤ و٤٦٦ لم تكن في القائمة. **تصحيح فرضية سابقة:** ٤٦٦ ليست «موافقة بشرية» —
بوّابتها آلية (`decision.filtered.state` + جهة صالحة + `metadata.passed`).
بعد الإضافة: `decision.approved.state = ٧٦٨/٧٦٨` بدل الصفر.

### ٣) قاطع الأمان ٥١٦: العطل كان في **المُدخَل** لا في القاطع
`RISK_STATE_UNKNOWN` سببه أنّ `platform.terminal_state` **لا مُنشِئ له إلا ٦١٩**، و٦١٩ لم تكن
محمولة؛ وحين حُمِّلت بقيت `reads=0` لأن استطلاعها **مهمة خلفية** لا تُدار في مُعيد تشغيل متزامن.
العلاج: المُعيد تشغيل يكتب صفّ `account_v2` في **جسر معزول** (`var/backtest_bridge.db`)،
وغلاف `read_now()` في ٦١٩ يستدعي `_read_once` نفسه (العقد وشرط الطزاجة لم يُمسّا).
النتيجة: `risk.account.state = status=READY` (٣٥ حدثًا)، الدفتر `account/system = HEALTHY/HEALTHY`.

### ٤) أفصح عطل في المستودع: مرجع الزمن
`section_contract._is_stale` يقارن `clock.now()` بـ`source_timestamp`. على بيانات ٢٠٢٥ مع
ساعة عملية ٢٠٢٦: **العمر = ٢٨٤٬٤٠٨٬٧٩١ ثانية** ⇒ كل القنوات `STALE` ⇒ ٤٥١ تجمع
`aggregate_state=STALE` ⇒ ٤٥٥/٤٥٦ ترفض ⇒ ٤٦٧ WAIT ⇒ صفر تنفيذ. عولج بمرجع
`ReplayOfficialClock` يُوطن «الرسميّ» على جدول البيانات ويُستعاد بعد آخر تيك؛ `mono()` لم يُمسّ.
(لم تُمسّ عتبة `STALE_AFTER_S=10.01` ولا أي شرط طزاجة.)

### ٥) بوّابة الأصول ٤٦٨
مانيفستها `allowed_symbols:[BTCUSD]` وأعيد تشغيل على `EURUSD` ⇒ `468 _allowed={'BTCUSD'}
_blocked=300` و٤٥٤ تُغلِق بـ`fail=asset`. عولج في **تهيئة المُعيد تشغيل** (طبقة ذاكرة تُطبَّق بعد
إرفاق البيانات: `adjust_pipeline_symbol_gate`)، لا بتخفيف البوّابة.

### ٦) لماذا لم تُغلَق الحلقة حتى الأمر — وهذا ليس عطلًا
كل الأقسام `NOT_READY` (ثقة مقيسة ٣٦٫٦ مقابل عتبة ٦٠)، وبعقد القسم ٨:
`weight_effect = weight if state==READY else 0.0` ⇒ لا ترجيح ⇒ `current_depth=None` عند ٤٥٥
⇒ رفض ⇒ WAIT. الجذر: **لا معايرة معتمدة** — `forex_runtime/var/store/analysis_settings.db`:
٣٦ صفاً **كلّها `UNAPPROVED`**، وجدول `analysis_settings` فارغ (٠ صف). الحارس يعمل كما يُراد له؛
فتحه **قرار اعتماد من المالك** (حقل `confirm=true`) — لم أزوّر سلطة.

### ٧) البيئة كانت تكسر الفحوص لا الكود
اختفت حزم من `requirements.lock.txt` ⇒ `asyncio_mode` «خيار غير معروف» ⇒ **٢٨/٢٨ فشل** في
`test_device_contract`. ثُبِّت `pytest-asyncio==1.4.0` وتسع من القفل
(`fastapi==0.141.1`, `starlette`, `uvicorn`, `websockets`, `httptools`, `watchfiles`,
`python-dotenv`, `cryptography`, `colorama`) ⇒ **28 passed**.

### ٨) أرقام التثبيت النهائية (كلّها مقيسة، لا منسوخة)
| الفحص | النتيجة |
|---|---|
| `tools/baseline_regen.py` ثم `--check` | متقادم ٠ · مزال ٠ · مضاف ٠ (1313/1313/655) |
| `tests/test_device_contract.py` | **28 passed** |
| `tests/backtest` + `tests/core` + `tests/smoke` | **384 passed** |
| `tests/test_*.py` (٤٥ ملفًّا، ٣ دفعات) | **497 + 161 + 101 = 759 passed، 1 skipped** |
| `governance/scripts/validate_atoms.py` | **مخالفات ٠ · تحذيرات ٢٠** · rc=0 |
| `governance/checks/check_path_authority.py` ×3 | **🟢 rc=٠** (القارئ والواضع جذر واحد، النسخ مطابقة، الحفظ لا يعتمد) |
| `governance/checks/check_crypto_isolation.py` | **الاختلافات ٠ · 🟢 العزل سليم** (نواة كريبتو حيّة ٨٠٢٠، لوحة ٨٠٩٣) |
| `scripts/check_project.py` | **rc=٠** — «المتوقع ٢٢٦ · بدأت ٢٢٦ · فشلت: لا شيء» |
| إقلاع فعلي | `run_forex.py`: ١٨١ ذرّة نجاح=True (فشلت=∅)، بوابة `execution` نجحت؛ `run_crypto.py`: ٢٢ + ٥٧ manual |
| `SHA256SUMS.txt` | **لم يُمسّ** · `git` ما زال `9e4f254` · بلا commit/push/tag/origin |
| التعديل | `git status --short` = ٩٦ سطرًا |

### ٩) عطلان جديدان مكشوفان — **لم أُصلحهما** (قرار نشر، لا تصحيح تقني)
1. **عقد الوصلة الموحّدة منهار**: `prepare_unified.py --verify-only` → **rc=2**، و**١٨ `real-dir-drift`
   + ٨ `real-dir-identical`**: العقد «وصلة»، والواقع نسخ فيزيائية لكلتا النسختين.
2. **ثلاث نسخ متباعدة من ذرّات الكريبتو**: `atoms_crypto/` (جذر) فيها ٢٢٧٠‑٢٢٧٧ ولا يوجد ٢١٦٠؛
   `crypto_runtime/atoms_crypto/` (وهي التي تُحمَّل) فيها ٢١٦٠ **ولا يوجد** ٢٢٧٠‑٢٢٧٧؛
   و`crypto_runtime/atoms/` **٦١ ملفًّا بنفس الأسماء ومحتوىً مختلف**. الحارسان لا يريان هذا:
   `check_path_authority` يفحص شجرة الكود ويطابق عدد الذرّات فقط (🟢 ٢٣٣/٨٠)، و
   `check_crypto_isolation` يقيس من `atoms_crypto/` **الجذر** لا من نسخة التشغيل — فيردّ
   «🟠 معرّفات محمّلة ليست بأي شجرة على القرص: 2160» ويظلّ 🟢.
   ملاحظة كاشفة: **كود** النسختين مطابق للجذر (فرق ٠ في `shared/core/tools/clock/security/
   transport/config/scripts/...`)؛ الاختلاف كله في **الذرّات** و`governance/ui/built` (قرار نشر).
3. بيئة Linux بلا MT5/جسر: `611/618/619 read failed: unable to open database file` لأن
   `db_path` في المانيفست مسار ويندوزي مطلق؛ وحاجز «مخزن سوق غائب» يبقى 🟠 هنا. لا يُقاس حيًّا في هذه البيئة.

### ١٠) الحكم
**جاهز للتشغيل المحلي/الورقيّ: لا.** السلسلة مُوصَلة ومقيسة حتى `risk.account.state=READY`
و`decision.approved.state=٧٦٨/٧٦٨`، لكن الطريق إلى أمر مُنفَّذ **مقفول باعتماد معايرة غائب**
(٣٦ `UNAPPROVED` + `analysis_settings` فارغ) — لا بعطل كود. و**الإقلاع الفعلي على MT5 غير قابل
للقياس هنا** (لا Windows/MT5/جسر): حكمي على المسار ويندوزي **قياسيّ بلا اتصال** فقط.
---

## §ح/١٥ — لماذا لا ينزل «اعتماد المعاير»؟ (جولة ١٨: الجاني ليس الزرّ، بل المسار)

### ١) السلّم الكامل معرَّف ومُختبَر — لا حلقة مفقودة

```
زرّ «اعتماد» (governance/ui/src/sections/Settings.tsx:223  →  confirm:true)
  → POST /gov/command  (خطوتان: رمز TTL=60ث، ومطابقة payload+operator حرفية و إلّا 409)
  → queue_command → جسر الأوامر: <runtime>/var/governance/commands.db   (سطر PENDING)
  → ٩٠١ بوابة الأوامر (نبضة كل ثانية، max_age_s=120) → تنشر decision.settings.command
  → الذرّة المالكة (١٥٠/١٦٦/٤٥٢-٤٥٨/٤٦٣/٥٨١) → shared.decision_dials.apply_command
  → registry.approve(source=OWNER, approved_by=<operator>, version+=1) + صفّ تدقيق
  → المحرّك يقرأ STATUS_APPROVED فقط ⇒ القسم READY ⇒ weight_effect ⇒ قرار ⇒ أمر
```

ما من «استيراد يدوي» ولا «ملفّ أبيض» في الطريق: الاعتماد كتابةٌ في السجلّ عبر ٩٠١ حصرًا (server.py:1769-1775 «الاعتماد لا يمرّ من هنا أبدًا»).

### ٢) العطل الذي كان يخنق السلم (مُثبَت بالقياس، ومُصلَح)

ذرّة ٩٠١ (ونظيرتها ٢٩٠١) كانت تُحلّل `db_path` النسبي من المانيفست (`var\governance\commands.db`) **بقياسه على `Path.cwd()`** — لا على مالك المسارات `shared/runtime_paths.py`، صاحب القاعدة «⛔ لا رجوع صامتًا إلى `<root>/var`». فاتفاق اللوحة مع البوّابة كان **بحادث الإقلاع**:

| طريقة التشغيل | أين تكتب اللوحة الطابور | ما تراقبه ٩٠١ | النتيجة |
|---|---|---|---|
| `python3 scripts/run_forex.py` (المُعتمد؛ `run_forex.py:25` يعمل `chdir forex_runtime`) | `forex_runtime/var/…` | `forex_runtime/var/…` | يمشي — بالاتفاق لا بالعقد |
| `QUANT_RUNTIME_ROOT=<جذر آخر>` (أو جولة بلا المُقلِع) | تحت الجذر المُعلَن | من `cwd` — ملفّ آخر | **اعتماد لا يصل أبدًا** |

قياس الجولة (نسخة معزولة كاملة تحت `/tmp`، لم تُمَسّ حالة المستودع):

| الدليل | القراءة |
|---|---|
| `/proc/<pid>/fd` للنواة | `forex_runtime/var/governance/commands.db` |
| جسر اللوحة (تحت الجذر المُقلَّب) | سطران `PENDING` |
| صحيّة ٩٠١ | `READY_AWAITING_FIRST_DASHBOARD_COMMAND` (لم ترَ أمرًا قطّ) |
| عمر السطر | `PENDING` بعد ٢٥٩ث — أي بعد مهلة ١٢٠ث بلا أن تُلْمَس أصلًا |

### ٣) الإصلاح الجذري (٥ مواضع متطابقة، بلا استثناءات فحص)

`_resolve_db_path(raw)` جديدة في ٩٠١ و٢٩٠١ (جذر + `forex_runtime/atoms` + `atoms_crypto` + `crypto_runtime/atoms` + `crypto_runtime/atoms_crypto`): المسار المطلق يُكرَم كما كُتب؛ النسبي يُلْصَق بجذر الـruntime الذي يملكه `runtime_root()` (تقديم `QUANT_RUNTIME_ROOT`)؛ تعذُّر الحلّ يرجع للسلوك القديم فلا يُعطَّل إقلاع. بصماتا الشجرتين متطابقتان لكل سوق (`de4575a78ba4` فوركس، `207c96ed96eb` كريبتو).

الإثبات الحي بعد الإصلاح (نفس شرط الجولة الأولى — جذر مُقلَّب):

```
① /gov/command (طلب)  → 200 {stage: confirm, ttl_s: 60}
② /gov/command (تأكيد) → 200 {stage: queued}
③ الجسر بعد ٣ث        → [(1, 'decision_setting', 'DONE')]      ← كان PENDING للأبد
④ السجلّ (تحت الجذر الصحيح) → APPROVED · OWNER · v1 · approved_by=dashboard
```

ثم أُرجعت السجلّات إلى حالتك الأصلية: **٣٦ صفًّا `UNAPPROVED/UNSET`، صفرا تدقيق، `analysis_settings` فارغ** — لم أغيّر معايرتك ولا سيّلةً واحدة.

### ٤) أسباب ثانية تُفشل الاعتماد وليست أعطالًا (اعرفها قبل أن تضغط)

1. **`confirm` في الـ payload هو الخطّ الفاصل** (بند ٥، ٢٦-٠٩-٠٣): `true` وحده يعتمد؛ الغياب أو النصّ `"true"` = مسودة `UNAPPROVED` لا يقرأها المحرّك. زرّا «حفظ» و«اعتماد» منفصلان في اللوحة عمدًا.
2. **التأكيد مشروط بمطابقة حرفية**: خطوة التأكيد تمرّر الرمز في حقل `confirm` وبنفس `payload`/`operator` وإلا `409 «التأكيد غير صالح أو تغيّرت بيانات الأصل»`.
3. **الأصل في الوقت**: ٩٠١ ترمي الأمر قديمًا (`EXPIRED`) إذا تجاوز `max_age_s=120` — واللوحة لا تعلم أنّ البوّابة نائمة.
4. **`operator` مقصور على Known**: `OPERATORS = {dashboard, telegram}` (server.py:920) — أي اسم آخر (مثل `owner_terminal`) يُطبَّع إلى `dashboard`؛ سجلّ الاعتماد يسمّي المُعتمِد «dashboard».
5. **كريبتو**: `/gov/decision/settings` يعيد `dials: []` عن قصد («لا عيارات قرار محكومة لهذا السوق») — لا اعتماد معايرة هناك عبر هذا الطريق.
6. `SOURCE_BACKTEST` معرَّف في السجلّ ولا كاتب له في المستودع كلّه؛ من يريده يبرمجه صراحةً، لا «تساهلًا».

**تحقّق إضافيّ (الأرض لا الاختلاق):** إقلاع النواة بلا قولبة ومن جذر المستودع يفتح
`forex_runtime/var/governance/commands.db` (مُثبَت من `/proc/<pid>/fd` للناتين) — أي ملفّ اللوحة
نفسه؛ والإقلاع بـ`QUANT_RUNTIME_ROOT=/tmp/…` يفتح `/tmp/nqexp/forex_runtime/var/governance/commands.db`
(تتبّع الـ`fd` نفسه). لم يُحذف سطر اختبار واحد من جسر المستودع: بقي `id=1 DONE` شاهدًا، والسجلّ
`36 صفًّا · معتمدة 0 · تدقيق 0`. (ملاحظة منهجية: اختبار استيرادٍ صناعيّ للذرّة أعطى مسارًا مكرَّرًا
`…/forex_runtime/forex_runtime/…` لأنّه مرّر قيمة manifest خاطئة؛ القياس على العملية الحيّة هو المعتمد.)

---

## §ح/١٦ — شقّ المسار في المخازن (٧٠١–٧٠٩ و٥٦٣): القاعدة مُدَّت، والنواة لم تُمَسّ

### ١) المحاولة الأولى ومقتها (توثيق بلا تجميل)

بدأتُ الإصلاح في `core/contracts/manifest.py` (ملصقٌ واحد يُلْصق كل `config` النسبي
بجذر الـruntime). قياسي قال: `check_project.py` ❌ — «**خرق ختم التجميد (المادة ١/٤١/١٠٠):
الحاجة لتعديل ملفّ داخل `core/` لتشغيل ذرّة = فشل معماري كامل**»، وأنّ `shared/` خارج الختم
بينما `core/` داخله (٢٣ ملفًّا، `Core V1.31.0`). **أرجعتُ `core/` كما كان** (`git checkout`) و
`freeze_core verify` عاد 🟢 بالبصمة `1b0d0f6b91505984…` — لا إعادة ختم، ولا استثناء فحص.

### ٢) ما صار (نمط ٩٠١ نفسه، في طبقة الذرّات)

`shared/runtime_paths.manifest_config_rebase()` (الملكية الوحيدة لمسار الحالة؛ قاعدة واحدة:
المفتاح المنتهي بـ`_path`/`_dir`/`_file` أو المسمّى `dir`، وقيمته تبدأ `var/` أو `var\` →
تُلْصق بـ`runtime_root()`؛ المطلق يمرّ حرفيًّا؛ تعذُّر الحلّ يرجع config كما هو). تُنادى من
مُحوِّل `_rebased_config()` المحلي في كل ذرّة — يبحث عن جذر تشغيل صالح (`…/shared/runtime_paths.py`)
فلا يعود لأيّ `Path.cwd()`.

| الموضع | الحالة |
|---|---|
| ملفات `atom.py` حاملة المُحوِّل (إعادة قياس) | **111** — كل ذرّة تحمل مسارًا نسبيًّا في خمس الأشجار: `atoms/` ٢٦ · `forex_runtime/atoms/` ٢٦ · `atoms_crypto/` ٢١ · `crypto_runtime/atoms/` ١٧ · `crypto_runtime/atoms_crypto/` ٢١ (٩٠١/٢٩٠١ خارج الحساب: يحلّان بمُحوِّل `_resolve_db_path` الخاصّ بهما) |
| كل نداء `_rebased_config` في المستودع | **111/111** بالشكل `cfg = _rebased_config(context.config)` — لا ذاتيّ ولا معلَّق (المسح البرمجي، لا العدّ اليدوي) |
| استيراد `Path` في الحاملة للمُحوِّل | **111/111** (كان ناقصًا في ١٣ ملفًّا فـ`NameError` يسبق الـ`try` — انظر §ح/١٧) |
| `core/` | لم يُمَسّ (الختم سليم) |
| `core/` | لم يُمَسّ (الختم سليم) |
| `shared/runtime_paths.py` | بصمة واحدة `c103d86616ac` في الجذر والـmirrors |
| مفاتيح `var/` النسبية في المانيفستات (إعادة قياس) | **مُعلَّبة 110 · ناقصة 5 · أخطاء ترجمة 0** (الخمسة = ٩٠١/٢٩٠١ في أشجارها، مقصودة) |
| قِياس حيّ بثلاثة أوضاع تشغيل | في كل وضع يرجع المسار من **شجرة الذرّة نفسها** لا من `cwd`: `forex_runtime/atoms/…/712` → `<runtime forex>/var/store/analysis.db`؛ `crypto_runtime/atoms_crypto/…/2712` و`2831` و`2901` → `<runtime crypto>/var/…`؛ ٧٠١ → `…/forex_runtime/var/store/market_data.db`؛ ٥٨٠ → `…/var/store/tilt_rules.db`؛ ٥١٦ → `…/var/store/risk_guard_consumer_516.db`؛ ٥٢٠ → `…/var/reconciliation/desired.json`؛ ١٠٠١ → `…/var/universe_overrides.json` |
| ٥٦٣ `dedupe_db_path` | `/…/forex_runtime/var/store/execution_confirmation.db` (مرّ عبر `cfg` بعد أن كان يقرأ `context.config.get` خامًا) |
| إقلاع حيّ (نواة 8010) | لا fd واحد خارج `<runtime>` — لا شجرة `var/` موازية من الإقلاع |
| ٩٠١ في نفس الإقلاع | يقرأ `forex_runtime/var/governance/commands.db` ✔ |

### ٣) الفحوص بعد التغيير

`validate_atoms` **مخالفات 0 · تحذيرات 20** (أول مسّ لـ٥٦٣ أدخل «رقمًا سحريًا» `[92]` من
`chr(92)` — أُزيل باعتماد `os.sep` لا بإسكات الفاحص) · `check_project` ✅ ·
`check_path_authority` 🟢 rc=0 · `baseline_regen --check` على الجذور الثلاثة: متقادم 0 ·
مزال 0 · مضاف 0 (1313/1313/655) · `test_device_contract` **28 passed** · اختبارات ذرّات
`قسم 701-750` + ٥٦٣: **88 passed** (قِيست قبل الانحدار؛ إعادة القياس في §ح/١٧: **116 passed**) · `tests/backtest`: **244 passed** ·
`check_crypto_isolation`: الأشجار 🟢 (ذرواتها الأربع)؛ الاختلاف الوحيد هو «نواة الكريبتو غير
قابلة للوصول» لأنّي أوقفتُ النواتين لقياس الإقلاع من الصفر.

### ٤) ما لم يُفعَل (دفتر صريح، لا طيّ)

| البند | التفصيل |
|---|---|
| ثوابت احتياطية تحمل `var/` داخل كود ١٨ ذرّة | ٥١٦/٥١٧/٥٢٠/٥٨٠/٦٠١/٦٢٥/٦٣٠/٧١٩/٧٢٠/٨١٠/٨٣١/٨٧٠ و٢٧١٩/٢٧٢٠/٢٨١٠/٢٨٣١ و١٠٠١: تُصلَح بنفس النداء حين تُطلب؛ مسار المانيفست صار مُعلَّبًا فالفعل لا يمرّ من هنا إلا عند غياب المفتاح |
| `var/journal.jsonl` في الجذر (سطر واحد، إقلاع ١٧:50) | طبقة حالة النواة خارج `<runtime>/var` — يُتتبَّع على حدة في `QUANT_CORE_STATE_ROOT` |
| ٦١١/٦١٨/٦١٩ و٤٦٤: `db_path`ويندوزيّ مطلق `C:\Users\NQ\…\nq_brain.db` | لم يُلْصَق عمدًا (المطلق يمرّ كما كُتب) — قرار نشر/جسر، لا تصحيح مسار |
| `backtest/runner.py::_make_context` | يبني `context.config` من yaml خام بلاعلبّة: الذرّات المُعلِّبةتقرأ configالمُعطىلها، فمن يدخل من هنا بمسار نسبي يبقىنسبيًّا — مقصورتحت القياس، غير مُصلَحة في هذهالجولة |
| `prepare_unified.py --verify-only` rc=2 (١٨ انحراف + ٨ نسخ مطابقة حيث الوصلة مُتعاقد عليها) و٢٢٧٠-٢٢٧٧ الغائبة عن `crypto_runtime/atoms_crypto` | ديْن نشر سابق، لم يتغيّر |

## §ح/١٧ — انحدار من صناعة الأدوات (جولة ٢٠): كيف كسرتُ ما أصلحتُه، وبِمَ ثبت الإصلاح

### ١) الانحدار، بلا تجميل

بعد توسيع القاعدة إلى كل الذرّات شغّلتُ سكربت «تنظيف» حذف السطر الذاتي
`cfg = _rebased_config(cfg.config)` (نتاج خلل في أداة الرقعة: نصّ البديل كان يُبنى من
مجموعة المتغيّر المستهدف نفسه). التنظيف حذف السطر **ولم يُعِد ربطه** — فبقي `cfg`
**غير معرَّف** في **23** ملفًّا: `initialize` يرمي `UnboundLocalError` عند الإقلاع، بينما
كل شيء يبقى سليمًا تركيبيًّا: يترجم، ينجح في `validate_atoms`، ويحتوي نصّ
`_rebased_config` فيبحث عنه الفاحص فلا يجد شيئًا. وفي ملفَّي **٢٨٣١** تركت الأداة
`config = _rebased_config(config.config)` كما هي (مُطبِّع الأداة كان يرجع المطابقة نفسها
حين يتساوى اسم المتغيّر ومصدره)، وفي **١٣** ملفًّا كان المُحوِّل يستخدم `Path` بلا
استيراد — و`NameError` ذاك يسبق `try` فلا يبتلعه الحارس.

**الدرس المسجَّل للأدوات:** `py_compile` و`validate_atoms` وبحثٌ نصّيّ عن اسم المُحوِّل —
ثلاثةُها يبقى أخضر على ذرّة مكسورة الإقلاع. معيار القبول الوحيد بعد أي رقعة جماعية هو
**استدعاء `initialize()` فعلًا** على الذرّة، من وضعَيْ تشغيل مختلفَيْن.

### ٢) الترميم (بالترتيب)

| # | الفاعل | الناتج (مقاس) |
|---|---|---|
| ١ | استيراد `from pathlib import Path` بعد `from __future__` مباشرة | **11** ملفًّا، ثم **2** آخران (٥١٨ ومراياها) حين ظهر أن الإقلاع كان يفشل |
| ٢ | `heal.py` يعيد بناء الربط من نسخة HEAD لكل ملفٍ بلا ربط صحيح | **رُتِّم 23 · بلا حيلة 0** |
| ٣ | إصلاح الربط الذاتي في ٢٨٣١ (جذر + مرآة) | `config = _rebased_config(context.config)` في **2** — ومتبقّي الذاتي **0** |
| ٤ | تبيين النصّ المرجعي للمُحوِّل في كل حاملة؛ انكشف أن رقعةً سابقة كانت قد **بترت** جسم الدالة عند أول `return raw_cfg` — أي أنها أبقت **111** ملفًّا بلا نداء `manifest_config_rebase` أصلًا | أُعيدت كتابتها **111/111** · أخطاء الترجمة **0** · مشبوهة البنية (مُحوِّل مكرَّر أو فرق أسطر > ٤٠) **0** |
| ٥ | إقلاع حقيقي بعد الترميم | قبل: بدأت **224** · فشلت **[518, 512]** — و**512** لم يكن مكسورًا (فرقه عن HEAD صفر)، بل انهار تحميلًا على جاره؛ بعد: **226 · فشلت=[] · استُبعدت=[107,256,257,258,625,626,630]** |

### ٣) الفحوص بعد الترميم (كلها أُعيد قياسها في هذه الجولة، لا منسوخة)

| الفحص | الناتج |
|---|---|
| `check_boot.py` | ✅ يطابق auto المكتشفة + التوقع المستقل 233/80 |
| `check_project.py` | ✅ فحص المشروع البنيوي ناجح |
| `validate_atoms` | مخالفات **0** · تحذيرات **20** |
| `baseline_regen --check` | **1313 · 1313 · 655** ومتقادم/مزال/مضاف = **0/0/0** |
| `tests/test_device_contract.py` | **28 passed** |
| اختبارات `atoms/قسم 701-750` + **٥٦٣** (مع عقد الأجهزة في جلسة واحدة) | **116 passed** |
| `tests/backtest` | **244 passed** |
| `freeze_core.py verify` | النواة سليمة — Core V1.31.0 · 23 ملفًّا · `1b0d0f6b91505984…` |
| `check_path_authority` | 🟢 القارئ والواضع على جذر واحد |
| `check_crypto_isolation` (بلا مصادقة) | الاختلاف الوحيد = `get()` لا يرفق `X-API-Key`؛ المفتاح في مخزن الأسرار المشفّر (DPAPI) الذي لا يُفكّ هنا — لا انحراف أشجار |
| نفس الفحص بنسخة مؤمَّنة خارج المستودع (لم يُمَسّ الأصل) | **الاختلافات = 0 🟢** · نواة الكريبتو حيّة **23/23** من شجرتها · لا ذرّة فوركس محمّلة بها · «2160» بقيت ملاحظةً برتقالية لا اختلافًا |
| `/proc/<pid>/fd` لنواتين حيّتين (فوركس 226 ذرّة · كريبتو 23) | فوركس: **6** ملفات حالة كلها داخل `forex_runtime/var/` · كريبتو: **0** · خارج الشجرة **0**، ولا `var/` في جذر المستودع بعد إقلاعَيْن كاملَيْن |

### ٤) انكشافٌ جديد أثناء القياس: فحص الإقلاع ينبت `var/` في الجذر — من HEAD نفسه

`governance/checks/check_boot.py` (السطر ٩٨) يشغّل `governance/scripts/run_core.py`
بـ`cwd=ROOT`، بينما عقد الإقلاع الحقيقي أن `scripts/run_forex.py` يعمل
`os.chdir(ROOT / "forex_runtime")` قبل تحميل الذرّات. على نسخة HEAD نقيّة (worktree) أنتج
ذلك **26 ملفًّا** تحت `var/` في جذر المستودع، منها أسماء بظهرٍ مائل حرفيٍّ
(`var/store\trades.db`، `var/store\decisions.db`) لأن القوالب الاحتياطية في ٦٠١/٥٧٨/٥١٧
تكتب `"var\store\…"`. وبقي الإقلاع الحقيقي (عبر `run_forex.py`) على **0** ملفات في الجذر.
قيست رقعةً من سطر واحد (`cwd=ROOT / "forex_runtime"`) على نسخة خارج المستودع:
**226 ذرّة · فشل 0**، ولم يبقَ في الجذر إلا `journal.jsonl` و`store/analysis_settings.db`
— وهما دفتر §ح/١٦ المعروف (فـ`run_core.py` لا يستورد عقد متغيّرات البيئة الذي يستورده
`run_forex.py`). **لم أطبّق هذا السطر في المستودع** لأنه مسٌّ بفحصٍ حارس — معروض على المالك (خيار **أ** أدناه).

### ٥) ما بقي مفتوحًا كما هو

المعايرة لم تُكتَب (صفر صفوف في `analysis_settings`، و**36** عيارًا جميعها
`scope='global'`) — فالحواجز الستّ ما تزال `NOT_READY` وسلسلة القرار تنتهي
`NO_ELIGIBLE_SIDE`؛ والحاجة إلى `account_id` و`symbol` لتصريح `ACTION_ANALYSIS_SETTINGS`
ليست في أي ملفّ إعداد؛ و`prepare_unified.py --verify-only` rc=2 (١٨ انحرافًا + ٨ وصلات
ناقصة)؛ و`backtest/runner.py::_make_context` يبني `context.config` خامًا؛ وثوابت ١٨ ذرّة
الاحتياطية تحمل `var/` وتُصلَح بنفس النداء عند الطلب.

## §ح/١٨ — طبقة النواة من شقّ المسار (journal/snapshots) + تنفيذ عيارات المالك المقاسة

### ١) أمر المالك وترتيبُه

اختار المالك: **أ ← ب ← قياس الحلقة ← الحكم**. نُفِّذ «أ» (تثبيت مرسى الإقلاع في الفحص)
أوّلًا، ثم قِيست «ب» (المعايرة) ولم تُكتب على عمياء — ما كان قابلًا للطريق القانوني نُفّذ،
وما يحتاج هويّة حساب تُرِك معلنًا.

### ٢) «أ» — فحص الإقلاع صار يقيس الإقلاعَ نفسه

`governance/checks/check_boot.py` (والنسختان في `forex_runtime/` و`crypto_runtime/`،
متطابقة الحبر) كان يُقْلِع `governance/scripts/run_core.py` بـ`cwd=ROOT` وبلا عقد البيئة؛
فكان يُنبت **26 ملفًّا** تحت `var/` جذر المستودع — منها `var/store\trades.db` و
`var/store\decisions.db` (ظهر مائل حرفيٌّ، لأن القوالب الاحتياطية في ٦٠١/٥٧٨/٥١٧ مكتوبة
بهذا الشكل) — ثم يُخبرك أنّ «كلّ شيء سليم». الآن: `cwd` = `QUANT_RUNTIME_ROOT` إن كان صالحًا
وإلا `<ROOT>/forex_runtime` (وإلا الجذر صراحةً كما كان)، ويُمرَّر عقدُ المُقْلِع
`QUANT_CORE_STATE_ROOT=<runtime>/var` و`QUANT_RUNTIME_ROOT=<runtime>` و`QUANT_CORE_CONFIG`.
مقاس: **الإقلاع 226 ذرّة · فشل 0** — و**0** ملفّات في `var/` الجذر بعد الفحص، وjournal الفحص
يقع في `forex_runtime/var/forex/journal.jsonl`. لا تغيير في أي توقّع ولا في منطق الحُكم.

### ٣) انكشافٌ من الطبقة العليا: journal وsnapshots كانا يرسوان على `var/var`

`config/core_forex.yaml` يحمل `journal.path: var/forex/journal.jsonl` و
`snapshot_root: var/forex/snapshots`، بينما `governance/scripts/run_core.py` كان يلصقهما
بـ`state_root` **وهو نفسه مرسى `…/var`** — فالحاصل `<runtime>/var/var/forex/…`. قِيس على
النسخة الحيّة: `forex_runtime/var/var/forex/journal.jsonl` بـ**3460 سطرًا** وعشرات
`snapshots/*.json`، أي أن سجلّ النواة وصورَها كانا في فرع لا يقرأه أحد من اللوحة.
الرُقعة: `_state_join()` في `run_core.py` (الجذر + `forex_runtime` + `crypto_runtime`،
نسخة واحدة حبريًّا) تُقلّم `var/` الأولى عن قيمة الإعداد قبل الإلصاق بمرسى الحالة —
**لم يُمَسّ `core/journal.py`** فهو داخل الختم؛ والنداء من طبقة المُشغِّل غير المُختومة.
بعد الرُقعة: `forex_runtime/var/forex/journal.jsonl` (231 سطرًا عند الإقلاع) و
`crypto_runtime/var/journal.jsonl`، ولا `var/var` في الشجرتين (`ls` رجع فارغًا).

### ٤) «ب» — ما قِيَس من المعايرة، وبأي طريق

| البند | مقياس |
|---|---|
| جدول الأوزان عبر `analysis_setting` | **ممنوع بلا هويّة**: يتطلّب `account_id` و`symbol` (المُحقِّق في `server.py:2666`)؛ ولا مفتاح حساب/رمز في `config/core.yaml` ولا `core_forex.yaml` ولا `core_crypto.yaml` — **معدوم القياس، لم يُخترع** |
| `RISK_DIAL` عند 0.25% | لا خريطة من نسبة مئوية إلى سلَّم 0–100 (حدّ العيار `[0,100]`) — **متروك بمعلَن، لا بتخمين** |
| `DECISION_*` / `ANALYSIS_*` (عيارات قرار محكومة) | طريقها القانوني `POST /gov/command action=decision_setting` (تأكيد بخطوتين ← بوّابة ٩٠١) — لا يحتاج رقم حساب |
| أوامر كُتبت ونُفِّذت | **9**، حصّة `commands.db`: `PENDING → DONE` كلّها؛ `operator=dashboard` (القيمة الافتراضية للمُسجِّل — لم يكن في يدِي اسمُ مشغِّل) |
| العيارات بعد ٩٠١ (من `GET /gov/decision/settings`) | `DECISION_MIN_STRENGTH 45→32` · `DECISION_ELIGIBILITY_MIN_CONFIDENCE 63→56` · `ANALYSIS_FAST_REQUIRED_DEPTH 60→32` · `ANALYSIS_SLOW_REQUIRED_DEPTH 60→32` · `DECISION_LIVE_STALE_AFTER_S 5.0→4.2` · `DECISION_MIN_SCORE 0→52` · `DECISION_BUY_MIN_DIRECTION 50→52` · `DECISION_SELL_MIN_DIRECTION 50→52` — كلٌّ **v1**، و`status=UNAPPROVED` و`source=UNSET` كما هما لصفوف السجلّ (اعتماد `parameter_approve` لم يُزدَّ عليه) |
| الأثر على السلسلة | 452 و458 في `/api/atoms`: `degraded · NO_INPUT_YET` — لا تدفّق أسعار في هذه البيئة؛ `market_data` = **0 سطرًا**. فالحاجز لم يعد المسار ولا العيار، بل **المدخل الحيّ** |

### ٥) الفحوص بعد «أ» و«ب» (كلّها أُعيد تشغيلها على الحالة النهائية)

`check_boot` ✅ (226 · فشل 0) · `check_project` ✅ · `baseline_regen --check` **0/0/0**
(1313 · 1313 · 655) · `validate_atoms` مخالفات **0** · تحذيرات **20** ·
`test_device_contract` **28 passed** · `قسم 701-750` + ٥٦٣ **116 passed** ·
`tests/backtest` **244 passed** · `check_path_authority` 🟢 · `freeze_core verify` 🟢
(Core V1.31.0 · 23 ملفًّا · `1b0d0f6b91505984…`) · `check_crypto_isolation` بنسخة مؤمَّنة
خارج المستودع **الاختلافات = 0** 🟢 · `/proc/<pid>/fd`: فوركس 6 ملفات حالة داخل
`forex_runtime/var/` والكريبتو 0 — **خارج الشجرة 0** · `var/` جذر المستودع **0**.

### ٦) ما لم يُفعَل

* أوزان المحلّلين الخمسة عشر وجدول المعايرة لكل محلّل: يحتاجان `account_id` و`symbol` من المالك.
* نسبة المخاطرة 0.25% (لا خريطة إلى سلَّم العيار) واعتمادٌ موقَّع باسم مشغِّل (`parameter_approve`).
* لوحة كريبتو (8093) موقوفة؛ لذا يبقى بندُها في فحص العزل 🟠 «تعذّر السؤال» (وليس اختلافًا).
* `check_boot` في نسخ `forex_runtime`/`crypto_runtime` منفردة يفشل بـ`ModuleNotFoundError: build_registry`
  — قِيس أنّه يُخفق كذلك بملفّ HEAD (حاله قبل الرُقعة)، فالرُقعة لم تُدخله.
* `prepare_unified.py --verify-only` rc=2؛ `backtest/runner.py::_make_context` بلاعلبة؛ ثوابت ١٨ ذرّة الاحتياطية.

## §ح/١٩ — «ب»: حاولنا إثبات الحلقة بمدخل صناعي — وأين توقفت بالضبط (مقياس، لا استنتاج)

### ١) ما بُني

قاعدة جسر صناعية `/tmp/feed.db` بجدولَيْ `ticks_v2` (الأعمدة الثمانية التي يقرأها ٦١٨:
`id, account_id, symbol, bid, ask, last, volume, tick_ms`) و`symbol_specs_v2` و`account_v2`،
ونواة فوركس مُقْلَعة بـ`NQ_BRIDGE_DB=/tmp/feed.db`، وزارعٌ يدسّ ~٤ ticks/ثانية بحساب
`SYNACC1/‏NQ100` و`bid<ask` و`tick_ms` حيّ (كي يجتاز `utc_gate` الذي يسقُط عنده كل قديم).

### ٢) ما ثبت (وهو كثير)

| المرحلة | مقياس |
|---|---|
| الجسر ← النواة | ٦١٨: `published=586 symbols=1` — قرأ صفحتي industrielle كاملة ونشر `feed.mt5.tick` |
| المحور | ٦١٣: `forwarding 1 symbols via 2 routes` ثم `PROVIDER_DOWN: MT5` بعد انقطاع الزرع (الحارس يعمل كما صُمِّم) |
| الحالة الصحّية للمدخل | ٦١١ `READY_AWAITING_FIRST_MT5_TRADE_EVENT` · ٦١٩ بعد إضافة `account_v2`: لا `no such table` · ٤٦٨ `allowed=1 seen=0 blocked=0` |
| العزل والمسار | لم يَنبُت ولا ملفّ خارج `<runtime>/var`؛ journal وsnapshots في `forex_runtime/var/forex/` |

### ٣) أين توقّفت الحلقة —السببُ سياسةٌ لا عطل

`112 NO_TICKS_YET · 102 NO_TICKS_YET · 103 NO_CANDLES_YET · 150/166 NO_CYCLES_YET ·
401/402 ticks=0 · 452…467 NO_INPUT_YET · market_data=0 · analysis=0`.

القيدة في `613/atom.py:196`: لا يمرّ إلى `market.tick` (مسار المحلّلين) إلّا مزوّدٌ مسموح
صرامةً، و`manifest.config.analyst_sources = ["CTRADER"]` في الشجرتين — فـ**MT5 محصور بقناة
العرض**. وقناة العرض `market.broker_tick` لا مشتركَ لها في الشجرة (محفوظة للوحة)، فلا تدير
الحلقة. وقناةُ `POST /api/events` موصدة **بالحراسة لا بالعطل**: `governance/control_adapter.py`
يُعرِّف `_CONTROL_EVENTS["forex"] = frozenset()` — fail-closed صراحة. وبقي `cryptography`
ناقصًا فأُنجِز (`50.0.1`) لتُنطَق عذرَة ٦٢٢؛ لكنّ ٦٢٢ يحتاج جلسة FIX إلى
`live-uk-eqx-01.p.c-trader.com:5211` بمفتاح سرّ من مخزن الأسرار (`password_secret_key`) —
لا منفذَ لهذين في هذه البيئة، ولا أختلق اعتماديّة وسيط.

**النتيجة بصراحة:** الحلقة مُثبَتة حتى أوّل وصلة سوق، وموصولةٌ من هناك بقناة واحدة فقط
(CTRADER/FIX). لمتابعة الإثبات إلى «قرار» يلزم أحد أمرين **كلاهما تعديلُ سياسةٍ أو بنيةٍ تحت
قرار المالك لا تحت يدي**. وقد رجّعتُ تعديلاً مؤقتًا كنتُ أدخلته على `analyst_sources`
(الشجرتان) بعد القياس — المانيفستتان الآن `["CTRADER"]` حرفيًّا كما كانتا، والفحوص بعد
التراجع: `baseline_regen --check` 0/0/0 · `check_project` ✅ · `var/` الجذر 0.

### ٤) خياران مقيسان ومحدّدا الكلفة

| الخيار | ما يُفعَل | ما يُثبَت | ما يُلط |
|---|---|---|---|
| **١٩-أ** | مُجيب FIX صناعي على `127.0.0.1` + تعديل **موقوت** لـ`host/port` في مانيفست ٦٢٢ (الشجرتان) + سطر سرّ في مخزن اختبارات + `symbols` قائمة على `NQ100` | تدفق `feed.ctrader.tick → 613 → market.tick → 112 → 102/103 → محلّل/قسم → أهلية → قرار` على قناة إنتاجية فعلية | ٣ ملفات تُرجَع بعد القياس؛ مُجيب Fixt F4.2/4.4 بسيط (logon/heartbeat/quote) — ~١٢٠ سطرًا |
| **١٩-ب** | إضافة `MT5` إلى `analyst_sources` في ٦١٣ (الشجرتان) بصفة **دائمة ومنصوصًا عليها**: «جسر الوسيط يُعاين أيضًا» | نفس السلسلة بمدخل الجسر الذي تملكه أنت (نفس ملفّ MT5 الذي يكتبه EA) | **قرار عمل**: MT5 يصير مصدرَ تحليل — يغيّر ما الذي يبني الشموع والأقسام |

> **إغلاق (قرار المالك «ج»)**: لا تعديل سياسة ولا بنية إضافية؛ الحكم النهائي مُثبَّت في `نتائج_الجولة.md` §«قرار الإغلاق (جولة ٢٢)» — الهندسة سليمة من شقّ المسار إلى بوّابة ٩٠١، والمدخل الحيّ عند المالك.

---

## ح/٢٠ — ماذا كشف تشغيلُ ويندوز، ومَن زرع `var/` فعلًا (جولة ٢٣)

المالك شغّل النواتين عندَه فظهرت ثلاث ظواهر: `bind 8010` مرفوض، «لا لوحة تعمل»، و`no such table: ticks_v2 / account_v2`. قِسنا كلًّا منها على الشجرة، لا على الرواية.

### ١) اللوحة: لم تُكسَر — لم تُشغَّل

`scripts/run_forex.py` **يقلع النواة وحدها**. اللوحة يقلعها `governance/unified_hub.py` (منفذ 8090) فوق خادم حوكمة 8092، ولا يستدعيه إلا `scripts/launch_market.py` / `launch_unified.py`. و`governance/ui/built` **موجود** في الشجرة الثلاث (٢٨ ملفًّا لكل نسخة)، فالأصل لا البناء هو المشكلة. رَفْض `bind` سببُه أنَّ المُقلِعَين يمرران `env = dict(os.environ)` ويستخدمان `setdefault` فقط: لو كان `QUANT_CORE_STATE_ROOT` أو `QUANT_RUNTIME_ROOT` مضبوطًا في جلسة المالك من قياسٍ سابق، **لم يدُسّه أحد** — وعندها يورَّث الجذر الخطأ إلى النواة كما هو.

### ٢) الجسر: الجداول ليست مهمّةَ بايثون

ذرّتا 618/619 تقرأان حرفيًّا `C:\Users\NQ\AppData\Roaming\MetaQuotes\Terminal\Common\Files\nq_brain.db`؛ والجداول (`ticks_v2` L370 · `account_v2` L389 · `symbol_specs` L340) **لا ينشئها إلا الإكسبرت** داخل `DatabaseOpen`. فـ«لا يوجد جدول» = الإكسبرت لم يعمل في ذلك المجلد (أو لا يعمل أصلًا — انظر ٤)؛ والحلّ إمّا تشغيلُه، أو تصحيح `db_path` إلى ملفّ المجلد الفعلي. **لم نُنشئ جداول يدويًا ولم نختلق `account_id`.**

### ٣) `var/` الجذر: الفاعل مُثبَت، والحكم السابق كان قاصرًا

حكمُ الجولة ٢٢ («`var/` = ٠») صدق على **سياق الإقلاع** وحده. القياس الجديد: تشغيلُ `pytest atoms/قسم ٥٠١-٥٥٠ atoms/قسم ٥٥١-٦٠٠` من جذر المستودع أنبت ملفَّين حقيقيَّين:

| الملف | الفاعل | الحالة |
|---|---|---|
| `var/store/pair_memory_578.db` | `DEFAULT_PATH` في `قسم 551-600/578_منفذ_التحوط/pair_store.py:20` (ثابت نسبيّ لا يراه `manifest_config_rebase`، والمانيفست بلا `config_schema` يسمح بمفتاح جديد) | **مُصلَح**: `default_path()` يحلّه عبر `shared.runtime_paths.runtime_var` |
| `var/store/risk_outcome_consumer_517.db` | `517/atom.py:101` كان يقرأ `context.config.get("consumer_db_path")` **خامًا** بدل `cfg` المُعلَّب | **مُصلَح**: تُقرأ من `cfg` |
| (سابق) حالة النواة | `shared/runtime_paths.py:248-249` — `return root if root.name not in RUNTIME_VARS else root` | **مُصلَح**: الفرع صار `runtime_root(...) / "var"`؛ القياس الآن: `governance·market=crypto → <ROOT>/crypto_runtime/var` (كان `<ROOT>`) |
| (سابق) `system_alerts.json` | `governance/server.py:851` يحيل `rel` إلى `ROOT.parent` = جذر المستودع حين يُقلَع من الجذر | **مُصلَح**: يُحال إلى `core_state_root()`، والمانيفست يُقرأ من جذر الشجرة |

وأُخرِج **الإقرار**: الحارس المكرّر في `shared/runtime_paths.py` (L184-187) **صنعتْه أداتي** في جولة الرقاعة، لا المالك؛ حُذف. والثابتُ المتعاطي (tautology) في **ملفي** أنا كاتبُه — فوصفُه سابقًا بـ«موجود عند HEAD» كان **غلطي** لأن `shared/runtime_paths.py` نفسه غير متتبَّع (`??`)؛ صُحِّح بالقياس لا بالاعتذار.

### ٤) الإكسبرت: «مكسور بالترجمة» — الترميز لا الصياغة

لا MetaEditor هنا، فلا نقول «سيُترجَم». لكن القياس يحدد الجاني:

| مقياس | القيمة |
|---|---|
| البنية | أقواس متوازنة (١٧٣/١٧٣ · ١٢٤٣/١٢٤٣) · ٥٥ دالة · ١٩١٢ سطرًا — **لا خطأ صياغة ظاهر** |
| الترميز | UTF‑8 **بلا BOM** · LF · ٨٢٤٦ حرفًا غير‑ASCII · **١١٦ نصًّا حرفيًّا فيه عربية** (رؤوس `input group`، `#property copyright/description`، بطاقات الشاشة) |
| تلفٌ سابق | **٢٥٦٣** علامة `?` (تطاير ٦٦ و٥٤ و٤٨ حرفًا) — منها **٧ داخل نصوص تُعرِض رؤوس المجموعات** `??? ? الجسر ???` بدل فواصل زخرفية: الملف كُتِب سابقًا بتحويلٍ خاسر |
| ثلاث نسخ | `mt5/` و`forex_runtime/mt5/` و`crypto_runtime/mt5/` — **بصمة واحدة** `5edb4df2ff7f7550` |

الآلية معروفة: MetaEditor يفكّ UTF‑8 بلا BOM بترميز النظام، وبايتات UTF‑8 العربية قد تُنتج `0x5C` (شرطة مائلة) داخل نصٍّ حرفي فتُتلِف السلسلة — «unknown character»/أخطاء غامضة بلا خطأ صياغة حقيقي. **فلا نلمس الأصل** (قرار نشر)، بل وُلِّدت نسختان فرعيتان مع فحص بنية آليّ:

- `mt5/QUANT_NQ.utf16.mq5` — الرموز نفسها **حرفيًّا** (طُبِّق: يُطابق الأصل بعد التطبيع)، UTF‑16LE + BOM + CRLF، ١٧٤٠٤٠ ب.
- `mt5/QUANT_NQ.ascii.mq5` — ASCII صرف (٠ غير‑ASCII، ١٩١٤ سطرًا CRLF): رؤوس المجموعات مُترجَمة (`--- BRIDGE ---` …)، والنصوص الـ١١٦ مُبدَّلة بجدول؛ توازن الأقواس والدوال والاستدعاءات **مطابق للأصل** (٥٥ دالة · فرق ٠).

### ٥) تباعد كريبتو: النسخة الرسمية **مُحدَّدة بالقياس**، والتباعد أقدم منّا

| الشجرة | ذرّات | ملاحظة |
|---|---|---|
| `atoms_crypto` (المصدر) | **80** | فيها 2270‑2277 |
| `crypto_runtime/atoms_crypto` (الحاملة) | **77** | **هذه ما يُقْلَع**: `run_crypto.py:27-31` يختار `atoms_crypto` إن وُجدت (موجودة)، وإلّا `atoms` |
| `crypto_runtime/atoms` | 80 | لا تُقلَع في سياق المرايا — نسخة احتياطية/للمخطط المسطّح |

الفروق (كلُّها **مطابقة لـHEAD**، أي لا يد لرقاعتنا فيها): مفاتيح 2270‑2277 في المصدر فقط؛ 2160 + 2261‑2264 في الحاملة فقط؛ **١٠ ذرّات مختلفة المحتوى**: 1001 · 2108 · 2153 · 2154 · 2170 · 2615 · 2621 · 2707 · 2719 · 2806 (و2800 تختلف ترميزًا فقط). **والأخطر: النسخة الحاملة أحدث في نصفها** — 2615 تشابه ٠.٠٥٢ (أُعيدت كتابتها في الحاملة على sqlite/os)، 2621 الحاملة v1.4.0 مقابل 1.3.0، 2170 الحاملة v2.0.0 مقابل 1.1.0، بينما 2707 المصدر v4.6.0 مقابل 4.2.0. **فـ«مزج عشوائي» أو «نسخ من المصدر» يُرجع النظام إلى الوراء** — لم يُفعَل، ولا يُفعَل بلا حكم ذرّة‑بذرّة من المالك.

### ٦) حصيلة الفحوص بعد هذه الرقاعات

`check_project` ✅ · `check_boot` 226 · فشل=[] · استُبعدت=[107,256,257,258,625,626,630] · `validate_atoms` **لا مخالفات** · `baseline_regen --check` 0/0/0 (1316·1313·655) · `check_path_authority` 🟢 · pytest (device_contract + 701‑750 + 563 + 551‑600 + backtest) **472 نجحت** · `freeze_core verify` Core V1.31.0 · 23 ملفًّا · `1b0d0f6b91505984…` · **`var/` الجذر = ٠ بعد التشغيل من الجذر ومن الـmirror** · نسخة 578 مُوحَّدة `ATOM_VERSION = "5.4.1"` = المانيفست (في الشجرتين).

---

## ح/٢١ — قياسُ المالك رَدّ على ح/٢٠: الأنماط الثلاثة مُثبَتة، ومُصلَحة، وحارسٌ جديد يرى ما لا يراه أحد

أرفق المالك `تشخيص_var_ويندوز_جولة23.md` (نُسِخ إلى `تقارير_المالك/`). فيه أربع قواعد نبتت تحت `Desktop\ارينا\QUANT_NQ\var\store\` **بعد الفكّ بدقيقة ونصف**، و٢٢ ملفًّا في الحزمة الأصلية بلا `var/` (الحكم ٢: الزيب نظيف). لا ردّ بالتفسير — بل إعادة قياس على حالتنا، ثم إصلاحٌ لكل نمط، ثم **حارس** يسقط لو رجع أيٌّ منها.

### ١) مصادقة قياس المالك على حالتنا (قبل الرقاعة)

| ما قاله المالك | القياس عندي |
|---|---|
| «٧ ملفات تحسب `_rebased_config` ولا تستعمله» | **٥** في حالتي (٥١٧ كان يصلح في تلك اللحظة بالضبط؛ ٧٠١/٢٧٠٢ × نسخها) — الفارق = نسخة ٥١٧ التي أصلحتها في ح/٢٠ |
| «٤ ذرّات بلا معلِّب أصلًا (٧١٦·٧١٧·٢٧١٦·٢٧١٧)» | ✓ صحيح: `helper=False`، ومساراتها في `config.stores[]` **داخل قوائم** — لا يراها معلِّبٌ طبقتُه واحدة |
| «٦٠١ ثابتٌ عمديّ `_CURSOR_DB`» | ✓ `atom.py:19` (قبل): `_CURSOR_DB = "var/store/bridge_cursor_601.db"`؛ والمفتاح `cursor_db` **غائب** عن المانيفست، فالرجوع هو المستعمل دائمًا |
| «٧٠٢ تحسب وتُهمِل ثم تقرأ الخام» | ✓ `atom.py:127` يحسب `cfg` · `:128` يقرأ `context.config["db_path"]` — وهذا حرفيًّا مصدر `var/store/trades.db` النابت |

### ٢) الإصلاح: المالك يعمل مرة واحدة، والذرّة سطرٌ لا نسخة

| الرقاعة | الملفّات |
|---|---|
| `manifest_config_rebase` صار **عائديًّا**: يعبر القواميس والقوائم في أيّ عمق (نفس القاعدة على المفاتيح، والمطلق يمرّ كما هو) | `shared/runtime_paths.py` × ٣ (بصمة واحدة `7ddb950d208e`) → داوى ٧١٦/٧١٧/٢٧١٦/٢٧١٧ **من جذره** |
| حارسٌ مُعلَّب (`_rebased_config`) مُدخَل حيث كان غائبًا، والقراءة من `cfg` بدل `context.config` | ٧١٦/٧١٧ × ٢ شجرتين (٤) · ٢٧١٦/٢٧١٧ × ٣ (٦) · ٧٠٢/٢٧٠٢ (٥) · ٥١٧ (٢) · ٨٣١/٢٨٣١ (٥) |
| مرسى `anchored_state_path` في **مالك المسارات** — لا منطق منسوخ في الذرّات — للثوابت التي «لا يراها المعلِّب بحكم التصميم» | `BARE_*` + سطر واحد في ٦٠١ · ٦٢٥ · ٨٣١ · ٨٧٠ · ٢٨٣١ · `pair_store.py` (٥٧٨) — ١٢ ملفًّا |

ولأنّ المالك وحده يملك الاشتقاق، صُحِّح عيبان فيه قيسا مباشرة: لا رجوع صامتًا إلى `PROJECT_ROOT/var` (كان يُسقط `check_path_authority` 🛑 — صار `runtime_var` وحده مصدرَ الاشتقاق، والفشل **يرفع** `RuntimeError`)؛ ومسارات ويندوز المطلقة (`C:\…`، `\\srv\…`) تمرّ **قبل** تطبيع الفواصل حرفيًّا، لا تُعاد صياغتها.

**درسٌ سُجِّل بالقوة:** رفعتُ `ATOM_VERSION` في ٦٢٥/٨٣١/٨٧٠/٥٧٨ فأنبت الإقلاعُ خطأ `INVALID_ALERT_AGGREGATOR_STATE` — لأنّ `831/restore()` تقارن `state["version"] != ATOM_VERSION` وترفض لقطة أقدم. اللقطة `forex_runtime/var/forex/snapshots/831.json` حُمِلت بـ`1.0.3` منجريْ القياس، فرُجِعت الإصدارات إلى قيم HEAD (كودًا ومانيفستًا) وحُذف الأثر المولَّد، فعاد **226/0**. أي رفعِ إصدارٍ في ذرّةٍ لها لقطةُ حالة = قرارُ ترحيلِ حالة، لا تجميلُ رقم.

### ٣) الحارس الجديد: `governance/checks/check_config_rebase.py`

لا يمسّ الحراس القائمة ولا عقود المانيفست، ويقيس ٦ أنماط على **٤٦٦** ملف ذرّة: م١ ناتجٌ محسوب ومُهمَل · م٢ `…config` خام مع مسارات نسبية · م٣ مسارات متداخلة بلا معلِّب · م٤ ثابتُ وحدة نسبيّ غير مُرسّى · م٥ نسخة مزدوجة · **م٦ مسارٌ يُقرأ من `config` الخام مع وجود معلِّب** — وهو النمط الذي كانت **كلّ** حراس الجولة السابقة عمياء عنه.

أُثبِت أنه لا يصرخ جزافًا ولا يسكت عمدًا: أُعيد زرعُ علّة ٧٠١ (`context.config["db_path"]`) مؤقتًا فسقط بـ`م6` rc=1، وبإرجاعها رجع نظيفًا. (ملاحظة صريحة: أول صيغة للحارس كانت **عمياء** عن هذه العلّة بعينها — لأنّ `cfg` كان «مُستعمَلًا» في سطور أخرى؛ ومن هنا وُلد م٦.)

### ٤) حصيلة هذه الجولة (كلُّ رقم مُعاد تشغيله بعد آخر تعديل)

| الفحص | النتيجة |
|---|---|
| `check_config_rebase` | **لا مخالفات** (٤٦٦ ذرّة) |
| `check_path_authority` | 🟢 القارئ والواضع على جذر واحد، والنسخ مطابقة |
| `check_boot` | **226 · فشلت=[] · استُبعدت=[107,256,257,258,625,626,630]** |
| `validate_atoms` (حكمان) | **لا مخالفات** · مخالفات ٠ / تحذيرات ٢٠ |
| `check_project` | ✅ ناجح |
| `baseline_regen --check` | 0/0/0 (1318 · 1313 · 655) |
| اختبارات | ٤٤٧ (الأقسام الستّة في الجذر) · ٤٨٤ (المرايا + كريبتو + device_contract + backtest) · ٨٠٤ (دفعة مركَّبة) |
| قياس الزراعة النهائي | `pytest` من `cwd=جذر المستودع` على ٦٠١‑٦٥٠/٧٠١‑٧٥٠/٨٠١‑٨٥٠ = **252 نجحت** · `var/` الجذر **0** · متخلّفات `C:/` **0** |
| الثابت | `freeze_core verify` Core V1.31.0 · 23 ملفًّا · `1b0d0f6b91505984…` (لم يُمَسّ) · `SHA256SUMS.txt` نظيف في `git status` |

### ٥) ما لم يُفعَل (بقي مفتوحًا ولا يُخلَط بما أُنجز)

تباعد كريبتو العشر ذرّات (ح/٢٠/٥) — لم يُمَسّ، ولا يُحسَم بلا حكم ذرّة‑بذرّة · ترجمة `QUANT_NQ.mq5` لا تُقاس إلّا في MetaEditor عند المالك (النسختان جاهزتان في `mt5/`) · قرار `analyst_sources` ما زال كما أغلقه المالك في ح/١٩ · النسخ الثلاث من `governance/ui/built` موجودة، فـ«لا لوحة» مسألة مُقلِعٍ/منفذٍ لا بناء.
