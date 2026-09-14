from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, Literal

from contracts.application import Application
from contracts.events import SSEEvent
from contracts.state import CreditState

from creditlens.agents.context import RunContext, _run_ctx, make_event
from creditlens.agents.graph import get_graph
from creditlens.agents.nodes import _top_shap
from creditlens.db import DB_LOCK, get_conn
from creditlens.observability.factory import get_observability, langchain_callbacks
from creditlens.observability.langfuse import trace_url as langfuse_trace_url
from creditlens.rag.retrieve import RAG_VERSION
from creditlens.scoring.features import FEATURE_LABELS
from creditlens.scoring.service import explain_application, load_metadata, score_application

HitlMode = Literal["interrupt", "auto"]


def _now() -> datetime:
    return datetime.now(UTC)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _save_run(run_id: str, app: Application, state: dict[str, Any], status: str) -> None:
    with DB_LOCK:
        _save_run_unlocked(run_id, app, state, status)


def _save_run_unlocked(run_id: str, app: Application, state: dict[str, Any], status: str) -> None:
    conn = get_conn()
    rec = state.get("recommendation")
    rec_json = rec.model_dump_json() if rec is not None and hasattr(rec, "model_dump_json") else (
        json.dumps(rec, ensure_ascii=False) if rec is not None else None
    )
    serializable = _jsonable(state)
    now = _now().isoformat()
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


def _plain(update: Any) -> dict[str, Any]:
    if hasattr(update, "model_dump"):
        return update.model_dump()
    if isinstance(update, dict):
        return update
    return {}


def _interrupt_data(update: Any) -> dict[str, Any]:
    if isinstance(update, (list, tuple)):
        items = list(update)
    else:
        items = [update]
    if not items:
        return {"reason": "human_review"}
    first = items[0]
    value = getattr(first, "value", first)
    if isinstance(value, dict):
        return value
    if isinstance(first, dict):
        return first
    return {"reason": "human_review", "value": str(value)}


def _done_payload(app: Application, state: dict[str, Any], status: str, ctx: RunContext) -> dict[str, Any]:
    debug = state.get("retrieval_debug")
    return {
        "status": status,
        "recommendation": state.get("recommendation").model_dump() if state.get("recommendation") else None,
        "scoring": state.get("scoring").model_dump() if state.get("scoring") else None,
        "shap": state.get("shap").model_dump() if state.get("shap") else None,
        "documents": [doc.model_dump() for doc in state.get("retrieved_documents") or []],
        "analysis": state.get("analysis").model_dump() if state.get("analysis") else None,
        "critique": state.get("critique").model_dump() if state.get("critique") else None,
        "node_trace": state.get("node_trace") or [],
        "application": app.model_dump(),
        "retrieval_debug": debug.model_dump() if debug is not None and hasattr(debug, "model_dump") else debug,
        "langfuse_url": langfuse_trace_url(ctx.run_id),
        "tool_calls": ctx.tool_calls,
        "tokens": ctx.tokens,
        "human_decision": state.get("human_decision"),
        "interrupt_reason": state.get("interrupt_reason"),
    }


def _resume_command(decision: str) -> Any:
    try:
        from langgraph.types import Command

        return Command(resume={"action": decision, "decision": decision})
    except ImportError:
        return None


def _graph_config(run_id: str, trace_id: str) -> dict[str, Any]:
    return {
        "configurable": {"thread_id": run_id},
        "callbacks": langchain_callbacks(trace_id, run_id),
        "recursion_limit": 25,
    }


def _checkpoint(ctx: RunContext, app: Application, state: dict[str, Any], status: str) -> None:
    state["tool_calls"] = list(ctx.tool_calls)
    _save_run(ctx.run_id, app, state, status)


