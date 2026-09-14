from __future__ import annotations

import uuid
from typing import Any

from creditlens.config import get_settings


def available() -> bool:
    return get_settings().langfuse_configured


def public_url() -> str | None:
    settings = get_settings()
    if not settings.langfuse_configured:
        return None
    return (settings.langfuse_public_url or settings.langfuse_host).rstrip("/")


def trace_url(run_id: str) -> str | None:
    base = public_url()
    if not base:
        return None
    return f"{base}/trace/{run_id}"


def _client() -> Any | None:
    if not available():
        return None
    settings = get_settings()
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception:
        return None


class LangfuseObservability:
    name = "langfuse"

    def __init__(self) -> None:
        self._client = _client()
        self._traces: dict[str, Any] = {}
        self._spans: dict[str, Any] = {}

    def start_trace(self, run_id: str, name: str, metadata: dict[str, Any]) -> str:
        if self._client is None:
            return run_id
        try:
            trace = self._client.trace(id=run_id, name=name, metadata=metadata, session_id=run_id)
            self._traces[run_id] = trace
        except Exception:
            pass
        return run_id

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
        span_id = str(uuid.uuid4())
        parent = self._spans.get(parent_span_id or "") or self._traces.get(trace_id)
        if parent is None:
            return span_id
        try:
            meta = {**(attributes or {}), "kind": kind, "code_path": code_path, "mmd_node": mmd_node}
            span = parent.span(name=name, metadata=meta)
            self._spans[span_id] = span
        except Exception:
            pass
        return span_id

    def end_span(self, span_id: str, status: str = "ok", error: str | None = None) -> None:
        span = self._spans.get(span_id)
        if span is None:
            return
        try:
            if error:
                span.end(status_message=error)
            else:
                span.end()
        except Exception:
            pass

    def event(self, span_id: str, name: str, payload: dict[str, Any] | None = None) -> None:
        span = self._spans.get(span_id)
        if span is None:
            return
        try:
            span.event(name=name, metadata=payload or {})
        except Exception:
            pass

    def generation(
        self,
        span_id: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        input_preview: str = "",
        output_preview: str = "",
    ) -> None:
        parent = self._spans.get(span_id) or next(iter(self._traces.values()), None)
        if parent is None:
            return
        try:
            gen = parent.generation(
                name="llm",
                model=model,
                input=input_preview,
                output=output_preview,
                usage={"input": prompt_tokens, "output": completion_tokens},
            )
            gen.end()
        except Exception:
            pass

    def end_trace(self, trace_id: str, status: str = "ok") -> None:
        if self._client is None:
            return
        try:
            self._client.flush()
        except Exception:
            pass

    def get_trace(self, trace_id: str) -> None:
        return None

    def get_trace_by_run(self, run_id: str) -> None:
        return None

    def list_traces(self, limit: int = 30) -> list:
        return []


def callback_handler(session_id: str | None = None) -> Any | None:
    if not available():
        return None
    settings = get_settings()
    try:
        from langfuse.callback import CallbackHandler

        return CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            session_id=session_id,
        )
    except Exception:
        try:
            from langfuse.langchain import CallbackHandler

            return CallbackHandler(session_id=session_id)
        except Exception:
            return None
