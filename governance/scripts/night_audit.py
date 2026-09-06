"""تدقيق ليلي شامل — جولة كل ساعة، ثماني جولات.

يفحص ما لا يظهر في التشغيل اليومي: الكود الميت، الثغرات، التسريبات،
جودة الترميز، تطابق الشجرتين، صحّة الحوكمة، ونموّ القرص. كل جولة تُلحق
تقريرها بملف واحد يقرأه المالك صباحًا، وتُبرز **ما تغيّر** عن الجولة
السابقة لا أن تكرّر السرد.

التشغيل: python governance/scripts/night_audit.py [--round N]
"""
from __future__ import annotations

import ast
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "سياق" / "تدقيق_ليلي"
STATE = OUT_DIR / "_state.json"
PY = str(ROOT / "vendor" / "python" / "runtime" / "python.exe")

SKIP_DIRS = {".git", "__pycache__", "node_modules", "vendor", "var",
             ".pytest_cache", ".mypy_cache"}


def _walk_py(base: Path):
    for path in base.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# ─────────────────────────── ١) كود ميت ───────────────────────────

def dead_code() -> dict:
    """دوال ومتغيّرات عليا معرَّفة ولا تُستدعى في المشروع كلّه.

    البحث نصّي عبر الشجرة كاملة — لا يدّعي يقينًا (قد يُستدعى الاسم
    ديناميكيًّا)، فيُصنَّف «مرشَّح» لا «ميت مؤكَّد».
    """
    defined: dict[str, str] = {}
    for path in _walk_py(ROOT / "atoms"):
        if "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if name.startswith("__") or name in (
                        "initialize", "start", "stop", "shutdown",
                        "health_check", "snapshot", "restore"):
                    continue
                defined.setdefault(name, _rel(path))
    haystack = []
    for base in ("atoms", "core", "shared", "governance", "scripts", "tools"):
        for path in _walk_py(ROOT / base):
            haystack.append(path.read_text(encoding="utf-8", errors="replace"))
    blob = "\n".join(haystack)
    candidates = []
    for name, where in defined.items():
        # تعريف واحد + استعمال واحد = التعريف نفسه فقط
        if len(re.findall(r"\b%s\b" % re.escape(name), blob)) <= 1:
            candidates.append({"name": name, "file": where})
    return {"candidates": sorted(candidates, key=lambda x: x["file"])[:60],
            "total": len(candidates), "scanned": len(defined)}


# ─────────────────────────── ٢) ثغرات ───────────────────────────

SECRET_PATTERNS = [
    (r"(?i)(api[_-]?key|secret|password|passwd|token)\s*=\s*['\"][^'\"]{8,}", "سرّ محتمل بنصّ صريح"),
    (r"(?i)aws_(access|secret)_key", "مفتاح AWS"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "مفتاح خاصّ"),
]
RISK_PATTERNS = [
    (r"\beval\s*\(", "eval — تنفيذ نصّ"),
    (r"\bexec\s*\(", "exec — تنفيذ نصّ"),
    (r"pickle\.loads?\s*\(", "pickle — فكّ تسلسل غير آمن"),
    (r"shell\s*=\s*True", "subprocess بـshell=True"),
    (r"verify\s*=\s*False", "TLS بلا تحقّق"),
    (r"execute\s*\(\s*f['\"]", "SQL بسلسلة منسَّقة (حقن)"),
    (r"execute\s*\([^,)]*%\s*[^,)]*\)", "SQL بتنسيق % (حقن)"),
]


def vulnerabilities() -> dict:
    findings = []
    for base in ("atoms", "core", "shared", "governance", "scripts", "tools"):
        for path in _walk_py(ROOT / base):
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern, label in SECRET_PATTERNS + RISK_PATTERNS:
                for m in re.finditer(pattern, text):
                    line = text[:m.start()].count("\n") + 1
                    snippet = text.splitlines()[line - 1].strip()[:100] if line <= len(text.splitlines()) else ""
                    if snippet.lstrip().startswith("#"):
                        continue
                    findings.append({"file": _rel(path), "line": line,
                                     "kind": label, "code": snippet})
    return {"findings": findings[:80], "total": len(findings)}


