"""اختبارات بوّابات الأمن — اختبار فشل واختبار نجاح لكل بوّابة.

سبب وجود هذا الملفّ (مقيس ٢٠٢٦-٠٩-٠١):
تقرير إغلاق بوّابة الإنتاج وجد **صفر** اختبار يمسّ المصادقة أو الربط الخارجيّ،
رغم 63 ملفّ اختبار و896 اختبارًا ناجحًا. والأسوأ: الاختبارات القائمة كانت
**تثبّت الثغرة** بدل كشفها — `test_network_contract.py` يشترط
`host == "0.0.0.0"` بلا أي اختبار يثبت أنّ ذلك الربط محميّ بمفتاح.

القاعدة هنا: لكل بوّابة اختباران — واحد يسقط حين تكون مفتوحة، وواحد يمرّ حين
تُغلق. بوّابة باختبار واحد ليست مُثبتة.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    """تحميل وحدة من مسارها مباشرةً — الملفّان خارج حزمة مستوردة."""
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ─────────────────────────── بوّابة اللوحة (P0-03) ───────────────────────────

def _hub(monkeypatch, *, host: str | None, key: str | None):
    for var in ("QUANT_HUB_HOST", "QUANT_HUB_KEY",
                "QUANT_CORE_API_KEY", "QUANT_GOV_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    if host is not None:
        monkeypatch.setenv("QUANT_HUB_HOST", host)
    if key is not None:
        monkeypatch.setenv("QUANT_HUB_KEY", key)
    return _load("hub_under_test", "governance/unified_hub.py")


def test_hub_defaults_to_loopback(monkeypatch):
    """اختبار نجاح: بلا إعداد، اللوحة محلّيّة — لا تُنشر على الشبكة."""
    hub = _hub(monkeypatch, host=None, key=None)
    assert hub._bind_host() == "127.0.0.1"
    assert hub._is_external_bind() is False


def test_hub_refuses_external_bind_without_key(monkeypatch):
    """اختبار فشل: ربط على كل الواجهات بلا مفتاح ⇒ لا يقلع.

    قبل ٢٠٢٦-٠٩-٠١ كان يقلع صامتًا: `QUANT_HUB_HOST` افتراضه `0.0.0.0`
    وصفر فحص مصادقة — وكيل مفتوح يمرّر `/gov` و`/api` إلى خادمي السوقين.
    """
    hub = _hub(monkeypatch, host="0.0.0.0", key=None)
    assert hub._is_external_bind() is True
    assert hub.HUB_KEY == ""
    with pytest.raises(SystemExit) as exc:
        hub.main()
    assert "QUANT_HUB_KEY" in str(exc.value)


def test_hub_accepts_external_bind_with_key(monkeypatch):
    """اختبار نجاح: المفتاح موجود ⇒ لا يعترض على الربط الخارجيّ."""
    hub = _hub(monkeypatch, host="0.0.0.0", key="s3cr3t")
    assert hub._is_external_bind() is True
    assert hub.HUB_KEY == "s3cr3t"


class _FakeRequest:
    """أدنى ما يلزم لفحص `_authorized` بلا فتح مقبس."""

    def __init__(self, hub, *, client: str, headers: dict[str, str], path: str = "/"):
        self.client_address = (client, 0)
        self.headers = headers
        self.path = path
        self._hub = hub

    def _client_is_local(self) -> bool:
        return self._hub.HubHandler._client_is_local(self)

    def authorized(self) -> bool:
        return self._hub.HubHandler._authorized(self)


def test_hub_denies_remote_client_without_key(monkeypatch):
    """اختبار فشل: عميل من الشبكة بلا مفتاح ⇒ يُرفض."""
    hub = _hub(monkeypatch, host="0.0.0.0", key="s3cr3t")
    assert _FakeRequest(hub, client="192.168.1.50", headers={}).authorized() is False


def test_hub_denies_remote_client_with_wrong_key(monkeypatch):
    """اختبار فشل: مفتاح خاطئ ⇒ يُرفض."""
    hub = _hub(monkeypatch, host="0.0.0.0", key="s3cr3t")
    request = _FakeRequest(hub, client="192.168.1.50",
                           headers={"X-API-Key": "wrong"})
    assert request.authorized() is False


def test_hub_allows_remote_client_with_correct_key(monkeypatch):
    """اختبار نجاح: مفتاح صحيح بالترويسة ⇒ يمرّ."""
    hub = _hub(monkeypatch, host="0.0.0.0", key="s3cr3t")
    request = _FakeRequest(hub, client="192.168.1.50",
                           headers={"X-API-Key": "s3cr3t"})
    assert request.authorized() is True


def test_hub_always_allows_loopback_client(monkeypatch):
    """اختبار نجاح: العميل المحلّي لا يتغيّر سلوكه — اللوحة تبقى تعمل بلا مفتاح."""
    hub = _hub(monkeypatch, host="0.0.0.0", key="s3cr3t")
    assert _FakeRequest(hub, client="127.0.0.1", headers={}).authorized() is True


# ──────────────────── بوّابة ربط النواة الخارجيّ (P0-01) ────────────────────

def test_core_refuses_external_bind_without_key_in_source():
    """اختبار فشل: مسار الإقلاع يجب أن **يرفع**، لا أن يحذّر ويمشي.

    قبل ٢٠٢٦-٠٩-٠١ كان `log.warning` ثمّ يفتح المنفذ. النواة تعمل 16.5 ساعة
    بمفسّر ومسار غير مقصودين هي حادثة مقيسة، لا فرضيّة.
    """
    source = (ROOT / "governance" / "scripts" / "run_core.py").read_text(encoding="utf-8")
    guard = source.split('if api_key is None and host != "127.0.0.1":')[1][:600]
    assert "raise RuntimeError" in guard, "الربط الخارجيّ بلا مفتاح يجب أن يوقف الإقلاع"
    assert "log.warning" not in guard, "التحذير وحده لا يغلق بوّابة أمن"


def test_local_mode_still_binds_loopback_without_key():
    """اختبار نجاح: الوضع المحلّي يبقى بلا مفتاح — الأزرار لا تنكسر."""
    source = (ROOT / "governance" / "scripts" / "run_core.py").read_text(encoding="utf-8")
    assert 'QUANT_LOCAL_MODE' in source
    assert '"127.0.0.1" if local_mode' in source


# ─────────────────── بوّابة ورقيّ/حيّ في مسار الفوركس (P0-04) ───────────────────

def test_bridge_writer_defaults_execution_mode_to_paper():
    """اختبار فشل: أمر بلا وضع صريح يجب ألّا يصير حيًّا."""
    atom = (ROOT / "atoms" / "قسم 601-650" / "601_كاتب_جسر_الدماغ" / "atom.py").read_text(encoding="utf-8")
    assert "execution_mode TEXT NOT NULL DEFAULT 'PAPER'" in atom
    assert '"PAPER"' in atom and 'exec_mode not in ("PAPER", "LIVE")' in atom


def test_expert_advisor_gate_is_two_key_and_fail_closed():
    """اختبار فشل: التنفيذ الحيّ يلزمه مفتاحان، والفراغ يسقط إلى ورقيّ."""
    ea = (ROOT / "mt5" / "QUANT_NQ.mq5").read_text(encoding="utf-8", errors="replace")
    assert 'input string InpExecutionMode = "PAPER"' in ea, "افتراض الإكسبرت يجب أن يكون ورقيًّا"
    assert 'if(cmd_exec_mode == "") cmd_exec_mode = "PAPER"' in ea, "الفراغ يجب أن يسقط إلى ورقيّ"
    assert 'InpExecutionMode != "LIVE" || cmd_exec_mode == "PAPER"' in ea, "يلزم مفتاحان معًا"
    assert "PAPER_SKIPPED" in ea, "الوضع الورقيّ يجب أن يتخطّى التنفيذ لا أن ينفّذ"


def test_expert_advisor_has_no_unterminated_string():
    """اختبار فشل: نصّ غير مغلق يمنع التجميع — والبوّابة تصير حبرًا.

    مقيس ٢٠٢٦-٠٩-٠١: السطر 408 فتح نصًّا ولم يغلقه، فما كان الإكسبرت
    ليُجمَّع أصلًا — أي أنّ بوّابة ورقيّ/حيّ كانت مكتوبة وغير موجودة.
    """
    ea = (ROOT / "mt5" / "QUANT_NQ.mq5").read_text(encoding="utf-8", errors="replace")
    offenders = []
    for number, line in enumerate(ea.splitlines(), start=1):
        if line.lstrip().startswith("//"):
            continue
        if line.replace('\\"', "").count('"') % 2:
            offenders.append(number)
    assert not offenders, f"نصوص غير مغلقة بالأسطر: {offenders}"
