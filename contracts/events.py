from typing import Any, Literal

from pydantic import BaseModel, Field

SSEEventType = Literal[
    "node_start",
    "node_end",
    "token",
    "tool",
    "retrieval",
    "interrupt",
    "error",
    "done",
]


class SSEEvent(BaseModel):
    type: SSEEventType
    node: str | None = None
    run_id: str
    timestamp_ms: int
    data: dict[str, Any] = Field(default_factory=dict)
