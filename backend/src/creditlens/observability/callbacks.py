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
        if span_id:
            self.obs.generation(span_id, model=str(getattr(response, "llm_output", {}) or "routerai"))
            self.obs.end_span(span_id)
