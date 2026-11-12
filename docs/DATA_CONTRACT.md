# Application data contract

OpenAPI at `/docs` and `/openapi.json` is generated from `app/schemas.py`.
Use synthetic complaints only. The service never submits complaints externally.

## Submit

`POST /api/v1/grievances` returns **202**, immediately after enqueueing:

```json
{"run_id":"<uuid>","status":"queued","status_url":"/api/v1/grievances/<uuid>","result_url":"/api/v1/grievances/<uuid>/result"}
```

Required fields: `complaint_text` (20–5000 characters), `entity_name` (1–200).
Optional fields:

| Field | Values / default |
|---|---|
| `complainant` | `{name, email, investor_category: retail or institutional}` |
| `investor_id`, `supporting_refs` | Optional legacy scaffold identifiers; references are never treated as regulatory evidence |
| `named_regulator` | `SEBI`, `RBI`, `unknown` (default) |
| `entity_type_claimed` | `bank`, `amc`, `broker`, `depository`, `rta`, `listed_company`, `unknown` (default); caller assertion only |
| `channel` | `web` (default), `api` |
| `incident_date` | ISO date, not in future |
| `amount_involved_inr` | Finite number, 0–1,000,000,000 |
| `approached_entity_first` | Boolean, default false |
| `entity_complaint_date` | Date bank/entity received written complaint |
| `entity_response` | `none` (default), `pending`, `rejected`, `unsatisfactory`, `resolved` |
| `entity_response_date` | Date of entity reply, if received |

Unknown fields are rejected. Complaint date cannot precede incident date; response
dates and all other submitted dates must fall between 1 January 1900 and today.
The lower bound is an application sanity check, not a regulatory time limit. Response
date requires a complaint date and cannot precede it. Prior-complaint details
require `approached_entity_first=true`. Missing prior dates are allowed but prevent
an eligibility assertion. Invalid requests return **422**, enter a bounded Redis
quarantine list (`grievance:quarantine`, latest 1,000), and do not enqueue jobs.
Queue outages return **503**. Quarantine is unavailable during a Redis outage;
validation still returns 422 and logs this failure.

The old `POST /api/v1/grievances/route` is a deprecated alias with the **new
asynchronous 202 contract**. Its previous synchronous fabricated-citation response
was removed; callers must now poll.

## Poll and retrieve

`GET /api/v1/grievances/{run_id}` returns `run_id`, `status`, `error`.
Typical states: `queued`, `started`, `finished`, `failed`; RQ may also expose
`stopped`, `canceled`, `scheduled`, `deferred`.

`GET /api/v1/grievances/{run_id}/result` returns **200** only on completion.
**409** means pending or failed; **404** means unknown/expired; **503** means
Redis unavailable. Failed results never return a recommendation.

The result includes domain, routing, target authority, immediate action, product,
entity type, reasoning, citations, next steps, eligibility, uncertainty,
verification summary, prompt version and a two-agent tool/handoff trace.
Every citation carries document ID/title, filename, PDF page, section, exact
whitespace-normalized extracted text, chunk ID and source SHA-256. Exact text and
all metadata are checked against the persisted index before release.

RBI `eligibility` is `bank_first`, `waiting_period`, `potentially_eligible`, or
`needs_review`. Even `potentially_eligible` requires a human to check all remaining
Scheme conditions and the bank's coverage. The 21-day AMC timeline is a complaint
redressal timeline, not a redemption payment deadline. Unknown or mixed cases
return `escalate_to_human`, `uncertain=true`, without invented citations.

## Storage and health

RQ payloads, results, and failures are retained for seven days by default,
configurable with `RESULT_TTL`. Redis AOF and Docker volumes persist across
`docker compose down`; `down -v` erases the demo data. AOF `everysec` can lose
roughly the last second of writes on a host crash. RQ failure registries retain
exceptions; public responses only show a safe error message and the run ID.

`GET /health` returns **200** when Redis responds, the index manifest is present,
and a worker heartbeat is recent. Otherwise it returns **503**. It is a readiness
check; it does not guarantee a subsequent job succeeds. No authentication or
production data privacy controls are included in Phase 0.

## Phase 2 reliability additions

