from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from creditlens.observability.local import LocalObservability


def _preview(value: Any, limit: int = 2000) -> str:
    text = str(value)
    return text[:limit]


class CreditLensCallback(BaseCallbackHandler):
    def __init__(
        self,
        obs: LocalObservability,
        trace_id: str,
        *,
        parent_span_id: str | None = None,
        node: str | None = None,
    ) -> None:
        self.obs = obs
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.node = node
        self._runs: dict[str, str] = {}
        self._inputs: dict[str, str] = {}

    def on_chain_start(self, serialized: dict[str, Any], inputs: dict[str, Any], *, run_id: UUID, **kwargs: Any) -> None:
        name = (serialized or {}).get("name") or kwargs.get("name") or "chain"
        span_id = self.obs.start_span(
            self.trace_id,
            str(name),
            parent_span_id=self.parent_span_id,
            kind="chain",
            attributes={"inputs": list(inputs.keys()) if isinstance(inputs, dict) else []},
            code_path="langchain_core.callbacks.BaseCallbackHandler.on_chain_start",
            mmd_node=self.node,
        )
        self._runs[str(run_id)] = span_id

    def on_chain_end(self, outputs: dict[str, Any], *, run_id: UUID, **kwargs: Any) -> None:
        span_id = self._runs.get(str(run_id))
        if span_id:
            self.obs.end_span(span_id)

    def on_chat_model_start(self, serialized: dict[str, Any], messages: list, *, run_id: UUID, **kwargs: Any) -> None:
        self._inputs[str(run_id)] = _preview(messages)
        span_id = self.obs.start_span(
            self.trace_id,
            "llm",
            parent_span_id=self.parent_span_id,
            kind="llm",
            code_path="creditlens.llm.routerai.chat_model",
            mmd_node="LLM",
        )
        self._runs[str(run_id)] = span_id

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], *, run_id: UUID, **kwargs: Any) -> None:
        if str(run_id) in self._runs:
            self._inputs.setdefault(str(run_id), _preview(prompts))
            return
        self._inputs[str(run_id)] = _preview(prompts)
        span_id = self.obs.start_span(
            self.trace_id,
            "llm",
            parent_span_id=self.parent_span_id,
            kind="llm",
            code_path="creditlens.llm.routerai.chat_model",
            mmd_node="LLM",
        )
        self._runs[str(run_id)] = span_id

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        span_id = self._runs.get(str(run_id))
        if not span_id:
            return
        text = ""
        try:
            text = response.generations[0][0].text
        except Exception:
            text = _preview(response)
        usage: dict[str, Any] = {}
        llm_output = getattr(response, "llm_output", None) or {}
        if isinstance(llm_output, dict):
            usage = llm_output.get("token_usage") or {}
        model = "routerai"
        if isinstance(llm_output, dict) and llm_output.get("model_name"):
            model = str(llm_output["model_name"])
        self.obs.generation(
            span_id,
            model=model,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            input_preview=self._inputs.get(str(run_id), ""),
            output_preview=text,
        )
        self.obs.end_span(span_id)
