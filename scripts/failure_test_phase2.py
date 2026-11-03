"""Controlled local dependency failure/recovery tests; always restore base config.

Run from the repository root after normal smoke/monitoring verification.
Only this project's stub/worker/Redis services are changed; volumes are retained.
"""
import json
from pathlib import Path
import subprocess
import time

from verify_phase2 import APP, REFERENCE, request, wait, completed


def compose(*arguments):
    subprocess.run(["docker","compose",*arguments],check=True)


def state():
    command="import json; from app.jobs import connection; x=connection().get('grievance:circuit:llm'); print(json.dumps(json.loads(x) if x else {'state':'CLOSED','retry_at':0}))"
    output=subprocess.check_output(["docker","compose","exec","-T","api","python","-c",command],text=True)
    return json.loads(output)


def job():
    accepted,_=request(APP+"/api/v1/grievances",REFERENCE,expected=202)
    return wait(lambda:completed(accepted),120)


def configure(fail=False,delay=.1):
    override={"services":{
        "llm-stub":{"environment":{"STUB_FAIL":str(fail).lower(),"STUB_DELAY_SECONDS":str(delay)}},
        # SpawnWorker imports the semantic runtime for every job. Keep OPEN long
        # enough to observe fail-fast even on a slow Docker Desktop host.
        "worker":{"environment":{"LLM_TIMEOUT":"0.8","DEPENDENCY_RETRIES":"1","RETRY_BASE_SECONDS":"0.05","CIRCUIT_FAILURE_THRESHOLD":"2","CIRCUIT_COOLDOWN_SECONDS":"60"}}
    }}
    Path("data").mkdir(exist_ok=True)
    Path("data/phase2-failure.json").write_text(json.dumps(override),encoding="utf-8")
    compose("-f","docker-compose.yml","-f","data/phase2-failure.json","up","-d","--no-deps","--wait","--wait-timeout","120","llm-stub","worker")


def cooldown():
    wait(lambda: time.time()>=state().get("retry_at",0),90)


def main():
    request(APP+"/health")
    try:
        configure(fail=True)
        for _ in range(2):
            result=job()
            assert result["routing"]=="escalate_to_human" and result["reliability_status"]=="degraded"
            assert not result["regulatory_citations"]
        assert state()["state"]=="OPEN"
        fast=job()
        assert fast["error_code"]=="circuit_open"
        print("PASS provider failures escalate; shared circuit opens and fails fast")
        cooldown()
        failed_probe=job()
        assert failed_probe["error_code"]=="unavailable" and state()["state"]=="OPEN"
        print("PASS failed HALF_OPEN probe reopens circuit")
        configure(fail=False)
        cooldown()
        recovered=job()
        assert recovered["routing"]=="refer_to_other_regulator" and recovered["eligibility"]=="bank_first"
        assert state()["state"]=="CLOSED"
        print("PASS recovered HALF_OPEN probe closes circuit and preserves RBI advice")
        configure(delay=2)
        slow=job()
        assert slow["error_code"]=="timeout" and slow["routing"]=="escalate_to_human"
        print("PASS slow provider reaches configured timeout and safely escalates")
        compose("stop","redis")
        request(APP+"/api/v1/grievances",REFERENCE,expected=503)
        request(APP+"/health",expected=503)
        print("PASS Redis outage returns controlled 503 responses")
    finally:
        compose("up","-d","--wait","--wait-timeout","180")
    result=job()
    assert result["routing"]=="refer_to_other_regulator" and result["eligibility"]=="bank_first"
    assert state()["state"]=="CLOSED"
    print("PASS restored normal configuration and completed a fresh verified job")
    try:
        compose("stop","jaeger")
        independent=job()
        assert independent["routing"]=="refer_to_other_regulator" and independent["reliability_status"]=="verified"
        print("PASS trace collector outage does not prevent a verified application result")
    finally:
        compose("up","-d","--no-deps","--wait","--wait-timeout","120","jaeger")


if __name__=="__main__":
    main()
