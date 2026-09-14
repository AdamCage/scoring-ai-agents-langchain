from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from creditlens.observability.local import LocalObservability


class CreditLensCallback(BaseCallbackHandler):
    def __init__(self, obs: LocalObservability, trace_id: str) -> None:
        self.obs = obs
        self.trace_id = trace_id
        self._runs: dict[str, str] = {}

    def on_chain_start(self, serialized: dict[str, Any], inputs: dict[str, Any], *, run_id: UUID, **kwargs: Any) -> None:
        name = (serialized or {}).get("name") or kwargs.get("name") or "chain"
        span_id = self.obs.start_span(
            self.trace_id,
            str(name),
            kind="chain",
            attributes={"inputs": list(inputs.keys()) if isinstance(inputs, dict) else []},
            code_path="langchain_core.callbacks.BaseCallbackHandler.on_chain_start",
        )
        self._runs[str(run_id)] = span_id

    def on_chain_end(self, outputs: dict[str, Any], *, run_id: UUID, **kwargs: Any) -> None:
        span_id = self._runs.get(str(run_id))
        if span_id:
            self.obs.end_span(span_id)

    def on_chat_model_start(self, serialized: dict[str, Any], messages: list, *, run_id: UUID, **kwargs: Any) -> None:
        span_id = self.obs.start_span(
            self.trace_id,
            "llm",
            kind="llm",
            code_path="creditlens.llm.routerai.chat_model",
            mmd_node="LLM",
        )
        self._runs[str(run_id)] = span_id

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        span_id = self._runs.get(str(run_id))
        if not span_id:
            return
        usage = {}
        llm_output = getattr(response, "llm_output", None) or {}
        if isinstance(llm_output, dict):
            usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
        generations = getattr(response, "generations", None) or []
        preview = ""
        if generations and generations[0]:
            first = generations[0][0] if isinstance(generations[0], list) else generations[0]
            preview = str(getattr(first, "text", "") or getattr(first, "message", "") or "")
        self.obs.generation(
            span_id,
            model=str(llm_output.get("model_name") or "routerai"),
            prompt_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
            output_preview=preview,
        )
        self.obs.end_span(span_id)

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, *, run_id: UUID, **kwargs: Any) -> None:
        name = (serialized or {}).get("name") or kwargs.get("name") or "tool"
        span_id = self.obs.start_span(
            self.trace_id,
            str(name),
            kind="tool",
            attributes={"input": input_str[:500]},
        )
        self._runs[str(run_id)] = span_id

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        span_id = self._runs.get(str(run_id))
        if span_id:
            self.obs.end_span(span_id)
