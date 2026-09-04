"""Start the isolated Forex/MT5+cTrader stack from the unified release."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from governance.network_preflight import validate_market  # noqa: E402

validate_market("forex")

# الجذر القانوني لكلّ حالة حيّة تُديره `shared/runtime_paths.py` (مالك المسارات).
# المتغيّرات الثلاثة هنا هي **عقد الإقلاع** الذي يقرأه المالك: `QUANT_RUNTIME_ROOT`
# (جذر البيانات) و`QUANT_CORE_STATE_ROOT` (journal/snapshots) و
# `QUANT_ANALYSIS_SETTINGS_DB` (سجلّ المعايرة) — ولا مسار يُحسب موازيًا له هنا،
# وإلا خالفه `governance/checks/check_path_authority.py` (البند ٨).

os.chdir(ROOT / "forex_runtime")
os.environ.setdefault("QUANT_CORE_CONFIG", str(ROOT / "config" / "core_forex.yaml"))
# ٢٠٢٦-٠٩-٠٣ (مالك جذور المسارات): الـruntime هو الجذر القانوني لكلّ حالة حيّة
# — data-root (var/)، سجلّ المعايرة، journal، snapshots — فلا يعود أيّ منها
# يعيش تحت جذر المشروع بينما يكتب أخوه داخل الـruntime.
os.environ.setdefault("QUANT_ATOMS_ROOT", str(ROOT / "forex_runtime" / "atoms"))
os.environ.setdefault("QUANT_RUNTIME_ROOT", str(ROOT / "forex_runtime"))
os.environ.setdefault("QUANT_CORE_STATE_ROOT", str(ROOT / "forex_runtime" / "var"))
os.environ.setdefault("QUANT_CORE_DOMAIN", "forex")
os.environ.setdefault("QUANT_ANALYSIS_SETTINGS_DB",
                      str(ROOT / "forex_runtime" / "var" / "store" / "analysis_settings.db"))
os.environ.setdefault("NQ_NEWS_DB", str(Path(os.environ.get("APPDATA", "")) / "MetaQuotes" / "Terminal" / "Common" / "Files" / "nq_brain.db"))
# NQ_BRIDGE_DB مقصوص عمدًا: ذرّات جسر MetaTrader (618/619/601) لازم تقرأ/تكتب
# nq_brain.db في مجلّد MetaTrader المشترك حيث يكتب الـEA، لا bridge.db المعزولة
# الفارغة — تعيينه كان يخفي ticks_v2/account_v2 ويعطب التنفيذ (درس server.py:615).

from governance.scripts.run_core import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
