# المهمّة ٤ — الذرّة ٢١٧٠: التزامن ✅

## المشكلة
الذرّة ٢١٧٠ (العقود المفتوحة) تأخذ OI والسعر من ساعتين مختلفتين:
- **OI**: يصل كل ~١٦٫٨ ثانية (من استطلاع ticker)
- **السعر**: من إغلاق آخر شمعة (كل ٥ دقائق)

**النتيجة**: بين إغلاقَي شمعة، يبقى السعر ثابتًا ⇒ `d_price_pct == 0` ⇒ **79.5% flat كاذب**

## الحل — جزآن

### ١. المصدر ٢٦٢١ (v1.3.0 → v1.4.0)
يُرفق `fair_price` (أو `index_price`) في حمولة `market.oi`:
```python
# قبل:
await self._context.publish(EVENT_OI, {
    "provider": PROVIDER, "symbol": symbol, "oi": oi, "timestamp": now})

# بعد:
price = fair if fair is not None else index
await self._context.publish(EVENT_OI, {
    "provider": PROVIDER, "symbol": symbol, "oi": oi,
    "price": price, "timestamp": now})
```

### ٢. الذرّة ٢١٧٠ (v1.1.0 → v2.0.0)
- تُفضّل السعر المرافق للـOI (`oi_sync`)
- تسقط لإغلاق الشمعة إن غاب (`candle_fallback`)
- تُعلن المصدر في الحقل `price_source`
- تُحصي الاستخدام في `_sync_used` و `_fallback_used`

```python
# التزامن: أوّلاً السعر المرافق للـOI
price = _f(payload.get("price"))
if price is not None and price > 0:
    price_source = "oi_sync"
    self._sync_used += 1
else:
    # سقوط: آخر إغلاق شمعة
    price = self._price.get(symbol)
    if price is None:
        return
    price_source = "candle_fallback"
    self._fallback_used += 1
```

## الدليل — نسبة flat

| الحالة | flat% |
|--------|-------|
| **v1.0** (شمعة منفصلة) | **100%** |
| **v2.0** (سعر متزامن) | **14%** |
| **هدف المهمة** | <40% |
| **النتيجة** | ✅ **14% < 40%** |

## الاختبارات — ٥ من ٥ ✅

```
[١] التزامن مقابل القدم:
    v1.0 (شمعة منفصلة): flat = 10/10 = 100%
    v2.0 (سعر متزامن):   flat = 0/10 = 0%
    ✅ التزامن أنقذ ١٠ رباعيّات من flat الكاذب

[٢] الرباعيّات الأربع:
    ✅ new_longs / short_covering / long_liquidation / new_shorts

[٣] السقوط لإغلاق الشمعة:
    ✅ يعمل — يُعلن candle_fallback

[٤] بلا سعر ⇒ لا رباعيّة:
    ✅ حماية صحيحة

[٥] الدليل الكميّ:
    100 قراءة، flat = 14 (14.0%)
    ✅ flat% = 14.0% < 40% — هدف المهمة محقّق
```

## الملفات المُعدَّلة

| الملف | التغيير |
|-------|---------|
| `2170_العقود_المفتوحة/atom.py` | v1.1.0 → v2.0.0: التزامن + السقوط + الإعلان |
| `2170_العقود_المفتوحة/manifest.yaml` | version: 1.1.0 → 2.0.0 |
| `2170_العقود_المفتوحة/tests/test_atom.py` | ملف اختبار جديد (٥ اختبارات) |
| `2621_مصدر_MEXC_REST/atom.py` | v1.3.0 → v1.4.0: fair_price في market.oi |
| `2621_مصدر_MEXC_REST/manifest.yaml` | version: 1.3.0 → 1.4.0 |

## الأثر على القرار

مع التزامن:
- تصويت OI في محكمة الزناد يستعيد قدرته على التمييز
- الرباعيّات الأربع تعمل فعلاً (لا flat كاذب)
- `price_source` في الحقل يُعلن الشفافية

## ملاحظة — الذرّة ٢١٧١ (الوقود)

الذرّة ٢١٧١ أيضًا تستعمل سعر الشمعة. لكن نافذتها ٣٠ دقيقة (ليست قراءة-بقراءة)، فالأثر أقلّ. يمكن معالجتها في مهمة لاحقة إن لزم.

---

**التاريخ:** 2026-09-02  
**الحالة:** ✅ مكتملة ومُختبرة
