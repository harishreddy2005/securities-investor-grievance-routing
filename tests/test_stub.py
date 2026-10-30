from fastapi.testclient import TestClient

from app.stub import app


def test_stub_http_and_failure_switch(reference, monkeypatch):
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    response = client.post("/infer", json={"task": "investigate", "payload": reference})
    assert response.json()["kind"] == "bank_fd"
    assert client.post("/infer", json={"task": "verify", "payload": {"evidence_valid": False}}).json() == {"supported": False}
    monkeypatch.setenv("STUB_FAIL", "true")
    assert client.post("/infer", json={"task": "investigate", "payload": reference}).status_code == 503
