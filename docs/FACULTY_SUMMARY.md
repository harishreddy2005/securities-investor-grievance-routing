# Securities Investor Grievance Routing
PESU mini-project 12 | ML System Design & AgentOps | Local integrated demo, 12 November 2026

## Purpose and reference case
Route synthetic investor complaints with traceable evidence; a human grievance officer decides. A bank fixed-deposit return shortfall naming SEBI identifies the RBI framework and advises a written complaint to the bank first. The system does not submit complaints, award compensation or invent passages.

## Architecture and corpus
FastAPI validates schema, dates and all nested free-text fields, quarantines rejects, and returns a Redis/RQ job ID. Two LangGraph agents investigate and verify; rejected evidence triggers one bounded re-search, then human escalation. Released citations match the persistent Chroma index. Three hash-verified PDFs cover SEBI SCORES 2023, the selected historical Mutual Funds Regulations 1996, and RBI Integrated Ombudsman Scheme 2021. Archive PDFs are excluded. CORPUS_CONFIRMATION.md records the reviewed interpretation and limits.

## Reliability and observability
Dependency deadlines, retries/backoff, a shared circuit breaker, idempotency and immutable outcomes protect processing. Worker heartbeat repairs expired queue metadata. Redis retrieval caching works across spawned job processes. Prometheus monitors seven targets; Grafana provisions 30 panels for API/agents, resources, corpus freshness, cache activity and mechanical quality trends. Jaeger correlates submission, queue, retrieval and agents. Durable run audits store tool evidence and actual-call accounting; complaint text and credentials stay out of exported trace attributes and logs. Docker log rotation bounds application logs.

## Evaluation and accounting
A deterministic v1/v2 policy comparison uses 22 scenarios: routing accuracy improves from 12/22 (54.5%) to 21/22 (95.5%). A bank mis-selling plus AMC redemption dispute conservatively escalates rather than forcing the AMC-only expected label. Evidence-overlap scores are documented heuristic proxies, not proof of general language-model reasoning. Actual model request/response characters provide labelled token/cost estimates; the local stub incurs zero billed API cost. Caller satisfaction is separate from independent provenance/policy checks.

## Load measurement and limits
Locust measures submission through validated result, including queue wait. The predeclared p95 target is eight seconds at one outstanding complaint per worker. One/three-worker runs retain failures and misses; see COMPLETION_STATUS.md and PHASE4_REPORT.md for actual results and sample-size limits. Higher-load performance is not guaranteed. This synthetic-data demo uses a zero-key stub, supports bounded product patterns, and has no production authentication. Unsupported or ambiguous cases escalate.

## Reproduce locally
Prerequisites: Python 3 for setup; Docker Desktop running Linux containers. Setup preserves existing settings and generates private Grafana credentials.
```bash
python scripts/configure_local.py
docker compose up --build -d --wait --wait-timeout 900
docker compose exec -T api python scripts/smoke_test.py
python scripts/verify_completion.py
```
UI/API docs: localhost:8000 and /docs. Prometheus: localhost:9090. Grafana: localhost:3000 (credentials in .env). Jaeger: localhost:16686. README.md and RUNBOOK.md cover monitoring, recovery, cache measurement and scaling. Consult COMPLETION_STATUS.md for current tests and publication status.
