# Mini Project 12 — Securities Investor Grievance Routing Service
**Course:** UE24AM342AA5 — ML System Design & AgentOps | **Component:** Jackfruit (Level 3)  
**Domain:** Capital Markets and Investor Protection | **Repository:** [harishreddy2005/securities-investor-grievance-routing](https://github.com/harishreddy2005/securities-investor-grievance-routing)

---

## 1. Executive Summary & Problem Scope
The Securities and Exchange Board of India (SEBI) receives retail complaints across brokers, mutual funds, RTAs, listed issuers, and depositories. Naive single-pass semantic search fails when investors use investment terminology about non-securities products (e.g., bank fixed deposits). Our production service uses a **two-agent LangGraph system with grounded two-pass RAG** that:
1. Enforces strict schema, range, categorical, cross-field, prompt-injection, and per-client rate-limiting guardrails at the ingestion boundary (`422`/`400`/`429`), quarantining rejected inputs.
2. Disentangles the underlying financial product from surface vocabulary and claimed regulator to establish jurisdictional competence.
3. Retrieves governing circulars across two passes and verifies every citation against persisted PDF SHA-256 checksums before emitting a routing decision.
4. Operates strictly as an advisory decision-support tool for human grievance officers (`escalate_to_human` on out-of-corpus, multi-regulator, or ambiguous complaints).

---

## 2. Multi-Agent Architecture & The Difficult Case (§4.1)

```
[ Investor / Web UI / REST API ]
             │  (Schema, Range, Rate-Limit & Injection Guardrails)
             ▼
      [ FastAPI Ingestion Boundary ] ──(Rejected)──► [ Quarantine Store ]
             │  (Accepted: 202 Accepted + Idempotent run_id)
             ▼
      [ Redis / RQ Job Queue + Distributed Circuit Breaker ]
             │
             ▼
   [ LangGraph 2-Agent Reasoning Worker (v2_modifier_aware) ]
   ┌─────────────────────────────────────────────────────────────┐
   │ Agent 1 (Investigator): Pass 1 Corpus Search ➔ Product vs   │
   │   Entity Hypothesis ➔ SEBI SCORES Para 5.3 Exclusion Lookup │
   │   ➔ Pass 2 Targeted Framework Search + Clause Lookups.      │
   │                           │ (Explicit Handoff)              │
   │                           ▼                                 │
   │ Agent 2 (Verifier): Audits required provision coverage &    │
   │   citation hashes against persisted PDF text. Enforces      │
   │   RBI 30-day rule & output authority boundary guardrails.   │
   └─────────────────────────────────────────────────────────────┘
             │
             ├──► Verified Result: Assign to Entity / Refer to Other Regulator
             └──► Unverified / Mixed / Out-of-Corpus: Escalate to Human Officer
```

### The Section 4.1 Difficult Case Resolution
> *"I invested in a fixed deposit through my bank's app. The interest credited is lower than what I was promised. I want to complain to SEBI."*

- **Why `v1_baseline` (Single-Pass RAG) Fails:** Pass 1 vector search on the raw complaint text retrieves 4 `SEBI-MF-1996` passages and only 1 `RBI-IOS-2021` passage because mutual fund schedules mention bank deposits. Combined with `named_regulator="SEBI"`, single-pass RAG fails to retrieve the required RBI Ombudsman provisions.
- **How `v2_modifier_aware` Resolves It:** The Investigator agent classifies the underlying product as a *Bank Fixed Deposit*, looks up **SEBI SCORES 2023 Para 5.3** (excluding matters under RBI's purview), switches frameworks to **RBI-IOS 2021**, and retrieves **Clauses 3(1)(j), 3(1)(f), 9, 10(1)(a), and 10(2)(a)**, routing to `refer_to_other_regulator` with mandatory **30-day bank-first** advice.

---

## 3. Verified Regulatory Corpus (SHA-256 Verified, 539 Indexed Chunks)
1. **SEBI SCORES Master Circular** (`SEBI/HO/OIAE/IGRD/CIR/P/2023/156`): Para 1.2 (21 calendar days resolution), Para 5.3 (statutory exclusions for RBI, IRDAI, PFRDA, CCI).
2. **SEBI (Mutual Funds) Regulations, 1996** (amended up to 01 Nov 2025): Reg 53 (redemption proceeds transfer), Reg 60A (21-day AMC grievance redressal).
3. **RBI Integrated Ombudsman Scheme, 2021** (amended up to 05 Aug 2022): Clause 3(1)(j) (Regulated Entity definition), Clause 9 (Grounds of Complaint), Clause 10(2)(a) (30-day prerequisite / 1-year filing limit).

---

## 4. LLMOps & AgentOps Evaluation: `v1_baseline` vs. `v2_modifier_aware` (`L2`, `L3`, `L5`, `D7`)

Evaluated across **22 domain scenarios** (`eval/scenarios.json`, executed via `python3 -m app.cli.evaluate`):

| Metric / Capability | `v1_baseline` (Before: Single-Pass) | `v2_modifier_aware` (After: 2-Pass Agent) | Measured Improvement / Notes |
|:---|:---:|:---:|:---|
| **Routing Accuracy** | **54.5%** (12 / 22) | **86.4%** (19 / 22) | **+31.8%** (solves §4.1 bank FD traps; 3 hard edge cases safely escalate) |
| **Groundedness** | **44.1%** | **73.7%** | **+29.6%** (sentence-level & citation support in retrieved corpus chunks) |
| **Context Relevance** | **38.5%** | **60.7%** | **+22.2%** (operative clause recall + signal-to-noise across Pass 1 & 2) |
| **Faithfulness** | **56.4%** | **80.0%** | **+23.6%** (entailment of authority, timeline & inferred product terms) |
| **Hallucination / Error Rate** | **48.7%** | **17.5%** | **-31.2%** (0 fabricated citations; remaining errors are conservative abstentions) |
| **Token & Cost Attribution (`L5`)** | 1,412 avg tokens/run | **4,012.4 avg tokens/run** | **\$0.1033 per 100 runs**; largest driver: `verifier:audit_handoff` (**60.5%**) |
| **Retrieval Cache Effect (`D7`)** | Uncached: 2,475.4 ms | **Warm Cache: 311.5 ms** | **-87.4% suite latency reduction** (**83.5%** cache hit rate) |
| **Automated Pytest Suite** | — | **64 / 64 Passed** | Unit, multi-agent, API, guardrails, rate-limit, feedback & reliability |

### Documented Edge-Case Limitations in `v2_modifier_aware` (3 / 22 Scenarios)
1. **Implicit Yield Phrasing (`SCENARIO-19`):** Bank FD maturity shortfall stated as *"at 7.25% p.a."* without the literal token `"interest"` conservatively escalates to a human officer.
2. **Auxiliary Bank Channel Mention (`SCENARIO-20`):** Mutual fund redemption delay mentioning *"my bank statement"* and *"bank branch confirmed no NEFT"* triggers the cross-regulator `mixed` split detector.
3. **Bancassurance Distribution Boundary (`SCENARIO-22`):** Dispute involving both a bank relationship manager mis-selling and an AMC lock-in redemption rejection is flagged as multi-regulator and escalated to human review.

---

## 5. Quickstart & Verification

```bash
# 1. Run automated test suite (64 tests) & Before/After evaluation CLI
python3 -m pytest -v
python3 -m app.cli.evaluate

# 2. Full Docker Stack (API, Worker, LLM-Stub, Redis, Prometheus, 26-panel Grafana, Jaeger)
cp .env.example .env && docker compose up --build -d
# Web UI: http://localhost:8000 | Swagger: http://localhost:8000/docs | Grafana: http://localhost:3000
```
