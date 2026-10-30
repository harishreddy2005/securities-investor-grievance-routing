# Corpus Sources

Official documents only, never paraphrased or synthesised. Files are verified by SHA-256.

## Active corpus (`corpus/raw/`, indexed)

| File | Document | Source URL | Retrieved | Pages | SHA-256 |
|---|---|---|---|---|---|
| `sebi_scores_circular_2023_156.pdf` | SEBI Circular SEBI/HO/OIAE/IGRD/CIR/P/2023/156 (20 Sep 2023): Redressal of investor grievances through SCORES and linking to ODR | https://www.sebi.gov.in/sebi_data/attachdocs/sep-2023/1695456916964.pdf | 2026-10-29 (agent script) | 15 | `26c230d804f1bbfd190e8187698276544a4a025b4a9f74a23e72b11a0abff40b` |
| `sebi_mutual_funds_regulations_1996.pdf` | SEBI (Mutual Funds) Regulations, 1996, last amended 01 Nov 2025 | Page: https://www.sebi.gov.in/legal/regulations/nov-2025/securities-and-exchange-board-of-india-mutual-funds-regulations-1996-last-amended-on-november-01-2025-_99120.html, PDF: https://www.sebi.gov.in/sebi_data/attachdocs/jan-2026/1768571780322.pdf | 2026-10-29 (agent script) | 162 | `79ca5ef10599fc83e7c77fc5ba5ef7be0e493628b03c1a05dab67127ea230043` |
| `RBIOS2021_amendments05082022.pdf` | RBI Integrated Ombudsman Scheme, 2021 (with amendments to 05 Aug 2022) | https://rbidocs.rbi.org.in/rdocs/content/pdfs/RBIOS2021_amendments05082022.pdf | 2026-10-29 (manual browser download by user; rbi.org.in blocks scripts) | 19 | `0d51cced7cce7481c45106cd8d2c260a34d4a65591e015262d1692d4a36d004b` |

## Archived (`corpus/archive/`, NOT indexed)

| File | Why archived |
|---|---|
| `sebi_mutual_funds_regulations_2026.pdf` | SEBI (MF) Regulations 2026 (amended to 10 Oct 2026), which supersede the 1996 regulations. The user chose the 1996 version (DECISIONS D-03). Swap it in if the instructor requires it. |

## Key verified provisions (page = PDF page)
- SCORES circular **para 1.2**: entities shall resolve a complaint within **21 calendar days** of receipt.
- SCORES circular **para 5 / 5.3**: complaints falling under other regulators (**RBI**, IRDAI, PFRDA, CCI) shall **not** be dealt with through SCORES. **This is central to §4.1.**
- MF Regs 1996 **Reg 53** (p79–80): dividend and redemption payment timelines (15 days from record date, 10 working days, or as the Board specifies in the amended text); interest payable for delay.
- MF Regs 1996 **Reg 60A** (p84): AMC shall redress investor grievances within **21 calendar days**.
- RBI-IOS **cl. 1(4)** (p1): the Scheme applies to services provided by a Regulated Entity under the RBI Act, the Banking Regulation Act, etc.
- RBI-IOS **cl. 3(1)(f)** (p2): "Complaint" means a representation alleging **deficiency in service** by a Regulated Entity.
- RBI-IOS **cl. 3(1)(j)** (p3): "Regulated Entity" means a **bank**, NBFC, System Participant or Credit Information Company.
- RBI-IOS **cl. 8(1)** (p5): the Ombudsman considers complaints of customers of Regulated Entities relating to deficiency in service.
- RBI-IOS **cl. 9** (p6): Grounds of Complaint, i.e. any customer aggrieved by an act or omission of a Regulated Entity resulting in deficiency in service.
- RBI-IOS **cl. 10(2)(a)** (p6–7): not maintainable unless the customer first complained in writing to the RE and it was rejected, the reply was unsatisfactory, or there was **no reply within 30 days**. Must be filed within **1 year** of the reply (1 year + 30 days if no reply).
- **Note:** the RBI scheme does NOT name "fixed deposit" or "interest". The §4.1 link is inferential: FD → bank product → bank = Regulated Entity (3(1)(j)) → interest shortfall = deficiency in service (3(1)(f), 9), combined with SCORES para 5.3 excluding RBI matters. The agent must establish the product and entity, which is exactly what the spec's §4.1 asks for.
