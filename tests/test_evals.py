from creditlens.db import init_db
from creditlens.evaluation.quality_gate import THRESHOLDS
from creditlens.evaluation.runner import run_evals


def test_smoke_evals_and_gate_metrics_exist():
    init_db()
    run = run_evals(experiment="ci-smoke", smoke=True)
    assert len(run.results) >= 10
    assert "scoring_consistency" in run.summary
    assert run.summary["scoring_consistency"] >= THRESHOLDS["scoring_consistency"]
    assert run.summary.get("required_tool_usage", 1) >= 1
