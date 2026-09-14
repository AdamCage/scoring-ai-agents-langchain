from fastapi.testclient import TestClient

from creditlens.db import init_db
from creditlens.main import app


def test_health_and_open_demo_flow():
    init_db()
    client = TestClient(app)
    health = client.get("/api/health")
    assert health.status_code == 200
    payload = health.json()
    assert payload["status"] == "ok"
    assert payload["langsmith"] in {"ready_no_key", "enabled"}
    assert payload["langfuse"] in {"missing", "enabled"}
    assert payload.get("vector_backend") == "in-memory"
    presets = client.get("/api/applications/presets")
    assert presets.status_code == 200
    assert len(presets.json()["presets"]) == 6
    analyzed = client.post("/api/analyze/sync", json={"preset_id": "alpha-low"})
    assert analyzed.status_code == 200
    run_id = analyzed.json()["run_id"]
    chat = client.post("/api/chat", json={"run_id": run_id, "message": "Почему такая долговая нагрузка?"})
    assert chat.status_code == 200
    assert "score" in chat.json()["answer"]
    traces = client.get("/api/traces")
    assert traces.status_code == 200
    assert traces.json()["traces"]
    evals = client.get("/api/evals")
    assert evals.status_code == 200
    assert "summary" in evals.json()
    assert "experiments" in evals.json()
