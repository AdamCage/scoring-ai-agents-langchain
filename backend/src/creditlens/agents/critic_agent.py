from __future__ import annotations

from pathlib import Path

from contracts.recommendation import Critique
from contracts.state import CreditState

from creditlens.llm.routerai import chat_model, llm_available

PROMPTS = Path(__file__).parent / "prompts"


def deterministic_critique(state: CreditState) -> Critique:
    analysis = state.get("analysis")
    docs = state.get("retrieved_documents") or []
    shap = state.get("shap")
    issues: list[str] = []
    missing: list[str] = []
    if not analysis:
        issues.append("Нет анализа риск-аналитика")
    if not docs:
        missing.append("Нет извлечённых документов политики")
    if analysis and not analysis.used_citations:
        missing.append("Анализ не содержит цитат")
    if analysis:
        retrieved = {doc.citation for doc in docs}
        for cite in analysis.used_citations:
            if cite not in retrieved:
                issues.append(f"Цитата вне retrieved documents: {cite}")
    if shap and analysis:
        known = {item.label for item in shap.features}
        for factor in analysis.positive_factors + analysis.negative_factors:
            if not any(label in factor for label in known):
                issues.append(f"Фактор вне SHAP: {factor}")
    acceptable = not issues and not missing
    if int(state.get("retrieval_attempts") or 0) >= 2:
        acceptable = True
        if issues:
            issues.append("Цикл retrieval исчерпан, critic принимает текущий пакет")
    if not docs:
        acceptable = False
    return Critique(
        acceptable=acceptable,
        issues=issues,
        missing_citations=missing,
        prompt_version="critic-v1",
    )


def run_policy_critic(state: CreditState) -> Critique:
    guard = deterministic_critique(state)
    if not docs_ok(state) or not llm_available():
        return guard
    model = chat_model()
    if model is None:
        return guard
    system = (PROMPTS / "critic.md").read_text(encoding="utf-8") if (PROMPTS / "critic.md").exists() else ""
    analysis = state.get("analysis")
    docs = state.get("retrieved_documents") or []
    user = (
        f"Анализ: {analysis.model_dump() if analysis else None}\n"
        f"Документы: {[doc.citation for doc in docs]}\n"
        "Верни Critique."
    )
    try:
        parsed = model.with_structured_output(Critique).invoke([("system", system), ("human", user)])
        if isinstance(parsed, Critique):
            if not docs_ok(state):
                parsed.acceptable = False
                parsed.missing_citations = list({*parsed.missing_citations, *guard.missing_citations})
            return parsed
    except Exception:
        return guard
    return guard


def docs_ok(state: CreditState) -> bool:
    return bool(state.get("retrieved_documents"))
