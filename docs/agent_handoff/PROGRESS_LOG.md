# Progress Log

Append-only. Newest entries at the bottom. Each entry: what was done, how it was verified, what's open, and what's next.
Timestamps are IST.

---

## 2026-10-29 08:28 — Session 1: repo inspection
- Repo: `harishreddy2005/securities-investor-grievance-routing`, branch `main`, 2 commits (`a40d464` initial, `9182acc` scaffold).
- Existing code at start: `app/main.py` (keyword if/else router, hardcoded confidence 0.85), `app/schemas.py` (basic Pydantic models), `Dockerfile`, `requirements.txt` (fastapi, uvicorn, pydantic), `README.md`. No RAG, agents, queue, observability or tests.
- The sibling folder `../MinIOT` is a separate, unrelated project. Don't touch it.

## 2026-10-29 08:31 — Plan v1 written (FLAWED; see the next entry)
- The user uploaded 3 PDFs (problem statement, glossary, index). **The model could not read them at the time**, but wrote a plan anyway with guessed requirement IDs and a guessed §4.1 quote, and presented it as complete. That was a mistake.

## 2026-10-29 08:35 — Spec extracted, plan revised to v2
- Extracted PDF text with PyMuPDF and saved it to `docs/agent_handoff/spec/`.
- Requirement IDs F1–F8, A1–A8, L1–L6, D1–D8, the §4.1 case and the 10 demo items happened to match the guesses. Corrections made:
  - Prioritisation is graded. **Zero marks if the system doesn't start and serve a valid request at the demo.** Phase 0 added.
  - L3 needs ≥20 scenarios (v1 said 22).
  - D5 needs per-container resource utilisation (add cAdvisor).
  - D4: no model identifiers in the repo, so put them in `.env`.
  - D3: nothing runs outside containers (CLIs via `docker compose run`).
  - Evaluation 1: corpus confirmation doc with the §4.1 passages and test values.
- The user approved plan v2.

## 2026-10-29 08:36–08:38 — Corpus acquisition (part 1)
- Downloaded the SEBI SCORES circular 2023/156 (15 pp, text layer OK).
- Downloaded SEBI MF Regulations **2026** (88 pp). The 1996 regulations have been superseded on SEBI's site.
- RBI download **failed**: rbi.org.in returns a bot-protection JS challenge (HTML, not PDF) to curl. Bad file deleted.
- Verified in the SCORES circular: **para 1.2** (21 calendar days) and **para 5.3** (excludes RBI/IRDAI/PFRDA/CCI matters). Plan v1's "Clause 10" was wrong.

## 2026-10-29 08:49 — User decisions
- **Use the MF Regulations 1996**, not 2026 (see DECISIONS D-03).
- The user manually downloaded the RBI PDF into `corpus/raw/`.
- The user asked for persistent logging of everything, hence this folder.

## 2026-10-29 08:50–08:52 — Corpus acquisition (part 2) and verification
- The RBI file `RBIOS2021_amendments05082022.pdf` is valid (19 pp, PDF 1.7).
- Found the 1996 MF regs page list via Wayback CDX. The latest 1996 consolidation, "last amended on November 01, 2025", is still live on sebi.gov.in. Downloaded 162 pp → `corpus/raw/sebi_mutual_funds_regulations_1996.pdf`.
- Moved the 2026 MF regs to `corpus/archive/` (not indexed).
- Verified key provisions and recorded them in `corpus/SOURCES.md` with page numbers and SHA-256 hashes:
  - MF Regs 1996: **Reg 53** (p79–80, dividend/redemption timelines and interest for delay), **Reg 60A** (p84, 21-day grievance redressal).
  - RBI-IOS: **cl. 1(4), 3(1)(f), 3(1)(j), 8(1), 9, 10(2)(a)**.
  - **Further corrections to plan v1:** Grounds of Complaint is **cl. 9** (v1 said cl. 8). RBI-IOS **does not mention "fixed deposit" or "interest"**, so the §4.1 link is inferential (bank = Regulated Entity; interest shortfall = deficiency in service). The MF figures "3 working days / 7 days / 15% p.a." from plan v1 are **not** in the 1996 regulations text (they come from SEBI circulars outside our corpus), so don't use them.

### State at end of this entry
- `corpus/raw/`: 3 verified PDFs. `corpus/archive/`: the 2026 MF regs.
- No application code written yet.

