from fastapi.testclient import TestClient

from creditlens.db import init_db
from creditlens.evaluation.quality_gate import THRESHOLDS, evaluate_summary
from creditlens.evaluation.runner import list_results, run_evals
from creditlens.main import app


def test_smoke_evals_and_gate_metrics_exist():
    init_db()
    run = run_evals(experiment="ci-smoke", smoke=True)
    assert len(run.results) >= 10
    assert "scoring_consistency" in run.summary
    assert run.summary["scoring_consistency"] >= THRESHOLDS["scoring_consistency"]
    assert run.summary.get("required_tool_usage", 1) >= 1
    passed, failed = evaluate_summary(run.summary)
    assert passed, failed
    stored = list_results(run.run_id)
    assert len(stored) == len(run.results)
    client = TestClient(app)
    payload = client.get("/api/evals").json()
    assert payload["results"]
    assert payload["thresholds"]["scoring_consistency"] == 1.0
    detail = client.get(f"/api/evals/{run.run_id}")
    assert detail.status_code == 200
    assert len(detail.json()["results"]) == len(run.results)