# ─────────────────────────── ٣) تسريبات ───────────────────────────

def leaks() -> dict:
    """اتصالات وملفات تُفتح بلا إغلاق مضمون (لا with ولا finally)."""
    findings = []
    for base in ("atoms", "core", "shared", "governance"):
        for path in _walk_py(ROOT / base):
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if re.search(r"\b(sqlite3\.connect|open)\s*\(", stripped) \
                        and "with " not in stripped:
                    window = "\n".join(lines[i - 1:i + 14])
                    if ".close()" not in window and "finally" not in window:
                        findings.append({"file": _rel(path), "line": i,
                                         "code": stripped[:100]})
    return {"findings": findings[:60], "total": len(findings)}


# ─────────────────────────── ٤) جودة الترميز ───────────────────────────

def encoding_quality() -> dict:
    bom, syntax = [], []
    for base in ("atoms", "core", "shared", "governance", "scripts", "tools",
                 "forex_runtime/atoms", "forex_runtime/shared"):
        target = ROOT / base
        if not target.exists():
            continue
        for path in _walk_py(target):
            raw = path.read_bytes()
            if raw[:3] == b"\xef\xbb\xbf":
                bom.append(_rel(path))
            try:
                ast.parse(raw.decode("utf-8", errors="replace"))
            except SyntaxError as exc:
                syntax.append({"file": _rel(path), "error": str(exc)[:120]})
    return {"bom": bom, "syntax_errors": syntax}


# ─────────────────────────── ٥) تطابق الشجرتين ───────────────────────────

def tree_parity() -> dict:
    import hashlib
    diff, same = [], 0
    for base, twin_base in (("atoms", "forex_runtime/atoms"),
                            ("shared", "forex_runtime/shared")):
        src_root, twin_root = ROOT / base, ROOT / twin_base
        if not twin_root.exists():
            continue
        for path in _walk_py(src_root):
            twin = twin_root / path.relative_to(src_root)
            if not twin.exists():
                diff.append({"file": _rel(path), "why": "مفقود في المرآة"})
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() != \
                    hashlib.sha256(twin.read_bytes()).hexdigest():
                diff.append({"file": _rel(path), "why": "محتوى مختلف"})
            else:
                same += 1
    return {"identical": same, "different": diff}


# ─────────────────────────── ٦) الحوكمة والاختبارات ───────────────────────────

def run(cmd: list[str], timeout: int = 900) -> tuple[int, str]:
    # ٢٠٢٦-٠٩-٠٦ (مقيس في الجولة الأولى): بلا ضبط الترميز يشغّل
    # subprocess الفحوصَ بترميز النظام (cp1256)، فتنهار كل فحوص الحوكمة
    # التي تطبع عربيةً أو رموزًا (✅ 🟢 ← ١) بـUnicodeEncodeError — فبدت
    # 13/79 خضراء وهي كاذبة: الإخفاق في الطباعة لا في الفحص.
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                              text=True, timeout=timeout, encoding="utf-8",
                              errors="replace", env=env)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as exc:  # noqa: BLE001
        return -2, repr(exc)[:200]


def governance() -> dict:
    out = {}
    checks_dir = ROOT / "governance" / "checks"
    for check in sorted(checks_dir.glob("check_*.py")):
        code, text = run([PY, str(check)], timeout=180)
        last = [ln for ln in text.strip().splitlines() if ln.strip()]
        tail = last[-1][:160] if last else ""
        # فحصٌ يحتاج نواةً حيّة يفشل حتمًا والنظام متوقّف — يُصنَّف
        # «معطَّل» لا «فاشل»، وإلا كذب التقرير على المالك بعدد إخفاقات
        # سببها التوقّف لا الكود.
        needs_live = bool(re.search(
            r"urlopen|10061|غير قابلة للوصول|ConnectionRefused|Connection refused",
            text))
        out[check.stem] = {"ok": code == 0, "tail": tail,
                           "needs_live": needs_live and code != 0}
    return out


