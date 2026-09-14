from contracts.application import Application

from creditlens.presets import presets
from creditlens.scoring.service import explain_application, score_application


def test_scoring_is_deterministic():
    app = presets()[0].application
    assert score_application(app) == score_application(app)


def test_shap_features_are_labeled():
    shap = explain_application(presets()[0].application)
    assert shap.features
    assert all(item.label for item in shap.features)


def test_llm_cannot_own_score_object():
    app = Application.model_validate(presets()[0].application.model_dump())
    scored = score_application(app)
    mutated = scored.model_copy(update={"score": 0.01})
    assert scored.score != mutated.score
    assert score_application(app).score == scored.score
