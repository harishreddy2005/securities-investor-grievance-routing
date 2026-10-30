# Team Plan — Securities Investor Grievance Routing Service (Mini Project 12)

Shareable summary for the team. Full detail: `docs/agent_handoff/IMPLEMENTATION_PLAN.md`. Day-by-day status: `docs/agent_handoff/PROGRESS_LOG.md`.

## 1. What we're building
A multi-agent service that takes an investor complaint, validates it, works out **which regulator and which entity** is responsible from real regulations, and routes it with **citations**. It never decides the complaint; a grievance officer does.

**The demo-critical case (spec §4.1):** *"I invested in a fixed deposit through my bank's app… I want to complain to SEBI."* → must route to the **RBI Integrated Ombudsman**, not SEBI. The reference answer is in `docs/CORPUS_CONFIRMATION.md`.

> ⚠️ If `docker compose up` doesn't start and serve a valid request at the demo, the project gets **zero marks**. Everything below is ordered around that.

## 2. Who does what (no Docker on Harish's laptop)

| Step | Where | Who |
|---|---|---|
| Write code, run Python unit tests (venv, no Docker) | Harish's laptop | Harish + AI agent |
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
docker compose up --build -d
docker compose ps             # every service should be "healthy"
docker compose run --rm ingest          # builds the vector index (first run downloads the embedding model)
python scripts/smoke_test.py            # or: open http://localhost:8000 and click the demo buttons
docker compose logs --tail=200 > logs.txt
```
Send back: the output of `docker compose ps`, the smoke-test output, and `logs.txt` if anything failed.

URLs once running: App/UI `:8000` · API docs `:8000/docs` · Grafana `:3000` · Prometheus `:9090` · Jaeger `:16686`.

## 4. Architecture (7 services under Docker Compose)

| Service | Role |
|---|---|
| `api` (FastAPI) | Data contract, validation and quarantine, guardrails, rate limit, enqueue job, return `run_id`, web UI |
| `worker` (scalable ×3) | Two LangGraph agents + tools + Chroma vector index |
| `redis` | Job queue, run state, cache, rate-limit counters |
| `llm-stub` | Fake LLM with realistic delay and failure switch (load tests, circuit-breaker demo) |
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
