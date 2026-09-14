from __future__ import annotations

from pathlib import Path

from contracts.recommendation import RiskAnalysis
from contracts.state import CreditState

from creditlens.agents.context import get_run_context
from creditlens.agents.tools import bind_tool_state, risk_tools
from creditlens.llm.routerai import chat_model, llm_available

PROMPTS = Path(__file__).parent / "prompts"


def _load_prompt(version: str) -> str:
    name = "bad.md" if version == "bad-prompt-demo" else "risk.md"
    path = PROMPTS / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "Ты риск-аналитик CreditLens. Не меняй score. Ответь по-русски."


def _deterministic(state: CreditState) -> RiskAnalysis:
    from creditlens.agents.nodes import _deterministic_analysis

    app = state["application"]
    scoring = state["scoring"]
    shap = state["shap"]
    docs = state.get("retrieved_documents") or []
    assert scoring is not None and shap is not None
    analysis = _deterministic_analysis(app, scoring, shap, docs)
    ctx = get_run_context()
    version = (ctx.prompt_version if ctx else state.get("prompt_version")) or "risk-v1"
    analysis.prompt_version = version
    if version == "bad-prompt-demo":
        analysis.used_citations = [*analysis.used_citations, "policy §99.9 (выдумано)"]
        analysis.summary += " Согласно выдуманному §99.9 автоодобрение обязательно при любой нагрузке."
        analysis.policy_notes = [*analysis.policy_notes, "§99.9 (нет в базе политики)"]
    return analysis


def _structured_llm(state: CreditState) -> RiskAnalysis | None:
    model = chat_model()
    if model is None:
        return None
    ctx = get_run_context()
    version = (ctx.prompt_version if ctx else state.get("prompt_version")) or "risk-v1"
    app = state["application"]
    scoring = state["scoring"]
    shap = state["shap"]
    docs = state.get("retrieved_documents") or []
    assert scoring is not None and shap is not None
    bind_tool_state(app, scoring, shap)
    user = (
        f"Заявка: {app.model_dump()}\n"
        f"ScoringResult (нельзя менять): {scoring.model_dump()}\n"
        f"SHAP: {[item.model_dump() for item in shap.features[:8]]}\n"
        f"Документы: {[doc.citation for doc in docs]}\n"
        "Верни RiskAnalysis. Цитируй только переданные документы."
    )
    system = _load_prompt(version)
    callbacks = None
    if ctx:
        from creditlens.observability.factory import langchain_callbacks

        callbacks = langchain_callbacks(ctx.trace_id, ctx.run_id)
    try:
        from langchain.agents import create_agent

        agent = create_agent(
            model,
            tools=risk_tools(),
            response_format=RiskAnalysis,
            system_prompt=system,
        )
        result = agent.invoke({"messages": [("human", user)]}, config={"callbacks": callbacks} if callbacks else None)
        structured = result.get("structured_response") if isinstance(result, dict) else None
        if isinstance(structured, RiskAnalysis):
            structured.prompt_version = version
            return structured
        if isinstance(result, dict) and "messages" in result:
            parsed = model.with_structured_output(RiskAnalysis).invoke(
                [("system", system), ("human", str(result["messages"][-1].content))]
            )
            if isinstance(parsed, RiskAnalysis):
                parsed.prompt_version = version
                return parsed
    except Exception:
        pass
    try:
        parsed = model.with_structured_output(RiskAnalysis).invoke(
            [("system", system), ("human", user)],
            config={"callbacks": callbacks} if callbacks else None,
        )
        if isinstance(parsed, RiskAnalysis):
            parsed.prompt_version = version
            return parsed
    except Exception:
        return None
    return None


def run_risk_analyst(state: CreditState) -> RiskAnalysis:
    if llm_available():
        try:
            analysis = _structured_llm(state)
            if analysis is not None:
                return analysis
        except Exception:
            pass
    return _deterministic(state)
