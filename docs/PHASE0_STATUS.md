# Phase 0 implementation and verification

Implementation complete; **Docker build and end-to-end smoke passed on the user's
device** after starting Docker Desktop. GitHub publication remains pending.

## Implemented

- Hash-checked parsing of exactly three active PDFs; archive excluded.
- 539 searchable chunks with traceable document/page/section metadata.
- Persistent Chroma, local semantic ONNX embeddings through LangChain, exact
  clause lookup, idempotent ingest and cached-chunk re-embedding.
- Two LangGraph agent nodes with explicit handoff, bounded tools, evidence
  verification, structured results and human escalation.
- Asynchronous FastAPI submission/status/result endpoints, validation, quarantine,
  readiness, Redis/RQ jobs, stored results/failures and a separate HTTP model stub.
- Browser form, polling, results, citations, next steps, and agent trace.
- Non-root Docker image; Compose startup ordering, automatic ingest, health checks,
  persistent volumes, .env example; smoke scripts and GitHub Actions.
- RBI fixed-deposit reference with bank-first advice and no SEBI timeline applied.
- Correct operative MF Regulation 53 anchor on page 80, avoiding historical
  amendment-footnote payment deadlines on page 79.

## Actual verification

| Check | Actual result |
|---|---|
| Full Python suite | **38 passed**, two upstream deprecation warnings on Python 3.14 |
| Corpus component suite | **4 passed** |
| Agent component suite | **17 passed** |
| API/queue and HTTP stub component suites | **17 passed**, including invalid ancient dates and field-specific errors |
| Genuine semantic ingestion | **539 chunks**; 53.39 seconds including first model download |
| Genuine semantic retrieval + LangGraph FD reference | **Passed**, all six required/considered provisions resolve |
| Local HTTP smoke, test embeddings | **4 scenarios passed** |
| Local HTTP smoke, semantic embeddings | **4 scenarios passed** |
| Compose configuration | **Passed**, exit 0; Docker client config-access warning |
| Dependency consistency | `pip check`: **no broken requirements** |
| Python compilation / frontend JS syntax / whitespace | **Passed** |
| Real Docker build/start, real Redis daemon and Linux SpawnWorker | **Passed on the user's Windows Docker Desktop**; four services healthy and ingestion exited 0 |
| Real Docker HTTP smoke | **All 4 scenarios passed**, including FD bank-first routing and uncertain escalations |
| Host access at localhost:8000 | **Passed**: frontend served and health reported 539 indexed chunks |
| Repeat ingestion inside Docker | **Passed**: unchanged index, 539 chunks |
| Redis/API/worker restart and persistence | **Passed**: original FD result retained; all 4 smoke scenarios passed again after restart |
| Dependency check inside Docker | **Passed**: no broken requirements |
| GitHub Actions execution | **Not executed: changes not pushed** |
| Real Edge browser form regression | **Passed**: prior details reset/disabled, invalid dates blocked before submission, completed RBI submission, readable API errors |

The local HTTP harness uses TCP fakeredis and RQ SimpleWorker, not a real Redis
server or the production process-isolated worker. Its transient connection-closed
warning was recovered by RQ; every job completed. These results must not be
reported as successful Docker tests. A subsequent real Docker run independently
passed the build, startup and all four HTTP smoke scenarios. Early dependency/download/harness errors and
fixes are recorded in INCIDENT_LOG.md and the append-only handoff progress log.

## Teammate's exact commands

After receiving this working tree, in the repository root:

```bash
cp .env.example .env
docker compose up --build -d --wait --wait-timeout 900
docker compose ps -a
docker compose exec -T api python scripts/smoke_test.py
```

On PowerShell, `Copy-Item .env.example .env` is also supported. Copy the environment
file only on first setup. Open http://localhost:8000. Expect `ingest` to exit 0 and
the other four services to be healthy. Share the smoke output and
`docker compose logs --tail=200` if anything fails. No second manual ingest step
is required. See README.md and RUNBOOK.md for restart/reindex instructions.

## Remaining limits

Phase 0's deterministic model substitute supports the two reference product
patterns and escalates unfamiliar or mixed complaints. It is not a general LLM
provider. Full guardrails, retries/circuit breaker, dashboards/traces, feedback,
evaluation/cost tracking, caching/rate limits, load/scaling benchmarks and real
provider adapters remain for Phases 1?4 in the latest TEAM_PLAN. The chosen 1996
MF corpus remains a project-specific historical-version decision. All routing
requires human review; no complaint is filed externally.

## Created or modified files

- `.dockerignore`
- `.env.example`
- `.github/workflows/tests.yml`
- `.gitignore`
- `Dockerfile`
- `README.md`
- `app/agents/__init__.py`
- `app/agents/graph.py`
- `app/agents/tools.py`
- `app/cli/__init__.py`
- `app/cli/ingest.py`
- `app/config.py`
- `app/jobs.py`
- `app/llm.py`
- `app/main.py`
- `app/rag/__init__.py`
- `app/rag/corpus.py`
- `app/rag/embeddings.py`
- `app/rag/ingest.py`
- `app/rag/retriever.py`
- `app/schemas.py`
- `app/static/index.html`
- `app/stub.py`
- `app/worker.py`
- `app/worker_health.py`
- `corpus/SOURCES.md`
- `docker-compose.yml`
- `docs/CORPUS_CONFIRMATION.md`
- `docs/DATA_CONTRACT.md`
- `docs/INCIDENT_LOG.md`
- `docs/PHASE0_STATUS.md`
- `docs/RUNBOOK.md`
- `docs/TEAM_PLAN.md`
- `docs/agent_handoff/PROGRESS_LOG.md`
- `requirements-dev.txt`
- `requirements-browser.txt`
- `scripts/browser_smoke.py`
- `requirements.txt`
- `scripts/local_e2e.py`
- `scripts/smoke_test.py`
- `tests/conftest.py`
- `tests/test_agents.py`
- `tests/test_api.py`
- `tests/test_corpus.py`
- `tests/test_stub.py`