def _run_graph(
    ctx: RunContext,
    app: Application,
    payload: Any,
    state: dict[str, Any],
) -> None:
    obs = get_observability()
    graph = get_graph()
    config = _graph_config(ctx.run_id, ctx.trace_id)
    token = _run_ctx.set(ctx)
    try:
        for step in graph.stream(payload, config, stream_mode="updates"):
            if not isinstance(step, dict):
                continue
            for node, update in step.items():
                if node == "__interrupt__":
                    data = _interrupt_data(update)
                    snapshot = graph.get_state(config)
                    if snapshot and snapshot.values:
                        state.update(snapshot.values)
                    _checkpoint(ctx, app, dict(state), "interrupt")
                    ctx.emit(make_event("interrupt", ctx.run_id, "human_review", data))
                    return
                if isinstance(update, dict):
                    state.update(update)
        snapshot = graph.get_state(config)
        if snapshot and snapshot.values:
            state.update(snapshot.values)
        if snapshot and snapshot.next:
            rec = state.get("recommendation")
            scoring = state.get("scoring")
            data = {
                "reason": "human_review",
                "pd": scoring.pd if scoring is not None else None,
                "score": scoring.score if scoring is not None else None,
                "risk_band": scoring.risk_band if scoring is not None else None,
                "decision": rec.decision if rec else None,
            }
            _checkpoint(ctx, app, dict(state), "interrupt")
            ctx.emit(make_event("interrupt", ctx.run_id, "human_review", data))
            return
        status = "ok"
        if state.get("interrupt_reason") == "validation":
            status = "interrupt"
            ctx.emit(make_event("interrupt", ctx.run_id, "request_information", {"reason": "validation"}))
            ctx.emit(make_event("done", ctx.run_id, None, _done_payload(app, state, status, ctx)))
            obs.end_span(ctx.parent_span_id)
            obs.end_trace(ctx.trace_id, "ok")
            _checkpoint(ctx, app, dict(state), status)
            return
        if state.get("interrupt_reason") == "human_review" and ctx.hitl == "interrupt":
            rec = state.get("recommendation")
            ctx.emit(
                make_event(
                    "interrupt",
                    ctx.run_id,
                    "human_review",
                    {"reason": "human_review", "decision": rec.decision if rec else None},
                )
            )
            _checkpoint(ctx, app, dict(state), "interrupt")
            return
        obs.end_span(ctx.parent_span_id)
        obs.end_trace(ctx.trace_id, "ok")
        _checkpoint(ctx, app, dict(state), status)
        ctx.emit(make_event("done", ctx.run_id, None, _done_payload(app, state, status, ctx)))
    except Exception as exc:
        name = type(exc).__name__
        if "Interrupt" in name:
            rec = state.get("recommendation")
            ctx.emit(
                make_event(
                    "interrupt",
                    ctx.run_id,
                    "human_review",
                    {"reason": "human_review", "decision": rec.decision if rec else None, "error": str(exc)},
                )
            )
            _checkpoint(ctx, app, dict(state), "interrupt")
            return
        obs.end_span(ctx.parent_span_id, status="error", error=str(exc))
        obs.end_trace(ctx.trace_id, "error")
        _checkpoint(ctx, app, dict(state), "error")
        ctx.emit(make_event("error", ctx.run_id, None, {"message": str(exc)}))
    finally:
        _run_ctx.reset(token)
        ctx.close()


def _start_context(
    app: Application,
    run_id: str,
    *,
    hitl: HitlMode,
    retrieval_mode: str,
    prompt_version: str,
) -> RunContext:
    obs = get_observability()
    meta = load_metadata()
    trace_id = obs.start_trace(
        run_id,
        "creditlens.analyze",
        {
            "application_id": app.application_id,
            "segment": app.segment,
            "model_version": meta.get("model_version", "catboost-v1"),
            "prompt_version": prompt_version,
            "rag_version": RAG_VERSION,
            "retrieval_mode": retrieval_mode,
        },
    )
    parent = obs.start_span(
        trace_id,
        "langgraph.run",
        kind="graph",
        code_path="creditlens.agents.graph.build_graph",
        mmd_node="langgraph-credit-flow",
    )
    return RunContext(
        run_id=run_id,
        trace_id=trace_id,
        parent_span_id=parent,
        hitl=hitl,
        retrieval_mode=retrieval_mode,
        prompt_version=prompt_version,
    )


def stream_analysis(
    app: Application | None = None,
    run_id: str | None = None,
    *,
    hitl: HitlMode = "interrupt",
    retrieval_mode: str = "hybrid-rerank",
    prompt_version: str = "risk-v1",
    resume: str | None = None,
) -> Iterator[SSEEvent]:
    if resume:
        if not run_id:
            raise ValueError("run_id required to resume")
        stored = load_run(run_id)
        if not stored:
            raise ValueError("run not found")
        app = Application.model_validate(stored["application"])
        state = stored.get("state") or {}
        obs = get_observability()
        existing = obs.get_trace_by_run(run_id)
        trace_id = existing.trace_id if existing else obs.start_trace(run_id, "creditlens.analyze", {})
        parent = existing.spans[0].span_id if existing and existing.spans else obs.start_span(trace_id, "langgraph.run")
        ctx = RunContext(
            run_id=run_id,
            trace_id=trace_id,
            parent_span_id=parent,
            hitl=hitl,
            retrieval_mode=str(state.get("retrieval_mode") or retrieval_mode),
            prompt_version=str(state.get("prompt_version") or prompt_version),
        )
        command = _resume_command(resume)
        payload: Any = command if command is not None else {"human_decision": resume}
        if command is None:
            graph = get_graph()
            graph.update_state(_graph_config(run_id, trace_id), {"human_decision": resume})
            payload = None
        worker = threading.Thread(target=_run_graph, args=(ctx, app, payload, dict(state)), daemon=True)
        worker.start()
        while True:
            event = ctx.events.get()
            if event is None:
                break
            yield event
        worker.join(timeout=30)
        return

    if app is None:
        raise ValueError("application required")
    run_id = run_id or str(uuid.uuid4())
    ctx = _start_context(app, run_id, hitl=hitl, retrieval_mode=retrieval_mode, prompt_version=prompt_version)
    state: CreditState = {
        "application": app,
        "retrieved_documents": [],
        "node_trace": [],
        "retrieval_attempts": 0,
        "messages": [],
        "retrieval_mode": retrieval_mode,
        "prompt_version": prompt_version,
        "tool_calls": [],
    }
    _save_run(run_id, app, dict(state), "running")
    worker = threading.Thread(target=_run_graph, args=(ctx, app, state, dict(state)), daemon=True)
    worker.start()
    while True:
        event = ctx.events.get()
        if event is None:
            break
        yield event
    worker.join(timeout=60)


