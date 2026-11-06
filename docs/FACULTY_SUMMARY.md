# Mini Project 12 — Securities Investor Grievance Routing Service
**Course:** UE24AM342AA5 — ML System Design & AgentOps | **Component:** Jackfruit (Level 3)  
**Domain:** Capital Markets and Investor Protection | **Repository:** [harishreddy2005/securities-investor-grievance-routing](https://github.com/harishreddy2005/securities-investor-grievance-routing)

---

## 1. Executive Summary & Problem Scope
The Securities and Exchange Board of India (SEBI) receives retail complaints across brokers, mutual funds, RTAs, listed issuers, and depositories. Naive semantic search fails when investors use investment terminology about non-securities products (e.g. bank fixed deposits). Our production service uses a **two-agent LangGraph system with grounded RAG** that:
1. Enforces strict schema, range, categorical, cross-field, and prompt-injection validation at the ingestion boundary.
2. Disentangles the underlying financial product from surface vocabulary to establish jurisdictional competence.
3. Retrieves governing circulars and produces an evidence-grounded determination with circular-level citations.
4. Operates as an advisory decision support tool for human grievance officers (never disposes complaints autonomously).

---

## 2. Multi-Agent Architecture & The Difficult Case (§4.1)

```
[ Investor / Web UI / REST API ]
             │  (Schema, Range, PAN & Injection Guardrails)
             ▼
      [ FastAPI Ingestion Boundary ] ──(Rejected)──► [ Quarantine Store ]
             │  (Accepted: 202 Accepted + run_id)
             ▼
      [ Redis / RQ Job Queue ]
             │
             ▼
   [ LangGraph 2-Agent Reasoning Worker ]
   ┌─────────────────────────────────────────────────────────────┐
   │ Agent 1 (Investigator): Calls Tools (Corpus Search, Clause   │
   │   Lookup, Entity-Regulator Taxonomy). Uncovers modifiers    │
   │   (e.g., SEBI SCORES Para 5.3 RBI exclusion).               │
   │                           │ (Explicit Handoff)              │
   │                           ▼                                 │
   │ Agent 2 (Verifier): Audits citations against retrieved PDF  │
   │   text. Verifies maintainability conditions (RBI 30-day rule)│
   └─────────────────────────────────────────────────────────────┘
             │
             ├──► Verified Result: Assign to Entity / Refer to Other Regulator
             └──► Unverified / Mixed / Out-of-Corpus: Escalate to Human Officer
```

### The Section 4.1 Difficult Case Resolution
> *"I invested in a fixed deposit through my bank's app. The interest credited is lower than what I was promised. I want to complain to SEBI."*

- **The Trap:** Naive RAG embeds "invested", "interest", and "SEBI", erroneously routing to SEBI SCORES.
- **Agentic Resolution:** The Investigator agent identifies the financial product as a *Bank Fixed Deposit* (a commercial bank product). It retrieves **SEBI SCORES 2023 Para 5.3** (explicitly excluding complaints under the regulatory purview of RBI), switches frameworks, and retrieves **RBI-IOS 2021 Clause 3(1)(j), 3(1)(f), and Clause 9** (deficiency in banking service).
- **Outcome:** Routes to `refer_to_other_regulator` (**RBI Integrated Ombudsman Scheme**) with circular-level citations, advising the complainant of the mandatory **Clause 10(2)(a) 30-day prior written complaint** to the bank.

---

## 3. Verified Regulatory Corpus (SHA-256 Verified)
1. **SEBI SCORES Master Circular** (`SEBI/HO/OIAE/IGRD/CIR/P/2023/156`): Para 1.2 (21 calendar days resolution), Para 5.3 (statutory exclusions for RBI, IRDAI, PFRDA, CCI).
2. **SEBI (Mutual Funds) Regulations, 1996** (amended up to 01 Nov 2025): Reg 53 (redemption proceeds transfer), Reg 60A (21-day AMC grievance redressal).
3. **RBI Integrated Ombudsman Scheme, 2021** (amended up to 05 Aug 2022): Clause 3(1)(j) (Regulated Entity definition), Clause 9 (Grounds of Complaint), Clause 10(2)(a) (30-day prerequisite / 1-year filing limit).

---

## 4. Requirement Verification & Performance Metrics

| Evaluation Metric | Target / Spec | Measured Result | Verification Method |
|:---|:---:|:---:|:---|
| **Automated Test Suite** | 100% Pass | **59 / 59 Passed** | Pytest (`tests/`) across unit, agents, API & reliability |
| **Golden Evaluation Suite** | ≥ 20 scenarios | **21 / 21 Passed (100%)** | `app/cli/evaluate.py` on `eval/scenarios.json` |
| **Groundedness & Faithfulness** | High fidelity | **100.0%** | All citations resolve to verbatim extracted corpus clauses |
| **Hallucination Rate** | Zero tolerance | **0.0%** | Zero fabricated clauses or unverified regulatory citations |
| **Context Relevance** | Operative clauses | **100.0%** | Multi-pass agent captures modifier clauses missed by single-pass RAG |
| **Observability (D5, A6)** | End-to-end | **7/7 Targets UP** | Prometheus + 26-panel Grafana dashboard + Jaeger distributed tracing |
| **Reliability & Circuit Breaker (A5)** | Zero crashes | **Verified** | Redis distributed circuit breaker (`CLOSED` ➔ `OPEN` ➔ `HALF_OPEN`) |
| **Ingestion Quarantine (F2, D1)** | Field-level | **Verified** | Schema, range, PAN, and prompt injection attempts quarantined |

---

## 5. Quickstart & Verification in Docker

```bash
# 1. Clone repository
git clone https://github.com/harishreddy2005/securities-investor-grievance-routing.git
cd securities-investor-grievance-routing

# 2. Configure environment & start 7+ container services
cp .env.example .env
docker compose up --build -d

# 3. Access endpoints
Web UI & Grievance Portal:  http://localhost:8000
API Documentation (Swagger): http://localhost:8000/docs
Prometheus Metrics:          http://localhost:9090
Grafana Dashboards:          http://localhost:3000 (26 live panels)
Jaeger Tracing UI:           http://localhost:16686
```
