from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from contracts.events import SSEEvent

from creditlens.observability.local import LocalObservability

NODE_META = {
    "validate_application": ("creditlens.agents.nodes.validate_application", "validate"),
    "request_information": ("creditlens.agents.nodes.request_information", "needInfo"),
    "calculate_score": ("creditlens.scoring.service.score_application", "scoreNode"),
    "explain_score": ("creditlens.scoring.service.explain_application", "shapNode"),
    "retrieve_policy": ("creditlens.rag.retrieve.retrieve_policy", "retrieveNode"),
    "retrieve_more": ("creditlens.rag.retrieve.retrieve_policy", "moreRag"),
    "risk_analysis": ("creditlens.agents.nodes.risk_analysis", "riskAgent"),
    "policy_critic": ("creditlens.agents.nodes.policy_critic", "criticAgent"),
    "synthesize": ("creditlens.agents.nodes.synthesize", "synthAgent"),
    "human_review": ("creditlens.agents.nodes.human_review", "humanReview"),
}

TOOL_NODES = {"calculate_score", "explain_score"}
RETRIEVER_NODES = {"retrieve_policy", "retrieve_more"}

GRAPH_NODES = [
    {
        "id": "validate_application",
        "mmd": "validate",
        "label": "Проверка",
        "tech": "LangGraph",
        "kind": "chain",
    },
    {
        "id": "request_information",
        "mmd": "needInfo",
        "label": "Нужны данные",
        "tech": "LangGraph",
        "kind": "chain",
        "optional": True,
    },
    {
        "id": "calculate_score",
        "mmd": "scoreNode",
        "label": "Скоринг",
        "tech": "CatBoost",
        "kind": "tool",
    },
    {
        "id": "explain_score",
        "mmd": "shapNode",
        "label": "SHAP",
        "tech": "Tool",
        "kind": "tool",
        "parallel_group": "explain",
    },
    {
        "id": "retrieve_policy",
        "mmd": "retrieveNode",
        "label": "Политика",
        "tech": "RAG",
        "kind": "retriever",
        "parallel_group": "explain",
    },
    {
        "id": "risk_analysis",
        "mmd": "riskAgent",
        "label": "Аналитик",
        "tech": "LLM",
        "kind": "chain",
    },
    {
        "id": "policy_critic",
        "mmd": "criticAgent",
        "label": "Критик",
        "tech": "LLM",
        "kind": "chain",
    },
    {
        "id": "retrieve_more",
        "mmd": "moreRag",
        "label": "Ещё RAG",
        "tech": "RAG",
        "kind": "retriever",
        "optional": True,
    },
    {
        "id": "synthesize",
        "mmd": "synthAgent",
        "label": "Синтез",
        "tech": "LangGraph",
        "kind": "chain",
    },
    {
        "id": "human_review",
        "mmd": "humanReview",
        "label": "Ревью",
        "tech": "Human",
        "kind": "chain",
    },
]

GRAPH_EDGES = [
    {"source": "validate_application", "target": "request_information", "label": "invalid"},
    {"source": "validate_application", "target": "calculate_score", "label": "valid"},
    {"source": "calculate_score", "target": "explain_score", "label": ""},
    {"source": "calculate_score", "target": "retrieve_policy", "label": ""},
    {"source": "explain_score", "target": "risk_analysis", "label": ""},
    {"source": "retrieve_policy", "target": "risk_analysis", "label": ""},
    {"source": "risk_analysis", "target": "policy_critic", "label": ""},
    {"source": "policy_critic", "target": "retrieve_more", "label": "insufficient"},
    {"source": "retrieve_more", "target": "risk_analysis", "label": "loop"},
    {"source": "policy_critic", "target": "synthesize", "label": "acceptable"},
    {"source": "synthesize", "target": "human_review", "label": ""},
]

HAPPY_PATH = [
    "validate_application",
    "calculate_score",
    "explain_score",
    "retrieve_policy",
    "risk_analysis",
    "policy_critic",
    "synthesize",
    "human_review",
]


def node_kind(name: str) -> str:
    if name in TOOL_NODES:
        return "tool"
    if name in RETRIEVER_NODES:
        return "retriever"
    return "chain"


def _now_ms() -> int:
    return int(time.time() * 1000)


def make_event(event_type: str, run_id: str, node: str | None, data: dict[str, Any]) -> SSEEvent:
    return SSEEvent(type=event_type, node=node, run_id=run_id, timestamp_ms=_now_ms(), data=data)  # type: ignore[arg-type]


@dataclass
class RunContext:
    run_id: str
    trace_id: str
    obs: LocalObservability
    parent_span_id: str
    emit: Callable[[SSEEvent], None]
    streamed_nodes: set[str] = field(default_factory=set)


_lock = threading.Lock()
_by_run: dict[str, RunContext] = {}
_local = threading.local()


def bind_context(ctx: RunContext) -> None:
    with _lock:
        _by_run[ctx.run_id] = ctx
    _local.ctx = ctx
    _local.node = None
    _local.span_id = None


def unbind_context(run_id: str) -> None:
    with _lock:
        _by_run.pop(run_id, None)
    _local.ctx = None
    _local.node = None
    _local.span_id = None


def get_context(run_id: str | None = None) -> RunContext | None:
    ctx = getattr(_local, "ctx", None)
    if ctx is not None:
        return ctx
    if run_id:
        with _lock:
            found = _by_run.get(run_id)
        if found is not None:
            _local.ctx = found
            return found
    return None


