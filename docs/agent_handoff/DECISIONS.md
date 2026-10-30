# Decisions Log

| # | Date (IST) | Decision | Made by | Notes |
|---|---|---|---|---|
| D-01 | 2026-10-29 | Implementation plan (revision 2) approved | User | See `IMPLEMENTATION_PLAN.md` |
| D-02 | 2026-10-29 | LLM: default `LLM_PROVIDER=stub`; Gemini/Groq/Ollama supported via `.env` | Agent default (user didn't answer the question) | Revisit if the user specifies a provider |
| D-03 | 2026-10-29 | **Use the SEBI (Mutual Funds) Regulations, 1996**, not the 2026 regulations | User | "lets not risk things with newer regulations. if he needs with 2026 we'll update it later". The 2026 PDF is kept out of the active index (see PROGRESS_LOG) |
| D-04 | 2026-10-29 | Build order: Phase 0 minimal end-to-end path first (zero-marks guard, spec §10) | Plan rev 2 | |
| D-05 | 2026-10-29 | Log every step persistently in `docs/agent_handoff/` | User | For other models / after limit resets |
