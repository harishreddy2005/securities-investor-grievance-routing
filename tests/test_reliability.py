import json
import logging
import time

import fakeredis
import httpx
import pytest
from prometheus_client import CollectorRegistry, generate_latest

from app.config import Settings
from app.reliability import CircuitBreaker, DependencyFailure, classify, retry_call
from app.observability.runtime import SafeJSONFormatter
from app.observability.metrics import WorkerCollector, count, observe


def settings(**values):
    return Settings(_env_file=None,retry_base_seconds=.1,**values)


def test_retry_backoff_and_safe_error():
    calls, waits=[],[]
    def failing():
        calls.append(1)
        raise httpx.ConnectError("SECRET password=bad complaint text")
    with pytest.raises(DependencyFailure) as caught:
        retry_call(failing,"llm",settings(),.1,sleep=waits.append,jitter=lambda a,b: 0)
    assert caught.value.code=="unavailable"
    assert "SECRET" not in str(caught.value)
    assert len(calls)==3 and waits==[.1,.2]


def test_retry_recovers_and_permanent_errors_not_retried():
    calls=[]
    def once():
        calls.append(1)
        if len(calls)==1:
            raise TimeoutError()
        return 42
    assert retry_call(once,"llm",settings(),1,sleep=lambda _:None)==42
    calls.clear()
    def bad():
        calls.append(1)
        raise ValueError("bad response")
    with pytest.raises(DependencyFailure) as caught:
        retry_call(bad,"llm",settings(),1)
    assert caught.value.code=="invalid_response" and len(calls)==1


def test_deadline_is_bounded():
    started=time.monotonic()
    with pytest.raises(DependencyFailure) as caught:
        retry_call(lambda:time.sleep(.2),"retrieval",settings(dependency_retries=0),.01)
    assert caught.value.code=="timeout"
    assert time.monotonic()-started<.15


def test_shared_circuit_half_open_single_probe_and_recovery():
    conn=fakeredis.FakeRedis()
    now=[100.0]
    one=CircuitBreaker(conn,settings(circuit_failure_threshold=2),clock=lambda:now[0])
    two=CircuitBreaker(conn,one.settings,clock=lambda:now[0])
    for _ in range(2):
        assert one.acquire() is None
        one.finish(False)
    assert json.loads(conn.get(one.key))["state"]=="OPEN"
    with pytest.raises(DependencyFailure): two.acquire()
    now[0]+=11
    token=two.acquire()
    assert json.loads(conn.get(one.key))["state"]=="HALF_OPEN"
    with pytest.raises(DependencyFailure): one.acquire()
    two.finish(True,token)
    assert json.loads(conn.get(one.key))["state"]=="CLOSED"


def test_failed_probe_reopens_and_late_success_does_not_close():
    conn=fakeredis.FakeRedis()
    now=[0.0]
    breaker=CircuitBreaker(conn,settings(circuit_failure_threshold=1),clock=lambda:now[0])
    breaker.finish(False)
    breaker.finish(True)
    assert json.loads(conn.get(breaker.key))["state"]=="OPEN"
    now[0]=11
    token=breaker.acquire()
    breaker.finish(False,token)
    assert json.loads(conn.get(breaker.key))["state"]=="OPEN"


def test_metrics_aggregate_and_have_no_job_labels():
    conn=fakeredis.FakeRedis()
    count("jobs","success",conn)
    count("retries","llm",conn)
    observe("job_duration",.5,backend=conn)
    registry=CollectorRegistry()
    registry.register(WorkerCollector(lambda:conn))
    data=generate_latest(registry).decode()
    assert 'grievance_jobs_total{outcome="success"} 1.0' in data
    assert 'grievance_retries_total{dependency="llm"} 1.0' in data
    assert 'grievance_job_duration_seconds_count 1.0' in data
    assert 'run_id=' not in data and 'complaint=' not in data


def test_logging_drops_untrusted_messages_and_exceptions():
    formatter=SafeJSONFormatter()
    record=logging.LogRecord("rq.worker",logging.ERROR,"test",1,"SECRET: password and complaint",(),None)
    output=formatter.format(record)
    assert "SECRET" not in output
    assert json.loads(output)["event"]=="library_event"


def test_agent_metrics_include_steps_tools_and_retries():
    from app.observability.runtime import instrument_agent, record_tool, metric_store
    conn=fakeredis.FakeRedis()
    token=metric_store.set(conn)
    def node(state):
        record_tool()
        record_tool()
        calls=[]
        def dependency():
            calls.append(1)
            if len(calls)==1:
                raise TimeoutError()
            return state
        return retry_call(dependency,"llm",settings(),1,sleep=lambda _:None)
    try:
        assert instrument_agent(node,"investigator")({"ok":True})=={"ok":True}
    finally:
        metric_store.reset(token)
    registry=CollectorRegistry()
    registry.register(WorkerCollector(lambda:conn))
    data=generate_latest(registry).decode()
    assert 'grievance_agent_steps_sum{agent="investigator"} 1.0' in data
    assert 'grievance_agent_tools_sum{agent="investigator"} 2.0' in data
    assert 'grievance_agent_retries_total{agent="investigator",dependency="llm"} 1.0' in data


@pytest.mark.parametrize("task,body",[("investigate",{"unexpected":"private content"}),("verify",{"supported":"yes"})])
def test_model_rejects_malformed_dependency_responses_without_retry(task,body,monkeypatch):
    from redis import Redis
    from app.llm import Model
    conn=fakeredis.FakeRedis()
    monkeypatch.setattr(Redis,"from_url",lambda *a,**kw:conn)
    calls=[]
    def response(*a,**kw):
        calls.append(1)
        return httpx.Response(200,json=body,request=httpx.Request("POST","http://stub/infer"))
    monkeypatch.setattr(httpx,"post",response)
    with pytest.raises(DependencyFailure) as caught:
        Model(settings(llm_stub_url="http://stub",llm_timeout=1)).call(task,{})
    assert caught.value.code=="invalid_response"
    assert len(calls)==1
