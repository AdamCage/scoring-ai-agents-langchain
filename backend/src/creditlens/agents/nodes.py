from __future__ import annotations

from contracts.application import Application, ValidationIssue, ValidationResult
from contracts.rag import RetrievedDocument
from contracts.recommendation import Recommendation, RiskAnalysis
from contracts.scoring import ScoringResult, ShapResult
from contracts.state import CreditState

from creditlens.agents.context import get_run_context, instrument
from creditlens.agents.critic_agent import run_policy_critic
from creditlens.agents.risk_agent import run_risk_analyst
from creditlens.rag.retrieve import retrieve_policy
from creditlens.scoring.service import explain_application, score_application


def _retrieval_mode(state: CreditState) -> str:
    ctx = get_run_context()
    return (ctx.retrieval_mode if ctx else None) or state.get("retrieval_mode") or "hybrid-rerank"


def _prompt_version(state: CreditState) -> str:
    ctx = get_run_context()
    return (ctx.prompt_version if ctx else None) or state.get("prompt_version") or "risk-v1"


@instrument("validate_application")
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


@instrument("calculate_score")
def calculate_score(state: CreditState) -> dict:
    scoring = score_application(state["application"])
    return {
        "scoring": scoring,
        "node_trace": [*state.get("node_trace", []), "calculate_score"],
    }


@instrument("explain_score")
def explain_score(state: CreditState) -> dict:
    shap = explain_application(state["application"])
    return {
        "shap": shap,
        "node_trace": [*state.get("node_trace", []), "explain_score"],
    }


def _do_retrieve(state: CreditState, node_name: str) -> dict:
    extra = ""
    critique = state.get("critique")
    if critique and not critique.acceptable:
        extra = " ".join(critique.issues + critique.missing_citations)
    docs, debug = retrieve_policy(state["application"], extra_query=extra, mode=_retrieval_mode(state))
    return {
        "retrieved_documents": docs,
        "retrieval_debug": debug,
        "retrieval_attempts": int(state.get("retrieval_attempts") or 0) + 1,
        "node_trace": [*state.get("node_trace", []), node_name],
    }


@instrument("retrieve_policy")
def retrieve_policy_node(state: CreditState) -> dict:
    return _do_retrieve(state, "retrieve_policy")


@instrument("retrieve_more")
def retrieve_more(state: CreditState) -> dict:
    result = _do_retrieve(state, "retrieve_more")
    result["human_decision"] = None
    return result


def _top_shap(shap: ShapResult, sign: int, n: int = 3) -> list[str]:
    selected = [f for f in shap.features if f.shap_value * sign > 0]
    selected.sort(key=lambda item: abs(item.shap_value), reverse=True)
    labels = []
    for item in selected[:n]:
        direction = "повышает риск" if item.shap_value > 0 else "снижает риск"
        labels.append(f"{item.label} ({item.shap_value:+.3f}, {direction})")
    return labels


def _deterministic_analysis(
    app: Application, scoring: ScoringResult, shap: ShapResult, docs: list[RetrievedDocument]
) -> RiskAnalysis:
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


@instrument("risk_analysis")
def risk_analysis(state: CreditState) -> dict:
    analysis = run_risk_analyst(state)
    return {
        "analysis": analysis,
        "node_trace": [*state.get("node_trace", []), "risk_analysis"],
    }


@instrument("policy_critic")
def policy_critic(state: CreditState) -> dict:
    critique = run_policy_critic(state)
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


def route_after_review(state: CreditState) -> str:
    if state.get("human_decision") == "request_documents":
        return "retrieve_more"
    return "end"


@instrument("request_information")
def request_information(state: CreditState) -> dict:
    return {
        "interrupt_reason": "validation",
        "node_trace": [*state.get("node_trace", []), "request_information"],
    }


@instrument("synthesize")
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
    citations = [doc.citation for doc in docs]
    if _prompt_version(state) == "bad-prompt-demo":
        citations = [*citations, "policy §99.9 (выдумано)"]
    recommendation = Recommendation(
        decision=scoring.decision,
        title=titles[scoring.decision],
        summary=analysis.summary if analysis else f"Решение модели: {scoring.decision}",
        score=scoring.score,
        risk_band=scoring.risk_band,
        confidence=confidence,  # type: ignore[arg-type]
        positive_factors=analysis.positive_factors if analysis else [],
        negative_factors=analysis.negative_factors if analysis else [],
        citations=citations,
        requires_human_review=requires_review,
        prompt_version="synth-v1",
    )
    return {
        "recommendation": recommendation,
        "node_trace": [*state.get("node_trace", []), "synthesize"],
    }


def _resume_action(payload: object) -> str:
    if isinstance(payload, str) and payload:
        return payload
    if isinstance(payload, dict):
        return str(payload.get("action") or payload.get("decision") or "approve")
    return "approve"


@instrument("human_review")
def human_review(state: CreditState) -> dict:
    rec = state.get("recommendation")
    existing = state.get("human_decision")
    if existing in {"approve", "reject", "auto-ack"}:
        return {
            "interrupt_reason": None,
            "human_decision": existing,
            "node_trace": [*state.get("node_trace", []), "human_review"],
        }
    needs = bool(rec and rec.requires_human_review)
    ctx = get_run_context()
    if not needs:
        return {
            "interrupt_reason": None,
            "human_decision": existing or "auto-ack",
            "node_trace": [*state.get("node_trace", []), "human_review"],
        }
    if ctx is not None and ctx.hitl == "auto":
        return {
            "interrupt_reason": None,
            "human_decision": "auto-ack",
            "node_trace": [*state.get("node_trace", []), "human_review"],
        }
    payload = {
        "reason": "human_review",
        "pd": state["scoring"].pd if state.get("scoring") else None,
        "risk_band": state["scoring"].risk_band if state.get("scoring") else None,
        "decision": rec.decision if rec else None,
        "recommendation": rec.model_dump() if rec else None,
    }
    try:
        from langgraph.types import interrupt

        resumed = interrupt(payload)
        action = _resume_action(resumed)
    except ImportError:
        return {
            "interrupt_reason": "human_review",
            "human_decision": None,
            "node_trace": [*state.get("node_trace", []), "human_review"],
        }
    return {
        "interrupt_reason": None,
        "human_decision": action,
        "node_trace": [*state.get("node_trace", []), "human_review"],
    }
