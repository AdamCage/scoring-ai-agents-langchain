from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvalResult(BaseModel):
    case_id: str
    dataset: str
    metric: str
    score: float
    passed: bool
    comment: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class EvalRun(BaseModel):
    run_id: str
    experiment: str
    started_at: datetime
    ended_at: datetime | None = None
    status: Literal["running", "ok", "error"] = "running"
    summary: dict[str, float] = Field(default_factory=dict)
    results: list[EvalResult] = Field(default_factory=list)
    git_sha: str | None = None
    rag_version: str = "hybrid-v1"
    prompt_version: str = "risk-v1"
