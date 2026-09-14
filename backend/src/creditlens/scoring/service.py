from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from catboost import CatBoostClassifier, Pool
from contracts.application import Application
from contracts.scoring import ScoringResult, ShapFeature, ShapResult

from creditlens.scoring.features import (
    FEATURE_LABELS,
    FEATURE_ORDER,
    MODELS_DIR,
    application_to_vector,
    feature_hash,
)

MODEL_PATH = MODELS_DIR / "scoring_model.cbm"
METADATA_PATH = MODELS_DIR / "model_metadata.json"

_SHAP_CACHE: dict[str, ShapResult] = {}


@lru_cache(maxsize=1)
def load_model() -> CatBoostClassifier:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Scoring model is missing: {MODEL_PATH}")
    model = CatBoostClassifier()
    model.load_model(str(MODEL_PATH))
    return model


@lru_cache(maxsize=1)
def load_metadata() -> dict:
    if METADATA_PATH.exists():
        return json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    return {"model_version": "catboost-v1"}


def _decision(score: float, pd: float, app: Application) -> tuple[str, str]:
    if score >= 0.72:
        band = "LOW"
    elif score >= 0.48:
        band = "MEDIUM"
    else:
        band = "HIGH"

    if band == "LOW" and app.overdue_90d_count == 0:
        decision = "APPROVE"
    elif band == "HIGH" and (app.overdue_90d_count >= 2 or pd >= 0.35):
        decision = "DECLINE"
    else:
        decision = "REVIEW"
    return band, decision


def score_application(app: Application) -> ScoringResult:
    model = load_model()
    vector = np.asarray([application_to_vector(app)], dtype=float)
    pd = float(model.predict_proba(vector)[0][1])
    score = float(max(0.0, min(1.0, 1.0 - pd)))
    band, decision = _decision(score, pd, app)
    meta = load_metadata()
    return ScoringResult(
        pd=round(pd, 4),
        score=round(score, 4),
        risk_band=band,  # type: ignore[arg-type]
        decision=decision,  # type: ignore[arg-type]
        model_version=meta.get("model_version", "catboost-v1"),
        feature_hash=feature_hash(app),
    )


def explain_application(app: Application) -> ShapResult:
    key = feature_hash(app)
    if key in _SHAP_CACHE:
        return _SHAP_CACHE[key]
    model = load_model()
    vector = np.asarray([application_to_vector(app)], dtype=float)
    pool = Pool(vector, feature_names=FEATURE_ORDER)
    shap_matrix = model.get_feature_importance(pool, type="ShapValues")
    row = shap_matrix[0]
    base_value = float(row[-1])
    features = [
        ShapFeature(
            feature=name,
            label=FEATURE_LABELS[name],
            value=float(vector[0][idx]),
            shap_value=round(float(row[idx]), 4),
        )
        for idx, name in enumerate(FEATURE_ORDER)
    ]
    features.sort(key=lambda item: abs(item.shap_value), reverse=True)
    result = ShapResult(
        base_value=round(base_value, 4),
        features=features,
        model_version=load_metadata().get("model_version", "catboost-v1"),
    )
    _SHAP_CACHE[key] = result
    return result


def model_ready() -> bool:
    return MODEL_PATH.exists()


def models_dir() -> Path:
    return MODELS_DIR
