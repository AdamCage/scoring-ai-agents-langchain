from creditlens.db import init_db
from creditlens.evaluation.quality_gate import THRESHOLDS, evaluate_summary
from creditlens.evaluation.runner import run_evals


def test_smoke_evals_and_gate_metrics_exist():
    init_db()
    run = run_evals(experiment="ci-smoke", smoke=True)
    assert len(run.results) >= 10
    assert "scoring_consistency" in run.summary
    assert run.summary["scoring_consistency"] >= THRESHOLDS["scoring_consistency"]
    assert run.summary.get("scoring_tool_called", 0) >= 1
    assert run.summary.get("agent_tool_usage", 0) >= 1
    assert run.summary.get("recall_at_5", 0) >= THRESHOLDS["recall_at_5"]
    assert run.summary.get("mrr", 0) >= THRESHOLDS["mrr"]
    assert run.summary.get("citation_grounding", 0) >= THRESHOLDS["citation_grounding"]
    passed, failed = evaluate_summary(run.summary, llm_enabled=False)
    assert passed, failed


def test_missing_required_metric_fails_gate():
    passed, failed = evaluate_summary(
        {"scoring_consistency": 1.0, "numeric_consistency": 1.0},
        require_missing=True,
        llm_enabled=False,
    )
    assert not passed
    assert any("recall_at_5=missing" in item for item in failed)
    assert any("citation_grounding=missing" in item for item in failed)
