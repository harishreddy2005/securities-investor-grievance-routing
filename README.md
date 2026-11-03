# Securities Investor Grievance Routing

An evidence-grounded grievance routing application with Phase 2 reliability and monitoring:
PDF ingestion → persistent semantic index → Redis/RQ queue → two LangGraph agents
→ verified result → web interface. It recommends a route for a grievance officer
to review; it never decides a complaint or contacts a regulator. Use synthetic data.

## Run with Docker Compose

Prerequisites: Docker Desktop with the engine running, Compose v2, internet for
image/package downloads and the first local embedding-model download. Allow at
least 6 GB Docker memory. No API key is required.

```bash
git clone https://github.com/harishreddy2005/securities-investor-grievance-routing.git
cd securities-investor-grievance-routing
cp .env.example .env
python scripts/configure_local.py
docker compose up --build -d --wait --wait-timeout 900
docker compose ps -a
docker compose exec -T api python scripts/smoke_test.py
```

PowerShell: use `Copy-Item .env.example .env` instead of `cp` if preferred. Copy
only on first setup, so existing configuration is retained. `configure_local.py`
preserves existing settings and generates a random Grafana password in ignored
`.env`; Python 3 is required for this one-time setup. Phase 0 is published
on GitHub; the annotated `phase-0-complete` tag identifies its completion checkpoint.

Open **http://localhost:8000** for the UI and **http://localhost:8000/docs** for
OpenAPI. Click **Bank FD example**, then **Submit complaint**. The page polls the
job and displays the authority, immediate action, reasoning, exact PDF passages,
next steps and agent trace. Health/readiness is at `/health`.

`ingest` runs automatically before workers start; **Exited (0) is its expected
state**. Nine long-running services should be healthy: `redis`, `llm-stub`,
`worker`, `api`, `worker-metrics`, `prometheus`, `grafana`, `jaeger`, and `cadvisor`.
First startup may take several minutes to download the embedding weights.
Ingestion is idempotent, so the older manual teammate command is also safe:

```bash
docker compose run --rm --no-deps ingest
```

The default uses genuine local ONNX semantic embeddings through a LangChain
embedding adapter and Chroma. `EMBEDDING_PROVIDER=test_hash` exists for offline
software tests only; it is not semantic retrieval and must not be used as evidence
of semantic quality. Parsed chunks, vector data, model weights and Redis AOF are
persisted in named volumes. `docker compose down` preserves them; `down -v`
intentionally erases them.

## Reference result

> I invested in a fixed deposit through my bank's app. The interest credited is
> lower than what I was promised. I want to complain to SEBI.

The result identifies **Reserve Bank of India — Integrated Ombudsman Scheme,
2021**, with `routing=refer_to_other_regulator` and
`domain=out_of_jurisdiction`. When `approached_entity_first=false`, its immediate
action is **first complain in writing to the bank**, not immediate Ombudsman
filing. It cites SCORES 5.3 and RBI-IOS 3(1)(j), 3(1)(f), 9, 10(2)(a), and the
considered commercial-judgment exclusion 10(1)(a). The FD/deficiency link is an
explicit inference; no clause is invented as naming fixed deposits or interest.

Mutual fund redemption complaints route to the AMC, citing current Regulation 53
on PDF page 80 and Regulation 60A's **21 calendar day grievance redressal** rule.
The historical payment periods in page 79's amendment footnote are not asserted
as current deadlines. Mixed bank/broker complaints, insurance and unknown products
escalate to a human.

## Architecture and agent handoff

| Service | Responsibility |
|---|---|
| `api` | Validation, quarantine of rejects, enqueueing, polling/results, static UI |
| `redis` | Persistent queue, job state, results and failures; AOF enabled |
| `worker` | RQ job isolation and the two-agent LangGraph workflow |
| `llm-stub` | Deterministic structured model tasks over HTTP, zero credentials |
| `ingest` | One-shot PDF parsing, exact clause anchors, embedding and indexing |
| `worker-metrics` | Redis-backed metrics aggregated across worker processes and replicas |
| `prometheus` | Seven monitored scrape targets; persistent seven-day metrics |
| `grafana` | Automatically provisioned datasource and 26-panel dashboard |
| `jaeger` | OTLP HTTP trace collection, query UI and persistent trace storage |
| `cadvisor` | Container CPU, memory and uptime; internal port 8080 |

The investigator node calls tools to inspect validated fields, search regulations,
and look up reviewed clauses. It performs an initial search, reads the SCORES
modifier, then derives an RBI or AMC search based on the established product.
The explicit graph handoff contains request, product/entity hypothesis, retrieved
citations, and tool events. The independent verifier node audits required provision
coverage and every citation's exact text and metadata against the persistent index.
Missing or inconsistent evidence produces an uncertain human escalation. Each run
has at most two agent nodes, 12 investigator tool calls, a graph recursion limit,
configurable dependency deadlines and an RQ wall-clock timeout. Phase 2 adds
bounded transient retries, exponential backoff with jitter, and a Redis-shared
LLM circuit breaker. Dependency failures produce an uncertain human escalation
without citations; unexpected programming failures remain visibly failed jobs.

Workers use RQ SpawnWorker to avoid inheriting Chroma native runtime state across
forks. All workers read an immutable index version selected by a published
manifest. Stop workers before rebuilding, then restart them to load the new index.
Workers can scale independently:

```bash
docker compose up -d --scale worker=3
```

This command is provided; no throughput/scaling benchmark has been claimed.

## Corpus and reproducibility