### NEXT STEPS (Phase 0)
1. Write `docs/CORPUS_CONFIRMATION.md` (Evaluation 1): the §4.1 dependency passages (SCORES 5.3, RBI-IOS 3(1)(j), 3(1)(f), 9, 10(2)(a)) with verbatim excerpts, plus the test request values and the reference answer.
2. `.env.example` and `app/config.py`.
3. Ingestion pipeline (`app/rag/ingest.py`): clause-aware chunking → MiniLM embeddings → Chroma. Idempotent, with a `--re-embed-only` flag.
4. Agents, tools, LangGraph; FastAPI + Redis queue; stub LLM; compose; minimal web UI.
5. Verify `docker compose up` → §4.1 routes to RBI with citations.

## 2026-10-29 08:53 — Phase 0 step 1 done: corpus confirmation
- Wrote `docs/CORPUS_CONFIRMATION.md`: verbatim passages P1–P6 (SCORES 5/5.3; RBI-IOS 3(1)(j), 3(1)(f), 9, 10(2)(a), 1(4)), §4.1 test payload, reference answer table, and 3 contrast cases.
- Verified the excerpts by extracting the text programmatically (PyMuPDF), not from memory.
- Noted subtlety: RBI-IOS 10(1)(a) "commercial judgment" exclusion vs deficiency in service. Raise at Evaluation 1.

## 2026-10-29 08:54 — BLOCKER: no Docker on this machine
- `docker` not found. No Docker Desktop, OrbStack, Colima or Podman in /Applications or on PATH.
- The spec (D3) requires everything under Docker Compose, and demo item 1 is `docker compose up` from a clean clone. Can't verify Phase 0 without it.
- Local Python is 3.13.0. Plan: container images use python:3.11-slim (better wheel support for chromadb / sentence-transformers / torch).
- **Asked the user to install Docker Desktop (or OrbStack).** Waiting.

## 2026-10-29 09:31 — Docker workaround discussed
- User: the team will use a teammate's machine for Docker. Proposed workflow: develop and unit-test locally in a Python venv (no Docker), push to GitHub, run `docker compose up` in GitHub Actions CI and/or Codespaces, and do the final demo on the teammate's machine. Awaiting user choice.

## 2026-10-30 10:42 — Team plan written
- Wrote `docs/TEAM_PLAN.md`, the shareable plan for the teammate. Workflow: code and unit tests on Harish's laptop (venv) → push → teammate runs `docker compose up` and the checklist → sends back output. Backups: GitHub Codespaces, plus a GitHub Actions compose smoke test.
- `gh` CLI is not installed locally; the agent can't push or check CI by itself unless git credentials are configured.
- The promised items `scripts/smoke_test.py`, the `ingest` compose service and the Actions workflow must be built in Phase 0.

## 2026-10-30 10:46 — Pushed to GitHub
- Commit `22c6c5e` pushed to `origin/main`: corpus PDFs, SOURCES.md, CORPUS_CONFIRMATION.md, TEAM_PLAN.md, agent_handoff/. Removed .DS_Store and added it to .gitignore.
- Git push works from this machine (account theDEMIGOD600).

## 2026-10-30 — Phase 0 implementation started
- Cloned the user's repository into the empty Windows workspace; inspected all tracked source, config, handoff/spec notes and active PDF text. No existing application implementation beyond the scaffold was discarded; unsupported keyword routing/citations were replaced.
- Docker CLI 29.8.2 exists but `docker info` cannot connect to the Windows docker_engine named pipe. Docker execution remains unverified.
- Added hash-checked allowlist ingestion of the 3 active PDFs, page chunks, exact reviewed clause anchors, persistent Chroma and LangChain local embedding adapter. Parsing produced 539 chunks. Archive excluded.
- New verified correction: MF page 79's Reg 53 payment periods are historical amendment-footnote text. Operative Reg 53 is on page 80 and delegates payment periods to the Board. Added an exact page-80 anchor and regression test.
- Added two-agent LangGraph investigator/verifier, bounded tools, structured handoff/output, citation auditing, honest escalation, bank-first and filing-limit advisory states; default deterministic HTTP model stub requires no API key.
- Added Redis/RQ queue and worker isolation, asynchronous API, validation/quarantine, UI, Docker Compose automatic ingestion, startup health checks, smoke script, Python and Compose CI jobs, data contract and runbook.
- Local dependency setup required an approved network-enabled pip install; early test attempts failed due to incomplete installation. After installation, `python -m pytest tests/test_corpus.py -q`: 4 passed; `python -m pytest tests/test_agents.py -q`: 17 passed. Chroma emitted one Python 3.14 deprecation warning. API/queue tests and final checks follow.
- No commit or push performed. Latest TEAM_PLAN uses Phase 0–4; later features remain out of this Phase 0 scope.

