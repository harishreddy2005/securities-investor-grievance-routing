# Repository audit — 2026-11-11

**Superseded for latest GitHub state:** see
[November 12 completion review](COMPLETION_REVIEW_2026-11-12.md).
GitHub now contains `736d95d`, with substantial application integrations beyond
the historical snapshot below. The new review records tested improvements,
remaining gaps, CI failure and the current local readiness/storage problems.

**Resolution:** the subsequent integrated fixes and final verification are in
[COMPLETION_STATUS.md](COMPLETION_STATUS.md). This file is a historical audit,
not a statement that the repaired issues remain open.

This audit checks executable integration against TEAM_PLAN.md and the original
problem statement. A committed module or a passing isolated unit test does not
by itself establish that the feature runs in the API/worker workflow. Historical
phase completion messages should be read alongside the gaps below.

Remote check: fetched `origin/main` at `b5ce9f6`. It is two commits ahead of local
`main` (`6e64c31`), adding only FACULTY_SUMMARY.md/.docx/.pdf. There are no newer
application fixes on GitHub. This audit includes remote change inspection without
merging over the uncommitted Phase 4 work; the benchmark records the actual local
base commit and hashes of its changed measurement/worker sources.

| Phase | Evidence and current scope | Remaining work |
|---|---|---|
| 0 | End-to-end PDF ingestion, semantic retrieval, two LangGraph agents, Redis/RQ, API and frontend; exact evidence audit and RBI bank-first reference case. Published checkpoint exists. | Maintain regression coverage and repeat startup/smoke on the teammate's environment. |
| 1 | Complaint-text input guardrails, unknown/mixed-product escalation and exact citation verification are integrated. Guardrail output helper exists. | Guard every free-text field passed to the model; integrate output authority/toxicity checks; implement the planned bounded verification/re-search loop. |
| 2 | Published as 6e64c31: deadlines, dependency retries, shared circuit breaker, idempotency, JSON logging, Prometheus/Grafana/Jaeger and cAdvisor, with actual Docker evidence. | Full original D5 reconstruction still lacks per-call prompt/token/cost recording. Index freshness/ingestion-throughput metrics are in the manifest/health response, not dedicated Prometheus series. Phase 4 addresses a stale worker identity found during resumed startup. |
| 3 | 21-scenario evaluation CLI, v1/v2 YAML files, cost helper and in-memory cache helper are present in teammate commits. | Runtime prompt selection/comparison, real cost attribution, integrated cache, rate limiting, persistent feedback and live quality metrics are not complete. Existing evaluation metrics are simplified proxies. |
| 4 | Locust lifecycle test, declared 8-second SLO, containerized generator, scaling runner and lifecycle tests exist locally. | See PHASE4_REPORT.md for actual final measurements and completion status; publication requires a separate commit/push request. |

## Evidence for the integration gaps

1. **Input/output guardrails:** [app/main.py](../app/main.py) calls
   `inspect_input_text` only on `complaint_text`. The model receives the entire
   validated request through [app/agents/tools.py](../app/agents/tools.py),
   including entity and other free-text fields. `inspect_output_decision` in
   [app/guardrails/safety.py](../app/guardrails/safety.py) is exercised by unit
   tests but has no application caller. It checks unauthorized determinations,
   not output toxicity. Add integration tests that demonstrate blocked model
   input/output, rather than only helper tests.
2. **Verification retries:** [app/agents/graph.py](../app/agents/graph.py) has
   START → investigator → verifier → END, with no conditional return edge.
   Invalid evidence escalates immediately. Phase 2's dependency retries retry an
   unavailable operation; they do not implement evidence-driven re-search.
3. **Prompt comparison:** YAMLs exist under `app/prompts/`, but the graph/model
   never loads them. [app/cli/evaluate.py](../app/cli/evaluate.py) accepts a
   `prompt_version` label without selecting a different runtime prompt/graph.
   [app/schemas.py](../app/schemas.py) still defaults results to `phase0-v1`.
   A v1-v2 before/after effectiveness claim requires actually different prompt
   execution on the same scenario set and saved reproducible results.
