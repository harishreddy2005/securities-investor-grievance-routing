"""Verify a running local stack using real jobs, Prometheus, Grafana and Jaeger."""
import base64
import json
import math
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

APP="http://localhost:8000"
PROM="http://localhost:9090"
GRAFANA="http://localhost:3000"
JAEGER="http://localhost:16686"
REFERENCE={"entity_name":"Synthetic Example Bank", "complaint_text":"I invested in a fixed deposit through my bank's app. The interest credited is lower than what I was promised. I want to complain to SEBI.", "approached_entity_first":False}


def request(url,payload=None,headers=None,expected=200):
    values={"Content-Type":"application/json",**(headers or {})}
    req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers=values)
    try:
        with urllib.request.urlopen(req,timeout=15) as response:
            code,body,response_headers=response.status,response.read(),dict(response.headers)
    except urllib.error.HTTPError as error:
        code,body,response_headers=error.code,error.read(),dict(error.headers)
    assert code==expected, f"Unexpected HTTP {code} (expected {expected}) from {urllib.parse.urlsplit(url).path}"
    return json.loads(body),{k.lower():v for k,v in response_headers.items()}


def wait(check,timeout=90):
    deadline=time.monotonic()+timeout
    while True:
        try:
            value=check()
            if value:
                return value
        except (AssertionError,urllib.error.URLError,KeyError):
            pass
        if time.monotonic()>=deadline:
            raise AssertionError("Timed out waiting for verification condition")
        time.sleep(1)


def query(expression,base=PROM,headers=None):
    data,_=request(base+"/api/v1/query?"+urllib.parse.urlencode({"query":expression}),headers=headers)
    assert data["status"]=="success"
    return data["data"]["result"]


def completed(job):
    state,_=request(APP+job["status_url"])
    assert state["status"] not in {"failed","stopped","canceled"}, "Job failed instead of returning a safe result"
    if state["status"]=="finished":
        return request(APP+job["result_url"])[0]
    return None


def grafana_headers():
    env={line.split("=",1)[0]:line.split("=",1)[1] for line in Path(".env").read_text(encoding="utf-8-sig").splitlines() if "=" in line and not line.startswith("#")}
    value=base64.b64encode((env["GRAFANA_ADMIN_USER"]+":"+env["GRAFANA_ADMIN_PASSWORD"]).encode()).decode()
    return {"Authorization":"Basic "+value}


def main():
    request(APP+"/health")
    expected={"api","workers","llm-stub","prometheus","grafana","jaeger","cadvisor"}
    def targets_ready():
        data,_=request(PROM+"/api/v1/targets")
        targets=data["data"]["activeTargets"]
        if {t["labels"]["job"] for t in targets}==expected and all(t["health"]=="up" for t in targets):
            return targets
    targets=wait(targets_ready)
    wait(lambda: any(float(row["value"][1])>=2 for row in query('count_over_time(up{job="api"}[1m])')))
    print("PASS Prometheus targets:",", ".join(sorted(expected)))

    canary="PRIVATE-CANARY-"+str(uuid4())
    payload={**REFERENCE,"complainant":{"name":canary,"email":"synthetic@example.com"}}
    cid=str(uuid4())
    headers={"Idempotency-Key":str(uuid4()),"X-Correlation-ID":cid}
    job,response_headers=request(APP+"/api/v1/grievances",payload,headers,202)
    repeat,_=request(APP+"/api/v1/grievances",payload,headers,202)
    assert repeat["run_id"]==job["run_id"]
    request(APP+"/api/v1/grievances",{**payload,"entity_name":"Different entity"},headers,409)
    assert response_headers["x-correlation-id"]==cid
    trace_id=response_headers["x-trace-id"]
    result=wait(lambda:completed(job),180)
    assert result["routing"]=="refer_to_other_regulator" and result["eligibility"]=="bank_first"
    assert result["reliability_status"]=="verified" and not result["uncertain"]
    print("PASS idempotent RBI bank-first result:",job["run_id"])

    names={"complaint.submit","job.process","retrieval","agent.investigator","agent.verifier","verification","result.store"}
    def trace_ready():
        data,_=request(JAEGER+"/api/traces/"+trace_id)
        if data.get("data") and names <= {s["operationName"] for s in data["data"][0]["spans"]}:
            return data["data"][0]
    trace=wait(trace_ready)
    services={p["serviceName"] for p in trace["processes"].values()}
    assert {"grievance-api","grievance-worker","grievance-llm-stub"}<=services, services
    assert canary not in json.dumps(trace)
    assert payload["complaint_text"] not in json.dumps(trace)
    print("PASS Jaeger single end-to-end trace:",trace_id)

    auth=grafana_headers()
    dashboard,_=request(GRAFANA+"/api/dashboards/uid/grievance-phase2",headers=auth)
    source,_=request(GRAFANA+"/api/datasources/uid/grievance-prometheus",headers=auth)
    assert source["url"]=="http://prometheus:9090"
    proxy=GRAFANA+"/api/datasources/proxy/uid/grievance-prometheus"
    panels=dashboard["dashboard"]["panels"]
    for panel in panels:
        expression=panel["targets"][0]["expr"]
        rows=wait(lambda: [r for r in query(expression,proxy,auth) if math.isfinite(float(r["value"][1]))])
        assert rows, panel["title"]
    print("PASS Grafana provisioned datasource and",len(panels),"panel queries with real numeric data")

    for row in query('{job=~"api|workers|llm-stub"}'):
        assert not {"run_id","trace_id","complaint","email","entity_name"}&row["metric"].keys()
    logs=subprocess.check_output(["docker","compose","logs","--no-color","--tail=1000","api","worker","llm-stub"],text=True,encoding="utf-8",errors="replace")
    assert canary not in logs and payload["complaint_text"] not in logs
    assert trace_id in logs and cid in logs
    print("PASS trace-correlated structured logs without complaint canary or content")
    proof={"run_id":job["run_id"],"trace_id":trace_id,"correlation_id":cid,"targets":{t["labels"]["job"]:t["health"] for t in targets},"dashboard_panels":len(panels),"span_names":sorted(names),"services":sorted(services)}
    Path("data").mkdir(exist_ok=True)
    Path("data/phase2-verification.json").write_text(json.dumps(proof,indent=2),encoding="utf-8")
    print("PASS Phase 2 monitoring verification")


if __name__=="__main__":
    main()
