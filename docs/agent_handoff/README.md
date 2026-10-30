# Agent Handoff — READ THIS FIRST

This folder is the **source of truth for any AI model or human continuing this project** (for example after a context or usage-limit reset). Read these files in order before changing anything:

1. `spec/12_problem_statement.txt` — the assignment (Mini Project 12, PESU UE24AM342AA5). **Authoritative.** Extracted from the PDF the user uploaded.
2. `spec/00_glossary.txt`, `spec/index.txt` — supporting course documents.
3. `IMPLEMENTATION_PLAN.md` — the approved plan. The revision notes at the top override the body text wherever they conflict.
4. `DECISIONS.md` — decisions the user made. **Do not reverse them without asking.**
5. `PROGRESS_LOG.md` — chronological log of every step: what was done, what was verified, what is blocked, and what comes next.

## Rules for whoever continues
- Append to `PROGRESS_LOG.md` after every meaningful step. Never rewrite history; add corrections as new entries.
- Never invent regulation text, clause numbers or timelines. Cite only what is in `corpus/raw/` PDFs and record the page or paragraph.
- Never claim something works without running it. Log the command and its outcome.
- If the spec PDFs or corpus can't be read, say so to the user. Don't guess.
