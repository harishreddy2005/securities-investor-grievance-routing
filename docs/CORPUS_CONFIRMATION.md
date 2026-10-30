# Corpus Confirmation & §4.1 Reference Answer (Evaluation 1 deliverable)

Spec §4.1: *"At Evaluation 1, show the passages in your corpus that this case depends on, and the values you will test with. Once confirmed, this is the reference answer for your demonstration."*

All excerpts are **verbatim** (footnote markers dropped, whitespace normalised) from the PDFs in `corpus/raw/` (see `corpus/SOURCES.md` for URLs and SHA-256). Page numbers are PDF pages.

## 1. Corpus

| Short ID | Document | Pages |
|---|---|---|
| `SEBI-SCORES-2023` | SEBI Circular SEBI/HO/OIAE/IGRD/CIR/P/2023/156, 20 Sep 2023 — Redressal of investor grievances through SCORES | 15 |
| `SEBI-MF-1996` | SEBI (Mutual Funds) Regulations, 1996 (last amended 01 Nov 2025) | 162 |
| `RBI-IOS-2021` | Reserve Bank – Integrated Ombudsman Scheme, 2021 (amendments to 05 Aug 2022) | 19 |

## 2. The §4.1 case

> "I invested in a fixed deposit through my bank's app. The interest credited is lower than what I was promised. I want to complain to SEBI."

### Why naive retrieval fails
"invested", "interest" and "complain to SEBI" pull the embedding toward the SEBI SCORES framework. No RBI passage contains "fixed deposit" or "interest", so the RBI provisions that decide the case **never appear in the query's nearest neighbours**. This is the "investment vocabulary pointing to the wrong regulator" obstacle (index, project 12).

### Passages the case depends on

**P1 — `SEBI-SCORES-2023` para 5 / 5.3 (p8–9): the modifier that removes SEBI's jurisdiction**
> "5. The following types of complaints shall not be dealt through SCORES: … 5.3. Complaints falling under the purview of other regulatory bodies such as Reserve Bank of India, (RBI), Insurance Regulatory and Development Authority of India (IRDAI), Pension Fund Regulatory and Development Authority of India (PFRDAI), Competition Commission of India (CCI), or complaints falling under the purview of other ministries."

**P2 — `RBI-IOS-2021` cl. 3(1)(j) (p3): a bank is a Regulated Entity**
> "(j) "Regulated Entity" means a bank or a Non-Banking Financial Company, or a System Participant or a Credit Information Company as defined in the Scheme, or any other entity as may be specified by the Reserve Bank from time to time; …"

**P3 — `RBI-IOS-2021` cl. 3(1)(f) (p2): what counts as a complaint**
> "(f) "Complaint" means a representation in writing or through other modes alleging deficiency in service on the part of a Regulated Entity, and seeking relief under the Scheme;"

**P4 — `RBI-IOS-2021` cl. 9 (p6): grounds of complaint**
> "9. Grounds of Complaint — Any customer aggrieved by an act or omission of a Regulated Entity resulting in deficiency in service may file a complaint under the Scheme personally or through an authorised representative as defined under clause 3(1)(c)."

**P5 — `RBI-IOS-2021` cl. 10(2)(a) (p6–7): maintainability precondition (sets the routing basis)**
> "(2) A complaint under the Scheme shall not lie unless: (a) the complainant had, before making a complaint under the Scheme, made a written complaint to the Regulated Entity concerned and - (i) the complaint was rejected wholly or partly by the Regulated Entity, and the complainant is not satisfied with the reply; or the complainant had not received any reply within 30 days after the Regulated Entity received the complaint; and (ii) the complaint is made to the Ombudsman within one year after the complainant has received the reply from the Regulated Entity to the complaint or, where no reply is received, within one year and 30 days from the date of the complaint."

**P6 — `RBI-IOS-2021` cl. 1(4) (p1): the scheme's scope (supporting)**
> "(4) The Scheme shall apply to the services provided by a Regulated Entity in India to its customers under the provisions of the Reserve Bank of India Act, 1934, the Banking Regulation Act, 1949, …"

> [!NOTE]
> **Subtlety (to raise at Evaluation 1):** RBI-IOS cl. 10(1)(a) excludes "commercial judgment/decision of a Regulated Entity". Setting an FD rate is a commercial decision, but **crediting less than the promised rate** is a deficiency in service (P3, P4). The reference answer rests on the second reading. The system should cite 10(1)(a) as considered if it retrieves it.

## 3. Test values (request payload)

```json
{
  "complainant": {"name": "Test Investor", "email": "test.investor@example.com", "investor_category": "retail"},
  "complaint_text": "I invested in a fixed deposit through my bank's app. The interest credited is lower than what I was promised. I want to complain to SEBI.",
  "named_regulator": "SEBI",
  "entity_name": "Example Bank Ltd",
  "entity_type_claimed": "unknown",
  "channel": "web",
  "incident_date": "2026-09-15",
  "approached_entity_first": false,
  "amount_involved_inr": 4500
}
```
(Field names are provisional until `docs/DATA_CONTRACT.md` is published. Synthetic data only, per spec §13.)

## 4. Reference answer

| Field | Expected |
|---|---|
| Domain (F3) | `out_of_jurisdiction` |
| Product / entity established | Bank fixed deposit / bank (Regulated Entity under RBI-IOS 3(1)(j)) |
| Routing (F6) | `refer_to_other_regulator` → **Reserve Bank of India — Integrated Ombudsman Scheme, 2021** |
| Basis | SCORES para 5.3 excludes RBI-purview matters; the bank is an RE (3(1)(j)); an interest shortfall against the promised rate is a deficiency in service (3(1)(f), cl. 9) |
| Required citations (must resolve to retrieved text) | `SEBI-SCORES-2023 §5.3`, `RBI-IOS-2021 cl.3(1)(j)`, `RBI-IOS-2021 cl.9` (also acceptable: 3(1)(f), 1(4)) |
| Advisory note | Under cl. 10(2)(a), the complainant must first complain in writing to the bank and wait 30 days (or get a rejection) before approaching the Ombudsman. `approached_entity_first=false`, so the system must state this |
| Must NOT | Assign to a SEBI entity; quote a 21-day SCORES timeline as applicable; invent an RBI clause naming "fixed deposit" |

## 5. Contrast cases (sanity checks for the same corpus)
- *"My mutual fund redemption proceeds haven't been paid for 3 weeks"* → `assign_to_entity` (AMC). Basis: `SEBI-MF-1996 Reg 53`, `Reg 60A` (21 calendar days); SCORES para 1.2.
- *"My bank failed a UPI payment to my broker, and the broker also executed a trade I didn't authorise"* → **escalate** (splits across RBI and SEBI; F7).
- *"My health insurance claim was rejected"* → **escalate** (IRDAI is out of corpus. SCORES 5.3 names IRDAI, but no IRDAI document is in the corpus to route against; F7).

## Phase 0 implementation clarification (2026-10-30)

Fresh extraction distinguishes operative MF Regulation 53 on PDF page 80 from
historical wording reproduced in an amendment footnote on page 79. The operative
text delegates payment periods and delayed-payment interest rates to the Board.
The mutual fund contrast test therefore checks the AMC route and the Regulation
60A 21-calendar-day **grievance** timeline, without asserting historical payment
deadlines. The RBI FD reference answer and bank-first requirement remain as above.
