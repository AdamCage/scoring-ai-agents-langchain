from __future__ import annotations

from contracts.recommendation import Recommendation
from contracts.scoring import ScoringResult

from creditlens.llm.routerai import chat_model, llm_available


def judge_faithfulness(
    explanation: str,
    evidence: list[str],
    scoring: ScoringResult | None,
    shap_labels: list[str],
) -> tuple[float, str]:
    if not llm_available():
        return 0.0, "judge skipped: no LLM key"
    model = chat_model()
    if model is None:
        return 0.0, "judge skipped: no model"
    prompt = (
        "Every factual claim in the explanation must be supported by the scoring result, "
        "SHAP labels or retrieved policy excerpts. "
        "Reply with a single number 0 or 1 and a short reason.\n\n"
        f"Explanation:\n{explanation}\n\n"
        f"Score: {scoring.model_dump() if scoring else None}\n"
        f"SHAP: {shap_labels}\n"
        f"Evidence:\n{chr(10).join(evidence[:8])}\n"
    )
    try:
        message = model.invoke([("system", "You are a strict faithfulness judge."), ("human", prompt)])
        text = str(message.content)
        score = 1.0 if "1" in text[:8] and "0" not in text[:3] else 0.0
        return score, text[:400]
    except Exception as exc:
        return 0.0, f"judge error: {exc}"


def judge_recommendation(rec: Recommendation | None, scoring: ScoringResult | None, docs: list[str]) -> tuple[float, str] | None:
    if rec is None:
        return None
    shap_labels = rec.positive_factors + rec.negative_factors
    return judge_faithfulness(rec.summary, docs, scoring, shap_labels)
