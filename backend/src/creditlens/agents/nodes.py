from __future__ import annotations

from contracts.application import Application, ValidationIssue, ValidationResult
from contracts.rag import RetrievedDocument
from contracts.recommendation import Critique, Recommendation, RiskAnalysis
from contracts.scoring import ScoringResult, ShapResult
from contracts.state import CreditState

from creditlens.llm.routerai import chat_model, llm_available
from creditlens.rag.retrieve import retrieve_policy
from creditlens.scoring.service import explain_application, score_application


def validate_application(state: CreditState) -> dict:
    app = state["application"]
    issues: list[ValidationIssue] = []
    if app.annual_revenue <= 0:
        issues.append(ValidationIssue(field="annual_revenue", message="Выручка должна быть > 0", code="revenue"))
    if app.requested_amount <= 0:
        issues.append(
            ValidationIssue(field="requested_amount", message="Сумма кредита должна быть > 0", code="amount")
        )
    if app.company_age_months < 6:
        issues.append(
            ValidationIssue(
                field="company_age_months",
                message="Срок регистрации менее 6 месяцев — недостаточно данных",
                code="age",
            )
        )
    notes = []
    if app.segment not in {"sme", "retail"}:
        notes.append("Сегмент нормализован в sme")
    result = ValidationResult(
        valid=len(issues) == 0,
        issues=issues,
        normalized_segment=app.segment if app.segment in {"sme", "retail"} else "sme",
        notes=notes,
    )
    payload: dict = {
        "validation": result,
        "node_trace": [*state.get("node_trace", []), "validate_application"],
    }
    if not result.valid:
        payload["interrupt_reason"] = "validation"
    return payload


def calculate_score(state: CreditState) -> dict:
    scoring = score_application(state["application"])
    return {
        "scoring": scoring,
        "node_trace": [*state.get("node_trace", []), "calculate_score"],
    }


def explain_score(state: CreditState) -> dict:
    shap = explain_application(state["application"])
    return {
        "shap": shap,
        "node_trace": [*state.get("node_trace", []), "explain_score"],
    }


def retrieve_policy_node(state: CreditState) -> dict:
    extra = ""
    critique = state.get("critique")
    if critique and not critique.acceptable:
        extra = " ".join(critique.issues + critique.missing_citations)
    docs, debug = retrieve_policy(state["application"], extra_query=extra)
    return {
        "retrieved_documents": docs,
        "retrieval_debug": debug,
        "retrieval_attempts": int(state.get("retrieval_attempts") or 0) + 1,
        "node_trace": [*state.get("node_trace", []), "retrieve_policy"],
    }


def retrieve_more(state: CreditState) -> dict:
    return retrieve_policy_node(state)


def _top_shap(shap: ShapResult, sign: int, n: int = 3) -> list[str]:
    selected = [f for f in shap.features if f.shap_value * sign > 0]
    selected.sort(key=lambda item: abs(item.shap_value), reverse=True)
    labels = []
    for item in selected[:n]:
        direction = "повышает риск" if item.shap_value > 0 else "снижает риск"
        labels.append(f"{item.label} ({item.shap_value:+.3f}, {direction})")
    return labels


def _deterministic_analysis(app: Application, scoring: ScoringResult, shap: ShapResult, docs: list[RetrievedDocument]) -> RiskAnalysis:
    positives = _top_shap(shap, sign=-1)
    negatives = _top_shap(shap, sign=1)
    citations = [doc.citation for doc in docs[:4]]
    notes = []
    if scoring.risk_band == "LOW" and app.debt_to_revenue > 0.65:
        notes.append("Нагрузка выше 0.65: даже при низком риске модели нужен разбор по §4.2.3.")
    if app.requested_amount > 40_000_000:
        notes.append("Сумма выше 40 млн ₽ — обязательный human review по продуктовым лимитам.")
    if app.overdue_90d_count:
        notes.append("Есть просрочки 90+: автоодобрение запрещено.")
    summary = (
        f"Модель оценила PD={scoring.pd:.3f}, score={scoring.score:.2f}, "
        f"диапазон {scoring.risk_band}, машинное решение {scoring.decision}. "
        f"Основные плюсы: {', '.join(positives) or 'нет'}. "
        f"Основные минусы: {', '.join(negatives) or 'нет'}."
    )
    return RiskAnalysis(
        summary=summary,
        positive_factors=positives,
        negative_factors=negatives,
        policy_notes=notes,
        used_citations=citations,
        prompt_version="risk-v1",
    )