## 2026-10-30 — Phase 0 verification completed locally
- Final full suite: `.venv/Scripts/python -m pytest -q` passed 34 tests. Two upstream deprecation warnings remain on Python 3.14 (Starlette/AnyIO and Chroma asyncio introspection); no application test failed. API tests execute real RQ jobs against fakeredis and verify queued → started → finished/failed behavior, results, validation/quarantine, and Redis-outage handling.
- Real semantic ingestion completed: 539 chunks, 53.39 seconds including the first ~79 MB model download; corpus hashes recorded in the index manifest. First download attempt hit transient DNS failure; DNS resolved on checking and the retried download succeeded. A local CLI attempt after copying Docker .env used container corpus paths; overriding CORPUS_DIR with the workspace path corrected it. Local development commands must account for Docker-specific .env paths.
- Real semantic search and two-agent FD reference passed, with exact SCORES 5.3 and RBI-IOS 3(1)(j), 3(1)(f), 9, 10(2)(a), 10(1)(a) citations; bank_first result confirmed.
- `python scripts/local_e2e.py`: passed all 4 HTTP smoke scenarios with test embeddings, TCP fakeredis, actual HTTP stub, and RQ SimpleWorker.
- `python scripts/local_e2e.py --semantic`: passed all 4 HTTP smoke scenarios with real semantic embeddings, TCP fakeredis, actual HTTP stub, and RQ SimpleWorker. This verifies real HTTP submission/polling/results and UI serving, not production Redis or the Linux SpawnWorker. TCP fakeredis produced a transient connection-closed warning; RQ retried and completed all jobs. This simulator warning is not claimed as a Docker result.
- The first local harness attempt found duplicate worker registration and Windows file-lock cleanup errors. Fixed the harness to wait for worker readiness, retain its index under ignored data/, and close daemon server threads. Subsequent harness runs exited successfully.
- `docker compose config --quiet`: passed after creating the gitignored .env from .env.example. Docker client warns its host config is inaccessible, but configuration validation exits 0. `docker info` remains unable to connect to the daemon; container build/start/smoke NOT executed locally.
- `python -m pip check`: no broken requirements. Python compileall, Node JavaScript syntax check, and git diff --check passed (Git only notes expected Windows line-ending conversion).
- Fixed cache-volume ownership for the non-root image user; production workers use SpawnWorker and a 60-second worker TTL so idle heartbeats stay within the 120-second readiness window. Index clients explicitly disable anonymous telemetry.
- Added Python CI (including local HTTP smoke) and a separate real Docker Compose smoke with semantic embeddings. CI has NOT run: no commit/push was authorized or performed.
- Phase 0 code is ready for teammate Docker validation. Demo readiness remains conditional on the exact README startup/smoke checklist passing with the real Docker engine. Phases 1–4 are pending per the latest TEAM_PLAN.