def tests() -> dict:
    code, text = run([PY, "-m", "pytest", "atoms", "tests", "-q",
                      "--no-header", "-p", "no:cacheprovider"], timeout=1800)
    summary = ""
    failed = []
    for line in text.splitlines():
        if re.search(r"\d+ (passed|failed)", line):
            summary = line.strip()
        if line.startswith("FAILED "):
            failed.append(line[7:].strip()[:140])
    return {"ok": code == 0, "summary": summary, "failed": failed}


# ─────────────────────────── ٧) القرص والتشغيل ───────────────────────────

def disk() -> dict:
    rows = []
    for name in ("forex_runtime/var", "crypto_runtime", "atoms", ".git",
                 "docs", "forex_runtime/atoms"):
        target = ROOT / name
        if not target.exists():
            continue
        total = 0
        count = 0
        for path in target.rglob("*"):
            if path.is_file():
                try:
                    total += path.stat().st_size
                    count += 1
                except OSError:
                    pass
        rows.append({"path": name, "mb": round(total / 1048576, 1), "files": count})
    return {"dirs": sorted(rows, key=lambda r: -r["mb"])}


def live_state() -> dict:
    out = {"running": False, "account": None, "positions": None,
           "orders_24h": None}
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*run_forex*' } | "
             "Measure-Object).Count"],
            capture_output=True, text=True, timeout=60)
        out["running"] = (proc.stdout or "0").strip() not in ("", "0")
    except Exception:  # noqa: BLE001
        pass
    db = Path(os.environ.get("APPDATA", "")) / "MetaQuotes/Terminal/Common/Files/nq_brain.db"
    if db.exists():
        try:
            conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=8)
            try:
                row = conn.execute("SELECT balance, equity FROM account_v2 LIMIT 1").fetchone()
                if row:
                    out["account"] = {"balance": row[0], "equity": row[1]}
                out["positions"] = conn.execute(
                    "SELECT COUNT(*) FROM positions_v2").fetchone()[0]
                since = time.time() - 86400
                out["orders_24h"] = conn.execute(
                    "SELECT COUNT(*) FROM commands WHERE action='OPEN' AND created_at > ?",
                    (since,)).fetchone()[0]
                out["failed_24h"] = conn.execute(
                    "SELECT COUNT(*) FROM commands WHERE action='OPEN' "
                    "AND status='FAILED' AND created_at > ?", (since,)).fetchone()[0]
            finally:
                conn.close()
        except sqlite3.Error as exc:
            out["db_error"] = str(exc)[:120]
    return out


# ─────────────────────────── التقرير ───────────────────────────