4. **Evaluation validity:** [app/eval/evaluator.py](../app/eval/evaluator.py)
   treats a nonempty quote as supported groundedness; `retrieved_citations` is
   unused. Faithfulness largely compares routing/authority. These are useful
   narrow checks, not comprehensive claim-level groundedness/faithfulness.
   Existing stored perfect scores are not proof of all original L3 requirements.
   A read-only rerun of all 21 scenarios on November 11 reproduced those stored
   proxy scores; it did not establish a different v1/v2 prompt execution path.
   The default application Dockerfile does not copy `eval/scenarios.json`, so
   the evaluation needs an explicit dataset mount (used for this audit) or a
   documented packaging change before its default CLI runs in that container.
5. **Cost/cache:** `CostTracker.record_step` has no model/worker caller and uses
   character-count token estimates and illustrative prices. `QueryCache` has no
   runtime caller and stores entries only in a process-local dictionary. Neither
   is shared Redis runtime caching. Submission idempotency is a separate
   correctness mechanism, not a cache benefit benchmark.
6. **Feedback/rate limits:** [app/main.py](../app/main.py) exposes submission,
   polling/results, health, frontend and metrics. No feedback endpoint,
   satisfaction aggregation, per-client rate limiter or quality trend endpoint
   is implemented. The load runner intentionally does not invent these features.
7. **Full trace/cost reconstruction:** Jaeger links required service/agent spans,
   and result `agent_trace` records investigator searches. There is no dedicated
   `/api/v1/grievances/{run_id}/trace` API, prompt token accounting or per-step
   billed cost reconstruction. Complaint contents must continue to stay out of
   exported telemetry; any richer internal audit needs appropriate privacy design.
8. **Faculty handout consistency:** the remote FACULTY_SUMMARY.md quickstart omits
   `python scripts/configure_local.py`, required to fill Grafana credentials on a
   fresh clone. It also claims PAN validation, which the current submission schema
   does not implement. Its perfect evaluation scores need the proxy-metric caveat
   above, and its test count predates Phase 4. Refresh the Markdown/DOCX/PDF
   handouts together before presenting them; do not call this unauthenticated stub
   demo a production service. Keep bank-first/eligibility language aligned with
   the verified CORPUS_CONFIRMATION.md reference.
9. **Reproducibility:** top-level requirements are pinned, but Python base images
   and transitive dependencies float. A fresh November 11 build downloaded newer
   runtime layers/dependencies than the earlier November 3 pilot. The Phase 4
   matrix uses one consistent newly built image and records its ID/source hashes;
   do not combine the two dates' latency samples. Fully locking image digests and
   transitive dependencies would strengthen repeatability.

## Suggested completion order after Phase 4

1. Finish Phase 1 integration: all-field input checks, output guardrails and the
   bounded verifier-to-investigator re-search path, preserving exact citations.
2. Wire Phase 3 prompt version selection and run a genuine v1-v2 comparison.
   Strengthen metric definitions and explicitly state their limits.
3. Integrate cache and per-client rate limiting; measure their actual effect on
   latency and cost using the Phase 4 harness. Do not count idempotency as caching.
4. Add persistent feedback, quality aggregation and per-step token/cost records.
   Reconcile those records with trace IDs and expose missing ingestion metrics.
5. Refresh the final report/demo checklist and run the documented Docker workflow
   on the teammate's machine. Commit/push only reviewed source and documentation;
   keep `.env`, screenshots, local benchmark artifacts and `.vscode` private/local.

The model remains a deterministic reference-case stub. Production authentication
and broad product understanding are limitations rather than prerequisites for
the stated college demonstration. Regulatory PDFs have not been changed.
