"""
Core.event_bus
================
Article 10 (+ Article 7 في الدستور الأول): يعرف الأحداث فقط، لا الذرات.
لا يسمح بالتواصل المباشر بين الذرات (Article 23) — كل تواصل يمر من هنا.

ضمانات المادة 89 (حظر تعطيل الـ Event Bus المشترك):
  * كل معالج يُنفَّذ معزولًا: استثناؤه يُلتقط ولا يمسّ بقية المشتركين.
  * كل معالج محكوم بمهلة قصوى (`dispatch_timeout_s`).
  * كل مشترك يستلم **نسخته الخاصة** من الحمولة (المادة 30/35).

ضمان المادة 31: تُحقن الحقول المعيارية تلقائيًا إن غابت.

—— فتحة النواة V2.0 (أوراق ٠٢–٠٥) ——
  ٠٢ العيون: عدّادات خام لكل حدث (نُشر/سُلِّم/بلا مشترك/مهلة/خطأ/أُعيد/أُسقط)
     + `stats()` لقطة قراءة فقط. النواة تقيس حقائق خام، وطبقة ٢ تفسّرها.
  ٠٣ الحالة عند الاشتراك: الناقل يحفظ آخر حدث "حالة" ويعيده فورًا لأي مشترك
     جديد — فالمتأخّر ما يفوته آخر حالة (جذر 619→651→413). الأوامر لا تُعاد أبدًا.
  ٠٤ وراثة الأثر: كل حدث يرث أثر أبيه (`trace_id`) ويسجّل أباه (`event_id`/
     `parent_event_id`) → شجرة سببية بدل ٢٥٠ حدثًا مقطوعًا.
  ٠٥ الساعة: ختم الناقل = الوقت المصحّح (خام + إزاحة ٦٠٨)، ولا يدوس وقت مصدر خارجي.
  ١١ firehose: `subscribe_all` يبثّ كل حدث خام لطبقة ٢ (برّا العملية) بلا تفسير؛
     وتوسيع ٠٣: المشترك على الكل ياخد آخر حالة عند الاتصال (لا تفضى اللوحة)، وحارس
     أوامر يمنع إعادة أي أمر (تنفيذ مزدوج) حتى لو سُمّي بلاحقة حالة.

—— فتحة النواة V3.0 (ختم nq · 2026-08-25) — صناديق البريد ——
  الجذر المقيس: `publish` كان ينتظر **كل** مشتركيه (`gather`) وقفلَ كلِّ
  معالج — فمستمع بطيء واحد (مقيس: 30ث × ثلاث ذرّات تخزين) يحبس الناشر،
  والناشر المحبوس هو تغذية السوق نفسها: مخزن 622 يتسمّر على عتبته ويرمي
  (مقيس: 88 م.ب مرميّة في جلسة واحدة). العلاج نفس قانون التغذية المعتمد
  «الخطّ الحيّ لا يحمل خلفية — قفزة وإعلان»:
  * لكل معالج **صندوق بريد** واحد (طابور + مستهلك واحد): النشر إيداعٌ فوريّ
    لا انتظار، والمستهلك يسلّم بالترتيب — نفس تسلسل القفل القديم حرفيًّا
    (صندوق واحد للمعالج مهما تعدّدت أحداثه) بلا حجز للناشر.
  * المهلة والعزل كما هما: المعالج المتجاوز يُعزل ويُعدّ ولا يعطّل غيره.
  * صندوق ممتلئ يقفز لذيله: يُسقط **الأقدم** ويعدّه (`dropped`) — معلَنًا
    في `stats()`، لا صمت. **الأوامر لا تُسقَط أبدًا** (نفس حارس ٠٣/١١:
    أي أثر "أمر" باسم الحدث ⇒ صندوق بلا سقف).
  * `drain()` للفحوص: ينتظر فراغ كل الصناديق — الفحص يقيس بعد التسليم لا
    بعد الإيداع.

—— V3.1 (ختم nq · 2026-08-25) — تقنين التنازل ——
  التنازل التعاونيّ بعد كل نشرة كان يحدّ أسرع ناشر بسرعة دورة الطابور
  (مقيس: ٩ رسائل/ثانية لمضخة FIX على حلقة مشغولة → فيضان النقل ورمي
  868KB/70ث بلا انقطاع شبكة). صار التنازل مرّة كل نافذة زمنية قصيرة
  (`_YIELD_EVERY_S`) — الدفعة تُودَع كاملة والحلقة تأخذ دورها في حدّها.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import inspect
import pickle
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from core.logger import current_event, current_event_id, current_trace_id

Handler = Callable[[dict[str, Any]], Awaitable[None] | None]
GlobalHandler = Callable[[str, dict[str, Any]], Awaitable[None] | None]

_log = logging.getLogger("quant_nq.core.event_bus")

DEFAULT_DISPATCH_TIMEOUT_S = 30.0
#: سقف صندوق بريد المعالج للأحداث غير الأمرية. عند الامتلاء يُسقَط الأقدم
#: ويُعدّ — القفزة معلَنة دائمًا عبر stats()["dropped"].
DEFAULT_MAILBOX_MAX_EVENTS = 1024
#: V3.1: نافذة التنازل التعاونيّ — الناشر يعطي الحلقة الدورَ مرّة كل هذه
#: النافذة كحدّ أقصى، لا بعد كل نشرة (القياس في _maybe_yield).
_YIELD_EVERY_S = 0.002
#: V3.1 (مراجعة عدائية 2026-08-25): علامة ضغط الصناديق — صندوقٌ بلغ نصف
#: سقفه أثناء دفعة نشر يفرض تنازلًا فوريًّا بلا انتظار النافذة، فالمستهلك
#: يلاحق الناشر قبل أن يبدأ الطرد. مقيس قبل العلاج: مستهلك بطيء تحت دفعة
#: 300ms فقد 93.6% من وقائعه (الأقدم يُطرد قبل أن يأخذ دورًا واحدًا)،
#: وصندوق أوامر بلا سقف تضخّم 16 ضعفًا في الذاكرة خلال الدفعة نفسها.
_PRESSURE_MARK = DEFAULT_MAILBOX_MAX_EVENTS // 2

# ورقة ٠٣ (موسّعة بورقة ١١): معيار "الحالة" معماري باللاحقة لا بقائمة أسماء يدوية.
# المنتهي بلاحقة حالة = حقيقة راهنة تُعاد للمتأخّر، فلا تفضى اللوحة عند الفتح.
_STATE_SUFFIXES = (".state", ".synced", ".snapshot")

# حارس أمان (خطّ أحمر): الأوامر (فعل يُطلق: تنفيذ/شراء/بيع/أمر) لا تُخزَّن ولا
# تُعاد **أبدًا**، حتى لو طابق اسمها لاحقة حالة بالغلط — إعادة أمرٍ لمشترك متأخّر
# (ذرة تنفيذ أُعيد تشغيلها) = تنفيذ مزدوج. نميل للأمان: أي أثر "أمر" باسم الحدث
# → غير قابل للإعادة قطّ، وغير قابل للإسقاط من صندوق بريد ممتلئ.
_COMMAND_MARKERS = (
    "order", ".buy", ".sell", ".execute", ".cancel",
    "final_decision", "command", ".submit", ".send",
)


# V3.1: تصنيف الاسم يُحسب مرّة واحدة لكل اسم — مقيس py-spy ‏2026-08-25:
# مسح سلاسل _COMMAND_MARKERS على كل نشرة أكل 36% من الخيط الرئيسي تحت
# السيل المتحرّر (762 عيّنة/8ث، 275 منها في هذا المسح). أسماء الأحداث
# مجموعة مغلقة صغيرة فالذاكرة محدودة بطبيعتها، وحارس السقف يفرّغها إن
# ولّد خللٌ أسماء بلا حدّ — التصنيف نفسه لم يتغيّر حرفًا.
_NAME_CLASS_CACHE: dict[str, tuple[bool, bool]] = {}
_NAME_CLASS_CACHE_MAX = 4096


def _classify_name(event_name: str) -> tuple[bool, bool]:
    cached = _NAME_CLASS_CACHE.get(event_name)
    if cached is None:
        command = any(marker in event_name for marker in _COMMAND_MARKERS)
        replayable = event_name.endswith(_STATE_SUFFIXES) and not command
        if len(_NAME_CLASS_CACHE) >= _NAME_CLASS_CACHE_MAX:
            _NAME_CLASS_CACHE.clear()
        cached = (command, replayable)
        _NAME_CLASS_CACHE[event_name] = cached
    return cached


def _is_command(event_name: str) -> bool:
    return _classify_name(event_name)[0]


def _fast_copy(value: Any) -> Any:
    """نسخة مستقلة كاملة لحمولة الحدث بسرعة C (جولة pickle) بدل كلفة
    `copy.deepcopy` (memo وبروتوكولات reduce بحلقات بايثون). ضمانة المادة
    30/35 كما هي: كل مشترك يستلم نسخته الخاصة — وما يعجز pickle عنه يسلك
    مسار deepcopy الكامل. (مقيس py-spy‏ 2026-08-19: النسخ العميق كان يأكل
    ثلث وقت الحلقة تحت تدفّق سبعة رموز، ونسخة تكرار بايثون أبقت ~29% —
    جولة pickle تنزل بها إلى قرابة العُشر.)"""
    try:
        return pickle.loads(pickle.dumps(value, pickle.HIGHEST_PROTOCOL))
    except Exception:  # noqa: BLE001 — حمولة غير قابلة للتسلسل: الضمانة الكاملة
        return copy.deepcopy(value)


def _is_replayable(event_name: str) -> bool:
    return _classify_name(event_name)[1]


def _coalesce_key(event_name: str, payload: Any) -> tuple:
    """مفتاح دمج الحالة: الاسم + نطاق الحمولة — لا يُدمَج عبر النطاقات.

    الحقول المعياريّة للنطاق في هذا المشروع: الحساب والرمز، ثم هويّة
    الجهة الناطقة إن حملتها الحمولة (قسم/محلّل/معرّف). حمولة بلا نطاق
    تُدمَج على الاسم وحده — سلوك 1.19.0 نفسه."""
    if not isinstance(payload, dict):
        return (event_name,)
    return (event_name,
            str(payload.get("account_id") or ""),
            str(payload.get("symbol") or ""),
            str(payload.get("section_id") or payload.get("analyzer_id")
                or payload.get("strategy_id") or payload.get("id") or ""))


@dataclass(slots=True)
class _Subscription:
    handler: Handler
    subscriber: str = ""
    # يُحسب مرة واحدة عند الاشتراك: فحص iscoroutinefunction انعكاسٌ غير رخيص
    # كان يجري مع **كل تسليم** (مقيس ضمن حِمل آلية التسليم 2026-08-19).
    is_coro: bool = False
    # V3.1 (فتحة nq الممتدة): عهد القراءة فقط — مشترك يُعلن صراحةً أنه
    # يقرأ ولا يعدّل يستلم المرجع بلا نسخة (تعميم عهد subscribe_all على
    # الاشتراك العادي). الافتراضي يبقى النسخة المعزولة (المادة 30/35).
    isolate: bool = True


@dataclass(slots=True)
class _Mailbox:
    """صندوق بريد معالج واحد — الطابور، الموقظ، ومهمّة المستهلك."""
    queue: deque = field(default_factory=deque)
    wakeup: asyncio.Event | None = None
    task: asyncio.Task | None = None
    busy: bool = False


class EventBus:
    def __init__(self, *, dispatch_timeout_s: float = DEFAULT_DISPATCH_TIMEOUT_S,
                 mailbox_max_events: int = DEFAULT_MAILBOX_MAX_EVENTS) -> None:
        self._subscribers: dict[str, list[_Subscription]] = defaultdict(list)
        self._dispatch_timeout_s = dispatch_timeout_s
        self._mailbox_max_events = max(1, int(mailbox_max_events))
        # ٠٥: النواة تحمل إزاحة (لا ساعة). صفر = سلوك اليوم بالضبط قبل أي مزامنة.
        self._time_offset_s = 0.0
        # ٠٣: آخر حدث "حالة" منشور لكل اسم — يُعاد للمشترك الجديد.
        self._last_event: dict[str, dict[str, Any]] = {}
        # ٠٢: عدّادات خام (defaultdict لتفادي KeyError، تُقرأ عبر stats فقط).
        self._published: dict[str, int] = defaultdict(int)
        self._delivered: dict[str, int] = defaultdict(int)
        self._no_subscribers: dict[str, int] = defaultdict(int)
        self._timeout: dict[str, int] = defaultdict(int)
        self._error: dict[str, int] = defaultdict(int)
        self._replayed: dict[str, int] = defaultdict(int)
        # V3.0: المُسقَط من صناديق بريد ممتلئة — قفزة معلَنة، لا صمت.
        self._dropped: dict[str, int] = defaultdict(int)
        # V3.1: المدموج (حالةٌ حلّت محلّ أقدم منها في صندوق لم يُسلَّم) — معلَن.
        self._coalesced: dict[str, int] = defaultdict(int)
        # ورقة ١١ (firehose): مشتركو "الكل" — يستلمون كل حدث خام (اسم+حمولة)،
        # لطبقة ٢ (الحوكمة) تبثّها برّا العملية. النواة تبقى غبية: تمرّر بلا تفسير.
        # العنصر الثالث: هل يستلم نسخة خاصة (المادة 30/35) أم المرجع نفسه —
        # «بلا نسخة» حصرًا لمشترك يقرأ ولا يعدّل (بثّ اللوحة الذي يرمّز فقط).
        # الرابع: هل المعالج دالّة coroutine (محسوب مرة عند الاشتراك).
        self._global_subscribers: list[tuple[GlobalHandler, str, bool, bool]] = []
        # V3.0: صندوق بريد لكل معالج (بمعرّف الكائن) — يحفظ ترتيب التسليم
        # لنفس المعالج عبر كل أحداثه، وهو بالضبط ما كان قفل المعالج يضمنه،
        # لكن بلا حبس للناشر.
        self._mailboxes: dict[int, _Mailbox] = {}
        # V3.1: آخر تنازل تعاونيّ — التنازل مُقنَّن زمنيًّا لا لكل نشرة (انظر
        # _maybe_yield)، وعلامة الضغط تفرضه فورًا عند احتقان صندوق.
        self._last_yield: float = 0.0
        self._yield_pressure: bool = False
        # عدّاد تسجيلات كل معالج (بمعرّف الكائن): كائن المعالج محفوظ في الاشتراك
        # نفسه فلا يُجمَع ولا يُعاد استعمال معرّفه ما دام مسجّلًا.
        self._handler_refs: dict[int, int] = {}

    def _handler_ref_add(self, handler_id: int, count: int = 1) -> None:
        self._handler_refs[handler_id] = self._handler_refs.get(handler_id, 0) + count

    def _handler_ref_drop(self, handler_id: int, count: int = 1) -> None:
        remaining = self._handler_refs.get(handler_id, 0) - count
        if remaining > 0:
            self._handler_refs[handler_id] = remaining
        else:
            self._handler_refs.pop(handler_id, None)
            self._retire_mailbox(handler_id)

    def _handler_is_active(self, handler_id: int) -> bool:
        return self._handler_refs.get(handler_id, 0) > 0

    # ————— صناديق البريد (V3.0) —————
    def _retire_mailbox(self, handler_id: int) -> None:
        box = self._mailboxes.pop(handler_id, None)
        if box is not None and box.task is not None and not box.task.done():
            box.task.cancel()

    def _mailbox_of(self, handler_id: int) -> _Mailbox:
        box = self._mailboxes.get(handler_id)
        if box is None:
            box = self._mailboxes[handler_id] = _Mailbox()
        return box

    def _enqueue(self, handler_id: int, item: tuple[Any, ...],
                 event_name: str) -> None:
        """إيداع في صندوق المعالج — O(1)، لا انتظار، والقفزة معلَنة."""
        box = self._mailbox_of(handler_id)
        # V3.1 — دمج أحداث الحالة (LATEST_ONLY): حدث حالة لم يُسلَّم بعد
        # لنفس المعالج تحلّ **الأحدث** محلّه في مكانه — المستهلك البطيء يقرأ
        # آخر حقيقة لا طابورًا من ماضيها، والترتيب بين الأحداث المختلفة
        # محفوظ. الأوامر والوقائع لا تُدمج أبدًا (نفس حارس ٠٣/١١)، والدمج
        # معلَن دائمًا عبر stats()["coalesced"].
        # 1.19.1: مفتاح الدمج نطاقيّ لا اسميّ — نفس الاسم على رمزين حالتان
        # مختلفتان، ودمجهما كان يدوس حالة رمزٍ بحالة رمزٍ آخر (تصويب مهندس
        # النواة، مقيس على 50 رمزًا).
        if _is_replayable(event_name):
            key = _coalesce_key(event_name, item[2])
            for index in range(len(box.queue) - 1, -1, -1):
                pending = box.queue[index]
                if (pending[1] == event_name
                        and _coalesce_key(event_name, pending[2]) == key):
                    box.queue[index] = item
                    self._coalesced[event_name] += 1
                    if box.wakeup is not None:
                        box.wakeup.set()
                    return
        if not _is_command(event_name):
            while len(box.queue) >= self._mailbox_max_events:
                oldest = box.queue.popleft()
                self._dropped[str(oldest[1])] += 1
        box.queue.append(item)
        # V3.1: صندوق بلغ نصف سقفه = ضغط — التنازل التالي فوريّ لا ينتظر
        # النافذة، فيأخذ المستهلك دوره قبل أن يبدأ طرد الوقائع.
        if len(box.queue) >= _PRESSURE_MARK:
            self._yield_pressure = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # لا حلقة تشغيل — سيُنشأ المستهلك عند أول نشر داخل الحلقة.
        if box.task is None or box.task.done():
            box.wakeup = asyncio.Event()
            box.task = loop.create_task(self._consume(handler_id, box))
        if box.wakeup is not None:
            box.wakeup.set()

    async def _consume(self, handler_id: int, box: _Mailbox) -> None:
        """مستهلك صندوق واحد — تسليم بالترتيب، بعزل ومهلة لكل تسليم."""
        try:
            while True:
                if not box.queue:
                    if not self._handler_is_active(handler_id):
                        return
                    box.wakeup.clear()
                    await box.wakeup.wait()
                    continue
                kind, event_name, payload, extra = box.queue.popleft()
                box.busy = True
                try:
                    if kind == "sub":
                        sub: _Subscription = extra
                        await self._deliver(sub, event_name, payload)
                    else:
                        handler, subscriber, is_coro = extra
                        await self._deliver_global(
                            handler, subscriber, is_coro, event_name, payload)
                finally:
                    box.busy = False
        except asyncio.CancelledError:
            return

    async def _deliver(self, sub: _Subscription, event_name: str,
                       payload: dict[str, Any]) -> None:
        try:
            await self._invoke(sub, event_name, payload)
        except asyncio.CancelledError:
            # إلغاء المهمة (إيقاف الحلقة) ليس فشل معالج — يمرّ ليُنهي
            # المستهلك. ابتلاعه كان يجعل المهمة غير قابلة للإلغاء فيعلّق
            # إيقاف الحلقة كلّه (مقيس: pytest-asyncio ينتظرها للأبد).
            raise
        except (asyncio.TimeoutError, TimeoutError):
            self._timeout[event_name] += 1
            _log.error(
                "تجاوز مستمع '%s' من '%s' المهلة %.1fث — عُزل ولم يُعطّل الناقل (المادة 89)",
                event_name, sub.subscriber, self._dispatch_timeout_s,
            )
        except BaseException as error:  # noqa: BLE001 — عزل المادة 89
            self._error[event_name] += 1
            _log.error(
                "فشل مستمع '%s' من '%s': %s",
                event_name, sub.subscriber, error, exc_info=error,
            )
        else:
            self._delivered[event_name] += 1

    async def _deliver_global(self, handler: GlobalHandler, subscriber: str,
                              is_coro: bool, event_name: str,
                              payload: dict[str, Any]) -> None:
        try:
            await self._invoke_global(handler, subscriber, is_coro, event_name, payload)
        except asyncio.CancelledError:
            raise  # إلغاء الحلقة يمرّ — انظر _deliver.
        except (asyncio.TimeoutError, TimeoutError):
            self._timeout[event_name] += 1
            _log.error(
                "تجاوز مشترك الكل '%s' المهلة %.1fث على '%s' — عُزل (المادة 89)",
                subscriber, self._dispatch_timeout_s, event_name,
            )
        except BaseException as error:  # noqa: BLE001 — عزل المادة 89
            self._error[event_name] += 1
            _log.error(
                "فشل مشترك الكل '%s' على '%s': %s",
                subscriber, event_name, error, exc_info=error,
            )
        else:
            self._delivered[event_name] += 1

    async def _run_handler(self, handler: Callable, is_coro: bool, *args: Any) -> None:
        # آلية التسليم بأخف كلفة: asyncio.timeout (3.11+) — نفس ضمانة المهلة
        # والعزل تمامًا بلا مهمة غلاف لكل تسليم؛ ونوع المعالج محسوب عند
        # الاشتراك لا مع كل استدعاء. V3.0: لا قفل — صندوق البريد هو المسلسِل.
        if is_coro:
            async with asyncio.timeout(self._dispatch_timeout_s):
                await handler(*args)
        else:
            # المادة 5 (السيادة): المعالج المتجاوز للمهلة **يُعزل ويُلغى** فورًا
            # ولا يحتجز الناقل. ممنوع `shield` هنا — الناقل لا ينتظر أحدًا.
            async with asyncio.timeout(self._dispatch_timeout_s):
                result = await asyncio.to_thread(handler, *args)
            if inspect.isawaitable(result):
                async with asyncio.timeout(self._dispatch_timeout_s):
                    await result

    # ————— الوقت (ورقة ٠٥) —————
    def now(self) -> float:
        """الوقت المصحّح (خام + إزاحة) — للاستعمال الداخلي وختم الأحداث."""
        return time.time() + self._time_offset_s

    def set_time_offset(self, offset_s: float) -> None:
        """يحدّثها الـBootloader من حدث `time.utc.synced` (اسم عام + رقم؛ النواة
        لا تعرف مصدره ولا معناه)."""
        self._time_offset_s = float(offset_s)

    # ————— الاشتراك —————
    def subscribe(self, event_name: str, handler: Handler, *, subscriber: str = "",
                  isolate_payload: bool = True) -> None:
        # `isolate_payload=False` عهدٌ صريح من المشترك أنه يقرأ ولا يعدّل
        # (V3.1) — يستلم المرجع بلا نسخة. الافتراضي: نسخة معزولة (30/35).
        self._subscribers[event_name].append(_Subscription(
            handler=handler, subscriber=subscriber,
            is_coro=inspect.iscoroutinefunction(handler),
            isolate=bool(isolate_payload)))
        self._handler_ref_add(id(handler))
        # ٠٣: إعادة آخر حالة فورًا للمشترك الجديد (عبر نفس مسار التسليم
        # بالكامل: صندوق بريد · مهلة · عزل · عدّادات).
        last = self._last_event.get(event_name)
        if last is None:
            return
        sub = self._subscribers[event_name][-1]
        self._replayed[event_name] += 1
        self._enqueue(id(handler), ("sub", event_name, _fast_copy(last), sub),
                      event_name)

    def unsubscribe(self, event_name: str, handler: Handler) -> None:
        subs = self._subscribers.get(event_name)
        if subs is None:
            return  # لا نُنشئ مفتاحًا وهميًا لحدث لم يُشترك فيه قط
        kept = [s for s in subs if s.handler is not handler]
        if kept:
            self._subscribers[event_name] = kept
        else:
            del self._subscribers[event_name]
        removed_rows = len(subs) - len(kept)
        if removed_rows:
            self._handler_ref_drop(id(handler), removed_rows)

    def unsubscribe_all(self, subscriber: str) -> int:
        """يزيل كل اشتراكات مشترك واحد ولا يترك أي أثر (المادة 15)."""
        removed = 0
        removed_handlers: dict[int, int] = {}
        for event_name in list(self._subscribers):
            subs = self._subscribers[event_name]
            for row in subs:
                if row.subscriber == subscriber:
                    handler_id = id(row.handler)
                    removed_handlers[handler_id] = removed_handlers.get(handler_id, 0) + 1
            kept = [s for s in subs if s.subscriber != subscriber]
            removed += len(subs) - len(kept)
            if kept:
                self._subscribers[event_name] = kept
            else:
                del self._subscribers[event_name]
        for handler_id, count in removed_handlers.items():
            self._handler_ref_drop(handler_id, count)
        return removed

    # ————— الاشتراك على الكل (firehose — ورقة ١١) —————
    def subscribe_all(self, handler: GlobalHandler, *, subscriber: str = "",
                      isolate_payload: bool = True) -> None:
        """يشترك على **كل** الأحداث خام (اسم الحدث + الحمولة). لطبقة ٢ تبثّها
        برّا العملية بلا ما تشترك على كل اسم — النواة تبقى غبية: تمرّر خام بلا
        تفسير. والمشترك المتأخّر ياخد آخر حالة مخزَّنة لكل تدفّق فورًا (٠٣) فلا
        تفضى اللوحة عند الفتح؛ والأوامر غير مخزَّنة أصلًا فلا تُعاد قطّ.
        `isolate_payload=False` عهدٌ صريح من المشترك أنه **يقرأ ولا يعدّل**
        (بثّ يُرمّز فحسب) فيستلم المرجع بلا نسخة — توفير مقيس تحت تدفّق
        السوق الكامل؛ أي معالج قد يلمس الحمولة يبقى على النسخة الخاصة."""
        is_coro = inspect.iscoroutinefunction(handler)
        self._global_subscribers.append((handler, subscriber, isolate_payload, is_coro))
        self._handler_ref_add(id(handler))
        if not self._last_event:
            return
        for event_name, last in list(self._last_event.items()):
            self._replayed[event_name] += 1
            self._enqueue(id(handler), (
                "global", event_name,
                _fast_copy(last) if isolate_payload else last,
                (handler, subscriber, is_coro)), event_name)

    def unsubscribe_global(self, handler: GlobalHandler) -> None:
        removed_rows = sum(1 for h, *_ in self._global_subscribers if h is handler)
        self._global_subscribers = [
            row for row in self._global_subscribers if row[0] is not handler
        ]
        if removed_rows:
            self._handler_ref_drop(id(handler), removed_rows)

    # ————— النشر —————
    async def publish(
        self, event_name: str, payload: dict[str, Any] | None = None, *, publisher: str = ""
    ) -> None:
        # نسخة مستقلة: لا نعدّل قاموس المستدعي إطلاقًا.
        base: dict[str, Any] = _fast_copy(payload or {})

        # المادة 31 + ٠٤ (وراثة الأثر) + ٠٥ (الوقت المصحّح) — كلها setdefault:
        # أي قيمة جاءت مع الحدث (وقت مصدر خارجي، أثر مُعاد…) تبقى كما هي بلا لمس.
        base.setdefault("source", publisher)
        base.setdefault("event_id", str(uuid.uuid4()))
        base.setdefault("trace_id", current_trace_id.get() or str(uuid.uuid4()))
        base.setdefault("parent_event_id", current_event_id.get())
        base.setdefault("parent_event", current_event.get())
        base.setdefault("timestamp", self.now())

        self._published[event_name] += 1

        # V3.1 (قياس py-spy مساء 2026-08-25): النسخ لكل مشترك كان 46% من
        # الخيط الرئيسي تحت بطاقات الأقسام الكبيرة — فصار التسلسل مرّة
        # واحدة لكل نشرة (dumps تُدفع مرّة) وكل مشترك معزول يأخذ loads
        # خاصّته. الضمانة نفسها حرفيًّا (المادة 30/35): نسخة مستقلة للجميع،
        # وما يعجز pickle عنه يسلك deepcopy كما كان.
        blob: bytes | None = None
        blob_ready = False

        def _isolated_copy() -> Any:
            nonlocal blob, blob_ready
            if not blob_ready:
                blob_ready = True
                try:
                    blob = pickle.dumps(base, pickle.HIGHEST_PROTOCOL)
                except Exception:  # noqa: BLE001 — حمولة غير قابلة للتسلسل
                    blob = None
            if blob is not None:
                return pickle.loads(blob)
            return copy.deepcopy(base)

        if _is_replayable(event_name):
            self._last_event[event_name] = _isolated_copy()

        subs = list(self._subscribers.get(event_name, ()))
        _log.debug(
            "نشر '%s' من '%s' إلى %d مشترك(ين) (trace_id: %s)",
            event_name, publisher or "؟", len(subs), base["trace_id"],
        )
        # V3.0: النشر إيداعٌ في صناديق البريد — الناشر لا ينتظر أحدًا (المادة
        # 5)، والتسليم بالترتيب لكل معالج، بعزل ومهلة عند المستهلك.
        # firehose (ورقة ١١): كل حدث خام لمشتركي الكل — حتى لو ما في مشترك
        # على الاسم.
        for handler, subscriber, isolate, is_coro in self._global_subscribers:
            self._enqueue(id(handler), (
                "global", event_name,
                _isolated_copy() if isolate else base,
                (handler, subscriber, is_coro)), event_name)

        if not subs:
            self._no_subscribers[event_name] += 1
            await self._maybe_yield()
            return

        for sub in subs:
            self._enqueue(id(sub.handler),
                          ("sub", event_name,
                           _isolated_copy() if sub.isolate else base, sub),
                          event_name)
        await self._maybe_yield()

    async def _maybe_yield(self) -> None:
        # V3.1 (ختم nq · 2026-08-25): التنازل التعاونيّ مُقنَّن زمنيًّا.
        # التنازل بعد كل نشرة كان يحكم أسرع ناشرٍ بسرعة دورة طابور الحلقة —
        # مقيس: مضخة FIX 622 عالجت ٩ رسائل/ثانية (~109ms للنشرة) على حلقة
        # مشغولة، ففاض نقلها عند سقفه 131072 ورُمي 868KB في 70 ثانية بلا أي
        # انقطاع شبكة (Δc=0). الإيداع في الصناديق O(1) ولا يحتاج تنازلًا كل
        # مرّة؛ الضمانة المطلوبة ألّا يحتكر ناشرٌ الحلقةَ أكثر من نافذة قصيرة،
        # فدفعة كاملة تُودَع ثم يُعطى الدور مرّة.
        # الساعة perf_counter لا monotonic (مراجعة عدائية 2026-08-25):
        # monotonic على ويندوز = GetTickCount64 بدقّة 15.625ms، فنافذة 2ms
        # كانت فعليًّا ~12.5–15.6ms (مقيس: 8 تنازلات بدل ~50 في 100ms).
        # perf_counter = QPC بدقّة دون الميكروثانية وبنفس ضمانة الرتابة.
        # وعلامة الضغط تتجاوز النافذة كلّها: صندوق محتقن يأخذ دوره فورًا.
        now = time.perf_counter()
        if self._yield_pressure or now - self._last_yield >= _YIELD_EVERY_S:
            self._yield_pressure = False
            self._last_yield = now
            await asyncio.sleep(0)

    async def drain(self, timeout_s: float | None = None) -> bool:
        """ينتظر فراغ كل صناديق البريد وسكون مستهلكيها — للفحوص والإيقاف.

        يعيد True عند الفراغ الكامل، وFalse إن انقضت المهلة قبل ذلك.
        الفحص الذي كان يعتمد أن `publish` يعود بعد التسليم يستدعي هذه بعده.
        """
        deadline = (time.monotonic() + timeout_s) if timeout_s is not None else None
        while True:
            pending = any(box.queue or box.busy for box in self._mailboxes.values())
            if not pending:
                return True
            if deadline is not None and time.monotonic() > deadline:
                return False
            await asyncio.sleep(0.001)

    async def _invoke(self, sub: _Subscription, event_name: str, payload: dict[str, Any]) -> None:
        # ٠٤: نربط أثر الحدث الجاري + هويّته + اسمه بالبيئة، فأي حدث ينشره المعالج
        # يرث أباه تلقائيًا (شجرة سببية)، وتسجّله النواة في كل رسالة Log.
        t_trace = current_trace_id.set(payload.get("trace_id"))
        t_eid = current_event_id.set(payload.get("event_id"))
        t_ev = current_event.set(event_name)
        try:
            await self._run_handler(sub.handler, sub.is_coro, payload)
        finally:
            current_event.reset(t_ev)
            current_event_id.reset(t_eid)
            current_trace_id.reset(t_trace)

    async def _invoke_global(
        self, handler: GlobalHandler, subscriber: str, is_coro: bool,
        event_name: str, payload: dict[str, Any]
    ) -> None:
        # firehose: نفس عزل/مهلة _invoke، بس يمرّر اسم الحدث كمان (المشترك على
        # الكل ما بيعرف الاسم من التوقيع). خطؤه معزول ولا يعطّل النشر.
        t_trace = current_trace_id.set(payload.get("trace_id"))
        t_eid = current_event_id.set(payload.get("event_id"))
        t_ev = current_event.set(event_name)
        try:
            await self._run_handler(handler, is_coro, event_name, payload)
        finally:
            current_event.reset(t_ev)
            current_event_id.reset(t_eid)
            current_trace_id.reset(t_trace)

    # ————— القراءة (ورقة ٠٢) —————
    def stats(self) -> dict[str, dict[str, int]]:
        """لقطة قراءة فقط (قواميس جديدة قيمها أعداد صحيحة غير قابلة للتغيير —
        تعديل اللقطة لا يمسّ الداخل) — حقائق خام بلا منطق أعمال. طبقة ٢
        (الحوكمة) تقرّر نشرها/عرضها/تخزينها."""
        return {
            "published": dict(self._published),
            "delivered": dict(self._delivered),
            "no_subscribers": dict(self._no_subscribers),
            "timeout": dict(self._timeout),
            "error": dict(self._error),
            "replayed": dict(self._replayed),
            "dropped": dict(self._dropped),
            "coalesced": dict(self._coalesced),
        }

    def last_states(self) -> list[tuple[str, dict[str, Any]]]:
        """لقطة آخر حالة مخزَّنة لكل تدفّق (٠٣) — نسخ مستقلة، للمنضمّ المتأخر
        الذي لا يملك اشتراكًا خاصًّا به (عميل بثّ يتشارك مشترك-كلّ واحدًا).
        الأوامر غير مخزَّنة أصلًا فلا تظهر هنا قطّ."""
        return [(name, _fast_copy(last)) for name, last in self._last_event.items()]

    def event_names(self) -> list[str]:
        return list(self._subscribers.keys())

    def subscriber_count(self, event_name: str) -> int:
        return len(self._subscribers.get(event_name, ()))
