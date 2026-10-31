import json
from typing import Dict, Any, Optional
from pydantic import BaseModel

# Standard public pricing benchmark (e.g. Gemini / lightweight embeddings & chat per 1M tokens)
# Free tiers are used, but L5 requires tracking cost attribution per step and per 100 runs.
COST_PER_MILLION_PROMPT = 0.15      # $0.15 per 1M prompt tokens
COST_PER_MILLION_COMPLETION = 0.60  # $0.60 per 1M completion tokens


class StepCostRecord(BaseModel):
    agent: str
    action: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class RunCostSummary(BaseModel):
    run_id: str
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: float
    steps: list[StepCostRecord]


class CostTracker:
    def __init__(self):
        self._records: Dict[str, list[StepCostRecord]] = {}

    def record_step(self, run_id: str, agent: str, action: str, prompt_text: str, completion_text: str):
        # Approximate tokens via ~4 chars per token if tokenizer not attached
        prompt_tokens = max(1, len(prompt_text) // 4)
        completion_tokens = max(1, len(completion_text) // 4)
        cost_usd = (prompt_tokens * COST_PER_MILLION_PROMPT / 1e6) + (completion_tokens * COST_PER_MILLION_COMPLETION / 1e6)
        
        record = StepCostRecord(
            agent=agent,
            action=action,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round(cost_usd, 6)
        )
        if run_id not in self._records:
            self._records[run_id] = []
        self._records[run_id].append(record)
        return record

    def get_run_summary(self, run_id: str) -> Optional[RunCostSummary]:
        steps = self._records.get(run_id, [])
        if not steps:
            return None
        p_toks = sum(s.prompt_tokens for s in steps)
        c_toks = sum(s.completion_tokens for s in steps)
        tot_cost = sum(s.cost_usd for s in steps)
        return RunCostSummary(
            run_id=run_id,
            total_prompt_tokens=p_toks,
            total_completion_tokens=c_toks,
            total_tokens=p_toks + c_toks,
            total_cost_usd=round(tot_cost, 6),
            steps=steps
        )

    def estimate_cost_per_100_runs(self, run_id: str) -> float:
        summary = self.get_run_summary(run_id)
        if not summary:
            return 0.0
        return round(summary.total_cost_usd * 100, 4)


global_cost_tracker = CostTracker()
