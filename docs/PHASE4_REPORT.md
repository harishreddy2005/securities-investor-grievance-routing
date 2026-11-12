# Phase 4 completion and measured benchmark — 2026-11-11

Historical pre-integration measurements. See [COMPLETION_STATUS.md](COMPLETION_STATUS.md)
for the combined teammate/local build, subsequent capacity/cache experiments and
retained quota failures. These original measurements remain unchanged.

Generated from real Docker Locust results. SLO declared in docs/PHASE4_SLO.md before measurements.

Timestamp: 20261111T033103Z; commit: `6e64c316f7f8a73345324245dbec6a5940d81f0b`.
Docker: 12 CPUs, 7.42 GiB RAM.
Active duration: 120 seconds/case; stub delay: 0.1 seconds/call.

| Workers | Clients | OK / failed / unfinished | Complete RPS | HTTP RPS | p50 s | p95 s | Queue p50 s | Max queue | SLO |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 37 / 0 / 0 | 0.306 | 4.631 | 3.128 | 3.827 | 0.786 | 0.0 | MET |
| 1 | 3 | 40 / 0 / 0 | 0.315 | 12.035 | 9.200 | 10.452 | 6.780 | 2.0 | MISSED |
| 1 | 6 | 42 / 0 / 0 | 0.308 | 22.336 | 19.056 | 22.486 | 16.488 | 5.0 | MISSED |
| 3 | 1 | 29 / 0 / 0 | 0.238 | 4.349 | 3.938 | 6.508 | 0.795 | 0.0 | MET |
| 3 | 3 | 73 / 0 / 0 | 0.597 | 12.684 | 4.776 | 6.011 | 0.843 | 0.0 | MET |
| 3 | 6 | 74 / 0 / 0 | 0.576 | 23.246 | 10.071 | 11.381 | 5.920 | 3.0 | MISSED |

Throughput includes graceful drain. HTTP RPS includes status polling and is not complaint RPS.
Percentiles use exact nearest-rank completed successful lifecycles; failed/unfinished work fails the SLO.
These are short closed-loop demonstration measurements, not production capacity or a statistically precise tail estimate.

- First tested SLO failure for 1 worker(s): 3 concurrent clients.
- First tested SLO failure for 3 worker(s): 6 concurrent clients.

## Outcome and scaling effect

Phase 4 load/scaling implementation and the six-case local Docker measurement are complete. All 295 reference complaints returned verified RBI bank-first results; no failed or unfinished lifecycles were recorded. The declared eight-second target was met at both normal-load points (1 worker/1 client and 3 workers/3 clients). Higher-concurrency misses are retained as measured failures of the target. No target or regulatory logic was changed to make the results pass.

| Same client concurrency | Throughput: 3 workers / 1 worker | p95 reduction |
|---|---|---|
| 1 | 0.78x | -70.1% |
| 3 | 1.90x | 42.5% |
| 6 | 1.87x | 49.4% |

Extra workers provide no benefit when one closed-loop client supplies only one outstanding complaint; that case also shows shared-machine variability. At 3 and 6 clients, compare like-for-like loads above. Scaling is useful but is not linear.

## Bottleneck evidence

| Workers | Clients | Mean worker CPU cores (sum) | Mean API CPU cores | Mean Redis CPU cores | Mean stub CPU cores | Peak combined worker memory MiB |
|---|---|---|---|---|---|---|
| 1 | 1 | 1.867 | 0.070 | 0.018 | 0.036 | 441.5 |
| 1 | 3 | 2.079 | 0.100 | 0.022 | 0.037 | 410.6 |
| 1 | 6 | 2.217 | 0.149 | 0.030 | 0.040 | 423.2 |
| 3 | 1 | 2.460 | 0.088 | 0.023 | 0.046 | 662.4 |
| 3 | 3 | 4.936 | 0.125 | 0.032 | 0.045 | 1045.4 |
| 3 | 6 | 5.483 | 0.209 | 0.043 | 0.055 | 1051.1 |

Observed queue wait increases with clients per worker while single-worker completed throughput stays near its ceiling. More workers substantially reduce queue wait and improve throughput. The worker execution path is the demonstrated service bottleneck; API/Redis/stub CPU consumption is much smaller. These are sampled container counters, not proof that every host CPU was saturated.

A sampled baseline trace (`a83d595491b0ca077b8fd50762c2d0cb`) has a 0.005s submission span, a 1.542s interval from submission to worker span start, 1.535s in job.process, 0.720s in the investigator and 0.152s in the verifier. The pre-worker interval includes dispatch/process startup as well as any queue wait; it cannot be attributed entirely to queueing.

Code inspection explains a repeatable cost: RQ SpawnWorker starts a fresh Python job process; imports occur before job.process, and resources() creates Chroma/embedding/graph state within that process. Parent warmup does not preserve those Python objects in spawned children. This is a supported initialization/worker-path explanation, not a separately proven Chroma-lock or memory-exhaustion diagnosis. Real-provider rate limiting is excluded by the deterministic local stub.

