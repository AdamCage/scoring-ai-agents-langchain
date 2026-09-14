from typing import Literal

from pydantic import BaseModel, Field

from contracts.scoring import Decision, RiskBand


class RiskAnalysis(BaseModel):
    summary: str
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    policy_notes: list[str] = Field(default_factory=list)
    used_citations: list[str] = Field(default_factory=list)
    prompt_version: str = "risk-v1"


class Critique(BaseModel):
    acceptable: bool
    issues: list[str] = Field(default_factory=list)
    missing_citations: list[str] = Field(default_factory=list)
    prompt_version: str = "critic-v1"


class Recommendation(BaseModel):
    decision: Decision
    title: str
    summary: str
    score: float
    risk_band: RiskBand
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    prompt_version: str = "synth-v1"
