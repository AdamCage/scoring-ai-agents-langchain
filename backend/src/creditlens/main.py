from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from contracts.application import Application
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from creditlens.agents.runner import (
    apply_human_decision,
    chat_about_run,
    iter_sse,
    list_runs,
    load_run,
    run_analysis,
    what_if,
)
from creditlens.api.auth import issue_session, require_session, set_cookie
from creditlens.api.docs import router as docs_router
from creditlens.api.rate_limit import limit
from creditlens.config import ROOT, get_settings
from creditlens.db import init_db
from creditlens.evaluation.quality_gate import THRESHOLDS, evaluate_summary
from creditlens.evaluation.runner import latest_summary, list_experiments, run_evals
from creditlens.llm.routerai import llm_available
from creditlens.observability.factory import get_observability
from creditlens.presets import preset_by_id, presets
from creditlens.rag.retrieve import knowledge_stats
from creditlens.scoring.service import load_metadata, model_ready


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


settings = get_settings()
app = FastAPI(title="CreditLens", version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(docs_router)


class LoginBody(BaseModel):
    password: str


class AnalyzeBody(BaseModel):
    application: Application | None = None
    preset_id: str | None = None


class ChatBody(BaseModel):
    run_id: str
    message: str


class WhatIfBody(BaseModel):
    application: Application
    overrides: dict[str, Any]


class ReviewBody(BaseModel):
    decision: str
    comment: str = ""


class EvalBody(BaseModel):
    experiment: str = "hybrid-rerank"
    smoke: bool = True


@app.get("/api/health")
def health() -> dict:
    kb = knowledge_stats()
    return {
        "status": "ok",
        "api": "healthy",
        "scoring_model": load_metadata().get("model_version") if model_ready() else "missing",
        "vector_index": "ready" if kb["ready"] else "empty",
        "knowledge_base": kb["documents"],
        "llm_provider": "RouterAI" if llm_available() else "offline-fallback",
        "llm_configured": llm_available(),
        "observability": settings.observability,
        "langsmith": "disabled",
        "langfuse": "disabled",
        "build": settings.app_version,
        "environment": settings.app_env,
    }


@app.post("/api/auth/login")
def login(body: LoginBody, request: Request):
    limit(request, 20, 60)
    from fastapi.responses import JSONResponse

    token = issue_session(body.password)
    response = JSONResponse({"ok": True})
    set_cookie(response, token)
    return response


@app.get("/api/auth/me")
def me(_: str = Depends(require_session)) -> dict:
    return {"authenticated": True}


@app.get("/api/applications/presets")
def get_presets(_: str = Depends(require_session)) -> dict:
    return {"presets": [item.model_dump() for item in presets()]}


@app.post("/api/analyze")
def analyze(body: AnalyzeBody, request: Request, _: str = Depends(require_session)):
    limit(request, settings.analyze_rate_limit, 60)
    app_data = body.application
    if body.preset_id:
        preset = preset_by_id(body.preset_id)
        if not preset:
            raise HTTPException(404, "preset not found")
        app_data = preset.application
    if app_data is None:
        raise HTTPException(400, "application or preset_id required")

    def stream():
        yield from iter_sse(app_data)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/analyze/sync")
def analyze_sync(body: AnalyzeBody, request: Request, _: str = Depends(require_session)):
    limit(request, settings.analyze_rate_limit, 60)
    app_data = body.application
    if body.preset_id:
        preset = preset_by_id(body.preset_id)
        if not preset:
            raise HTTPException(404, "preset not found")
        app_data = preset.application
    if app_data is None:
        raise HTTPException(400, "application or preset_id required")
    run_id, state, events = run_analysis(app_data)
    return {
        "run_id": run_id,
        "state": {
            key: (value.model_dump() if hasattr(value, "model_dump") else value) for key, value in state.items()
        },
        "events": [event.model_dump() for event in events],
    }


@app.get("/api/runs")
def runs(_: str = Depends(require_session)) -> dict:
    return {"runs": list_runs()}


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str, _: str = Depends(require_session)) -> dict:
    item = load_run(run_id)
    if not item:
        raise HTTPException(404)
    return item


@app.post("/api/runs/{run_id}/review")
def review(run_id: str, body: ReviewBody, _: str = Depends(require_session)) -> dict:
    item = apply_human_decision(run_id, body.decision, body.comment)
    if not item:
        raise HTTPException(404)
    return item


@app.post("/api/chat")
def chat(body: ChatBody, request: Request, _: str = Depends(require_session)) -> dict:
    limit(request, settings.chat_rate_limit, 3600)
    try:
        return chat_about_run(body.run_id, body.message)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/what-if")
def whatif(body: WhatIfBody, _: str = Depends(require_session)) -> dict:
    return what_if(body.application, body.overrides)


@app.get("/api/traces")
def traces(_: str = Depends(require_session)) -> dict:
    items = get_observability().list_traces()
    return {"traces": [item.model_dump() for item in items]}


@app.get("/api/traces/{trace_id}")
def trace_detail(trace_id: str, _: str = Depends(require_session)) -> dict:
    item = get_observability().get_trace(trace_id)
    if not item:
        raise HTTPException(404)
    return item.model_dump()


@app.get("/api/runs/{run_id}/trace")
def run_trace(run_id: str, _: str = Depends(require_session)) -> dict:
    item = get_observability().get_trace_by_run(run_id)
    if not item:
        raise HTTPException(404)
    return item.model_dump()


def _evals_payload() -> dict:
    summary = latest_summary()
    experiments = list_experiments()
    gate = None
    if experiments:
        passed, failed = evaluate_summary(summary)
        gate = {"passed": passed, "failed": failed}
    return {
        "summary": summary,
        "experiments": experiments,
        "gate": gate,
        "thresholds": THRESHOLDS,
    }


@app.get("/api/evals")
def evals(_: str = Depends(require_session)) -> dict:
    return _evals_payload()


@app.post("/api/evals")
def run_evaluation(body: EvalBody, request: Request, _: str = Depends(require_session)):
    limit(request, 4, 300)
    run_evals(experiment=body.experiment, smoke=body.smoke)
    return _evals_payload()


FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"service": "CreditLens", "ui": "frontend/dist is not built"}
else:

    @app.get("/")
    def root() -> dict:
        return {"service": "CreditLens", "ui": "frontend/dist is not built"}
