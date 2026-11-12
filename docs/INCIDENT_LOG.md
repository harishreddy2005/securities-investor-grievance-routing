# Development incidents

## 2026-11-12 — Completion review recovery and test-fixture defects

The local API returned 503 while Redis had heartbeat-only worker hashes without
queue metadata. RQ's default heartbeat recreated only last_heartbeat after expiry.
ReliableSpawnWorker now repairs queue/identity metadata on heartbeat; worker
readiness checks the metadata too. Removing queues from an idle real worker's
hash reproduced the defect, then recovered without restart or deleting state.

The local HTTP CI harness was also reproduced on Python 3.11/Linux. Fakeredis's
TCP decoder raised ValueError and IndexError while handling binary RQ frames,
causing HTTP 503. Replaced only the simulator with a shared in-memory FakeServer.
The HTTP API/stub still run over real sockets; Compose separately tests real
Redis. Host and Linux harnesses then passed all four scenarios. This does not
represent the simulator as equivalent to the production Redis/SpawnWorker test.

Docker Desktop could not restart after a full-disk incident; its log explicitly
reported failure writing init.log. Space was available when completion resumed;
a non-destructive Desktop restart restored the engine and existing volumes.
Application container logs now rotate, and the benchmark checks disk headroom.
No named volume, regulatory index, user data or unrelated cache was deleted.

The integrated load test correctly encountered the default per-IP 60/minute
submission quota (HTTP 429). Preserved all failed samples in production-quota.json
and separated worker-capacity experiments with a declared benchmark-only 10000
quota; base settings are restored. The eight-second target remains unchanged.

One accepted workload was cancelled by a Locust stopping greenlet before its
result was collected. The failed sample remains in the original artifacts. The
collector now retains accepted IDs and drains them at stop without resubmission,
using the original timer/deadline; targeted timing/timeout tests verify this.
Controlled Docker cancellation recovered exactly one accepted complaint, with
zero failed/unfinished jobs. The same 60-second affected case then passed all
32 complaints; p95 13.929s still correctly misses the unchanged 8s stress target.
Original evidence is retained as worker-capacity-before-drain-fix; the retest and
consolidated report explicitly record which case was replaced. Full host and
Python 3.11 container suites pass 87 tests each. The current controlled failure
suite also passes provider timeout/error, circuit recovery, Redis outage/restore
and Jaeger independence, with normal settings and all volumes retained.

## 2026-11-11 — Stale RQ registration after Docker Desktop resumed

Docker Desktop was initially stopped. Starting its per-user installation restored
the existing containers and Redis AOF. The worker repeatedly exited with
`ValueError: There exists an active worker named ... already`; Redis showed a
registration with a heartbeat from 2026-11-03. Compose correctly refused readiness.
No queue, worker keys, indexed corpus or Docker volumes were deleted.

The worker now registers a unique incarnation suffix after its container hostname.
Its health check accepts only a matching container's recent heartbeat and rejects
stale/other-replica registrations. A focused test verifies those conditions.
The complete host suite passed 67 tests after the fix. Rebuilding/recreating the
application containers applies it; Phase 4's scaling and post-benchmark restart
checks provide the real-Docker recovery evidence recorded in PHASE4_REPORT.md.

## 2026-11-03 — Phase 2 test discovery and circuit timing

Pytest initially discovered a historical checkout in ignored `data/audit-c248225`
and reported duplicate module names. Added `pytest.ini` with `testpaths=tests`
and excluded runtime/audit directories; retained the audit and existing data.
The corrected complete local regression suite passes.

The first real Docker circuit demonstration used a five-second cooldown. RQ
SpawnWorker needed long enough to import its semantic runtime that the next job
correctly reached HALF_OPEN instead of observing OPEN, failing the test's
`circuit_open` assertion. Increased only the failure fixture's cooldown to 60
seconds. The repeated test passed provider exhaustion, fail-fast OPEN, failed
HALF_OPEN reopening, recovered HALF_OPEN closing, timeout escalation, Redis 503,
fresh post-recovery RBI bank-first routing, and Jaeger-outage independence.
The script restored normal configuration after both attempts, without deleting
volumes. This was a timing assumption in the fixture, not a bypass of the circuit.

## 2026-10-30 — Local Docker engine unavailable

`docker --version` returned 29.8.2. `docker info` failed because the Windows
`docker_engine` named pipe did not exist. The client also reported denied access
to the host Docker configuration. This prevents local container execution; it is
not evidence of an application error. Recovery: start Docker Desktop on the
teammate's machine and run the README checklist. Docker CI has been added but
must actually run before it can be claimed as passing.

## 2026-10-30 — Dependency setup and early test attempts

The workspace was empty and GitHub network access was blocked in the restricted
shell. An approved network-enabled clone succeeded. Initial pip access also
failed in the restricted shell; an approved install into `.venv` proceeded.
Early pytest attempts failed during the still-running install because pytest,
pydantic-settings, and then Chroma were not installed yet. These runs did not
exercise the application. Subsequent completed test runs are recorded in the
append-only handoff progress log.

## 2026-10-30 — Historical MF Regulation 53 discovered in PDF footnotes

Parsing the actual corpus showed page 79's numeric payment periods are historical
text quoted in an amendment footnote. The operative Regulation 53 is on page 80
and delegates periods/rates to the Board. The exact-section index now anchors to
page 80; a regression test forbids the old `10 working days` text in that anchor.
The Phase 0 recommendation states only the verified 21-day grievance timeline
under Regulation 60A and SCORES 1.2.

## 2026-10-30 — First local HTTP harness failure and recovery

The development-only harness initially registered an RQ worker twice. RQ correctly
refused the duplicate; cleanup also found Windows native Chroma file locks. The
harness now waits for normal worker registration and retains its local index in
ignored data/, with daemon TCP handler threads that shut down cleanly. Both test-
and semantic-embedding HTTP smoke runs subsequently passed all four scenarios.
TCP fakeredis occasionally closes a blocking queue connection; RQ logged a retry
and recovered, with every job completed. Production Redis/SpawnWorker verification
is still reserved for Docker; the simulator is not presented as equivalent.

The initial semantic-model download also encountered a transient DNS resolution
failure. DNS resolution and the subsequent model download succeeded; real semantic
ingestion built 539 chunks. No hash checks were disabled.

## 2026-10-30 — Docker engine blocker resolved

The user requested local execution. Starting the installed Docker Desktop made
the Linux engine available. Actual Compose build/start and both pre-restart and
post-restart four-scenario smoke tests passed with real Redis, Linux SpawnWorker,
semantic embeddings and the HTTP model stub. Ingestion completed with 539 chunks;
repeat ingest returned unchanged=true. Redis/API/worker restart retained the
original FD result. All four services are healthy and the app is running at
http://localhost:8000. The earlier unavailable-engine incident is now resolved.

## 2026-10-30 — Prior-complaint form and date input

The UI allowed prior complaint dates/responses without selecting the prior-approach
checkbox; the API correctly rejected the contradiction, but the UI displayed raw
JSON. Dates such as year 1202 passed the API's future/order-only checks. Fixed UI
field state/payloads and readable messages; added a 1900-01-01 application sanity
bound on dates in both browser and API. Python regression suite passed 38 tests;
actual Edge browser tests and real-Docker HTTP smoke passed. Existing browser tabs
need refreshing to load the new form.
