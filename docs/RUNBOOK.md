# Phase 0 runbook

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
avoids silently duplicating work. Timeout and retry/circuit-breaker demonstrations
are later phases. Never return a result for a failed job.

## Verification and cleanup

```bash
docker compose exec -T api python scripts/smoke_test.py
docker compose logs --tail=200 > logs.txt
docker compose down
```

Only use `docker compose down -v` when intentionally discarding all stored demo
jobs, the vector index and model cache. No commit or push is part of these steps.
