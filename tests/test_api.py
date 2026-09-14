from fastapi.testclient import TestClient

from creditlens.db import init_db
from creditlens.main import app


def test_health_and_login_flow():
    init_db()
    client = TestClient(app)
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    denied = client.get("/api/applications/presets")
    assert denied.status_code == 401
    login = client.post("/api/auth/login", json={"password": "creditlens-demo"})
    assert login.status_code == 200
    presets = client.get("/api/applications/presets")
    assert presets.status_code == 200
    assert len(presets.json()["presets"]) == 6
    analyzed = client.post("/api/analyze/sync", json={"preset_id": "alpha-low"})
    assert analyzed.status_code == 200
    run_id = analyzed.json()["run_id"]
    chat = client.post("/api/chat", json={"run_id": run_id, "message": "Почему такая долговая нагрузка?"})
    assert chat.status_code == 200
    assert "score" in chat.json()["answer"]