Only the three reviewed PDFs in `corpus/raw/` are allowlisted and hash-checked.
The archived 2026 mutual fund regulations are never indexed or copied into the
image. See [sources](corpus/SOURCES.md) and the
[reference answer](docs/CORPUS_CONFIRMATION.md). The 1996 document is retained by
explicit project decision; this demo corpus is not a claim about current law.

General page chunks use 1,400 characters with 250-character overlap; additional
reviewed exact-section chunks retain full key provisions, including the cross-page
RBI maintainability condition. Quotes preserve normalized PDF text, including
printed amendment markers; they are not generated by the stub. IDs, page, section,
filename and SHA-256 accompany every citation. The manifest records corpus hashes,
build time, chunk count, embedding provider and ingestion throughput. Publication
happens only after successful indexing. Dependencies are version-pinned at the
application level; Docker base images and transitive packages are not digest-locked.

To re-embed cached chunks without re-parsing:

```bash
docker compose stop worker
docker compose run --rm --no-deps ingest python -m app.cli.ingest --re-embed-only
docker compose up -d worker
```

## API and tests

See [DATA_CONTRACT.md](docs/DATA_CONTRACT.md) for payloads and error semantics.
The original `/api/v1/grievances/route` is now a deprecated asynchronous alias;
clients must poll rather than expecting the old synchronous keyword response.

```bash
# Development tests (optional local workflow)
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q

# Optional local HTTP harness without Docker (TCP fakeredis, not real Redis)
python scripts/local_e2e.py

# Optional real-browser form regressions against the running app
python -m pip install -r requirements-browser.txt
python scripts/browser_smoke.py --channel msedge

# Container smoke test, normal teammate/demo workflow
docker compose exec -T api python scripts/smoke_test.py
```

Python tests parse the real PDFs and persist real Chroma vectors using deterministic
test embeddings. They exercise the LangGraph graph, exact citations, eligibility,
FastAPI, actual RQ execution against fakeredis, invalid-input quarantine, and failure
status. They do not substitute for real Redis/container tests. The GitHub Actions
workflow runs Python tests and a separate Compose smoke test with real semantic
embeddings, Redis, HTTP stub and worker. CI runs only after these changes are
pushed; it has not been run merely by writing the workflow.

## Phase boundary and verification status

Phase 0 implements the minimum workflow. Its deterministic stub recognizes the FD
shortfall and mutual fund redemption reference cases and escalates other cases.
It is a test/demo model substitute, not a general language model. Real provider
adapters and broader product understanding remain limitations. Teammate Phase 1
and Phase 3 work is preserved; Phase 2 adds resilience and observability. Phase 4
load testing and scaling measurements remain pending under the latest
[team plan](docs/TEAM_PLAN.md). The older implementation-plan phase numbering is
superseded by that team plan. No production authentication is provided.

Docker Desktop was subsequently started on this development machine. The real
Docker build and startup passed, with four healthy services and ingestion exiting
0. All four HTTP smoke scenarios passed using real Redis, the Linux SpawnWorker,
semantic embeddings and HTTP model stub. The host frontend and health endpoint
also passed at localhost:8000. See [Phase 0 status](docs/PHASE0_STATUS.md),
the append-only [progress log](docs/agent_handoff/PROGRESS_LOG.md),
[runbook](docs/RUNBOOK.md), and [incident log](docs/INCIDENT_LOG.md) for actual results
and recovery instructions. The historical Phase 0 counts above describe that
checkpoint. See [Phase 2 status](docs/PHASE2_STATUS.md) for current verification.

## Phase 2 monitoring and failure verification

| Component | Local URL |
|---|---|
| Application / API docs | http://localhost:8000 / http://localhost:8000/docs |
| Prometheus targets | http://localhost:9090/targets |
| Grafana dashboard | http://localhost:3000/d/grievance-phase2 |
| Jaeger trace search | http://localhost:16686 |

Use `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD` from your local `.env` to
sign in. Monitoring host ports bind to loopback. Select the last 15 minutes in
Grafana and submit complaints to populate throughput and latency panels.
Prometheus scrapes every five seconds. The seven target jobs are `api`, `workers`,
`llm-stub`, `prometheus`, `grafana`, `jaeger`, and `cadvisor`.

```bash
python scripts/verify_phase2.py
# Optional browser rendering check after installing requirements-browser.txt
python scripts/browser_monitoring_phase2.py --channel msedge
# Intentionally interrupt only this project's dependencies; allow several minutes.
# Restores normal Compose settings and retains all named volumes.
python scripts/failure_test_phase2.py
docker compose exec -T api python scripts/smoke_test.py
docker compose ps -a
```

The verification script processes a real queued complaint, verifies idempotency
and RBI bank-first advice, checks all targets and Grafana panel queries, and finds
a single trace across API, Redis queue handoff, worker, retrieval and both agents.
`X-Trace-ID` on submission identifies its Jaeger trace. Structured logs carry
trace, correlation and run IDs, but omit complaint bodies and exception messages.
Only traceparent crosses the queue; baggage is discarded. The script writes safe
local evidence to ignored `data/phase2-verification.json`.

The failure script exercises provider errors, OPEN/HALF_OPEN/CLOSED recovery,
timeouts, Redis 503 responses and collector independence. Run it while idle; it
temporarily recreates workers and the model stub and stops Redis and Jaeger.
See [runbook](docs/RUNBOOK.md) for manual recovery and troubleshooting. No Locust
benchmark or three-worker throughput result is claimed by these Phase 2 checks.
