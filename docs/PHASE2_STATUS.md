# Phase 2 local verification — 2026-11-03

Phase 2 is implemented and verified locally on `main`, based on teammate commit
`c248225`. Ready for demonstration. The results below were recorded before
publication; use Git history for the publication checkpoint. Phase 4 was not started.
Reviewed PDFs and teammate work remain
preserved. Preexisting untracked `.vscode/` is untouched.

## Implemented

- Configurable LLM/retrieval/Redis deadlines; RQ process timeout.
- Bounded transient retries, exponential backoff and jitter; malformed-response
  validation; Redis-shared CLOSED/OPEN/HALF_OPEN circuit with a single probe.
- Safe dependency classification and uncertain, citation-free human escalation.
  Unexpected programming failures remain visibly failed jobs.
- Atomic submission Idempotency-Key handling, conflict 409, execution leases and
  durable per-run outcomes reused by duplicate delivery.
- JSON logging with run/correlation/trace IDs and sensitive-content suppression.
- API/stub metrics and Redis-aggregated worker metrics across processes/replicas:
  requests, latency, outcomes, errors, queue depth, durations, retries, circuit
  states/transitions and per-agent outcomes, steps, tools and retries.
- Seven-target Prometheus configuration, provisioned Grafana datasource and 26
  panels, including API p50/p95 and cAdvisor container CPU/memory/uptime.
- OpenTelemetry OTLP HTTP to persistent Jaeger; traceparent across Redis; spans
  for submission, worker, retrieval, investigator, verifier, verification and
  result storage. Complaint content and arbitrary baggage are not exported.
- Compose health checks, persistence, local monitoring ports, scalable workers,
  repeatable verification/fault scripts and updated CI configuration.

## Actual results

| Check | Result |
|---|---|
| Full host Python 3.14 suite | 59 passed; 2 upstream deprecation warnings |
| Final suite inside Python 3.11 application container | 59 passed; 1 upstream deprecation warning |
| Compose build/start | Passed; nine services healthy; ingest exited 0 |
| Original Docker application smoke | Four scenarios passed after recovery |
| Prometheus | 7/7 UP: api, workers, llm-stub, prometheus, grafana, jaeger, cadvisor |
| Grafana | All 26 panel expressions returned finite numeric data |
| Jaeger | One trace across API, worker and HTTP model stub, including all required spans |
| Privacy checks | Canary and complaint body absent from checked logs and exported trace |
| Idempotency | Repeated key reused run; conflicting payload returned 409 |
| Edge form regressions | Date validation, cleared prior details, readable errors, rendered RBI bank-first result passed |
| Edge monitoring UI | Grafana charts and Jaeger trace rendered successfully |
| Compile/dependencies/whitespace | compileall, pip check, git diff --check passed |
| GitHub Actions | Updated locally; not executed on GitHub for unpushed changes |
| Locust / three-worker benchmark | Not executed; Phase 4 |

`scripts/failure_test_phase2.py` passed provider-error exhaustion, OPEN fail-fast,
failed HALF_OPEN reopening, healthy HALF_OPEN closing, slow-provider timeout,
Redis submission/readiness 503, fresh verified post-recovery RBI bank-first job,
and continued verified routing during Jaeger outage. Normal configuration and
all dependencies were restored without deleting volumes.

Initial fault-test attempt failed because its five-second cooldown expired during
SpawnWorker startup. Only the fixture cooldown was increased to 60 seconds;
the complete rerun passed. See INCIDENT_LOG.md for diagnosis and recovery.

Proof artifacts are ignored: `data/phase2-verification.json`,
`data/phase2-grafana.png`, and `data/phase2-jaeger.png`.
Verified run: `3589231d-4b5a-4e8d-b77a-e0267478f261`.
Trace: `057c2661fe89032602ab2c4e8409f619`.

## Files created or modified

Application: `app/config.py`, `app/reliability.py`, `app/llm.py`, `app/jobs.py`,
`app/main.py`, `app/worker.py`, `app/stub.py`, `app/schemas.py`,
`app/rag/retriever.py`, `app/agents/graph.py`, `app/agents/tools.py`,
`app/metrics_server.py`, and new `app/observability/` modules (`runtime.py`,
`http.py`, `metrics.py`, `__init__.py`).

Deployment: `docker-compose.yml`, `.env.example`, `requirements.txt`, `pytest.ini`,
`.github/workflows/tests.yml`, `deploy/prometheus/prometheus.yml`,
`deploy/grafana/provisioning/`, `deploy/grafana/dashboards/grievance.json`,
`deploy/jaeger/Dockerfile`, and `deploy/jaeger/jaeger.yml`.

Verification: `tests/conftest.py`, `tests/test_api.py`, `tests/test_reliability.py`,
`scripts/configure_local.py`, `scripts/verify_phase2.py`,
`scripts/failure_test_phase2.py`, and `scripts/browser_monitoring_phase2.py`.

Documentation: `README.md`, this file, `docs/DATA_CONTRACT.md`, `docs/RUNBOOK.md`,
`docs/INCIDENT_LOG.md`, `docs/TEAM_PLAN.md`, and
`docs/agent_handoff/PROGRESS_LOG.md`. Secrets, caches and runtime data stay ignored.

## Exact startup

With Docker Desktop running Linux containers, from the repository root:

```bash
# First setup only; preserve an existing .env.
cp .env.example .env
python scripts/configure_local.py
docker compose up --build -d --wait --wait-timeout 900
docker compose ps -a
docker compose exec -T api python scripts/smoke_test.py
python scripts/verify_phase2.py
```

PowerShell can use `Copy-Item .env.example .env`. The helper creates a random
private Grafana password when absent. First downloads need internet and time.

- Application: http://localhost:8000
- API docs: http://localhost:8000/docs
- Prometheus: http://localhost:9090/targets
- Grafana: http://localhost:3000/d/grievance-phase2 (credentials in local `.env`)
- Jaeger: http://localhost:16686
- Verified trace: http://localhost:16686/trace/057c2661fe89032602ab2c4e8409f619

See RUNBOOK.md for failure tests, restoration and troubleshooting.

## Limits

The model remains a deterministic demo stub. This phase does not certify broader
language understanding or repair unrelated teammate Phase 1/3 gaps. Retrieval's
caller deadline cannot forcibly kill native daemon-thread work; RQ's process
timeout is the final boundary. Telemetry is best effort and collector outages can
lose spans. Idempotency is bounded by Redis retention/persistence, not globally
exactly-once execution under data loss. Each agent is one graph node per run.
Production API authentication/privacy controls remain out of scope. Grafana
initializes stored credentials on first startup only. cAdvisor requires privileged
access to Docker's Linux VM; it has no published host port, and application
containers remain unprivileged. Phase 4 SLO, Locust and scaling measurements remain
pending. Existing named volumes and regulatory indexes have been retained.
