# Team Plan — Securities Investor Grievance Routing Service (Mini Project 12)

Shareable summary for the team. Full detail: `docs/agent_handoff/IMPLEMENTATION_PLAN.md`. Day-by-day status: `docs/agent_handoff/PROGRESS_LOG.md`.

**Current integrated status (12 November):** use [COMPLETION_STATUS.md](COMPLETION_STATUS.md)
for verification of phases 0–4 and limits. Docker now runs on this device. Older
dated progress sections below are preserved as history, not current blockers.

## 1. What we're building
A multi-agent service that takes an investor complaint, validates it, works out **which regulator and which entity** is responsible from real regulations, and routes it with **citations**. It never decides the complaint; a grievance officer does.

**The demo-critical case (spec §4.1):** *"I invested in a fixed deposit through my bank's app… I want to complain to SEBI."* → must route to the **RBI Integrated Ombudsman**, not SEBI. The reference answer is in `docs/CORPUS_CONFIRMATION.md`.

> ⚠️ If `docker compose up` doesn't start and serve a valid request at the demo, the project gets **zero marks**. Everything below is ordered around that.

## 2. Team workflow

| Step | Where | Who |
|---|---|---|
| Write code, run Python and Docker checks | Harish's laptop | Harish + AI agent |
| Push to GitHub (`main` or feature branches) | GitHub | Harish |
| `git pull` → `docker compose up --build` → run checks below → send back output | **Teammate's machine (has Docker)** | Teammate |
| Fix anything reported, push again | Harish's laptop | Harish + AI agent |
| Final demo | Teammate's machine | Team |

**Backup if the teammate isn't available: GitHub Codespaces** (free monthly hours, Docker built in). Open the repo on GitHub → Code → Codespaces → Create, then run the same commands. A GitHub Actions workflow will also run `docker compose up` plus a smoke test on every push, so breakage shows up without anyone's machine.

## 3. Teammate's checklist (each time code is pushed)

One-time setup: install Docker Desktop and give it **≥ 6 GB RAM** (Settings → Resources). Clone the repo.

```bash
git pull
cp .env.example .env          # first time only; default LLM_PROVIDER=stub needs no API key
python scripts/configure_local.py       # generate private Grafana credentials
docker compose up --build -d --wait --wait-timeout 900
docker compose ps -a          # nine healthy services; ingest Exited (0)
docker compose exec -T api python scripts/smoke_test.py
python scripts/verify_completion.py
python scripts/verify_phase2.py
docker compose logs --tail=200 > logs.txt
```
Send back: the output of `docker compose ps`, the smoke-test output, and `logs.txt` if anything failed.

URLs once running: App/UI `:8000` · API docs `:8000/docs` · Grafana `:3000` · Prometheus `:9090` · Jaeger `:16686`.

## 4. Architecture (nine long-running services plus one-shot ingestion)

| Service | Role |
|---|---|
| `api` (FastAPI) | Data contract, validation and quarantine, guardrails, rate limit, enqueue job, return `run_id`, web UI |
| `worker` (scalable ×3) | Two LangGraph agents + tools + Chroma vector index |
| `redis` | Job queue, run state, cache, rate-limit counters |
| `llm-stub` | Fake LLM with realistic delay and failure switch (load tests, circuit-breaker demo) |
| `worker-metrics`, `ingest` | Redis-backed worker metrics exporter; one-shot corpus indexing |
| `prometheus`, `grafana`, `jaeger` (+ `cadvisor`) | Metrics, dashboards, traces, per-container resources |

**Agents:** Agent 1 = investigator (searches the corpus, checks for provisions that *modify* the first answer, searches again). Agent 2 = verifier and router (every citation must match retrieved text; otherwise retry or escalate to a human).

**Corpus** (`corpus/raw/`, official PDFs): SEBI SCORES circular 2023/156 · SEBI (Mutual Funds) Regulations **1996** · RBI Integrated Ombudsman Scheme 2021.

## 5. Phases

| Phase | Goal | Demo items covered |
|---|---|---|
| **0** | Minimal end-to-end: ingest → 2 agents → API + queue → UI; §4.1 routes to RBI | 1, 2, 4, 10 |
| 1 | Guardrails, escalation, self-verification retries | 5, 6, 7 |
| 2 | Timeouts, retries, circuit breaker, observability (logs, traces, Grafana) | 3, 8 |
| 3 | Eval set (≥20 scenarios), prompt v1 vs v2, cost tracking, feedback, caching | — (report) |
| 4 | Locust load test, `--scale worker=3`, runbook, incident log, report | 9 |

## 6. Status (as of 30 Oct)
- ✅ Spec analysed, plan approved, corpus downloaded and verified, §4.1 reference answer written.
- ⏳ Next: Phase 0 code. The first push for the teammate to test will come with the steps above.

## Phase 0 implementation status (2026-10-30)

Phase 0 code, Docker configuration, tests and run documentation are implemented.
Local verification: 34 Python tests passed; real semantic ingestion produced 539
chunks; the 4-scenario HTTP smoke passed with real semantic embeddings, HTTP model
stub and TCP fakeredis/RQ SimpleWorker. This is not a real Redis/container result.
Docker engine access remains unavailable on this development machine, so the
teammate's Docker smoke is the remaining demonstration gate. No commit/push yet.

