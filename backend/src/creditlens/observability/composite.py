from __future__ import annotations

from typing import Any

from contracts.observability import Trace

from creditlens.observability.base import Observability
from creditlens.observability.local import LocalObservability


class CompositeObservability:
    name = "composite"

    def __init__(self, local: LocalObservability, extras: list[Any] | None = None) -> None:
        self.local = local
        self.extras = extras or []
        self._run_by_trace: dict[str, str] = {}
        self._span_map: dict[str, list[tuple[Any, str]]] = {}

    @property
    def sinks(self) -> list[Any]:
        return [self.local, *self.extras]

    def start_trace(self, run_id: str, name: str, metadata: dict[str, Any]) -> str:
        local_id = self.local.start_trace(run_id, name, metadata)
        self._run_by_trace[local_id] = run_id
        for sink in self.extras:
            try:
                sink.start_trace(run_id, name, metadata)
            except Exception:
                continue
        return local_id

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
    ) -> str:
        local_span = self.local.start_span(
            trace_id,
            name,
            parent_span_id=parent_span_id,
            kind=kind,
            attributes=attributes,
            code_path=code_path,
            mmd_node=mmd_node,
        )
        mapped: list[tuple[Any, str]] = []
        run_id = self._run_by_trace.get(trace_id, trace_id)
        for sink in self.extras:
            try:
                extra_id = sink.start_span(
                    run_id,
                    name,
                    parent_span_id=parent_span_id,
                    kind=kind,
                    attributes=attributes,
                    code_path=code_path,
                    mmd_node=mmd_node,
                )
                mapped.append((sink, extra_id))
            except Exception:
                continue
        self._span_map[local_span] = mapped
        return local_span

    def end_span(self, span_id: str, status: str = "ok", error: str | None = None) -> None:
        self.local.end_span(span_id, status=status, error=error)
        for sink, extra_id in self._span_map.get(span_id, []):
            try:
                sink.end_span(extra_id, status=status, error=error)
            except Exception:
                continue

    def event(self, span_id: str, name: str, payload: dict[str, Any] | None = None) -> None:
        self.local.event(span_id, name, payload)
        for sink, extra_id in self._span_map.get(span_id, []):
            try:
                sink.event(extra_id, name, payload)
            except Exception:
                continue

    def generation(
        self,
        span_id: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        input_preview: str = "",
        output_preview: str = "",
    ) -> None:
        self.local.generation(
            span_id,
            model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            input_preview=input_preview,
            output_preview=output_preview,
        )
        for sink, extra_id in self._span_map.get(span_id, []):
            try:
                sink.generation(
                    extra_id,
                    model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    input_preview=input_preview,
                    output_preview=output_preview,
                )
            except Exception:
                continue

    def end_trace(self, trace_id: str, status: str = "ok") -> None:
        self.local.end_trace(trace_id, status)
        run_id = self._run_by_trace.get(trace_id, trace_id)
        for sink in self.extras:
            try:
                sink.end_trace(run_id, status)
            except Exception:
                continue

    def get_trace(self, trace_id: str) -> Trace | None:
        return self.local.get_trace(trace_id)

    def get_trace_by_run(self, run_id: str) -> Trace | None:
        return self.local.get_trace_by_run(run_id)

    def list_traces(self, limit: int = 30) -> list[Trace]:
        return self.local.list_traces(limit)


def _unused_protocol(obs: Observability) -> Observability:
    return obs
