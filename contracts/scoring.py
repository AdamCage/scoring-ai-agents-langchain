from typing import Literal

from pydantic import BaseModel, Field

RiskBand = Literal["LOW", "MEDIUM", "HIGH"]
Decision = Literal["APPROVE", "REVIEW", "DECLINE"]


class ScoringResult(BaseModel):
    """Deterministic model output. LLM must never overwrite this object."""

    pd: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=1)
    risk_band: RiskBand
    decision: Decision
    model_version: str
    feature_hash: str


class ShapFeature(BaseModel):
    feature: str
    label: str
    value: float
    shap_value: float = Field(description="Positive value increases PD / risk")


class ShapResult(BaseModel):
    base_value: float
    features: list[ShapFeature] = Field(default_factory=list)
    model_version: str
