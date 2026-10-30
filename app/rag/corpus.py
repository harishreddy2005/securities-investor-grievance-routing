"""Allowlisted documents and reviewed section locations, never an archive glob."""
DOCUMENTS = {
    "sebi_scores_circular_2023_156.pdf": ("SEBI-SCORES-2023", "SEBI SCORES Circular 2023/156", "26c230d804f1bbfd190e8187698276544a4a025b4a9f74a23e72b11a0abff40b"),
    "sebi_mutual_funds_regulations_1996.pdf": ("SEBI-MF-1996", "SEBI (Mutual Funds) Regulations, 1996 (amended 01 Nov 2025)", "79ca5ef10599fc83e7c77fc5ba5ef7be0e493628b03c1a05dab67127ea230043"),
    "RBIOS2021_amendments05082022.pdf": ("RBI-IOS-2021", "RBI Integrated Ombudsman Scheme, 2021 (amended 05 Aug 2022)", "0d51cced7cce7481c45106cd8d2c260a34d4a65591e015262d1692d4a36d004b"),
}

# Patterns select extracted PDF text; missing reviewed anchors stop ingestion.
SECTIONS = [
    ("SEBI-SCORES-2023", "5.3", 8, 9, r"5\.3\.", r"5\.4\."),
    ("SEBI-SCORES-2023", "1.2", 3, 4, r"1\.2\.", r"1\.3\."),
    ("RBI-IOS-2021", "3(1)(f)", 2, 2, r'\(f\)\s*.?Complaint', r"\(ff\)"),
    ("RBI-IOS-2021", "3(1)(j)", 3, 3, r'\(j\)\s*.?Regulated Entity', r"\(k\)"),
    ("RBI-IOS-2021", "9", 6, 6, r"9\.\s*Grounds of Complaint", r"10\."),
    ("RBI-IOS-2021", "10(1)(a)", 6, 6, r"\(a\)\s*commercial judgment", r"\(b\)"),
    ("RBI-IOS-2021", "10(2)(a)", 6, 7, r"\(2\)\s*A complaint under the Scheme shall not lie unless", r"\(b\)\s*the complaint is not"),
    ("SEBI-MF-1996", "53", 80, 80, r"53\.\s*", r"Annual Report"),
    ("SEBI-MF-1996", "60A", 84, 84, r"60A\.\s*", r"311 Inserted"),
]
