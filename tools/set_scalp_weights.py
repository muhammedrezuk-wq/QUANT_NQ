# -*- coding: utf-8 -*-
"""تطبيق جدولي أوزان المحلّلين (المرحلة C — ورقة Scalping Micro-Tick v3.0) على قاعدة الإعدادات الحيّة.

التشغيل (من داخل مجلد المشروع — والنظام موقوف):
    py set_scalp_weights.py
أو:
    python set_scalp_weights.py

ماذا يفعل:
  1. يفتح قاعدة الإعدادات الحيّة (var/store/analysis_settings.db — أو المسار
     من متغيّر البيئة QUANT_ANALYSIS_SETTINGS_DB إن وُجد).
  2. يكتب جدولَي أوزان الورقة (سريع §10 · بطيء §11-12) دفعةً واحدة لكل
     نطاق (حساب+وسيط+رمز) موجود في القاعدة — بلا إعادة توزيع وبلا مساس
     بالأعماق والعتبات.
  3. يطبع ملخّصًا: كم نطاقًا كُتب، وعلامة النجاح.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _find_project_root(start: Path) -> Path:
    """يصعد من موقع السكربت حتى يجد جذر المشروع (حيث توجد shared/)."""
    candidates = [start, *start.parents]
    cwd = Path.cwd()
    if cwd not in candidates:
        candidates.append(cwd)
    for candidate in candidates:
        if (candidate / "shared" / "live_analysis.py").is_file():
            return candidate
    return start  # لم يُعثر — نستخدم مجلد السكربت نفسه


ROOT = _find_project_root(_HERE)
sys.path.insert(0, str(ROOT))

# ── جدولا الورقة — المرحلة C (config فقط، بختم nq) ────────────────────────
FAST_WEIGHTS = {
    "velocity": 25.0, "momentum": 20.0, "acceleration": 20.0, "spread": 12.0,
    "volatility": 8.0, "noise": 10.0, "volume_quality": 5.0, "volume": 0.0,
    "trend": 0.0, "candle": 0.0, "gap": 0.0, "session": 0.0, "time": 0.0,
    "correlation": 0.0, "relative_strength": 0.0,
}
SLOW_WEIGHTS = {
    "trend": 25.0, "momentum": 15.0, "candle": 15.0, "relative_strength": 10.0,
    "volume_quality": 10.0, "session": 10.0, "gap": 5.0, "correlation": 5.0,
    "time": 5.0, "velocity": 0.0, "acceleration": 0.0, "spread": 0.0,
    "volatility": 0.0, "noise": 0.0, "volume": 0.0,
}


def main() -> int:
    configured = os.environ.get("QUANT_ANALYSIS_SETTINGS_DB")
    db_path = Path(configured) if configured else ROOT / "var" / "store" / "analysis_settings.db"

    # تحقّق مسبق: هل القاعدة موجودة؟
    exists = db_path.exists()
    print(f"[1/3] قاعدة الإعدادات: {db_path}  ({'موجودة' if exists else 'غير موجودة — ستُنشأ'})")

    # اكتشف النطاقات الموجودة (حساب+وسيط+رمز) — لا تخمين
    scopes: list[tuple[str, str, str]] = []
    if exists:
        try:
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    "SELECT DISTINCT account_id, broker, symbol FROM analysis_settings"
                ).fetchall()
            scopes = [tuple(str(x) for x in r) for r in rows]
        except sqlite3.Error as exc:
            print(f"⚠ تعذّر قراءة القاعدة: {exc}")
            return 2

    if not scopes:
        # قاعدة فارغة/جديدة: نكتب للنطاق المرجعي للورقة؛ وعند أول تِكّة حيّة
        # يتكوّن النطاق الفعلي — يُعاد التشغيل بعدها أو تُطبَّق من اللوحة.
        scopes = [("A", "Raw Trading Ltd", "NQ")]
        print("[2/3] لا نطاقات مسجّلة بعد — أكتب للنطاق المرجعي (A · Raw Trading Ltd · NQ)")
        targets = scopes
    else:
        # فضّل نطاقات NQ إن وُجدت (الورقة لـ NQ تحديدًا)
        nq = [s for s in scopes if "NQ" in s[2].upper()]
        targets = nq or scopes
        print(f"[2/3] نطاقات موجودة: {len(scopes)} — سأكتب لـ {len(targets)}"
              + (" (NQ)" if nq else " (كلها)"))

    from shared.live_analysis import AnalysisSettingsStore

    store = AnalysisSettingsStore(str(db_path))
    command_id = f"SCALP-PHASEC-{time.strftime('%Y%m%d-%H%M%S')}"
    changed_at = time.time()

    written = 0
    for account, broker, symbol in targets:
        for path, table in (("fast", FAST_WEIGHTS), ("slow", SLOW_WEIGHTS)):
            store.set_weights(
                account, broker, symbol, table,
                changed_by="NQ", command_id=command_id, changed_at=changed_at,
                path=path,
            )
            written += 1
    print(f"[3/3] ✅ كُتب {written} جدولًا (سريع+بطيء) لـ {len(targets)} نطاقًا "
          f"بأمر {command_id}")

    print("\nالتحقق: افتح اللوحة → إعدادات التحليل — السرعة: velocity 25 · momentum 20 · "
          "acceleration 20 · spread 12 · noise 10؛ البطيء: trend 25 · momentum 15 · "
          "candle 15 · relative_strength 10 · volume_quality 10 · session 10.")
    print("ثم أعد تشغيل النظام بالطريقة المعتادة.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
