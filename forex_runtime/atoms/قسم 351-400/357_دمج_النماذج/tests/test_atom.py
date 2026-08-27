import pytest
from shared.probability_contract import BASE_MODEL_IDS, EQUAL_MODEL_WEIGHT
from tests.learning_test_support import make_atom, manifest_config


@pytest.mark.asyncio
async def test_weighted_merge_uses_only_ready_weight():
    module, atom, bus = await make_atom(357, manifest_config(357))
    for index, model_id in enumerate(BASE_MODEL_IDS):
        await atom._on_model({
            "account_id": "A", "broker": "B", "symbol": "NQ",
            "cycle_id": "tick-1", "period_start": "t1", "sequence": 10,
            "id": model_id, "model_id": model_id,
            "direction": 100 if index < 4 else -100 if index < 6 else 0,
            "strength": 80, "confidence": 80, "probability": .7,
            "current_depth": 90, "required_depth": 60,
            "weight": EQUAL_MODEL_WEIGHT, "weight_applied": EQUAL_MODEL_WEIGHT,
            "ready": True,
        })
    merged = bus.payloads(module.EVENT_OUT)[-1]
    assert merged["ready"] is True
    assert merged["active_weight"] == pytest.approx(100.0, abs=1e-4)
    assert merged["direction"] > 0
    assert merged["weight"] == 0
