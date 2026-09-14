from __future__ import annotations

from typing import Any, Protocol

from contracts.observability import Trace


class Observability(Protocol):
    name: str

    def start_trace(self, run_id: str, name: str, metadata: dict[str, Any]) -> str: ...

    def start_span(
        self,
        trace_id: str,
        name: str,
        *,
        parent_span_id: str | None = None,
        kind: str = "chain",
        attributes: dict[str, Any] | None = None,
        code_path: str | None = None,
        mmd_node: str | None = None,
    ) -> str: ...

    def end_span(self, span_id: str, status: str = "ok", error: str | None = None) -> None: ...

    def event(self, span_id: str, name: str, payload: dict[str, Any] | None = None) -> None: ...

    def generation(
        self,
        span_id: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        input_preview: str = "",
        output_preview: str = "",
    ) -> None: ...

    def end_trace(self, trace_id: str, status: str = "ok") -> None: ...

    def get_trace(self, trace_id: str) -> Trace | None: ...

    def get_trace_by_run(self, run_id: str) -> Trace | None: ...

    def list_traces(self, limit: int = 30) -> list[Trace]: ...