Potential follow-up experiments are bounded native-thread settings, finer startup spans and a persistent spawned worker/retrieval process design that preserves isolation. Keep this baseline and run before/after tests before adopting such changes. Phase 4 does not silently replace the process-isolation architecture.

## Method and reproducibility limits

- Six cases each had 120 seconds active traffic, followed by graceful drain. Completed RPS uses the full measured elapsed interval, including drain. HTTP RPS includes status polling and is shown separately.
- Each user has one outstanding fresh complaint, 0.1s think time and 0.25s polling. The stub delays each model call by 0.1s; real semantic retrieval and the full queue/agent/evidence workflow remain enabled. A warmup was excluded and cases began with no queued/started jobs.
- Exact nearest-rank percentiles come from successful raw lifecycle samples. Failures and unfinished work independently fail the SLO. The observed queue-wait estimate includes submission overhead and polling resolution. Prometheus/cAdvisor samples are approximately every three seconds with five-second scraping and 30-second CPU rate windows.
- This is a short closed-loop demonstration on a shared Docker Desktop host. Per-case samples are below the recommended 100; p95 is not a statistically precise production estimate. First *tested* failure levels are not an exact capacity threshold between tested points.
- The entire matrix used the same rebuilt application image. The November 3 pilot is historical and is not pooled with these samples; floating base/transitive dependencies and host conditions changed between dates. Parent commit is recorded above; Phase 4 source changes were uncommitted during the measurement. Actual image ID and source SHA-256 values are in the local benchmark JSON.
- Raw lifecycle samples, Locust CSV/logs, example traces and sampled resources are retained in ignored data/phase4/. Publish aggregate documentation, not private environment files or runtime data.
- Use the JSON lifecycle samples for exact final counts/percentiles. Locust CSV histories are periodic, rounded snapshots and can precede the last gracefully drained completion; the generic aggregated row also mixes HTTP polls with synthetic lifecycle events.

## Run commands

```bash
python scripts/configure_local.py
docker compose up --build -d --wait --wait-timeout 900
docker compose --profile loadtest build loadtest
python scripts/run_scale_benchmark.py --duration 120 --users 1 3 6 --workers 1 3
```

Use --fail-on-slo to return exit 2 for any target miss after the full matrix. Without that flag, target misses are reported; failed/unfinished lifecycle samples still return an error. No commit or push is part of the runner.

## Verification and remaining scope

Host Python 3.14 and rebuilt application Python 3.11 container suites each passed 67 tests (two and one upstream deprecation warnings). The load runner restored one worker and original stub settings without deleting persistent volumes. Post-load smoke, monitoring and restart checks are recorded below. GitHub Actions was extended with a short one/three-worker functional smoke and artifact collection, but has not run for these unpushed changes.

See PROJECT_AUDIT.md for remaining Phase 1/3 integration gaps and the remote faculty-handout corrections. Phase 4 completion does not certify those separate requirements. PROJECT_REPORT.md summarizes deployment, decisions, costs and demonstration limits.

### Post-load checks actually executed

- Abrupt idle-worker `SIGKILL`, followed by Compose startup/readiness: passed;
  no stale-name collision and no Redis/index/volume deletion.
- Original Docker HTTP smoke: all four reference scenarios passed after restart.
- `scripts/verify_phase2.py`: seven scrape targets UP, all 26 Grafana expressions
  returned finite data, idempotency/conflict checks passed, and a fresh single
  Jaeger trace linked API/worker/stub. Checked logs/trace contained no private
  canary or complaint body. Trace: `e2ba5b92202f61683fb3625dec1062a2`.
- Read-only 21-scenario evaluation in an application container with an explicit
  dataset mount reproduced the existing proxy scores: routing accuracy,
  groundedness, context relevance and faithfulness 1.0; hallucination proxy 0.0.
  No saved teammate result was overwritten. This is not a real v1-v2 comparison.
- `compileall`, host `pip check` and `git diff --check`: passed.
- CI workflow changes remain unexecuted on GitHub; no commit/push performed.

### Changed project files

Load testing: `locustfile.py`, `loadtests/lifecycle.py`, `loadtests/__init__.py`,
`requirements-load.txt`, `deploy/loadtest/Dockerfile`,
`scripts/run_scale_benchmark.py`, `tests/test_load_lifecycle.py`.
Runtime restart fix: `app/worker.py`, `app/worker_health.py`,
`tests/test_worker_health.py`. Configuration: `docker-compose.yml`,
`.env.example`, `.github/workflows/tests.yml`. Documentation: `README.md`,
`docs/PHASE4_SLO.md`, this report, `docs/PROJECT_REPORT.md`,
`docs/PROJECT_AUDIT.md`, `docs/RUNBOOK.md`, `docs/INCIDENT_LOG.md`,
`docs/TEAM_PLAN.md`, and `docs/agent_handoff/PROGRESS_LOG.md`.
Preexisting `.vscode/` and reviewed PDFs were not modified.
