from __future__ import annotations

from contracts.rag import RetrievedDocument
from contracts.recommendation import Recommendation
from contracts.scoring import ScoringResult, ShapResult

from creditlens.llm.routerai import chat_model, llm_available


def _shap_evidence(shap: ShapResult | None) -> list[str]:
    if shap is None:
        return []
    lines = []
    for item in shap.features[:12]:
        lines.append(f"{item.label}: shap={item.shap_value:+.4f} value={item.value}")
    return lines


def _document_evidence(documents: list[RetrievedDocument]) -> list[str]:
    blocks = []
    for doc in documents[:6]:
        blocks.append(
            f"{doc.citation} | section={doc.section} | version={doc.version} | doc_id={doc.doc_id}\n{doc.text[:900]}"
        )
    return blocks


def judge_faithfulness(
    explanation: str,
    scoring: ScoringResult | None,
    shap: ShapResult | None,
    documents: list[RetrievedDocument],
) -> tuple[float, str]:
    if not llm_available():
        return 0.0, "judge skipped: no LLM key"
    model = chat_model()
    if model is None:
        return 0.0, "judge skipped: no model"
    evidence = _document_evidence(documents)
    shap_lines = _shap_evidence(shap)
    prompt = (
        "Judge faithfulness of a credit explanation. "
        "A claim is faithful only if it is supported by the immutable ScoringResult, "
        "the SHAP feature table, or the retrieved policy text. "
        "Citations alone without matching text are not enough. "
        "Reply with a single number 0 or 1 on the first line and a short reason.\n\n"
        f"Explanation:\n{explanation}\n\n"
        f"Immutable ScoringResult:\n{scoring.model_dump() if scoring else None}\n\n"
        f"SHAP features:\n{chr(10).join(shap_lines) or 'none'}\n\n"
        f"Retrieved policy evidence:\n{chr(10).join(evidence) or 'none'}\n"
    )
    try:
        message = model.invoke([("system", "You are a strict faithfulness judge."), ("human", prompt)])
        text = str(message.content)
        score = 1.0 if "1" in text[:8] and "0" not in text[:3] else 0.0
        return score, text[:400]
    except Exception as exc:
        return 0.0, f"judge error: {exc}"


def judge_recommendation(
    rec: Recommendation | None,
    scoring: ScoringResult | None,
    shap: ShapResult | None,
    documents: list[RetrievedDocument],
) -> tuple[float, str] | None:
    if rec is None:
        return None
    return judge_faithfulness(rec.summary, scoring, shap, documents)
