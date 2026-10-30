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