def _hydrate_state(raw: dict[str, Any], app: Application | None = None) -> dict[str, Any]:
    from contracts.rag import RetrievalDebug, RetrievedDocument
    from contracts.recommendation import Critique, Recommendation, RiskAnalysis
    from contracts.scoring import ScoringResult, ShapResult

    state = dict(raw)
    if app is not None:
        state["application"] = app
    if isinstance(state.get("scoring"), dict):
        state["scoring"] = ScoringResult.model_validate(state["scoring"])
    if isinstance(state.get("shap"), dict):
        state["shap"] = ShapResult.model_validate(state["shap"])
    if isinstance(state.get("analysis"), dict):
        state["analysis"] = RiskAnalysis.model_validate(state["analysis"])
    if isinstance(state.get("critique"), dict):
        state["critique"] = Critique.model_validate(state["critique"])
    if isinstance(state.get("recommendation"), dict):
        state["recommendation"] = Recommendation.model_validate(state["recommendation"])
    if isinstance(state.get("retrieval_debug"), dict):
        state["retrieval_debug"] = RetrievalDebug.model_validate(state["retrieval_debug"])
    docs = state.get("retrieved_documents") or []
    if docs and isinstance(docs[0], dict):
        state["retrieved_documents"] = [RetrievedDocument.model_validate(doc) for doc in docs]
    return state


def run_analysis(
    app: Application,
    run_id: str | None = None,
    *,
    hitl: HitlMode = "auto",
    retrieval_mode: str = "hybrid-rerank",
    prompt_version: str = "risk-v1",
) -> tuple[str, dict[str, Any], list[SSEEvent]]:
    events = list(
        stream_analysis(
            app,
            run_id,
            hitl=hitl,
            retrieval_mode=retrieval_mode,
            prompt_version=prompt_version,
        )
    )
    resolved = events[0].run_id if events else (run_id or "")
    done = next((event for event in events if event.type == "done"), None)
    if done:
        state = _hydrate_state(
            {
                "scoring": done.data.get("scoring"),
                "shap": done.data.get("shap"),
                "analysis": done.data.get("analysis"),
                "critique": done.data.get("critique"),
                "recommendation": done.data.get("recommendation"),
                "retrieved_documents": done.data.get("documents"),
                "retrieval_debug": done.data.get("retrieval_debug"),
                "node_trace": done.data.get("node_trace") or [],
                "human_decision": done.data.get("human_decision"),
                "interrupt_reason": done.data.get("interrupt_reason"),
                "tool_calls": done.data.get("tool_calls") or [],
            },
            app,
        )
        return resolved, state, events
    stored = load_run(resolved)
    state = _hydrate_state(stored["state"], app) if stored else {}
    return resolved, state, events


def iter_sse(
    app: Application,
    run_id: str | None = None,
    *,
    hitl: HitlMode = "interrupt",
    retrieval_mode: str = "hybrid-rerank",
    prompt_version: str = "risk-v1",
) -> Iterator[str]:
    for event in stream_analysis(
        app,
        run_id,
        hitl=hitl,
        retrieval_mode=retrieval_mode,
        prompt_version=prompt_version,
    ):
        yield f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"


def iter_resume_sse(run_id: str, decision: str, comment: str = "") -> Iterator[str]:
    apply_human_decision(run_id, decision, comment)
    for event in stream_analysis(run_id=run_id, resume=decision, hitl="interrupt"):
        yield f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"


def load_run(run_id: str) -> dict[str, Any] | None:
    with DB_LOCK:
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
    with DB_LOCK:
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
