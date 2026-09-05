from __future__ import annotations

import math
from typing import Any

from core.contracts.atom import AtomBase, AtomContext, HealthState, HealthStatus
from shared.financial_scope import account_broker, financial_key, text

ATOM_VERSION = "4.3.1"
# v4.3.1 (2026-08-27, item 22/27 of the 27-atom review -- verification
# only, no code change): _on_validated builds an order via one of two
# paths -- _direct_order() (already-priced/sized input) or the sized
# path computed from a stored 513 size. Only the direct path never
# validates stop_loss at all (payload.get("stop_loss") passes straight
# through, even as None or wrong-sided; the sized path DOES check via
# risk_dist <= 0.0). Traced the real pipeline wiring in the manifests,
# not assumed: 552 and 601 (the atom that actually writes to the broker
# bridge) subscribe only to 584's execution.order.legal /
# trading.final_decision, never to this atom's raw execution.order.built
# -- so 584's stop-legality gate is not a parallel observer, it genuinely
# blocks a malformed direct-path order before real execution. An
# end-to-end test with real 551+584 code proves the gap is caught.

EVENT_VALIDATED = "risk.validation.completed"
EVENT_SIZE = "risk.position_size.state"
EVENT_SIZE_REJECTED = "risk.position_size.rejected"
EVENT_ACCOUNT = "platform.account.state"
EVENT_OUT = "execution.order.built"
EVENT_DESIRED = "execution.desired.state"
EVENT_SKIPPED = "execution.order.skipped"

ACTION_OPEN = "OPEN"
SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

REASON_NOT_STARTED = "NOT_STARTED"
REASON_NO_INPUT = "NO_INPUT_YET"

REASON_UPSTREAM_REJECTED = "UPSTREAM_REJECTED"
REASON_BAD_SYMBOL_OR_SIDE = "BAD_SYMBOL_OR_SIDE"
REASON_NO_SIZE_YET = "NO_SIZE_YET"
REASON_INCOMPLETE_SIZE_DATA = "INCOMPLETE_SIZE_DATA"
REASON_INVALID_RISK_DISTANCE = "INVALID_RISK_DISTANCE"
REASON_LOSS_ABOVE_CAP = "LOSS_ABOVE_CAP"
_RISK_TOLERANCE = 1.02

# NQ seal item 22, package T (T2): 513's real sizing-rejection reason no
# longer disappears silently -- it rides here as an extra, honest field
# alongside our own categorical skip reason. Never invented: only what 513
# itself published on risk.position_size.rejected.

_PRICE_DP = 6
_VOLUME_DP = 2

_DIRECT_FIELDS = (
    "request_id", "account_id", "action", "symbol", "side", "volume",
    "reference_price", "stop_loss", "take_profit", "cycle_id", "origin",
    "pair_id", "leg_role", "attempt", "pair_required", "protection_mode",
    "pair_volume", "purpose", "target_net", "current_net", "delta_net",
    "ticket", "params_json", "logical_symbol", "broker_symbol", "asset_canonical",
    "symbol_resolution_status", "symbol_spec", "snapshot_id",
    "risk_budget", "asset_stop_distance", "broker", "magic",
    # v4.3.0 (2026-08-25): the parent-identity chain crosses this hop AS-IS
    # (layer-3 contract). Measured: the three built orders of 08-19..21
    # carried NONE of these although 576 sent them -- 551 dropped the chain,
    # and 552's snapshot-based recovery was impossible (snapshot_id null).
    # Absent stays absent (never invented); present crosses untouched.
    "decision_id", "gate_request_id", "parent_decision_id",
    "owner_command_id", "session_epoch",
)


def _to_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


