from __future__ import annotations

from contracts.evaluation import EvalVariant

VARIANTS: dict[str, EvalVariant] = {
    "vector-only": EvalVariant(
        name="vector-only",
        retrieval="vector",
        reranker=False,
        prompt="risk-v1",
        expected_gate="fail",
    ),
    "hybrid": EvalVariant(
        name="hybrid",
        retrieval="hybrid",
        reranker=False,
        prompt="risk-v1",
        expected_gate="pass",
    ),
    "hybrid-rerank": EvalVariant(
        name="hybrid-rerank",
        retrieval="hybrid-rerank",
        reranker=True,
        prompt="risk-v1",
        expected_gate="pass",
    ),
    "bad-prompt": EvalVariant(
        name="bad-prompt",
        retrieval="hybrid-rerank",
        reranker=True,
        prompt="bad-prompt-demo",
        expected_gate="fail",
    ),
}

PRODUCTION_VARIANT = "hybrid-rerank"


def get_variant(name: str) -> EvalVariant:
    return VARIANTS.get(name, VARIANTS[PRODUCTION_VARIANT])


def list_variants() -> list[EvalVariant]:
    return list(VARIANTS.values())
