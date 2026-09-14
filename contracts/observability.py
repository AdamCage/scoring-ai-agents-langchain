from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SpanEvent(BaseModel):
    timestamp: datetime
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)


class Generation(BaseModel):
    span_id: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    input_preview: str = ""
    output_preview: str = ""


class Span(BaseModel):
    span_id: str
    trace_id: str
    parent_span_id: str | None = None
    name: str
    kind: Literal["chain", "llm", "tool", "retriever", "graph", "eval"] = "chain"
    status: Literal["running", "ok", "error"] = "running"
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[SpanEvent] = Field(default_factory=list)
    error: str | None = None
    code_path: str | None = None
    mmd_node: str | None = None


class Trace(BaseModel):
    trace_id: str
    run_id: str
    name: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None
    status: Literal["running", "ok", "error"] = "running"
    metadata: dict[str, Any] = Field(default_factory=dict)
    spans: list[Span] = Field(default_factory=list)
