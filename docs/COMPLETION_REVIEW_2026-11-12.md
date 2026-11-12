# Project completion review — 2026-11-12

**Verdict: the reference demo is substantially implemented, but the combined
project is not yet fully complete or ready for an unconditional completion claim.**
This review supersedes the GitHub-state conclusions in the November 11 audit.
No application code was merged, committed, pushed or restarted for this review.

**Subsequent resolution:** the user authorized fixing these findings. Current
integrated implementation and verification are in
[COMPLETION_STATUS.md](COMPLETION_STATUS.md); this review is retained as the
pre-fix evidence, not the current completion status.

## Versions and verification

- GitHub `origin/main`: `736d95d400cce463c5883831b9bc634d9b713836`.
- Local `main`: `6e64c31`, plus uncommitted Phase 4 sources/reports and the worker
  restart fix. GitHub is three commits ahead; the newest contains real application
  changes. The Phase 4 load profile, runner, report and restart fix are not there.
- Reviewed the full app/test/configuration inventory and every changed application
  file in the new remote commit in isolated ignored `data/audit-736d95d/`.
- Remote-code suite: **64 passed**, two upstream deprecation warnings, executed
  against the isolated checkout using the existing local Python 3.14 environment.
- Actual latest GitHub Actions: Compose job **passed**; Python job **failed** at
  `HTTP smoke with local test dependencies`. Public annotations expose exit 1,
  not its root cause. [Run evidence](https://github.com/harishreddy2005/securities-investor-grievance-routing/actions/runs/43148477226).
- Local Docker API currently reports **503**, Redis reachable, 539 indexed chunks,
  `worker=false`. The worker container reports healthy, but inspected Redis worker
  hashes contain only `last_heartbeat`, with no queue metadata. That discrepancy
  explains why API worker discovery rejects it; the cause/recovery needs a fix.
- Attempting the remote-code local HTTP harness stopped at Chroma initialization:
  SQLite code 13, `database or disk is full`. A separate shell then failed with
  Windows error 112 (not enough disk space). This is an environment blocker;
  it is not proof of the cause of the GitHub failure. Only the duplicate temporary
  audit ZIP created for this review was removed; user/runtime data were retained.

## What the new GitHub commit genuinely adds

Prompt artifact loading/version labels, differing offline v1/v2 retrieval policies,
22-scenario before/after evaluation, retrieval-cache call sites, estimated cost
records, an output authority-filter call, per-IP submission rate limiting, and
Redis-persisted feedback/summary endpoints are now present. The older claim that
these helpers have no runtime callers is no longer accurate for `736d95d`.
Do not dismiss those additions, but distinguish their integration limits below.

## Remaining issues, in priority order

1. **Restore reliable readiness and make CI green.** Reproduce/fix the missing
   worker-registration metadata and the failed local HTTP CI smoke. Repeat clean
   startup, idle/restart readiness and queued complaint processing. The current
   red readiness check precludes an unconditional demonstration-ready claim.
2. **Combine the two versions safely.** Preserve local Phase 4 work while bringing
   in GitHub's latest application changes. Re-run regressions, Docker smoke,
   monitoring and scaling on that combined source. November 11's 67 local tests
   and 295 successful benchmark complaints remain valid historical evidence,
   not verification of this newer integrated version.
3. **Complete L4 coverage.** A controlled graph probe confirmed an injection in
   `entity_name` reaches the model: API and investigator still inspect only
   `complaint_text`, while inspect_request_fields passes the whole request.
   An independent helper probe confirmed toxic output is accepted because the
   output filter checks authority patterns only. Guard all free-text fields and
   all relevant output paths; add corresponding integration tests.
4. **Fix prompt-version parity.** A mocked-HTTP probe selected v1, but the HTTP
   request omitted `prompt_version`: offline v1 returned `unknown`, HTTP mode
   returned default-v2 `bank_fd` for the same test complaint. The evaluation CLI
   explicitly forces in-process stub mode, hiding this discrepancy. Prompt text
   is not sent to an actual language model; the demo still supports a stub only.
5. **Persist realistic per-call cost records.** Records now exist, but only in a
   process-local dictionary. RQ SpawnWorker discards that state when the job child
   exits; no cost summary is included in stored results or durable records.
   Counts are character-based estimates of constructed text after the call,
   including passages/full routing results the HTTP stub did not receive/produce.
   Label estimates clearly, count actual call payloads/usage, persist by run/step,
   and correlate with trace data. Local stub billing is not an external API bill.
6. **Validate caching on the deployed worker path.** The retrieval cache is now
   called, but remains an in-memory dictionary per process. Offline cold/warm
   suite totals are not submission-to-result p95/cost evidence across fresh RQ
   children or replicas. Measure that path; use suitable shared/persistent caching
   if the goal is a cross-job improvement. D7's p95/cost comparison remains open.
7. **Finish independent live quality evaluation.** Feedback is now persisted,
   but its quality score is a weighted caller rating plus status/citation flags,
   not the same evidence-based evaluator used on live run samples. A probe got
   HTTP 201 and score 0.75 for a nonexistent run. Validate run references and
   implement independent quality scoring/trends, rather than calling that score
   groundedness/faithfulness. No Grafana quality-over-time panel was added.
8. **Finish original trace/ingestion reporting.** Per-call prompt/cost history is
   not reconstructible from the current spans/results; ingestion freshness and
   throughput remain manifest fields rather than dedicated Prometheus metrics.
9. **Align packaging/docs and report scope.** The default image still does not
   copy `eval/scenarios.json`; evaluation needs a mount. Faculty quickstart still
   skips Grafana credential setup. Clearly state stub/heuristic limitations.
   Verification failures already escalate safely (satisfying A3's fallback), but
   the team plan's verifier-to-investigator re-search loop remains unimplemented.
   Broad domain coverage/model-selected tool policy also remains limited to the
   reference-pattern implementation, rather than a general grievance planner.

The new evaluator uses raw evidence and sentence-overlap heuristics and no longer
claims universal perfect scores. Those are stronger diagnostic proxies, not an
independent semantic entailment proof. Its stored 19/22 v2 result and all three
conservative edge-case misses should remain visible in the final report.

## Completion gates

Free sufficient disk space without deleting useful data; restore API readiness;
resolve the failed CI job; integrate remote changes with local Phase 4; address
or explicitly scope the remaining requirements; then run one clean combined
Docker demonstration and publish the reviewed source/report. No fresh full
six-case benchmark or combined-version Compose test was claimed in this review.
Completing every original requirement is not required by the assignment, but
unimplemented items must be acknowledged and cannot be marked completed.
