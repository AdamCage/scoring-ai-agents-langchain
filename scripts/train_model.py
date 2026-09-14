#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, Pool
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend" / "src"))

from creditlens.scoring.features import (  # noqa: E402
    FEATURE_ORDER,
    MODELS_DIR,
    write_feature_schema,
)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def generate_dataset(n: int = 8000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    company_age_months = rng.uniform(3, 240, n)
    annual_revenue = rng.lognormal(mean=18.2, sigma=0.7, size=n).clip(1_000_000, 2_000_000_000)
    revenue_growth = rng.normal(0.08, 0.18, n).clip(-0.6, 1.2)
    ebitda_margin = rng.normal(0.12, 0.08, n).clip(-0.2, 0.45)
    debt_to_revenue = rng.beta(2.0, 4.0, n) * 1.6
    requested_amount = (annual_revenue * rng.uniform(0.05, 0.55, n)).clip(200_000, 400_000_000)
    requested_term = rng.choice([6, 12, 18, 24, 36, 48, 60], size=n)
    credit_history_months = rng.uniform(0, 180, n)
    overdue_30d_count = rng.poisson(0.4, n).clip(0, 12)
    overdue_90d_count = rng.poisson(0.15, n).clip(0, 6)
    bureau_score = rng.normal(690, 80, n).clip(300, 900)
    existing_loans_count = rng.poisson(1.4, n).clip(0, 12)
    industry_risk = rng.beta(2.0, 3.5, n)
    region_risk = rng.beta(2.2, 4.0, n)
    amount_to_revenue = requested_amount / np.maximum(annual_revenue, 1.0)

    logit = (
        -2.15
        + 2.4 * debt_to_revenue
        + 0.35 * overdue_30d_count
        + 0.85 * overdue_90d_count
        + 1.35 * industry_risk
        + 0.7 * region_risk
        + 1.1 * amount_to_revenue
        + 0.08 * (requested_term / 12.0)
        - 0.004 * (bureau_score - 500)
        - 0.004 * company_age_months
        - 2.1 * ebitda_margin
        - 1.1 * revenue_growth
        - 0.004 * credit_history_months
        + 0.08 * existing_loans_count
        - 0.15 * np.log(annual_revenue / 10_000_000)
        + rng.normal(0, 0.35, n)
    )
    default_p = _sigmoid(logit)
    defaulted = (rng.uniform(0, 1, n) < default_p).astype(int)

    frame = pd.DataFrame(
        {
            "company_age_months": company_age_months,
            "annual_revenue": annual_revenue,
            "revenue_growth": revenue_growth,
            "ebitda_margin": ebitda_margin,
            "debt_to_revenue": debt_to_revenue,
            "requested_amount": requested_amount,
            "requested_term": requested_term,
            "credit_history_months": credit_history_months,
            "overdue_30d_count": overdue_30d_count,
            "overdue_90d_count": overdue_90d_count,
            "bureau_score": bureau_score,
            "existing_loans_count": existing_loans_count,
            "industry_risk": industry_risk,
            "region_risk": region_risk,
            "amount_to_revenue": amount_to_revenue,
            "defaulted": defaulted,
        }
    )
    return frame


def train() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    write_feature_schema()
    data = generate_dataset()
    x = data[FEATURE_ORDER]
    y = data["defaulted"]
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=42, stratify=y
    )
    model = CatBoostClassifier(
        iterations=180,
        depth=6,
        learning_rate=0.08,
        loss_function="Logloss",
        eval_metric="AUC",
        verbose=False,
        random_seed=42,
    )
    model.fit(Pool(x_train, y_train), eval_set=Pool(x_test, y_test), use_best_model=True)
    proba = model.predict_proba(x_test)[:, 1]
    auc = float(roc_auc_score(y_test, proba))
    model_path = MODELS_DIR / "scoring_model.cbm"
    model.save_model(str(model_path))
    metadata = {
        "model_version": "catboost-v1",
        "algorithm": "CatBoostClassifier",
        "rows": int(len(data)),
        "auc": round(auc, 4),
        "default_rate": round(float(y.mean()), 4),
        "features": FEATURE_ORDER,
    }
    (MODELS_DIR / "model_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved {model_path} auc={auc:.4f} default_rate={y.mean():.3f}")


if __name__ == "__main__":
    train()