def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rnd = 1
    for i, arg in enumerate(sys.argv):
        if arg == "--round" and i + 1 < len(sys.argv):
            rnd = int(sys.argv[i + 1])
    started = time.time()
    result = {
        "round": rnd,
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dead_code": dead_code(),
        "vulnerabilities": vulnerabilities(),
        "leaks": leaks(),
        "encoding": encoding_quality(),
        "parity": tree_parity(),
        "disk": disk(),
        "live": live_state(),
        "governance": governance(),
        "tests": tests(),
    }
    result["seconds"] = round(time.time() - started, 1)

    prev = load_state()
    STATE.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                     encoding="utf-8")

    lines = []
    a = lines.append
    a(f"\n\n{'=' * 66}")
    a(f"## الجولة {rnd} — {result['at']}  (استغرقت {result['seconds']}ث)")
    a(f"{'=' * 66}\n")

    live = result["live"]
    acc = live.get("account") or {}
    a(f"**التشغيل:** {'يعمل' if live['running'] else 'متوقّف'} · "
      f"الرصيد {acc.get('balance')} · الحقوق {acc.get('equity')} · "
      f"مراكز مفتوحة {live.get('positions')} · "
      f"أوامر ٢٤س {live.get('orders_24h')} (فشل {live.get('failed_24h')})")

    t = result["tests"]
    a(f"\n**الاختبارات:** {t['summary'] or 'لم تكتمل'}")
    for f in t["failed"][:10]:
        a(f"  ✗ {f}")

    gov = result["governance"]
    green = [k for k, v in gov.items() if v["ok"]]
    offline = [k for k, v in gov.items() if not v["ok"] and v.get("needs_live")]
    bad = [k for k, v in gov.items() if not v["ok"] and not v.get("needs_live")]
    a(f"\n**الحوكمة:** {len(green)} خضراء · {len(bad)} فاشلة · "
      f"{len(offline)} تحتاج نظامًا يعمل (النظام "
      f"{'يعمل' if live['running'] else 'متوقّف'})")
    for k in bad[:25]:
        a(f"  ✗ {k}: {gov[k]['tail']}")
    if offline:
        a(f"  ⏸ معطَّلة بالتوقّف: {', '.join(offline[:12])}"
          + (" …" if len(offline) > 12 else ""))

    p = result["parity"]
    a(f"\n**تطابق الشجرتين:** متطابق {p['identical']} · مختلف {len(p['different'])}")
    for d in p["different"][:10]:
        a(f"  ✗ {d['file']} — {d['why']}")

    enc = result["encoding"]
    if enc["bom"] or enc["syntax_errors"]:
        a(f"\n**جودة الترميز:** BOM في {len(enc['bom'])} ملف · "
          f"أخطاء صياغة {len(enc['syntax_errors'])}")
        for b in enc["bom"][:10]:
            a(f"  ✗ BOM: {b}")
        for s in enc["syntax_errors"][:10]:
            a(f"  ✗ {s['file']}: {s['error']}")
    else:
        a("\n**جودة الترميز:** سليمة — لا BOM ولا أخطاء صياغة")

    v = result["vulnerabilities"]
    a(f"\n**الثغرات:** {v['total']} إشارة")
    for f in v["findings"][:12]:
        a(f"  ⚠ {f['file']}:{f['line']} — {f['kind']}")
        a(f"      {f['code']}")

    lk = result["leaks"]
    a(f"\n**تسريبات محتملة (فتح بلا إغلاق مضمون):** {lk['total']}")
    for f in lk["findings"][:10]:
        a(f"  ⚠ {f['file']}:{f['line']} — {f['code']}")

    dc = result["dead_code"]
    a(f"\n**كود ميت مرشَّح:** {dc['total']} من {dc['scanned']} دالّة مفحوصة")
    for f in dc["candidates"][:15]:
        a(f"  · {f['name']}  ←  {f['file']}")

    a("\n**القرص:**")
    for d in result["disk"]["dirs"]:
        a(f"  {d['path']:<26} {d['mb']:>9.1f} MB  ({d['files']} ملف)")

    if prev:
        a("\n**ما تغيّر عن الجولة السابقة:**")
        changed = False
        pt = (prev.get("tests") or {}).get("summary", "")
        if pt != t["summary"]:
            a(f"  الاختبارات: {pt}  →  {t['summary']}"); changed = True
        pv = (prev.get("vulnerabilities") or {}).get("total")
        if pv is not None and pv != v["total"]:
            a(f"  الثغرات: {pv}  →  {v['total']}"); changed = True
        pp = len((prev.get("parity") or {}).get("different", []))
        if pp != len(p["different"]):
            a(f"  اختلاف الشجرتين: {pp}  →  {len(p['different'])}"); changed = True
        pl = (prev.get("live") or {}).get("positions")
        if pl != live.get("positions"):
            a(f"  المراكز المفتوحة: {pl}  →  {live.get('positions')}"); changed = True
        if not changed:
            a("  لا تغيير جوهري.")

    report = OUT_DIR / f"تدقيق_{time.strftime('%Y-%m-%d')}.md"
    with report.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines[-40:]))
    print(f"\n[التقرير: {report}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