class Atom(AtomBase):
    def __init__(self) -> None:
        self._context: AtomContext | None = None
        self._running = False
        self._reward_risk = 2.0
        self._magic = 20260801
        self._sizes: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._size_rejections: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._broker_by_account: dict[str, str] = {}
        self._seen = 0
        self._built = 0
        self._skipped = 0
        self._skip_reasons: dict[str, int] = {}

    async def initialize(self, context: AtomContext) -> None:
        self._context = context
        self._reward_risk = float(context.config["reward_risk"])
        self._magic = int(context.config.get("magic",20260801))
        context.subscribe(EVENT_VALIDATED, self._on_validated)
        context.subscribe(EVENT_SIZE, self._on_size)
        context.subscribe(EVENT_SIZE_REJECTED, self._on_size_rejected)
        context.subscribe(EVENT_ACCOUNT, self._on_account)

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def shutdown(self) -> None:
        await self.stop()

    async def _on_account(self, payload: dict[str, Any]) -> None:
        if not self._running or not isinstance(payload, dict):
            return
        account_id = text(payload.get("account_id"))
        broker = text(payload.get("broker"))
        if account_id and broker:
            self._broker_by_account[account_id] = broker

    async def _on_size(self, payload: dict[str, Any]) -> None:
        if not self._running or not isinstance(payload, dict):
            return
        symbol = payload.get("symbol")
        key = financial_key(payload, symbol, self._broker_by_account)
        if key is None:
            return
        if payload.get("status") == "REJECTED":
            return
        # T2: a fresh usable size clears any stale sizing rejection for this
        # scope -- the next skip (if any) must not carry a stale reason.
        self._size_rejections.pop(key, None)
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        self._sizes[key] = {
            "price": _to_float(meta.get("price")),
            "buy_lot": _to_float(meta.get("buy_lot")),
            "buy_stop": _to_float(meta.get("buy_stop")),
            "sell_lot": _to_float(meta.get("sell_lot")),
            "sell_stop": _to_float(meta.get("sell_stop")),
            # معاملات معادلة الحجم — تعبر من 513 كي يُعاد الحساب هنا على
            # مسافة الوقف الفعلية بدل الاعتماد على لوت محسوب لوقف آخر.
            "risk_amount": _to_float(meta.get("risk_amount")),
            "tick_value": _to_float(meta.get("tick_value")),
            "tick_size": _to_float(meta.get("tick_size")),
            "volume_step": _to_float(meta.get("volume_step")),
            "volume_min": _to_float(meta.get("volume_min")),
            "volume_max": _to_float(meta.get("volume_max")),
            "spread": _to_float(meta.get("spread")),
            "slippage_reserve": _to_float(meta.get("slippage_reserve")),
            "commission_per_lot": _to_float(meta.get("commission_per_lot")),
            "max_trade_loss": _to_float(meta.get("max_trade_loss")),
        }

    @staticmethod
    def _lot_for_stop(size: dict[str, Any], distance: float) -> float | None:
        """حجم اللوت من مسافة الوقف الفعلية، بعد ابتلاع تكاليف العبور.

        حكم المالك ٢٠٢٦-٠٩-٠٥: «لما يحسب لوت لازم يضمن دخول وانزلاق
        وسبريد وعمولة داخل الستوب» و«ما في صفقة تضرب ستوب أكثر من ١٠
        دولار». الخسارة الكلية = اللوت × (المسافة + السبريد + احتياطي
        الانزلاق) × قيمة النقطة + العمولة، وهي التي تُقيَّد بالميزانية —
        لا مسافة الوقف وحدها. التقريب لأسفل دائمًا كي لا تُتجاوز.
        """
        risk_amount = size.get("risk_amount")
        tick_value = size.get("tick_value")
        tick_size = size.get("tick_size")
        if not risk_amount or not tick_value or not tick_size or distance <= 0.0:
            return None
        cap = size.get("max_trade_loss")
        if cap:
            risk_amount = min(risk_amount, cap)
        effective = distance + (size.get("spread") or 0.0) \
            + (size.get("slippage_reserve") or 0.0)
        denom = effective * tick_value / tick_size + (size.get("commission_per_lot") or 0.0)
        if denom <= 0.0:
            return None
        step = size.get("volume_step") or 0.01
        stepped = math.floor((risk_amount / denom) / step) * step
        v_min = size.get("volume_min") or 0.0
        v_max = size.get("volume_max")
        if stepped + 1e-12 < v_min:
            return None
        if v_max:
            stepped = min(stepped, v_max)
        return round(stepped, _VOLUME_DP)

    async def _on_size_rejected(self, payload: dict[str, Any]) -> None:
        """T2: remember 513's real sizing-rejection reason per scope, so a
        later skip here (REASON_NO_SIZE_YET) can carry it forward instead of
        losing it -- the reason is exactly what 513 published, never
        invented."""
        if not self._running or not isinstance(payload, dict):
            return
        symbol = payload.get("symbol")
        key = financial_key(payload, symbol, self._broker_by_account)
        if key is None:
            return
        self._size_rejections[key] = {"reason": text(payload.get("reason")) or None}

    def _direct_order(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        symbol = payload.get("symbol")
        side = str(payload.get("side") or "").upper()
        action = str(payload.get("action") or ACTION_OPEN).upper()
        volume = _to_float(payload.get("volume"))
        price = _to_float(payload.get("reference_price"))
        if not symbol or side not in (SIDE_BUY, SIDE_SELL):
            return None
        if volume is None or volume <= 0.0:
            return None
        if action == ACTION_OPEN and (price is None or price <= 0.0):
            return None
        if action != ACTION_OPEN and payload.get("ticket") in (None, "", 0):
            return None
        account = text(payload.get("account_id"))
        broker = text(payload.get("broker")) or self._broker_by_account.get(account, "")
        if not account or not broker:
            return None
        order = {key: payload.get(key) for key in _DIRECT_FIELDS}
        order.update({
            "request_id": str(payload.get("request_id", "")),
            "account_id": account, "broker": broker, "magic":self._magic,
            "action": action,
            "symbol": str(symbol), "side": side, "volume": volume,
            "reference_price": round(price, _PRICE_DP) if price is not None else None,
            "stop_loss": payload.get("stop_loss"),
            "take_profit": payload.get("take_profit"),
        })
        return order

    def _resize_direct(self, order: dict[str, Any],
                       payload: dict[str, Any]) -> dict[str, Any] | None:
        """يُخضع أمر المسار المباشر لسقف خسارة المالك.

        حكمه ٢٠٢٦-٠٩-٠٥: «ما في صفقة تضرب ستوب أكثر من ١٠ دولار» و«لازم
        لوت ينحسب على ستوب ويطلع لوت مناسب، مو ثابت». الحجم يُحسب من
        مسافة وقف **هذا الأمر** بعد ابتلاع السبريد والانزلاق والعمولة،
        ولا يزيد أبدًا عمّا طلبه صاحب الأمر (سقف الخطوة يبقى حدًّا أعلى).
        أمرٌ لا يمكن تصغيره تحت السقف لا يُرسَل.
        """
        price = _to_float(order.get("reference_price"))
        stop = _to_float(order.get("stop_loss"))
        volume = _to_float(order.get("volume"))
        side = str(order.get("side") or "").upper()
        if not price or not stop or not volume or side not in (SIDE_BUY, SIDE_SELL):
            return order            # لا وقف = لا معادلة؛ 584 يحرس شرعيّته
        distance = (price - stop) if side == SIDE_BUY else (stop - price)
        if distance <= 0.0:
            return order            # مقلوب — حارس 584 يرفضه بسببه الصريح
        account = text(order.get("account_id"))
        broker = text(order.get("broker")) or self._broker_by_account.get(account, "")
        symbol = str(order.get("symbol") or "")
        size = self._sizes.get((account, broker, symbol)) if (account and broker) else None
        if not size:
            return order            # لا مواصفة بعد؛ الحارس التالي يقرّر
        size = dict(size)
        req_spread = _to_float(payload.get("spread"))
        if req_spread is not None and req_spread > 0.0:
            size["spread"] = req_spread
            req_slip = _to_float(payload.get("slippage_reserve"))
            if req_slip is not None:
                size["slippage_reserve"] = req_slip
        sized = self._lot_for_stop(size, distance)
        if sized is None:
            self._context.logger.warning(
                "551 direct %s %s: sizing unavailable — volume=%s dist=%.2f "
                "risk_amount=%r tv=%r ts=%r", symbol, side, volume, distance,
                size.get("risk_amount"), size.get("tick_value"), size.get("tick_size"))
            return order
        final = min(volume, sized)
        v_min = size.get("volume_min") or 0.0
        if final + 1e-12 < v_min:
            self._skipped += 1
            self._skip_reasons[REASON_LOSS_ABOVE_CAP] = \
                self._skip_reasons.get(REASON_LOSS_ABOVE_CAP, 0) + 1
            self._context.logger.warning(
                "551 skip %s %s: LOSS_ABOVE_CAP — أصغر لوت مسموح %s يتجاوز "
                "السقف على مسافة %.2f", symbol, side, v_min, distance)
            return None
        self._context.logger.warning(
            "551 direct %s %s: volume %s -> %s (dist=%.2f spread=%s slip=%s cap=%s)",
            symbol, side, volume, final, distance, size.get("spread"),
            size.get("slippage_reserve"), size.get("max_trade_loss"))
        order["volume"] = final
        return order

    async def _on_validated(self, payload: dict[str, Any]) -> None:
        if not self._running or self._context is None or not isinstance(payload, dict):
            return
        self._seen += 1
        if not payload.get("approved"):
            await self._skip(REASON_UPSTREAM_REJECTED, payload)
            return

        direct = self._direct_order(payload)
        if direct is not None:
            # ٢٠٢٦-٠٩-٠٥ (مقيس، وهو جذر ثبات الحجم عند 0.5): الطلب
            # الاتجاهي يحمل volume وreference_price، فيلتقطه المسار
            # المباشر ويخرج من هنا فورًا — وكل حساب الحجم وحارس السقف
            # أدناه شيفرة ميتة لم تُنفَّذ ولا مرّة. لهذا لم يظهر سطر
            # «551 built» ولا LOSS_ABOVE_CAP في السجلّ رغم ثماني صفقات.
            # النتيجة: الحجم يعبر كما أرسله 581 (سقف الخطوة 0.5) مهما
            # كان بُعد الوقف — قِيست مسافات 17.76 → 56.76 كلّها بـ0.5،
            # وخسائر 10.23 · 11.34 · 15.26 فوق سقف المالك.
            # الحجم يُعاد حسابه هنا على مسافة وقف الأمر نفسه.
            direct = self._resize_direct(direct, payload)
            if direct is None:
                return
            await self._context.publish(EVENT_OUT, direct)
            await self._publish_desired(direct)
            self._built += 1
            return

        side = str(payload.get("side", "")).upper()
        symbol = payload.get("symbol")
        if not symbol or side not in (SIDE_BUY, SIDE_SELL):
            await self._skip(REASON_BAD_SYMBOL_OR_SIDE, payload)
            return
        symbol = str(symbol)
        account = text(payload.get("account_id"))
        broker = text(payload.get("broker")) or self._broker_by_account.get(account, "")
        scope = (account, broker, symbol) if account and broker else None
        size = self._sizes.get(scope) if scope else None
        if size is None:
            rejection = self._size_rejections.get(scope) if scope else None
            await self._skip(REASON_NO_SIZE_YET, payload,
                              sizing_reason=rejection.get("reason") if rejection else None)
            return
        price = size.get("price")
        volume = size.get("buy_lot") if side == SIDE_BUY else size.get("sell_lot")
        stop = size.get("buy_stop") if side == SIDE_BUY else size.get("sell_stop")
        if price is None or volume is None or stop is None or volume <= 0.0:
            await self._skip(REASON_INCOMPLETE_SIZE_DATA, payload)
            return
        # ٢٠٢٦-٠٩-٠٥ (مقيس على الحساب): الطلب يصل بوقف وهدف محسوبين من
        # مستويات بنيوية (مخاطرة 7.4 مقابل عائد 32.5 = نسبة 4.4)، وكان
        # يُستبدلان هنا بوقف 513 البعيد (74,655 على سعر 79,655 = 6.3%)
        # وهدف بنسبة ثابتة — فتنهار النسبة إلى 0.004 بعد حسابها. وقف
        # الطلب البنيوي يُحترم متى جاء صالحًا؛ وقف التحجيم يبقى الاحتياط.
        requested_stop = _to_float(payload.get("stop_loss"))
        requested_target = _to_float(payload.get("take_profit"))
        if requested_stop is not None and requested_stop > 0.0:
            valid = (requested_stop < price) if side == SIDE_BUY else (requested_stop > price)
            if valid:
                stop = requested_stop
        risk_dist = (price - stop) if side == SIDE_BUY else (stop - price)
        if risk_dist <= 0.0:
            await self._skip(REASON_INVALID_RISK_DISTANCE, payload)
            return
        target = (price + self._reward_risk * risk_dist) if side == SIDE_BUY \
            else (price - self._reward_risk * risk_dist)
        if requested_target is not None and requested_target > 0.0:
            valid_t = (requested_target > price) if side == SIDE_BUY else (requested_target < price)
            if valid_t:
                target = requested_target
        # حكم المالك ٢٠٢٦-٠٩-٠٥: «وقف الخسارة لازم ينحسب على معادلة حجم
        # لوت». اللوت الوارد من 513 محسوب على وقف 513؛ متى تغيّر الوقف
        # وجب أن يتغيّر معه اللوت، وإلا صارت المخاطرة الفعلية رقمًا آخر
        # غير الميزانية. يُعاد الحساب هنا على المسافة النهائية، وسقف
        # خطوة 581 (volume في الطلب) يبقى حدًّا أعلى لا يُتجاوز.
        # تكاليف العبور المقيسة في الطلب تسبق ما نشره 513: 513 يستمع إلى
        # market.tick.validated (بلا bid/ask) فيرسل السبريد صفرًا، بينما
        # 581 يقيسه من تِكّة الوسيط نفسها.
        req_spread = _to_float(payload.get("spread"))
        req_slip = _to_float(payload.get("slippage_reserve"))
        if req_spread is not None and req_spread > 0.0:
            size = dict(size)
            size["spread"] = req_spread
            if req_slip is not None:
                size["slippage_reserve"] = req_slip
        sized = self._lot_for_stop(size, risk_dist)
        if sized is not None:
            volume = sized
        elif self._context is not None:
            # مقيس ٢٠٢٦-٠٩-٠٥ على التذكرة 1911030333: بُني لوت 0.5 على وقف
            # 30 نقطة = 15$ — فوق سقف المالك — فاضطُرّ 577 إلى تضييق الوقف
            # بعد الفتح فمات التحليل وضُرب الوقف (-9.90). اللوت يجب أن
            # يُصغَّر قبل الإرسال؛ فشل حسابه يجب أن يُرى بأسمائه لا يمرّ.
            self._context.logger.warning(
                "551 sizing fallback %s: risk_amount=%r tick_value=%r "
                "tick_size=%r max_loss=%r spread=%r volume=%r dist=%.2f",
                symbol, size.get("risk_amount"), size.get("tick_value"),
                size.get("tick_size"), size.get("max_trade_loss"),
                size.get("spread"), volume, risk_dist)
        step_cap = _to_float(payload.get("volume"))
        if step_cap is not None and step_cap > 0.0:
            volume = min(volume, step_cap)
        volume = round(volume, _VOLUME_DP)
        if volume <= 0.0:
            await self._skip(REASON_INCOMPLETE_SIZE_DATA, payload)
            return
        # حارس نهائي على حكم المالك «ما في صفقة تضرب ستوب أكثر من ١٠
        # دولار»: تُحسب الخسارة الكلّية بالحجم النهائي، وما يتجاوز السقف
        # لا يُرسَل. بلا هذا الحارس مرّت التذكرة 1911030333 بلوت 0.5 على
        # وقف 30 نقطة (15$)، فصحّحها 577 بتضييق الوقف بعد الفتح — أي
        # بقتل التحليل بدل تصغير الحجم.
        tick_value = size.get("tick_value")
        tick_size = size.get("tick_size")
        cap = size.get("max_trade_loss")
        if cap and tick_value and tick_size:
            effective = risk_dist + (size.get("spread") or 0.0) \
                + (size.get("slippage_reserve") or 0.0)
            loss = volume * effective * tick_value / tick_size \
                + volume * (size.get("commission_per_lot") or 0.0)
            if loss > cap * _RISK_TOLERANCE:
                await self._skip(REASON_LOSS_ABOVE_CAP, payload)
                if self._context is not None:
                    self._context.logger.warning(
                        "551 skip %s: LOSS_ABOVE_CAP loss=%.2f cap=%.2f "
                        "volume=%s dist=%.2f", symbol, loss, cap, volume, risk_dist)
                return
        order = {
            "request_id": str(payload.get("request_id", "")),
            "account_id": account, "broker": broker, "magic":self._magic,
            "action": ACTION_OPEN, "symbol": symbol, "side": side,
            "volume": volume, "reference_price": round(price, _PRICE_DP),
            "stop_loss": round(stop, _PRICE_DP),
            "take_profit": round(target, _PRICE_DP),
            "reward_risk": self._reward_risk,
            "cycle_id": str(payload.get("cycle_id", "")),
        }
        # v4.3.0: parent-identity chain passthrough (layer-3 contract) --
        # present fields cross untouched, absent fields stay absent.
        for chain_field in ("decision_id", "gate_request_id",
                            "parent_decision_id", "owner_command_id",
                            "session_epoch"):
            if payload.get(chain_field) is not None:
                order[chain_field] = payload[chain_field]
        # ٢٠٢٦-٠٩-٠٥ (مقيس على ٨ صفقات): الحجم خرج 0.5 في كلّها بينما
        # مسافات الوقف تراوحت 17.76 → 56.76 — أي أن المعادلة لم تحكم.
        # مكوّناتها تُطبع مع كل أمر كي يُعرف أيّ حدّ هو الذي قصّ الحجم:
        # المحسوب من الوقف، أم سقف خطوة 581، أم لوت 513 الاحتياطي.
        self._context.logger.warning(
            "551 built %s %s: volume=%s sized=%s step_cap=%s dist=%.2f "
            "spread=%s slip=%s cap=%s vpp=%s",
            symbol, side, volume, sized, step_cap, risk_dist,
            size.get("spread"), size.get("slippage_reserve"),
            size.get("max_trade_loss"),
            (size.get("tick_value") / size.get("tick_size"))
            if size.get("tick_value") and size.get("tick_size") else None)
        await self._context.publish(EVENT_OUT, order)
        await self._publish_desired(order)
        self._built += 1

    async def _skip(self, reason: str, payload: dict[str, Any],
                    sizing_reason: str | None = None) -> None:
        self._skipped += 1
        self._skip_reasons[reason] = self._skip_reasons.get(reason, 0) + 1
        if self._context is None:
            return
        if self._skipped <= 25:
            self._context.logger.warning(
                "551 skip reason=%s symbol=%s account=%s side=%s approved=%r "
                "origin=%s sizes_keys=%s", reason, payload.get("symbol"),
                payload.get("account_id"), payload.get("side"),
                payload.get("approved"), payload.get("origin"),
                list(self._sizes)[:4])
        body = {
            "reason": reason,
            "symbol": payload.get("symbol"),
            "account_id": payload.get("account_id"),
            "request_id": str(payload.get("request_id", "")),
            "cycle_id": str(payload.get("cycle_id", "")),
            # T2: the skipped request keeps its decision identity when the
            # input carried one -- absent stays None, never invented.
            "decision_id": payload.get("decision_id"),
            "gate_request_id": payload.get("gate_request_id"),
        }
        if sizing_reason:
            # T2: 513's real sizing-rejection reason, passed through as-is
            # instead of disappearing behind our own NO_SIZE_YET category.
            body["sizing_reason"] = sizing_reason
        await self._context.publish(EVENT_SKIPPED, body)

    async def _publish_desired(self, order: dict[str, Any]) -> None:
        if self._context is None:
            return
        leg = dict(order)
        leg["leg_id"] = order.get("request_id") or order.get("symbol")
        leg["entry_price"] = order.get("reference_price")
        await self._context.publish(EVENT_DESIRED, {
            "account_id": order.get("account_id"), "broker": order.get("broker"),
            "symbol": order.get("symbol"),
            "asset_canonical": order.get("symbol"),
            "legs": [leg], "leg_id": leg["leg_id"],
            "entry_price": leg["entry_price"], "version": self._built + 1,
            "pair_id": order.get("pair_id"),
            "leg_role": order.get("leg_role"),
        })

    async def health_check(self) -> HealthStatus:
        if not self._running:
            return HealthStatus(state=HealthState.UNHEALTHY, message=REASON_NOT_STARTED)
        details = {"seen": self._seen, "built": self._built, "skipped": self._skipped,
                   "skip_reasons": dict(self._skip_reasons),
                   "sized_scopes": len(self._sizes),
                   "accounts_with_broker": len(self._broker_by_account)}
        if self._seen == 0:
            return HealthStatus(state=HealthState.HEALTHY,
                                message="READY_AWAITING_FIRST_RISK_VALIDATION | built=0 skipped=0",
                                details=details)
        return HealthStatus(state=HealthState.HEALTHY,
                            message="built=%d skipped=%d" % (self._built, self._skipped),
                            details=details)