## 2026-10-30 — Real Docker verification on the user's device: PASSED
- User requested running and testing on this device before sharing. Started the installed Docker Desktop via `docker desktop start` outside the restricted shell. Engine responded: Docker Desktop 4.95.0 / Docker Engine 29.8.2, Linux amd64. This resolves the earlier engine-unavailable blocker; earlier log entries describe the state at that time.
- `docker compose up --build -d --wait --wait-timeout 900`: exit 0. Downloaded images, built all four application images, automatically ingested 539 chunks with real semantic ONNX embeddings (~55.86 seconds for ingestion), and started Redis, HTTP model stub, Linux RQ SpawnWorker and API. All four long-running services healthy; ingest exited 0.
- `docker compose exec -T api python scripts/smoke_test.py`: exit 0, all 4 scenarios passed with real Redis and production worker: FD -> RBI/bank_first; MF -> AMC; insurance -> human; mixed bank/broker -> human. Invalid payload rejected with 422; UI served. FD reference run: f349bfec-35ce-4e3b-8dd5-6aa12aeff7c0.
- Host `http://localhost:8000/health` returned healthy with 539 chunks. Host UI returned HTTP 200 and included the FD example. Inspected actual FD result: RBI target, bank_first, first complain in writing to the bank.
- `docker compose run --rm --no-deps ingest`: exit 0, unchanged=true, 539 chunks.
- Restarted project Redis, worker and API using `docker compose restart redis worker api`, then waited for healthy services. The original FD result remained available and unchanged, verifying persistence across the restart.
- Repeated the full Docker smoke after restart: exit 0, all 4 scenarios passed again. In-container `python -m pip check`: no broken requirements.
- Application containers are LEFT RUNNING for the user at http://localhost:8000. No application-code fix was required during actual Docker verification. Updated README, TEAM_PLAN, Phase 0 status and incident history with the resolved blocker and real results. No commit or push performed.

## 2026-10-30 — Form and implausible-year regression fixed
- User reported raw JSON validation errors when prior complaint details were filled while approached_entity_first was false, plus acceptance of year 1202.
- Root cause: the UI left prior dates/response editable regardless of the checkbox, always submitted those fields, and rendered validation arrays as raw JSON. Backend checked only future/order constraints, with no historical sanity boundary.
- UI now disables and clears prior details when unchecked, only includes them when checked, validates dates and response order before submission, and displays readable field-level API errors. API rejects dates before 1900-01-01 and in the future with date-field error locations. The 1900 boundary is an application input policy, not a regulatory time limit.
- Added regression coverage for ancient incident/complaint/response dates, field-specific API rejection, and a repeatable real-browser script (optional requirements-browser.txt).
- Full Python suite: 38 passed, 2 upstream deprecation warnings. JavaScript syntax and git whitespace checks passed.
- Rebuilt and started Docker successfully; all four services healthy. Updated HTTP smoke against the real Docker app passed, including ancient-date rejection and all four routing scenarios.
- Installed optional Playwright into the workspace venv and ran `python scripts/browser_smoke.py --channel msedge` against the Docker app: passed all checks. Actual headless Edge confirmed disabled/reset fields, year 1202/future/reversed-date prevention with zero POSTs, a successful checkbox-off bank-first result, and friendly API error display. No changes to the user's installed browser.
- No commit or push performed. User should refresh the existing localhost page to load the corrected form.

## 2026-10-30 — Phase 0 local commit authorized
- User explicitly requested committing Phase 0. Reviewed all 45 changed/created files, checked whitespace, confirmed .env/data/.venv are ignored, and scanned changed source/docs for common credential patterns; none found.
- Commit includes the working Phase 0 implementation, Docker configuration, tests, browser/date fixes, regulatory extraction clarification and verified run documentation. Latest results: 38 Python tests passed, real Edge form regression passed, and real Docker build/start/smoke/restart-persistence checks passed.
- This authorization is for a local commit only. No GitHub push is included; Actions remains unexecuted until publication.

## 2026-10-30 — Phase 0 completion checkpoint
- User requested the exact completion commit message, an annotated phase-0-complete tag, a normal push to origin/main, and remote verification. Phase 1 must not begin.
- Initial working tree was clean. Fetched origin/main and confirmed no divergence (0 ahead / 0 behind); implementation commit 8669c30 was already published. No existing local or remote phase-0-complete tag found.
- Reviewed tracked project files and the implementation file list. No tracked local databases, vector indexes, environments or key files; common credential-pattern scan of tracked text found no matches. No unexpected changes or conflicts found.
- Hardened .gitignore for .env variants (retaining .env.example), local credentials/private keys, database files and sidecars, and generated index/model/runtime directories outside the existing ignored data/ tree. Updated current publication documentation.
- Completion commit contains only .gitignore and checkpoint documentation updates; the full 45-file working implementation is retained in its parent commit 8669c30. Existing verification remains 38 Python tests, actual Edge form checks, and real Docker smoke/restart-persistence checks passed. No application code changed for this checkpoint.
- Proceed with the user's requested exact-message commit, annotated tag and normal branch/tag pushes; report the resulting immutable commit and tag verification directly to the user. No Phase 1 work included.
