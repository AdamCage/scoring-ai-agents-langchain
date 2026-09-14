from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from contracts.application import Application
from contracts.events import SSEEvent
from contracts.state import CreditState

from creditlens.agents.graph import get_graph
from creditlens.agents.nodes import _top_shap
from creditlens.db import get_conn
from creditlens.observability.factory import get_observability
from creditlens.rag.retrieve import RAG_VERSION
from creditlens.scoring.features import FEATURE_LABELS
from creditlens.scoring.service import explain_application, load_metadata, score_application

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


def _now_ms() -> int:
    return int(time.time() * 1000)


def _event(event_type: str, run_id: str, node: str | None, data: dict[str, Any]) -> SSEEvent:
    return SSEEvent(type=event_type, node=node, run_id=run_id, timestamp_ms=_now_ms(), data=data)  # type: ignore[arg-type]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _save_run(run_id: str, app: Application, state: dict[str, Any], status: str) -> None:
    conn = get_conn()
    rec = state.get("recommendation")
    rec_json = rec.model_dump_json() if rec is not None and hasattr(rec, "model_dump_json") else (
        json.dumps(rec, ensure_ascii=False) if rec is not None else None
    )
    serializable = _jsonable(state)
    now = datetime.now(UTC).isoformat()
    existing = conn.execute("SELECT run_id FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE runs SET status=?, updated_at=?, state_json=?, recommendation_json=?
            WHERE run_id=?
            """,
            (status, now, json.dumps(serializable, ensure_ascii=False, default=str), rec_json, run_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO runs(run_id, application_id, thread_id, status, created_at, updated_at,
                             application_json, state_json, recommendation_json, human_decision)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                run_id,
                app.application_id,
                run_id,
                status,
                now,
                now,
                app.model_dump_json(),
                json.dumps(serializable, ensure_ascii=False, default=str),
                rec_json,
            ),
        )
    conn.commit()


def run_analysis(app: Application, run_id: str | None = None) -> tuple[str, dict[str, Any], list[SSEEvent]]:
    run_id = run_id or str(uuid.uuid4())
    events: list[SSEEvent] = []
    obs = get_observability()
    meta = load_metadata()
    trace_id = obs.start_trace(
        run_id,
        "creditlens.analyze",
        {
            "application_id": app.application_id,
            "segment": app.segment,
            "model_version": meta.get("model_version", "catboost-v1"),
            "prompt_version": "risk-v1",
            "rag_version": RAG_VERSION,
        },
    )
    graph = get_graph()
    state: CreditState = {
        "application": app,
        "retrieved_documents": [],
        "node_trace": [],
        "retrieval_attempts": 0,
        "messages": [],
    }
    _save_run(run_id, app, dict(state), "running")

    parent = obs.start_span(
        trace_id,
        "langgraph.run",
        kind="graph",
        code_path="creditlens.agents.graph.build_graph",
        mmd_node="langgraph-credit-flow",
    )
    try:
        for step in graph.stream(state, stream_mode="updates"):
            for node, update in step.items():
                code_path, mmd = NODE_META.get(node, (f"creditlens.agents.nodes.{node}", node))
                events.append(_event("node_start", run_id, node, {"mmd_node": mmd, "code_path": code_path}))
                span_id = obs.start_span(
                    trace_id,
                    node,
                    parent_span_id=parent,
                    kind="tool" if node in {"calculate_score", "explain_score", "retrieve_policy", "retrieve_more"} else "chain",
                    attributes={"mmd_node": mmd},
                    code_path=code_path,
                    mmd_node=mmd,
                )
                if node in {"retrieve_policy", "retrieve_more"} and update.get("retrieval_debug"):
                    debug = update["retrieval_debug"]
                    obs.event(span_id, "vector", {"ids": debug.vector_ids})
                    obs.event(span_id, "bm25", {"ids": debug.bm25_ids})
                    obs.event(span_id, "rrf", {"ids": debug.fused_ids})
                    obs.event(span_id, "rerank", {"ids": debug.reranked_ids})
                    events.append(
                        _event(
                            "retrieval",
                            run_id,
                            node,
                            {
                                "vector": debug.vector_ids,
                                "bm25": debug.bm25_ids,
                                "rrf": debug.fused_ids,
                                "rerank": debug.reranked_ids,
                                "latency_ms": debug.latency_ms,
                            },
                        )
                    )
                if node == "calculate_score" and update.get("scoring"):
                    events.append(_event("tool", run_id, node, update["scoring"].model_dump()))
                state.update(update)
                obs.end_span(span_id)
                events.append(
                    _event(
                        "node_end",
                        run_id,
                        node,
                        {
                            "keys": list(update.keys()),
                            "mmd_node": mmd,
                        },
                    )
                )
        status = "ok"
        if state.get("interrupt_reason") == "validation":
            status = "interrupt"
            events.append(_event("interrupt", run_id, "request_information", {"reason": "validation"}))
        elif state.get("recommendation") and state["recommendation"].requires_human_review:
            events.append(
                _event(
                    "interrupt",
                    run_id,
                    "human_review",
                    {"reason": "human_review", "decision": state["recommendation"].decision},
                )
            )
        obs.end_span(parent)
        obs.end_trace(trace_id, "ok")
        _save_run(run_id, app, dict(state), status)
        events.append(
            _event(
                "done",
                run_id,
                None,
                {
                    "status": status,
                    "recommendation": state.get("recommendation").model_dump() if state.get("recommendation") else None,
                    "scoring": state.get("scoring").model_dump() if state.get("scoring") else None,
                    "shap": state.get("shap").model_dump() if state.get("shap") else None,
                    "documents": [doc.model_dump() for doc in state.get("retrieved_documents") or []],
                    "analysis": state.get("analysis").model_dump() if state.get("analysis") else None,
                    "critique": state.get("critique").model_dump() if state.get("critique") else None,
                    "node_trace": state.get("node_trace") or [],
                    "application": app.model_dump(),
                },
            )
        )
    except Exception as exc:
        obs.end_span(parent, status="error", error=str(exc))
        obs.end_trace(trace_id, "error")
        _save_run(run_id, app, dict(state), "error")
        events.append(_event("error", run_id, None, {"message": str(exc)}))
        raise
    return run_id, dict(state), events


def iter_sse(app: Application, run_id: str | None = None) -> Iterator[str]:
    _run_id, _state, events = run_analysis(app, run_id)
    for event in events:
        yield f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"


def load_run(run_id: str) -> dict[str, Any] | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if not row:
        return None
    return {
        "run_id": row["run_id"],
        "application_id": row["application_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "application": json.loads(row["application_json"]),
        "state": json.loads(row["state_json"]) if row["state_json"] else {},
        "recommendation": json.loads(row["recommendation_json"]) if row["recommendation_json"] else None,
        "human_decision": row["human_decision"],
    }


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [
        {
            "run_id": row["run_id"],
            "application_id": row["application_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "recommendation": json.loads(row["recommendation_json"]) if row["recommendation_json"] else None,
        }
        for row in rows
    ]


def apply_human_decision(run_id: str, decision: str, comment: str = "") -> dict[str, Any] | None:
    conn = get_conn()
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE runs SET human_decision=?, status=?, updated_at=? WHERE run_id=?",
        (json.dumps({"decision": decision, "comment": comment}, ensure_ascii=False), "reviewed", now, run_id),
    )
    conn.commit()
    return load_run(run_id)


def what_if(app: Application, overrides: dict[str, Any]) -> dict[str, Any]:
    payload = app.model_dump()
    payload.update(overrides)
    updated = Application.model_validate(payload)
    before = score_application(app)
    after = score_application(updated)
    shap_before = explain_application(app)
    shap_after = explain_application(updated)
    return {
        "before": before.model_dump(),
        "after": after.model_dump(),
        "shap_before": shap_before.model_dump(),
        "shap_after": shap_after.model_dump(),
        "application": updated.model_dump(),
        "delta": {
            "score": round(after.score - before.score, 4),
            "pd": round(after.pd - before.pd, 4),
            "risk_band": [before.risk_band, after.risk_band],
            "top_after_positive": _top_shap(shap_after, -1),
            "top_after_negative": _top_shap(shap_after, 1),
        },
        "labels": FEATURE_LABELS,
    }


def chat_about_run(run_id: str, question: str) -> dict[str, Any]:
    run = load_run(run_id)
    if not run:
        raise ValueError("run not found")
    state = run["state"]
    scoring = state.get("scoring") or {}
    shap = state.get("shap") or {}
    rec = state.get("recommendation") or {}
    raw_docs = state.get("retrieved_documents") or []
    docs: list[dict[str, Any]] = [doc if isinstance(doc, dict) else {"citation": str(doc)} for doc in raw_docs]
    feats = shap.get("features") or [] if isinstance(shap, dict) else []
    answer = (
        f"По заявке {run['application_id']} модель дала score={scoring.get('score') if isinstance(scoring, dict) else scoring}, "
        f"PD={scoring.get('pd') if isinstance(scoring, dict) else ''}, "
        f"диапазон {scoring.get('risk_band') if isinstance(scoring, dict) else ''}, "
        f"решение {scoring.get('decision') if isinstance(scoring, dict) else ''}. "
    )
    q = question.lower()
    if "shap" in q or "влия" in q or "фактор" in q or "нагруз" in q:
        top = ", ".join(
            f"{f.get('label')} ({f.get('shap_value'):+})"
            for f in feats[:5]
            if isinstance(f, dict)
        )
        answer += f"Главные SHAP-факторы: {top}. "
    if "политик" in q or "правил" in q or "цитат" in q or "нагруз" in q:
        cites = ", ".join(doc.get("citation", "") for doc in docs[:4])
        answer += f"Применённые основания: {cites}. "
    if "что если" in q or "what" in q or "измен" in q:
        answer += "Числовой what-if считается той же CatBoost-моделью, LLM только комментирует дельту. "
    if isinstance(rec, dict):
        answer += rec.get("summary") or ""
    conn = get_conn()
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO chat_messages(run_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
        (run_id, question, now),
    )
    conn.execute(
        "INSERT INTO chat_messages(run_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
        (run_id, answer, now),
    )
    conn.commit()
    return {"answer": answer, "run_id": run_id, "citations": [d.get("citation") for d in docs]}
