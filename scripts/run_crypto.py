"""Start the isolated Crypto/MEXC stack from the unified release."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRYPTO_RUNTIME = ROOT / "crypto_runtime"
CRYPTO_DATA_ROOT = CRYPTO_RUNTIME / "var"
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from governance.network_preflight import validate_market  # noqa: E402

validate_market("crypto")

# الجذر القانوني لكلّ حالة حيّة تُديره `shared/runtime_paths.py` (مالك المسارات).
# المتغيّرات الثلاثة هنا هي **عقد الإقلاع** الذي يقرأه المالك: `QUANT_RUNTIME_ROOT`
# (جذر البيانات) و`QUANT_CORE_STATE_ROOT` (journal/snapshots) و
# `QUANT_ANALYSIS_SETTINGS_DB` (سجلّ المعايرة) — ولا مسار يُحسب موازيًا له هنا،
# وإلا خالفه `governance/checks/check_path_authority.py` (البند ٨).

os.chdir(CRYPTO_RUNTIME)
os.environ.setdefault("QUANT_CORE_CONFIG", str(ROOT / "config" / "core_crypto.yaml"))
_crypto_atoms = CRYPTO_RUNTIME / "atoms_crypto"
if not _crypto_atoms.is_dir():
    # نسخة الـmirror تحمل الذرّات تحت atoms/ كما في فوركس
    _crypto_atoms = CRYPTO_RUNTIME / "atoms"
os.environ.setdefault("QUANT_ATOMS_ROOT", str(_crypto_atoms))
os.environ.setdefault("QUANT_RUNTIME_ROOT", str(CRYPTO_RUNTIME))
os.environ.setdefault("QUANT_CORE_STATE_ROOT", str(CRYPTO_DATA_ROOT))
os.environ.setdefault("QUANT_CORE_DOMAIN", "crypto")
# ختم NQ 2026-09-01: كل قراءة وكتابة خاصة بالكريبتو تعيش تحت runtime نفسه.
# ٢٠٢٦-٠٩-٠٣ (المالك): تحت var/store/ تحديدًا — نفس عقد الفوركس بلا تفريع.
os.environ.setdefault("QUANT_ANALYSIS_SETTINGS_DB",
                      str(CRYPTO_DATA_ROOT / "store" / "analysis_settings.db"))
os.environ.setdefault("NQ_NEWS_DB", str(CRYPTO_DATA_ROOT / "news.db"))
os.environ.setdefault("NQ_BRIDGE_DB", str(CRYPTO_DATA_ROOT / "bridge.db"))

from governance.scripts.run_core import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
