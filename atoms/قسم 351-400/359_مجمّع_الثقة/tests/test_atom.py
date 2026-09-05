import pytest
from shared.probability_contract import BASE_MODEL_IDS, EQUAL_MODEL_WEIGHT
from tests.learning_test_support import make_atom, manifest_config


@pytest.mark.asyncio
async def test_confidence_panel_has_depth_threshold_and_coverage():
    # ٢٠٢٦-٠٩-٠٦: العتبة كانت مثبَّتة هنا برقم 60، فسقط الاختبار يوم
    # خُفّضت في المانيفست إلى 1.0 (كوميت 838642c — دفعة تخفيفات مؤقّتة
    # شملت 359 و451 و455 و456 و463 و576 و578 و581 لفتح السلسلة قبل
    # تسخين الأقسام). والكود لم يخطئ: نشر العتبة التي أُعطيت له.
    # الاختبار يحرس **السلوك** — أن تُنشر العتبة السارية كما هي — لا
    # قيمةً بعينها، فيبقى صحيحًا حين تُرفع العتبة إلى 60 مرّة أخرى.
    cfg = manifest_config(359)
    module, atom, bus = await make_atom(359, cfg)
    for model_id in BASE_MODEL_IDS:
        await atom._on_model({
            "account_id": "A", "broker": "B", "symbol": "NQ",
            "cycle_id": "tick-1", "period_start": "t1", "sequence": 10,
            "id": model_id, "model_id": model_id,
            "confidence": 80, "probability": .7, "current_depth": 90,
            "weight": EQUAL_MODEL_WEIGHT, "weight_applied": EQUAL_MODEL_WEIGHT,
            "ready": True,
        })
    card = bus.payloads(module.EVENT_OUT)[-1]
    assert card["ready"] is True
    assert card["coverage"] == 100
    assert card["confidence"] == 80
    assert card["confidence_threshold"] == cfg["min_confidence"]
