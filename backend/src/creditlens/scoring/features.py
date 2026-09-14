from __future__ import annotations

import hashlib
import json
from pathlib import Path

from contracts.application import Application

from creditlens.config import ROOT

FEATURE_ORDER = [
    "company_age_months",
    "annual_revenue",
    "revenue_growth",
    "ebitda_margin",
    "debt_to_revenue",
    "requested_amount",
    "requested_term",
    "credit_history_months",
    "overdue_30d_count",
    "overdue_90d_count",
    "bureau_score",
    "existing_loans_count",
    "industry_risk",
    "region_risk",
    "amount_to_revenue",
]

FEATURE_LABELS = {
    "company_age_months": "Возраст бизнеса",
    "annual_revenue": "Выручка",
    "revenue_growth": "Рост выручки",
    "ebitda_margin": "Рентабельность EBITDA",
    "debt_to_revenue": "Долговая нагрузка",
    "requested_amount": "Сумма кредита",
    "requested_term": "Срок",
    "credit_history_months": "Кредитная история",
    "overdue_30d_count": "Просрочки 30+",
    "overdue_90d_count": "Просрочки 90+",
    "bureau_score": "Бюро-скор",
    "existing_loans_count": "Действующие кредиты",
    "industry_risk": "Отраслевой риск",
    "region_risk": "Региональный риск",
    "amount_to_revenue": "Сумма / выручка",
}

MODELS_DIR = ROOT / "models"


def application_to_vector(app: Application) -> list[float]:
    amount_to_revenue = app.requested_amount / max(app.annual_revenue, 1.0)
    values = {
        "company_age_months": app.company_age_months,
        "annual_revenue": app.annual_revenue,
        "revenue_growth": app.revenue_growth,
        "ebitda_margin": app.ebitda_margin,
        "debt_to_revenue": app.debt_to_revenue,
        "requested_amount": app.requested_amount,
        "requested_term": float(app.requested_term),
        "credit_history_months": app.credit_history_months,
        "overdue_30d_count": float(app.overdue_30d_count),
        "overdue_90d_count": float(app.overdue_90d_count),
        "bureau_score": app.bureau_score,
        "existing_loans_count": float(app.existing_loans_count),
        "industry_risk": app.industry_risk,
        "region_risk": app.region_risk,
        "amount_to_revenue": amount_to_revenue,
    }
    return [values[name] for name in FEATURE_ORDER]


def feature_hash(app: Application) -> str:
    payload = json.dumps(application_to_vector(app), separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def write_feature_schema() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    path = MODELS_DIR / "feature_schema.json"
    path.write_text(
        json.dumps(
            {"order": FEATURE_ORDER, "labels": FEATURE_LABELS},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
