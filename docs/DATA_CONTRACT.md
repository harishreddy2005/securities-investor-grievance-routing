# Phase 0 data contract

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
