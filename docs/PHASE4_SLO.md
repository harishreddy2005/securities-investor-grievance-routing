# Phase 4 SLO and measurement protocol

Declared 2026-11-03 before executing Phase 4 load measurements. Retains the
existing `D6` target in agent_handoff/IMPLEMENTATION_PLAN.md; it is not selected
after inspecting benchmark results.

**Target: p95 submission-to-validated-result latency <= 8.0 seconds**, with no
failed/degraded reference results, at normal load. Normal load is one concurrent
grievance per worker: 1 client with 1 worker, or 3 clients with 3 workers.
Eight seconds permits interactive grievance-officer triage while two agents
retrieve and verify evidence. This is an engineering demo target, not a regulator
deadline. A failed measurement must be reported as a miss, not used to move it.

Use the deterministic HTTP model stub with **0.1 seconds per model call**, real
semantic embeddings, persistent corpus and real Redis. Keep monitoring enabled.
Each client has one outstanding fixed-deposit reference complaint and 0.1 seconds
think time between runs. Use unique idempotency keys to execute fresh work.
Validate RBI routing, bank-first advice, evidence and both-agent participation.
Never count an uncertain escalation as a successful reference answer.

Measure with Locust inside Compose. Start the monotonic timer before POST and
stop only after polling completion, fetching and validating the final result.
Submission HTTP latency and poll HTTP requests are separate from the custom
`GRIEVANCE / complete` lifecycle metric. Report complete-run RPS, HTTP RPS,
p50/p95, failures, SLO-violation proportion, observed queue wait and maximum
queue depth. Include graceful-drain time in lifecycle throughput denominators.
Report active load duration and drain separately; never hide unfinished jobs.

Compare 1 and 3 workers at client concurrency 1, 3 and 6 (optionally 12+).
Default active load is 120 seconds per case, with up to 210 seconds graceful
drain. A shorter local demonstration must state its duration/sample-size limits;
recommend >=100 successful runs per case for more credible tail estimates.
Use exact nearest-rank percentiles on raw completed-run samples; zero successes
produce null percentiles and cannot pass. Failures and cancelled/unfinished
lifecycles fail the SLO independently of successful-run latency.

Identify the first **tested** failing concurrency for each worker count. If the
first tested level already misses, report that the boundary is <= that level;
if none misses, report the boundary was not found. This is a closed-loop test,
not a fixed arrival-rate capacity claim. Capture queue/service observations and
container CPU/memory for a supported bottleneck explanation. Preserve raw JSON,
Locust CSV and environment metadata in ignored data/phase4/. Record selected
aggregate results and limitations in docs/PHASE4_REPORT.md.

Do not flush Redis or delete volumes. Start each case with no queued/started jobs,
scale with `docker compose up -d --scale worker=3`, and restore one worker and the
original stub settings afterward. Do not change regulatory logic to improve time.

## Integrated-build capacity experiment (declared before its rerun, 2026-11-12)

The initial combined-source run at the production default 60 submissions/minute
correctly hit HTTP 429 around one run/second from Locust's single IP. Preserve
that run as rate-limit evidence. It measures application quota as well as workers.
For the separate worker-capacity and cache experiments, set a benchmark-only quota
of 10000/minute, report it explicitly, and restore the base API settings afterward.
This does not change the eight-second latency target or production default.
It prevents the intentional client budget from masking worker/cache behavior.
