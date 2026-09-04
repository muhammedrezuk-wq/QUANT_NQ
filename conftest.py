# -*- coding: utf-8 -*-
"""عزل أسطول الفحوص عن سجل العيارات الحي — يسري على كل جلسة pytest من الجذر.

الدرس (166 المقيس + صيد ٢٦-٠٨): اعتماد المالك الحي (مثل ANALYSIS_SPEED=10)
كان سيُقرأ داخل الفحوص عبر approved_value فتنكسر على قيمة يومه لا على عقدها.
كل جلسة فحص تأخذ سجلًا مؤقتًا فارغًا: الساري داخل الفحوص هو قيم المانيفست
ونقاط التطابق دائمًا، واعتماد المالك يبقى ملكًا للنظام الحي وحده.
"""
import os
import tempfile

# ٢٠٢٦-٠٩-٠٣ (فصل ٢٣ · البند ١٢): بعد أن صار `shared/runtime_paths.py` مالك
# الجذور، «العزل» لا يعني السجلّ وحده — بل جذر التشغيل كلّه. قرصٌ مؤقت واحد
# للجلسة: لا الفحوص تكتب في `forex_runtime/var` الحيّ، ولا قيمُ يوم المالك
# تُقرأ داخل فحصٍ فينكسر عقده.
_TEST_RUNTIME = tempfile.mkdtemp(prefix="nq_runtime_test_")
os.environ.setdefault("QUANT_RUNTIME_ROOT", _TEST_RUNTIME)
os.environ.setdefault("QUANT_CORE_STATE_ROOT", _TEST_RUNTIME)
os.environ.setdefault(
    "QUANT_ANALYSIS_SETTINGS_DB",
    os.path.join(tempfile.mkdtemp(prefix="nq_params_test_"),
                 "analysis_settings.db"))