Optional submission header `Idempotency-Key` (1-128 characters) identifies one
submission for the configured result retention window. Repeating the same key
and validated payload returns the original run_id with HTTP 202, including after
completion. A different payload with the same key returns 409. Keys and payload
hashes are stored in Redis atomically with enqueueing; raw keys are not metric
labels or log attributes. A new key is needed to request new work after an
escalation/failure. Worker execution locking and an immutable per-run stored
outcome prevent duplicate delivery from publishing a second outcome. This is
bounded idempotency, not a guarantee of globally exactly-once execution under
arbitrary Redis data loss or side effects.

`X-Correlation-ID` accepts a UUID; otherwise the server generates one. Responses
include it and `X-Trace-ID` when tracing is enabled. W3C traceparent propagates
through the Redis job metadata; arbitrary baggage/tracestate are discarded.

Results add `reliability_status` (`verified` or `degraded`) and nullable
`error_code` (`timeout`, `unavailable`, `circuit_open`, `invalid_response`, or
`internal_error`). Exhausted dependency attempts and circuit rejection complete
the job with `routing=escalate_to_human`, `uncertain=true`, degraded reliability,
and no regulatory citations. A verified reliability status means dependencies
completed; normal evidence-based uncertain routing remains possible. Unexpected
programming failures retain the failed-job contract. Redis unavailability at
submission or polling returns controlled 503 rather than a model result.

`GET /metrics` exposes stable API route/status/method aggregates. Worker aggregate
metrics are internal at `worker-metrics:9101/metrics`. Complaint fields, job IDs,
trace IDs and arbitrary URLs are never metric labels.

## Integrated audit, accounting, feedback and quality

All string leaves in the submission (including complainant fields, entity name,
identifiers and reference strings) undergo guardrail inspection before any model
call. Unsafe submissions return 400 and are quarantined. Generated user-facing
text is screened for unauthorized determinations and toxicity; verbatim reviewed
regulatory quotes remain unchanged. Evidence rejection permits one bounded
re-search before escalation. The workflow has at most five agent/finalization
node executions and at most 12 investigator tools per attempt, two attempts.

Results add nullable `cost_summary` and `quality_metrics`. Cost records count the
actual model request/validated response JSON characters divided by four, labelled
`character_estimate_not_billed_usage`; they are not provider tokenizer counts or
an API invoice. Each local stub record has `billed_cost_usd=0`. Attempt records,
including failed calls, persist in Redis under the run ID for RESULT_TTL.

`GET /api/v1/grievances/{run_id}/trace` returns durable internal audit events:
model task/version/hash, request/response, durations, trace IDs, tool queries and
passages, handoff and verification. This local synthetic-data audit can contain
the submitted text. It is separate from exported OTLP spans, which omit complaint
content and credentials. There is no production authentication; use synthetic
data only. Unknown runs return 404; unavailable Redis returns 503.

`POST /api/v1/feedback` accepts `{run_id, satisfactory, reason,
corrected_routing?}`. A completed durable outcome is required: unknown/expired
runs return 404, pending/failed runs without a completed outcome return 409.
Unsafe reasons return 400. Valid feedback returns 201. Caller satisfaction does
not change the independent automated quality score. `GET /api/v1/feedback/summary`
returns satisfaction counters and recent scores; no side effect contacts a regulator.

`GET /api/v1/quality/summary` returns the most recent 100 live-run quality samples
and their means. `method=mechanical_provenance_and_policy_proxy` checks exact
citation equality against retrieved evidence, required-clause coverage and
bank-first policy. It does not prove semantic entailment or correctness on
unknown products. Dependency failures use `unscored_dependency_failure` with
zero coverage/faithfulness. These live checks need no caller rating or golden
label. Up to 1,000 recent samples are retained; per-run records have RESULT_TTL.

`GET /api/v1/costs/summary` reports recent-run estimated cost per 100 runs, zero
stub billed cost, per-step totals and largest estimated driver. Models' estimates
and audit records are durably recorded in job processes; they survive process exit.

Submission rate limiting is a Redis-atomic fixed-minute counter per direct client
IP, configured by RATE_LIMIT_PER_MINUTE (default 60). Exceeding it returns 429.
Reverse-proxy client identity and production authentication are outside this demo.
The Redis retrieval cache uses corpus fingerprint, provider, scope and query keys;
new corpus versions cannot reuse old entries. Cache TTL defaults to one hour.
ENABLE_QUERY_CACHE=false disables it; idempotency remains a separate contract.
