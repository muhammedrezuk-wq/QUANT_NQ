import pytest
from shared.learning_model import predict
from tests.learning_test_support import artifact, feature, make_atom


@pytest.mark.asyncio
async def test_validator_uses_ordered_holdout_and_multiple_metrics():
    module, atom, bus = await make_atom(364, {"validation_size": 1,
                                               "min_accuracy": 0.0})
    candidate = artifact()
    row = feature("hold", "buy", 0.15)
    probabilities = predict(candidate, row["feature_vector"])
    row["label"] = max(("buy", "sell", "neutral"),
                       key=lambda name: probabilities["p_" + name])
    await atom._on_feature(row)
    candidate["train_ids"] = []
    await atom._on_candidate(candidate)
    report = bus.payloads(module.EVENT_OUT)[-1]
    assert report["passed"] is True
    assert "balanced_accuracy" in report
    assert "log_loss" in report
    assert "brier_score" in report