def current_node() -> str | None:
    return getattr(_local, "node", None)


def current_span_id() -> str | None:
    return getattr(_local, "span_id", None)


def emit_token(text: str, node: str | None = None) -> None:
    ctx = get_context()
    if ctx is None or not text:
        return
    name = node or current_node()
    if name:
        ctx.streamed_nodes.add(name)
    ctx.emit(make_event("token", ctx.run_id, name, {"text": text}))


def _attach_thread(state: dict[str, Any] | None) -> RunContext | None:
    run_id = None
    if isinstance(state, dict):
        run_id = state.get("run_id")
    ctx = get_context(run_id if isinstance(run_id, str) else None)
    if ctx is not None:
        _local.ctx = ctx
    return ctx


def on_node_start(name: str, state: dict[str, Any]) -> None:
    ctx = _attach_thread(state)
    if ctx is None:
        return
    _local.node = name
    code_path, mmd = NODE_META.get(name, (f"creditlens.agents.nodes.{name}", name))
    span_id = ctx.obs.start_span(
        ctx.trace_id,
        name,
        parent_span_id=ctx.parent_span_id,
        kind=node_kind(name),
        attributes={"mmd_node": mmd},
        code_path=code_path,
        mmd_node=mmd,
    )
    _local.span_id = span_id
    ctx.emit(make_event("node_start", ctx.run_id, name, {"mmd_node": mmd, "code_path": code_path, "kind": node_kind(name)}))


def on_node_end(name: str, state: dict[str, Any], update: dict[str, Any]) -> None:
    ctx = _attach_thread(state)
    if ctx is None:
        return
    span_id = current_span_id()
    if name in RETRIEVER_NODES and update.get("retrieval_debug"):
        debug = update["retrieval_debug"]
        if span_id:
            ctx.obs.event(span_id, "vector", {"ids": debug.vector_ids})
            ctx.obs.event(span_id, "bm25", {"ids": debug.bm25_ids})
            ctx.obs.event(span_id, "rrf", {"ids": debug.fused_ids})
            ctx.obs.event(span_id, "rerank", {"ids": debug.reranked_ids})
        ctx.emit(
            make_event(
                "retrieval",
                ctx.run_id,
                name,
                {
                    "vector": debug.vector_ids,
                    "bm25": debug.bm25_ids,
                    "rrf": debug.fused_ids,
                    "rerank": debug.reranked_ids,
                    "latency_ms": debug.latency_ms,
                },
            )
        )
    if name == "calculate_score" and update.get("scoring"):
        ctx.emit(make_event("tool", ctx.run_id, name, update["scoring"].model_dump()))
    if name == "explain_score" and update.get("shap"):
        ctx.emit(make_event("tool", ctx.run_id, name, update["shap"].model_dump()))
    preview: dict[str, Any] = {}
    analysis = update.get("analysis")
    if analysis is not None:
        preview["summary"] = analysis.summary
        if name not in ctx.streamed_nodes:
            emit_token(analysis.summary, name)
    critique = update.get("critique")
    if critique is not None:
        preview["acceptable"] = critique.acceptable
        preview["issues"] = critique.issues
        preview["missing_citations"] = critique.missing_citations
        text = (
            "Критик принял пакет."
            if critique.acceptable
            else "Критик запросил ещё документы: " + "; ".join(critique.issues + critique.missing_citations)
        )
        if name not in ctx.streamed_nodes:
            emit_token(text, name)
    recommendation = update.get("recommendation")
    if recommendation is not None:
        preview["title"] = recommendation.title
        preview["decision"] = recommendation.decision
        if name not in ctx.streamed_nodes and recommendation.summary:
            emit_token(recommendation.summary, name)
    if span_id:
        if preview:
            ctx.obs.event(span_id, "output", preview)
        ctx.obs.end_span(span_id)
    _, mmd = NODE_META.get(name, (f"creditlens.agents.nodes.{name}", name))
    ctx.emit(
        make_event(
            "node_end",
            ctx.run_id,
            name,
            {"keys": list(update.keys()), "mmd_node": mmd, "preview": preview},
        )
    )
    _local.node = None
    _local.span_id = None


def on_node_error(name: str, state: dict[str, Any], exc: Exception) -> None:
    ctx = _attach_thread(state)
    if ctx is None:
        return
    span_id = current_span_id()
    if span_id:
        ctx.obs.end_span(span_id, status="error", error=str(exc))
    _local.node = None
    _local.span_id = None


def traced(name: str, fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    def wrapped(state: dict[str, Any]) -> dict[str, Any]:
        on_node_start(name, state)
        try:
            update = fn(state)
            on_node_end(name, state, update)
            return update
        except Exception as exc:
            on_node_error(name, state, exc)
            raise

    wrapped.__name__ = getattr(fn, "__name__", name)
    return wrapped


def graph_definition() -> dict[str, Any]:
    from creditlens.config import ROOT

    mermaid_path = ROOT / "docs" / "architecture" / "langgraph-credit-flow.mmd"
    mermaid = mermaid_path.read_text(encoding="utf-8") if mermaid_path.exists() else ""
    return {
        "nodes": GRAPH_NODES,
        "edges": GRAPH_EDGES,
        "happy_path": HAPPY_PATH,
        "mermaid": mermaid,
        "node_meta": {key: {"code_path": path, "mmd_node": mmd} for key, (path, mmd) in NODE_META.items()},
    }
