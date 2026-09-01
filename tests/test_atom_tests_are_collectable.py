"""حارس: ملفّ اختبار بلا دالّة `test_` لا يُشغَّل — وهو نجاحٌ لا يثبت شيئًا.

المقيس ٢٠٢٦-٠٩-٠١:
    atoms/        238 ملفّ اختبار · 31 بلا أيّ دالّة `test_`
    atoms_crypto/  71 ملفّ اختبار · 22 بلا أيّ دالّة `test_`

هذه الملفّات تحمل `async def main()` وتُشغَّل من `scripts/test_atoms.py`
وحده، فلا يجمعها pytest إطلاقًا. النتيجة: `pytest atoms_crypto` يجمع 237
اختبارًا ويمرّ، بينما 22 ملفًّا لم يُقرأ منها سطر — ومن بينها ملفّات ذرّات
حرجة مثل `552 مدقّق الأمر` و`585 حارس الهامش` و`584 شرعيّة الستوب`.

هذا الحارس لا يصلح الملفّات — يمنع نموّ العدد، ويُبقيها مسمّاة بالعين.
**السقف يهبط ولا يرتفع:** كلّما حُوِّل ملفّ إلى دوالّ `test_` حقيقيّة،
يُنقص الرقم هنا. رفعه يحتاج مبرّرًا مكتوبًا.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DEF = re.compile(r"^\s*(?:async\s+)?def\s+test_", re.MULTILINE)

#: سقف ما هو معروف اليوم. لا يرتفع.
CEILING = {"atoms": 31, "atoms_crypto": 22}


def _uncollectable(tree: str) -> list[str]:
    base = ROOT / tree
    if not base.exists():
        return []
    out = []
    for path in sorted(base.rglob("test_*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not TEST_DEF.search(text):
            out.append(path.relative_to(ROOT).as_posix())
    return out


def test_forex_atom_tests_stay_collectable():
    found = _uncollectable("atoms")
    assert len(found) <= CEILING["atoms"], (
        f"ملفّات اختبار غير قابلة للجمع ارتفعت إلى {len(found)} "
        f"(السقف {CEILING['atoms']}). الجديد منها:\n  " + "\n  ".join(found)
    )


def test_crypto_atom_tests_stay_collectable():
    found = _uncollectable("atoms_crypto")
    assert len(found) <= CEILING["atoms_crypto"], (
        f"ملفّات اختبار غير قابلة للجمع ارتفعت إلى {len(found)} "
        f"(السقف {CEILING['atoms_crypto']}). الجديد منها:\n  " + "\n  ".join(found)
    )


def test_ceiling_is_not_stale():
    """السقف يجب أن يبقى ملتصقًا بالواقع.

    لو هبط العدد الفعليّ ولم يُنقَص السقف، ضاع أثر التقدّم وصار الحارس
    يسمح بالتراجع صامتًا — وهو عين العلّة التي وُضع لمنعها.
    """
    for tree, ceiling in CEILING.items():
        found = len(_uncollectable(tree))
        assert found == ceiling, (
            f"{tree}: العدد الفعليّ {found} والسقف {ceiling} — "
            f"{'أنقص السقف إلى ' + str(found) if found < ceiling else 'ارتفع العدد'}"
        )
