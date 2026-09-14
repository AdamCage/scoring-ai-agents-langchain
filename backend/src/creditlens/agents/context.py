from __future__ import annotations

import queue
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal

from contracts.events import SSEEvent

from creditlens.observability.factory import get_observability

NODE_META = {
    "validate_application": ("creditlens.agents.nodes.validate_application", "validate"),
    "request_information": ("creditlens.agents.nodes.request_information", "needInfo"),
    "calculate_score": ("creditlens.scoring.service.score_application", "scoreNode"),
    "explain_score": ("creditlens.scoring.service.explain_application", "shapNode"),
    "retrieve_policy": ("creditlens.rag.retrieve.retrieve_policy", "retrieveNode"),
    "retrieve_more": ("creditlens.rag.retrieve.retrieve_policy", "moreRag"),
    "risk_analysis": ("creditlens.agents.risk_agent.run_risk_analyst", "riskAgent"),
    "policy_critic": ("creditlens.agents.critic_agent.run_policy_critic", "criticAgent"),
    "synthesize": ("creditlens.agents.nodes.synthesize", "synthAgent"),
    "human_review": ("creditlens.agents.nodes.human_review", "humanReview"),
}

_run_ctx: ContextVar[RunContext | None] = ContextVar("creditlens_run", default=None)


def get_run_context() -> RunContext | None:
    return _run_ctx.get()


def _now_ms() -> int:
    return int(time.time() * 1000)


def make_event(event_type: str, run_id: str, node: str | None, data: dict[str, Any]) -> SSEEvent:
    return SSEEvent(type=event_type, node=node, run_id=run_id, timestamp_ms=_now_ms(), data=data)  # type: ignore[arg-type]


@dataclass
class RunContext:
    run_id: str
    trace_id: str
    parent_span_id: str
    events: queue.Queue[SSEEvent | None] = field(default_factory=queue.Queue)
    hitl: Literal["interrupt", "auto"] = "interrupt"
    retrieval_mode: str = "hybrid-rerank"
    prompt_version: str = "risk-v1"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens: dict[str, int] = field(default_factory=lambda: {"prompt": 0, "completion": 0})
    _seq: int = 0
    _started: dict[str, float] = field(default_factory=dict)
    _span_ids: dict[str, str] = field(default_factory=dict)

    def emit(self, event: SSEEvent) -> None:
        self.events.put(event)

    def close(self) -> None:
        self.events.put(None)

    def begin_node(self, node: str) -> str:
        self._seq += 1
        key = f"{node}:{self._seq}"
        obs = get_observability()
        code_path, mmd = NODE_META.get(node, (f"creditlens.agents.nodes.{node}", node))
        self._started[key] = time.perf_counter()
        span_id = obs.start_span(
            self.trace_id,
            node,
            parent_span_id=self.parent_span_id,
            kind="tool" if node in {"calculate_score", "explain_score", "retrieve_policy", "retrieve_more"} else "chain",
            attributes={"mmd_node": mmd},
            code_path=code_path,
            mmd_node=mmd,
        )
        self._span_ids[key] = span_id
        self.emit(make_event("node_start", self.run_id, node, {"mmd_node": mmd, "code_path": code_path, "key": key}))
        return key

    def finish_node(self, key: str, node: str, update: dict[str, Any], status: str = "ok", error: str | None = None) -> None:
        obs = get_observability()
        span_id = self._span_ids.get(key)
        duration_ms = 0.0
        if key in self._started:
            duration_ms = (time.perf_counter() - self._started[key]) * 1000
        if node in {"retrieve_policy", "retrieve_more"} and update.get("retrieval_debug"):
            debug = update["retrieval_debug"]
            payload = {
                "query": debug.query,
                "filters": debug.filters,
                "mode": getattr(debug, "mode", self.retrieval_mode),
                "vector": debug.vector_ids,
                "bm25": debug.bm25_ids,
                "rrf": debug.fused_ids,
                "rerank": debug.reranked_ids,
                "latency_ms": debug.latency_ms,
            }
            if span_id:
                obs.event(span_id, "vector", {"ids": debug.vector_ids})
                obs.event(span_id, "bm25", {"ids": debug.bm25_ids})
                obs.event(span_id, "rrf", {"ids": debug.fused_ids})
                obs.event(span_id, "rerank", {"ids": debug.reranked_ids})
            self.emit(make_event("retrieval", self.run_id, node, payload))
        if node == "calculate_score" and update.get("scoring"):
            scoring = update["scoring"]
            self.emit(
                make_event(
                    "tool",
                    self.run_id,
                    node,
                    scoring.model_dump() if hasattr(scoring, "model_dump") else dict(scoring),
                )
            )
        if span_id:
            obs_status = "ok" if status == "interrupt" else status
            obs.end_span(span_id, status=obs_status, error=error)
            if status == "interrupt":
                obs.event(span_id, "interrupt", {"node": node})
        code_path, mmd = NODE_META.get(node, (f"creditlens.agents.nodes.{node}", node))
        self.emit(
            make_event(
                "node_end",
                self.run_id,
                node,
                {
                    "keys": list(update.keys()),
                    "mmd_node": mmd,
                    "code_path": code_path,
                    "duration_ms": round(duration_ms, 2),
                    "status": status,
                    "error": error,
                },
            )
        )

    def record_tool(self, name: str, detail: str = "") -> None:
        item = {"name": name, "detail": detail[:400]}
        self.tool_calls.append(item)
        self.emit(make_event("tool", self.run_id, "risk_analysis", item))


def _is_graph_interrupt(exc: BaseException) -> bool:
    name = type(exc).__name__
    return "Interrupt" in name


def instrument(node: str):
    def decorator(fn):
        def wrapped(state):
            ctx = get_run_context()
            key = ctx.begin_node(node) if ctx else None
            try:
                result = fn(state)
                if ctx and key:
                    ctx.finish_node(key, node, result)
                return result
            except Exception as exc:
                if ctx and key:
                    status = "interrupt" if _is_graph_interrupt(exc) else "error"
                    ctx.finish_node(key, node, {}, status=status, error=None if status == "interrupt" else str(exc))
                raise

        wrapped.__name__ = getattr(fn, "__name__", node)
        wrapped.__wrapped__ = fn
        return wrapped

    return decorator
