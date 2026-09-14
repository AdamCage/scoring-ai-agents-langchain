from creditlens.db import init_db
from creditlens.evaluation.quality_gate import VARIANT_THRESHOLDS, evaluate_summary
from creditlens.evaluation.runner import run_evals
from creditlens.presets import presets
from creditlens.rag.retrieve import retrieve_policy


def test_retrieval_modes_change_debug():
    app = presets()[0].application
    _docs_v, debug_v = retrieve_policy(app, mode="vector")
    _docs_h, debug_h = retrieve_policy(app, mode="hybrid")
    _docs_r, debug_r = retrieve_policy(app, mode="hybrid-rerank")
    assert debug_v.mode == "vector"
    assert debug_v.vector_ids
    assert not debug_v.bm25_ids
    assert debug_h.bm25_ids and debug_h.fused_ids
    assert not debug_h.reranked_ids
    assert debug_r.reranked_ids


def test_bad_prompt_fails_citation_grounding():
    init_db()
    run = run_evals(experiment="bad-prompt", smoke=True)
    assert run.summary.get("citation_grounding", 1) < 0.95
    passed, failed = evaluate_summary(run.summary, VARIANT_THRESHOLDS["bad-prompt"])
    assert not passed
    assert any("citation_grounding" in item for item in failed)


def test_health_does_not_claim_langsmith_disabled():
    from fastapi.testclient import TestClient

    from creditlens.main import app

    init_db()
    health = TestClient(app).get("/api/health").json()
    assert health["langsmith"] == "ready_no_key"
    assert health["langfuse"] in {"enabled", "missing"}
    assert health.get("vector_backend") == "in-memory"
