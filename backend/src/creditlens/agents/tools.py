from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any

from contracts.application import Application
from contracts.scoring import ScoringResult, ShapResult
from langchain_core.tools import tool

from creditlens.agents.context import get_run_context
from creditlens.rag.retrieve import retrieve_policy
from creditlens.scoring.service import explain_application, score_application

_application: ContextVar[Application | None] = ContextVar("tool_application", default=None)
_scoring: ContextVar[ScoringResult | None] = ContextVar("tool_scoring", default=None)
_shap: ContextVar[ShapResult | None] = ContextVar("tool_shap", default=None)


def bind_tool_state(
    application: Application,
    scoring: ScoringResult | None = None,
    shap: ShapResult | None = None,
) -> None:
    _application.set(application)
    _scoring.set(scoring)
    _shap.set(shap)


def _note(name: str, detail: str = "") -> None:
    ctx = get_run_context()
    if ctx:
        ctx.record_tool(name, detail)


@tool
def search_credit_policy(query: str) -> str:
    """Search credit policy. Read-only hybrid retrieval over the knowledge base."""
    app = _application.get()
    if app is None:
        return "[]"
    ctx = get_run_context()
    mode = ctx.retrieval_mode if ctx else "hybrid-rerank"
    docs, _debug = retrieve_policy(app, extra_query=query, mode=mode)
    _note("search_credit_policy", query)
    return json.dumps(
        [{"citation": doc.citation, "title": doc.title, "text": doc.text[:400]} for doc in docs],
        ensure_ascii=False,
    )


@tool
def get_score_explanation() -> str:
    """Return the immutable ScoringResult and top SHAP features. Does not rescore."""
    scoring = _scoring.get()
    shap = _shap.get()
    _note("get_score_explanation")
    return json.dumps(
        {
            "scoring": scoring.model_dump() if scoring else None,
            "shap": [item.model_dump() for item in (shap.features[:8] if shap else [])],
        },
        ensure_ascii=False,
    )


@tool
def get_application_data() -> str:
    """Return the current credit application fields. Read-only."""
    app = _application.get()
    _note("get_application_data")
    return json.dumps(app.model_dump() if app else {}, ensure_ascii=False)


@tool
def simulate_what_if(requested_amount: float) -> str:
    """Simulate a different requested amount with the same CatBoost model. Does not write ScoringResult."""
    app = _application.get()
    if app is None:
        return "{}"
    payload = app.model_dump()
    payload["requested_amount"] = requested_amount
    updated = Application.model_validate(payload)
    before = score_application(app)
    after = score_application(updated)
    shap_after = explain_application(updated)
    _note("simulate_what_if", str(requested_amount))
    return json.dumps(
        {
            "before": before.model_dump(),
            "after": after.model_dump(),
            "delta_score": round(after.score - before.score, 4),
            "top_shap": [item.model_dump() for item in shap_after.features[:5]],
            "note": "what-if is a side calculation; graph ScoringResult is unchanged",
        },
        ensure_ascii=False,
    )


def risk_tools() -> list[Any]:
    return [search_credit_policy, get_score_explanation, get_application_data, simulate_what_if]
