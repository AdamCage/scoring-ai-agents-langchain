from __future__ import annotations

import json
import queue
import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from contracts.application import Application
from contracts.events import SSEEvent
from contracts.state import CreditState

from creditlens.agents.graph import get_graph
from creditlens.agents.nodes import _top_shap
from creditlens.agents.runtime import RunContext, bind_context, make_event, unbind_context
from creditlens.db import get_conn
from creditlens.observability.factory import get_observability
from creditlens.rag.retrieve import RAG_VERSION
from creditlens.scoring.features import FEATURE_LABELS
from creditlens.scoring.service import explain_application, load_metadata, score_application

_SENTINEL = object()


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


def run_analysis(
    app: Application,
    run_id: str | None = None,
    sink: Any | None = None,
) -> tuple[str, dict[str, Any], list[SSEEvent]]:
    run_id = run_id or str(uuid.uuid4())
    events: list[SSEEvent] = []
    obs = get_observability()
    meta = load_metadata()

    def emit(event: SSEEvent) -> None:
        events.append(event)
        if sink is not None:
            sink(event)

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
        "run_id": run_id,
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
    ctx = RunContext(run_id=run_id, trace_id=trace_id, obs=obs, parent_span_id=parent, emit=emit)
    bind_context(ctx)
    try:
        for step in graph.stream(state, stream_mode="updates"):
            for _node, update in step.items():
                state.update(update)
        status = "ok"
        if state.get("interrupt_reason") == "validation":
            status = "interrupt"
            emit(make_event("interrupt", run_id, "request_information", {"reason": "validation"}))
        elif state.get("recommendation") and state["recommendation"].requires_human_review:
            emit(
                make_event(
                    "interrupt",
                    run_id,
                    "human_review",
                    {"reason": "human_review", "decision": state["recommendation"].decision},
                )
            )
        obs.end_span(parent)
        obs.end_trace(trace_id, "ok")
        _save_run(run_id, app, dict(state), status)
        emit(
            make_event(
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
        emit(make_event("error", run_id, None, {"message": str(exc)}))
        raise
    finally:
        unbind_context(run_id)
    return run_id, dict(state), events


def iter_analysis_events(app: Application, run_id: str | None = None) -> Iterator[SSEEvent]:
    pending: queue.Queue[Any] = queue.Queue()

    def worker() -> None:
        try:
            run_analysis(app, run_id, sink=pending.put)
        except Exception:
            pass
        finally:
            pending.put(_SENTINEL)

    threading.Thread(target=worker, daemon=True, name="creditlens-analyze").start()
    while True:
        item = pending.get()
        if item is _SENTINEL:
            break
        yield item


def iter_sse(app: Application, run_id: str | None = None) -> Iterator[str]:
    for event in iter_analysis_events(app, run_id):
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
