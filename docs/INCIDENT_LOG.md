# Development incidents

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
