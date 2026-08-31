"""Start the isolated Crypto/MEXC stack from the unified release."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from governance.network_preflight import validate_market  # noqa: E402

validate_market("crypto")

os.chdir(ROOT / "crypto_runtime")
os.environ.setdefault("QUANT_CORE_CONFIG", str(ROOT / "config" / "core_crypto.yaml"))
os.environ.setdefault("QUANT_ATOMS_ROOT", str(ROOT / "atoms_crypto"))
os.environ.setdefault("QUANT_CORE_DOMAIN", "crypto")
os.environ.setdefault("QUANT_ANALYSIS_SETTINGS_DB", str(ROOT / "var" / "crypto" / "analysis_settings.db"))
os.environ.setdefault("NQ_NEWS_DB", str(ROOT / "var" / "crypto" / "news.db"))
os.environ.setdefault("NQ_BRIDGE_DB", str(ROOT / "var" / "crypto" / "bridge.db"))

from governance.scripts.run_core import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