def _try_llm(system: str, user: str) -> str | None:
    if not llm_available():
        return None
    model = chat_model()
    if model is None:
        return None
    try:
        message = model.invoke([("system", system), ("human", user)])
        return str(message.content)
    except Exception:
        return None


def risk_analysis(state: CreditState) -> dict:
    app = state["application"]
    scoring = state["scoring"]
    shap = state["shap"]
    docs = state.get("retrieved_documents") or []
    assert scoring is not None and shap is not None
    llm_text = _try_llm(
        "Ты риск-аналитик. Не меняй score. Ответь по-русски кратко.",
        f"Заявка: {app.model_dump()}\nScore: {scoring.model_dump()}\nSHAP: {[f.model_dump() for f in shap.features[:8]]}\nDocs: {[d.citation for d in docs]}",
    )
    analysis = _deterministic_analysis(app, scoring, shap, docs)
    if llm_text:
        analysis.summary = llm_text[:1200]
    return {
        "analysis": analysis,
        "node_trace": [*state.get("node_trace", []), "risk_analysis"],
    }


def policy_critic(state: CreditState) -> dict:
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
    critique = Critique(
        acceptable=acceptable,
        issues=issues,
        missing_citations=missing,
        prompt_version="critic-v1",
    )
    return {
        "critique": critique,
        "node_trace": [*state.get("node_trace", []), "policy_critic"],
    }


def route_after_validation(state: CreditState) -> str:
    validation = state.get("validation")
    if validation and not validation.valid:
        return "request_information"
    return "calculate_score"


def route_after_critic(state: CreditState) -> str:
    critique = state.get("critique")
    attempts = int(state.get("retrieval_attempts") or 0)
    if critique and not critique.acceptable and attempts < 2:
        return "retrieve_more"
    return "synthesize"


def request_information(state: CreditState) -> dict:
    return {
        "interrupt_reason": "validation",
        "node_trace": [*state.get("node_trace", []), "request_information"],
    }


def synthesize(state: CreditState) -> dict:
    scoring = state["scoring"]
    analysis = state.get("analysis")
    docs = state.get("retrieved_documents") or []
    app = state["application"]
    assert scoring is not None
    confidence = "HIGH" if scoring.risk_band == "LOW" else "MEDIUM" if scoring.risk_band == "MEDIUM" else "LOW"
    requires_review = scoring.decision != "APPROVE" or app.requested_amount > 40_000_000
    titles = {
        "APPROVE": "ОДОБРЕНИЕ",
        "REVIEW": "РУЧНОЕ РАССМОТРЕНИЕ",
        "DECLINE": "ОТКАЗ",
    }
    recommendation = Recommendation(
        decision=scoring.decision,
        title=titles[scoring.decision],
        summary=analysis.summary if analysis else f"Решение модели: {scoring.decision}",
        score=scoring.score,
        risk_band=scoring.risk_band,
        confidence=confidence,  # type: ignore[arg-type]
        positive_factors=analysis.positive_factors if analysis else [],
        negative_factors=analysis.negative_factors if analysis else [],
        citations=[doc.citation for doc in docs],
        requires_human_review=requires_review,
        prompt_version="synth-v1",
    )
    return {
        "recommendation": recommendation,
        "node_trace": [*state.get("node_trace", []), "synthesize"],
    }


def human_review(state: CreditState) -> dict:
    rec = state.get("recommendation")
    reason = "human_review" if rec and rec.requires_human_review else None
    return {
        "interrupt_reason": reason,
        "human_decision": state.get("human_decision") or ("auto-ack" if not reason else None),
        "node_trace": [*state.get("node_trace", []), "human_review"],
    }
