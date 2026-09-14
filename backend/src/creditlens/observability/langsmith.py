from __future__ import annotations

import os
import uuid
from typing import Any

from creditlens.config import get_settings


def available() -> bool:
    return get_settings().langsmith_configured


def status() -> str:
    return "enabled" if available() else "ready_no_key"


def public_url() -> str | None:
    if not available():
        return None
    project = get_settings().langsmith_project
    return f"https://smith.langchain.com/projects/p/{project}"


def configure_env() -> None:
    settings = get_settings()
    if not settings.langsmith_api_key:
        return
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)
    if settings.langsmith_tracing:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"


class LangSmithObservability:
    name = "langsmith"

    def __init__(self) -> None:
        configure_env()
        self._enabled = available()

    def start_trace(self, run_id: str, name: str, metadata: dict[str, Any]) -> str:
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
        return str(uuid.uuid4())

    def end_span(self, span_id: str, status: str = "ok", error: str | None = None) -> None:
        return None

    def event(self, span_id: str, name: str, payload: dict[str, Any] | None = None) -> None:
        return None

    def generation(
        self,
        span_id: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        input_preview: str = "",
        output_preview: str = "",
    ) -> None:
        return None

    def end_trace(self, trace_id: str, status: str = "ok") -> None:
        return None

    def get_trace(self, trace_id: str) -> None:
        return None

    def get_trace_by_run(self, run_id: str) -> None:
        return None

    def list_traces(self, limit: int = 30) -> list:
        return []


def callback_handler() -> Any | None:
    if not available():
        return None
    configure_env()
    try:
        from langsmith.callbacks import LangChainTracer

        return LangChainTracer(project_name=get_settings().langsmith_project)
    except Exception:
        return None
