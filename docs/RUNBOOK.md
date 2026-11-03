# Application and Phase 2 runbook

Run commands in the repository root. See README for first startup.

## Ingestion or model download fails

Symptom: `ingest` exits nonzero; `worker` and `api` wait for it.

```bash
docker compose ps -a
docker compose logs --tail=200 ingest
```

Check outbound access and free disk space. The first ingest downloads Chroma's
bundled ONNX semantic model; later starts use the persistent model cache. Hash or
section-anchor errors require reviewing the PDF against `corpus/SOURCES.md`;
never disable verification to start the app. Restore the reviewed source files.

After fixing the cause:

```bash
docker compose run --rm --no-deps ingest
docker compose up -d --wait --wait-timeout 900
docker compose exec -T api python scripts/smoke_test.py
```

Use `docker compose run --rm --no-deps ingest python -m app.cli.ingest
--re-embed-only` to embed cached parsed chunks without reparsing the PDFs. Do not
rebuild an index concurrently with jobs; stop workers first and restart them after
reindexing. Workers retain their loaded index version until restart.

## Jobs fail or remain queued

```bash
docker compose ps -a
docker compose logs --tail=200 worker redis llm-stub
docker compose exec -T api python scripts/smoke_test.py
```

Search worker logs for the run UUID. Confirm Redis health, worker heartbeat,
matching embedding settings, and `STUB_FAIL=false`. Fix `.env`, then:

```bash
docker compose up -d --force-recreate llm-stub worker api
```

Failed jobs remain failed; resubmit the synthetic request after recovery. RQ
isolates each job in a child process; errors and timeouts are stored in Redis.
After a worker/host dies abruptly, RQ maintenance may take time to classify an
abandoned job as failed. Phase 0 does not automatically retry failed jobs; this
avoids silently duplicating work. Phase 2 retries transient dependency operations
within a bounded job and returns an explicit human escalation when they exhaust.
Never return a recommendation for a failed job.

## Verification and cleanup

```bash
docker compose exec -T api python scripts/smoke_test.py
docker compose logs --tail=200 > logs.txt
docker compose down
```

Only use `docker compose down -v` when intentionally discarding all stored demo
jobs, the vector index and model cache. No commit or push is part of these steps.

## Phase 2 startup and monitoring

```bash
python scripts/configure_local.py
docker compose up --build -d --wait --wait-timeout 900
docker compose ps -a
python scripts/verify_phase2.py
```

The setup helper preserves existing `.env` and fills missing/blank Grafana
credentials. Keep `.env` private. Nine services should be healthy and ingest
should exit 0. Startup can be slow during the first embedding or image download.
Do not interrupt a successful image download merely because it is slow.

Open Prometheus http://localhost:9090/targets: all seven jobs should be UP.
`workers` points to `worker-metrics:9101`, which aggregates Redis counters and
histograms across RQ child processes and worker replicas. It does not depend on
Prometheus discovering ephemeral job processes. Queue depth excludes running jobs.
If a target is down, check its `lastError`, the named service's health and logs,
and the internal hostname/port in `deploy/prometheus/prometheus.yml`.

cAdvisor uses read-only Docker host system mounts and privileged access to collect
CPU/memory/uptime for containers in Docker's Linux VM. It has no published host
port and stores no complaint labels. Docker Desktop must run Linux containers;
this collector requires access to that VM's cgroups and Docker runtime metadata.
Application containers remain unprivileged. After editing the mounted scrape
configuration, run `docker compose restart prometheus` to load it.

Open http://localhost:3000/d/grievance-phase2 using `.env` credentials. Provisioned
datasource UID is `grievance-prometheus`; dashboard UID is `grievance-phase2`.
Submit complaints and allow two five-second scrapes before expecting rates or
latency. For missing data, query `up` and `grievance_jobs_total` in Explore.
Counters may persist from earlier runs; select a suitable time range for rates.
Persisted Grafana credentials are initialized on first start: editing `.env`
later does not reset a password in its existing database. Use Grafana's documented
admin password reset procedure against that instance instead of deleting volumes.

Open http://localhost:16686 and select `grievance-api` or `grievance-worker`.
Submission response header `X-Trace-ID` links directly to
`http://localhost:16686/trace/<trace-id>`. Expect complaint.submit, job.process,
retrieval, agent.investigator, agent.verifier, verification, and result.store in
one trace. OTLP export is HTTP to internal `http://jaeger:4318/v1/traces`; the
export port is not published to the host. Give batches a few seconds to arrive.
Structured logs include trace_id, correlation_id and run_id; payloads and raw
exception messages are suppressed. A collector outage can lose traces but must
not prevent processing. Redis and index volumes are independent of monitoring.

## Controlled failure demonstration and restoration

Run only against an idle local synthetic-data stack:

```bash
python scripts/failure_test_phase2.py
python scripts/verify_phase2.py
docker compose exec -T api python scripts/smoke_test.py
```

The script uses an ignored override at `data/phase2-failure.json`, recreates
stub/worker with short call deadlines and a 60-second circuit cooldown, verifies
provider failures and a single HALF_OPEN probe, then tests Redis and collector
outages. A long enough cooldown is necessary to observe OPEN across SpawnWorker
startup on Docker Desktop. Brief HALF_OPEN states are visible in the transition
counter and logs even if Prometheus's five-second gauge scrape misses them.
The script restores normal settings in `finally` blocks without deleting data.
It may take several minutes. Do not run smoke or other complaint jobs concurrently
with these deliberate outages. If interrupted, restore with:

```bash
docker compose up -d --wait --wait-timeout 900
```

An existing OPEN circuit waits for its recorded cooldown before a recovery probe;
restarting a worker deliberately does not reset shared circuit state. Healthy
probe success closes it. Safe result codes include timeout, unavailable,
invalid_response and circuit_open. Their result is uncertain, requires human
review and contains no regulatory citations. Programming errors remain failed
jobs. New submissions after recovery should use a new Idempotency-Key if the
previous key identifies a completed escalation or failed job.

`LLM_TIMEOUT`, `RETRIEVAL_TIMEOUT`, `REDIS_TIMEOUT`, `DEPENDENCY_RETRIES`,
`RETRY_BASE_SECONDS`, `RETRY_CAP_SECONDS`, `CIRCUIT_FAILURE_THRESHOLD`, and
`CIRCUIT_COOLDOWN_SECONDS` configure the policy. An operation has at most
`DEPENDENCY_RETRIES + 1` attempts. Retrieval deadlines bound the caller; Python
cannot forcibly cancel native work in a daemon thread. RQ's overall job timeout
is the final process boundary. `TELEMETRY_EXPORT_TIMEOUT` bounds export attempts;
traces are best effort. No production authentication is implemented on the API.
