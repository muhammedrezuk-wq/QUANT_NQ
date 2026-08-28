# -*- coding: utf-8 -*-
"""تطبيق جدولي أوزان المحلّلين (المرحلة C — ورقة Scalping Micro-Tick v3.0) على قاعدة الإعدادات الحيّة.

التشغيل (من داخل مجلد المشروع — والنظام موقوف):
    py set_scalp_weights.py
أو:
    python set_scalp_weights.py

ماذا يفعل:
  1. يفتح قاعدة الإعدادات الحيّة (var/store/analysis_settings.db — أو المسار
     من متغيّر البيئة QUANT_ANALYSIS_SETTINGS_DB إن وُجد). إن لم تكن الجداول
     موجودة يبنيها (نفس بنية النظام الحيّ تمامًا) ثم يكتب الأوزان.
  2. يكتب جدولَي أوزان الورقة (سريع §10 · بطيء §11-12) دفعةً واحدة لكل
     نطاق (حساب+وسيط+رمز) موجود في القاعدة — بلا إعادة توزيع وبلا مساس
     بالأعماق والعتبات.
  3. يتحقق بالقراءة من القيم المكتوبة ويطبعها، ويفحص وجود قواعد أخرى محتملة
     في المشروع لئلا يكتب في ملفّ ظلّ لا يقرؤه النظام.
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
ALL_ANALYZERS = list(FAST_WEIGHTS.keys())


def _scan_candidate_dbs() -> list[Path]:
    """يفحص المشروع عن كل ملفات قواعد الإعدادات المحتملة (لرصد ملفّ الظلّ)."""
    found: list[Path] = []
    for pattern in ("**/analysis_settings*.db", "**/analysis_settings*.sqlite*"):
        found.extend(p for p in ROOT.glob(pattern) if p.is_file())
    return sorted(set(found))


def main() -> int:
    configured = os.environ.get("QUANT_ANALYSIS_SETTINGS_DB")
    db_path = Path(configured) if configured else ROOT / "var" / "store" / "analysis_settings.db"
    if not db_path.is_absolute():
        db_path = ROOT / db_path

    print(f"[1/4] قاعدة الإعدادات: {db_path}")
    print(f"      (متغيّر البيئة QUANT_ANALYSIS_SETTINGS_DB: "
          f"{configured if configured else 'غير مضبوط — يستخدم الافتراضي'})")

    # ⚠ مهم: نُنشئ المخزن أولًا — منشئه يبني الجداول إن لم تكن موجودة
    # (نفس سلوك النظام الحيّ تمامًا عند إقلاعه).
    from shared.live_analysis import AnalysisSettingsStore

    try:
        store = AnalysisSettingsStore(str(db_path))
    except Exception as exc:  # noqa: BLE001 — نعرض الخطأ ونقف
        print(f"⚠ تعذّر فتح قاعدة الإعدادات: {exc}")
        print("  تأكد أن النظام موقوف، ثم أعد التشغيل. إن تكرر، انسخ نص الخطأ.")
        return 2

    # اكتشف النطاقات الموجودة (حساب+وسيط+رمز) — لا تخمين
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT account_id, broker, symbol FROM analysis_settings"
            ).fetchall()
        scopes = [tuple(str(x) for x in r) for r in rows]
    except sqlite3.Error as exc:
        print(f"⚠ تعذّر قراءة القاعدة بعد البناء: {exc}")
        return 2

    if not scopes:
        scopes = [("A", "Raw Trading Ltd", "NQ")]
        print(f"[2/4] لا نطاقات مسجّلة بعد — أكتب للنطاق المرجعي "
              f"(A · Raw Trading Ltd · NQ) ثم سيتزامن مع النطاق الحيّ عند أول تِكّة.")
    else:
        nq = [s for s in scopes if "NQ" in s[2].upper()]
        targets = nq or scopes
        print(f"[2/4] نطاقات موجودة: {len(scopes)} — سأكتب لـ {len(targets)}"
              + (" (NQ)" if nq else " (كلها)"))
        scopes = targets

    command_id = f"SCALP-PHASEC-{time.strftime('%Y%m%d-%H%M%S')}"
    changed_at = time.time()

    written = 0
    for account, broker, symbol in scopes:
        for path, table in (("fast", FAST_WEIGHTS), ("slow", SLOW_WEIGHTS)):
            store.set_weights(account, broker, symbol, table,
                              changed_by="NQ", command_id=command_id,
                              changed_at=changed_at, path=path)
            written += 1
    print(f"[3/4] ✅ كُتب {written} جدولًا (سريع+بطيء) لـ {len(scopes)} نطاقًا "
          f"بأمر {command_id}")

    # تحقق بالقراءة
    print("[4/4] التحقق بالقراءة:")
    ok = True
    for account, broker, symbol in scopes:
        for path in ("fast", "slow"):
            vals = {a: store.get(account, broker, symbol, a, path)["weight"]
                    for a in ALL_ANALYZERS}
            total = round(sum(vals.values()), 2)
            nonzero = {a: v for a, v in vals.items() if v}
            marker = "✅" if total == 100.0 else "⚠ المجموع ليس 100!"
            if total != 100.0:
                ok = False
            print(f"  {marker} {account} · {broker} · {symbol} · {path}: "
                  f"المجموع={total} → {nonzero}")

    # رصد ملفّات الظلّ
    candidates = _scan_candidate_dbs()
    others = [p for p in candidates if p.resolve() != db_path.resolve()]
    if others:
        print("\n⚠ انتبه — وُجدت قواعد إعدادات أخرى في المشروع (قد يكون النظام يقرأ منها):")
        for p in others:
            print(f"   • {p}")
        print("   إذا ظهرت القيم الجديدة في اللوحة فكل شيء تمام، وإلا أخبرني.")
    else:
        print("\nلا توجد قواعد أخرى — المسار المعتمد وحيد. ✅")

    if not ok:
        print("\n⚠ فشل التحقق — راجع الأرقام أعلاه وأخبرني.")
        return 1
    print("\nتم بنجاح. أعد تشغيل النظام ثم افتح اللوحة → إعدادات التحليل "
          "وتأكد من القيم الجديدة.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