Current startup is automatic: copy `.env.example` to `.env`, then run
`docker compose up --build -d --wait --wait-timeout 900`. Ingestion is a one-shot
service and should show **Exited (0)**; four long-running services should be
healthy. Then run `docker compose exec -T api python scripts/smoke_test.py`.
The earlier manual ingest command remains safe but is no longer necessary.
Grafana, Prometheus, Jaeger and cAdvisor are later-phase services and are not
available in the Phase 0 stack. Use README.md for the current teammate checklist.

## Local Docker verification completed (2026-10-30)

This supersedes the earlier Docker-blocked status: Docker Desktop was started on
the user's device. Actual Compose build/start passed; all four long-running
services are healthy and ingest exited 0 with 539 semantic chunks. The real Docker
smoke passed all four scenarios before and after restarting Redis, API and worker.
The original FD result survived the restart. Phase 0 is ready for the team's
minimum-workflow demonstration; later-phase features remain pending. Containers
are left running at http://localhost:8000. No commit or push has been performed.

## Phase 2 locally verified (2026-11-03)

This supersedes earlier pending-observability notes. Docker Desktop is available
on this device. Phase 2 is implemented and verified locally: dependency deadlines,
bounded retries, shared circuit breaker, safe escalation, idempotency and redacted
telemetry. Nine long-running containers are healthy; ingest exited 0. Prometheus
has seven UP targets; all 26 provisioned Grafana panels query real numeric data;
Jaeger links submission through worker/agents to result storage. Real Edge browser
checks passed for app, dashboard and trace UI. Host and Docker regression suites
each passed 59 tests; all four Docker smoke scenarios and controlled dependency
failure/recovery checks passed. See PHASE2_STATUS.md for evidence and limitations.

Current setup: preserve existing `.env`, run `python scripts/configure_local.py`,
then `docker compose up --build -d --wait --wait-timeout 900`. Grafana credentials
come from local `.env`. Worker scaling remains configurable; Phase 4 load/scaling
measurement has not started. Teammate Phase 1/3 code is preserved, not recertified
in full by this update. Phase 2 changes remain uncommitted and unpushed.

## Current phase status and Phase 4 completion (2026-11-11)

Phase 0 and Phase 2 are published; Phase 2 commit is `6e64c31`. Phase 4 is now
implemented and measured locally: real Docker Locust matrix, 120 seconds per case,
one/three workers and one/three/six concurrent clients. All 295 synthetic reference
complaints completed with verified RBI bank-first results; none failed or remained
unfinished. Normal-load p95 passed: 3.827s at 1 worker/1 client and 6.011s at
3 workers/3 clients. First tested SLO misses: 3 clients with one worker, 6 clients
with three workers. At 3 clients scaling improved completed throughput 1.90x and
reduced p95 42.5%. See PHASE4_REPORT.md for the full table, bottleneck and limits.

Host and rebuilt Python 3.11 Docker suites each passed 67 tests. A stale RQ
registration encountered after Docker resumed was fixed using worker incarnation
names and heartbeat-scoped readiness. The benchmark restored one worker and all
original data volumes. No Phase 4 commit/push has been performed.

Phase 1 and Phase 3 contain teammate work, but runtime inspection found incomplete
integration. Do not mark all five phases finished: see PROJECT_AUDIT.md for
all-field/output guardrails, planned verification re-search, actual v1/v2 prompt
comparison, cost/cache/rate-limit/feedback integration and faculty handout fixes.
Remote `origin/main` has two newer documentation-only commits (`b5ce9f6` tip),
which have been inspected but not merged over the local Phase 4 working tree.

## Integrated phases 0–4 verified locally (2026-11-12)

Supersedes the dated incomplete-integration notes above. Local main now includes
teammate commit 736d95d plus preserved Phase 4 work and reviewed fixes. All-field
guardrails, version parity, bounded evidence re-search, durable actual-call
accounting/audits, shared Redis cache and independent quality/feedback reporting
are wired into the worker path. Host and Python 3.11 Docker suites each pass 87
tests; actual Redis smoke/integration, failure/recovery, registry repair and Edge
browser checks pass. Seven Prometheus targets are UP and all 30 Grafana panels
return real data; a single Jaeger trace crosses the full queue/agent path.

Combined-build capacity measurements validate 348 reference complaints across
one/three workers and 1/3/6/12 clients, with no failed/unfinished work in the final
table. Normal-load p95 is 3.120s (1/1), 3.194s (3/3); the unchanged 8s target is
missed at 1/6 and 3/12. Default-quota 429 failures are separately retained. Deployed
cache comparison reduced p95 from 5.049s to 3.288s; billed stub cost remains zero.
Evaluation v2 is 21/22 with one deliberately conservative mixed-case escalation.
See COMPLETION_STATUS.md for complete evidence and limits. Phases 0–4 are ready
for the scoped local demo; current changes are not committed/pushed and remote
Actions have not been rerun. No named volume or regulatory PDF was changed.
