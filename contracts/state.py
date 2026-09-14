from typing import Annotated, Any, TypedDict

from contracts.application import Application, ValidationResult
from contracts.rag import RetrievalDebug, RetrievedDocument
from contracts.recommendation import Critique, Recommendation, RiskAnalysis
from contracts.scoring import ScoringResult, ShapResult


def _extend_list(left: list, right: list) -> list:
    return [*left, *right]


class CreditState(TypedDict, total=False):
    application: Application
    validation: ValidationResult | None
    scoring: ScoringResult | None
    shap: ShapResult | None
    retrieved_documents: list[RetrievedDocument]
    retrieval_debug: RetrievalDebug | None
    analysis: RiskAnalysis | None
    critique: Critique | None
    recommendation: Recommendation | None
    messages: Annotated[list[dict[str, Any]], _extend_list]
    retrieval_attempts: int
    node_trace: Annotated[list[str], _extend_list]
    interrupt_reason: str | None
    human_decision: str | None
    what_if: dict[str, Any] | None
    retrieval_mode: str
    prompt_version: str
    tool_calls: Annotated[list[dict[str, Any]], _extend_list]
