from datetime import date, timedelta

import fakeredis
import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError
from rq import SimpleWorker
from rq.timeouts import TimerDeathPenalty

import app.jobs as jobs
import app.main as main
from app.agents.graph import build_graph
from app.llm import Model


class TestWorker(SimpleWorker):
    __test__ = False
    death_penalty_class = TimerDeathPenalty


@pytest.fixture
def api(settings, retriever, monkeypatch):
    conn = fakeredis.FakeRedis()
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(jobs, "get_settings", lambda: settings)
    monkeypatch.setattr(jobs, "resources", lambda: build_graph(retriever, Model(settings)))
    main.app.dependency_overrides[main.redis_connection] = lambda: conn
    with TestClient(main.app) as client:
        yield client, conn
    main.app.dependency_overrides.clear()


def drain(conn):
    TestWorker([jobs.queue(conn)], connection=conn).work(burst=True)


def test_queue_to_verified_result(api, reference):
    client, conn = api
    response = client.post("/api/v1/grievances", json=reference)
    assert response.status_code == 202
    job = response.json()
    assert client.get(job["status_url"]).json()["status"] == "queued"
    assert client.get(job["result_url"]).status_code == 409
    assert jobs.queue(conn).count == 1
    drain(conn)
    assert client.get(job["status_url"]).json()["status"] == "finished"
    result = client.get(job["result_url"])
    assert result.status_code == 200
    assert result.json()["eligibility"] == "bank_first"
    assert len(result.json()["regulatory_citations"]) == 6
    assert "Reserve Bank of India" in result.json()["target_authority"]


@pytest.mark.parametrize("patch", [
    {"complaint_text": "tiny"}, {"amount_involved_inr": -1}, {"unrecognised": 1},
    {"channel": "email"}, {"incident_date": "not-a-date"},
    {"entity_complaint_date": "2026-01-01", "approached_entity_first": False},
    {"incident_date": (date.today()+timedelta(days=1)).isoformat()},
    {"complainant": {"name": "Test", "email": "bad"}},
    {"incident_date": "1202-01-01"},
    {"approached_entity_first": True, "entity_complaint_date": "1202-01-01"},
    {"approached_entity_first": True, "entity_complaint_date": "2020-01-01", "entity_response_date": "1202-01-01"},
])
def test_invalid_payload_is_quarantined_not_queued(api, reference, patch):
    client, conn = api
    response = client.post("/api/v1/grievances", json={**reference, **patch})
    assert response.status_code == 422
    assert jobs.queue(conn).count == 0
    assert conn.llen("grievance:quarantine") == 1


def test_date_error_identifies_field(api, reference):
    client, conn = api
    response = client.post("/api/v1/grievances", json={**reference, "approached_entity_first": True, "entity_complaint_date": "1202-01-01"})
    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "entity_complaint_date"]
    assert "1900" in error["msg"]
    assert jobs.queue(conn).count == 0


def test_worker_failure_is_visible_and_api_survives(api, reference, monkeypatch):
    client, conn = api
    def fail():
        raise RuntimeError("simulated index failure")
    monkeypatch.setattr(jobs, "resources", fail)
    job = client.post("/api/v1/grievances", json=reference).json()
    drain(conn)
    state = client.get(job["status_url"]).json()
    assert state["status"] == "failed"
    assert state["error"]
    assert client.get(job["result_url"]).status_code == 409
    assert client.get("/").status_code == 200


def test_health_and_missing_job(api, monkeypatch):
    client, _ = api
    assert client.get("/health").status_code == 503  # no running worker
    monkeypatch.setattr(main, "worker_available", lambda conn: True)
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/grievances/no-such-run").status_code == 404
    assert client.get("/api/v1/grievances/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/openapi.json").status_code == 200
    assert "Bank FD example" in client.get("/").text


def test_redis_outage_returns_503(api, reference, monkeypatch):
    client, conn = api
    monkeypatch.setattr(conn, "ping", lambda: (_ for _ in ()).throw(ConnectionError("down")))
    assert client.get("/health").status_code == 503
    monkeypatch.setattr(conn, "execute_command", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("down")))
    assert client.post("/api/v1/grievances", json=reference).status_code == 503


def test_idempotency_reuses_job_and_rejects_conflicting_payload(api, reference):
    client,conn=api
    headers={"Idempotency-Key":"repeatable-test-key"}
    first=client.post("/api/v1/grievances",json=reference,headers=headers)
    second=client.post("/api/v1/grievances",json=reference,headers=headers)
    assert first.status_code==second.status_code==202
    assert first.json()["run_id"]==second.json()["run_id"]
    assert jobs.queue(conn).count==1
    conflict=client.post("/api/v1/grievances",json={**reference,"entity_name":"Another bank"},headers=headers)
    assert conflict.status_code==409 and jobs.queue(conn).count==1


def test_dependency_failure_returns_safe_human_escalation(api,reference,monkeypatch):
    from app.reliability import DependencyFailure
    client,conn=api
    def fail():
        raise DependencyFailure("timeout","llm")
    monkeypatch.setattr(jobs,"resources",fail)
    job=client.post("/api/v1/grievances",json=reference).json()
    drain(conn)
    assert client.get(job["status_url"]).json()["status"]=="finished"
    result=client.get(job["result_url"]).json()
    assert result["routing"]=="escalate_to_human" and result["uncertain"]
    assert result["reliability_status"]=="degraded" and result["error_code"]=="timeout"
    assert result["regulatory_citations"]==[]


def test_duplicate_delivery_returns_stored_outcome_without_rerunning(api,reference,monkeypatch):
    client,conn=api
    job=client.post("/api/v1/grievances",json=reference).json()
    drain(conn)
    stored=client.get(job["result_url"]).json()
    monkeypatch.setattr(jobs,"connection",lambda:conn)
    monkeypatch.setattr(jobs,"resources",lambda:pytest.fail("Duplicate execution called agents again"))
    repeated=jobs.process_grievance(reference,job["run_id"])
    assert repeated==stored
    assert conn.hget("grievance:metrics:jobs","success")==b"1"


def test_metrics_paths_use_route_template_not_identifier(api,reference):
    client,_=api
    job=client.post("/api/v1/grievances",json=reference).json()
    client.get(job["status_url"])
    metrics=client.get("/metrics")
    assert metrics.status_code==200
    assert 'route="/api/v1/grievances/{run_id}"' in metrics.text
    assert job["run_id"] not in metrics.text
