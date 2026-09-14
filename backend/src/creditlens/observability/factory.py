from __future__ import annotations

from typing import Any

from creditlens.observability.callbacks import CreditLensCallback
from creditlens.observability.composite import CompositeObservability
from creditlens.observability.langfuse import LangfuseObservability
from creditlens.observability.langfuse import available as langfuse_available
from creditlens.observability.langfuse import callback_handler as langfuse_callback
from creditlens.observability.langsmith import LangSmithObservability
from creditlens.observability.langsmith import available as langsmith_available
from creditlens.observability.langsmith import callback_handler as langsmith_callback
from creditlens.observability.langsmith import configure_env as configure_langsmith
from creditlens.observability.local import LocalObservability

_local = LocalObservability()
_composite: CompositeObservability | None = None


def get_observability() -> CompositeObservability:
    global _composite
    if _composite is None:
        extras: list[Any] = []
        if langfuse_available():
            extras.append(LangfuseObservability())
        if langsmith_available():
            configure_langsmith()
            extras.append(LangSmithObservability())
        _composite = CompositeObservability(_local, extras)
    return _composite


def langchain_callbacks(trace_id: str, session_id: str | None = None) -> list[Any]:
    callbacks: list[Any] = []
    if langfuse_available() or langsmith_available():
        callbacks.append(CreditLensCallback(_local, trace_id))
    handler = langfuse_callback(session_id)
    if handler is not None:
        callbacks.append(handler)
    smith = langsmith_callback()
    if smith is not None:
        callbacks.append(smith)
    return callbacks


def reset_observability() -> None:
    global _composite
    _composite = None
