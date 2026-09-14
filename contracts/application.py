from typing import Literal

from pydantic import BaseModel, Field

Segment = Literal["sme", "retail"]


class Application(BaseModel):
    application_id: str
    company_name: str
    segment: Segment = "sme"
    industry: str = "wholesale"
    region: str = "moscow"
    company_age_months: float = Field(ge=0, le=600)
    annual_revenue: float = Field(ge=0)
    revenue_growth: float = Field(ge=-1.0, le=3.0)
    ebitda_margin: float = Field(ge=-1.0, le=1.0)
    debt_to_revenue: float = Field(ge=0, le=5.0)
    requested_amount: float = Field(gt=0)
    requested_term: int = Field(ge=1, le=84)
    credit_history_months: float = Field(ge=0, le=480)
    overdue_30d_count: int = Field(ge=0, le=50)
    overdue_90d_count: int = Field(ge=0, le=20)
    bureau_score: float = Field(ge=0, le=1000)
    existing_loans_count: int = Field(ge=0, le=30)
    industry_risk: float = Field(ge=0, le=1)
    region_risk: float = Field(ge=0, le=1)


class ApplicationPreset(BaseModel):
    id: str
    title: str
    subtitle: str
    scenario: str
    application: Application


class ValidationIssue(BaseModel):
    field: str
    message: str
    code: str


class ValidationResult(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    normalized_segment: Segment = "sme"
    notes: list[str] = Field(default_factory=list)
