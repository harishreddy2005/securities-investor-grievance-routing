from typing import Dict, Any, Optional
from pydantic import BaseModel

# Standard public pricing benchmark (e.g. Gemini 2.5 Flash / lightweight chat per 1M tokens)
# Free/local tiers are used at runtime, and L5 requires tracking token & cost attribution per step and per 100 runs.
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

    def reset(self):
        self._records.clear()

    def record_step(self, run_id: str, agent: str, action: str, prompt_text: str, completion_text: str) -> StepCostRecord:
        # Approximate BPE token count (~4 chars per token)
        prompt_tokens = max(1, len(prompt_text) // 4)
        completion_tokens = max(1, len(completion_text) // 4)
        cost_usd = (prompt_tokens * COST_PER_MILLION_PROMPT / 1e6) + (completion_tokens * COST_PER_MILLION_COMPLETION / 1e6)

        record = StepCostRecord(
            agent=agent,
            action=action,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round(cost_usd, 8),
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
            steps=steps,
        )

    def estimate_cost_per_100_runs(self, run_id: str) -> float:
        summary = self.get_run_summary(run_id)
        if not summary:
            return 0.0
        return round(summary.total_cost_usd * 100, 4)

    def aggregate_report(self) -> Dict[str, Any]:
        if not self._records:
            return {
                "total_runs": 0,
                "avg_prompt_tokens": 0,
                "avg_completion_tokens": 0,
                "avg_total_tokens": 0,
                "cost_per_100_runs_usd": 0.0,
                "largest_cost_driver": None,
                "step_breakdown": {},
            }
        num_runs = len(self._records)
        total_prompt = 0
        total_completion = 0
        total_cost = 0.0
        by_step: Dict[str, Dict[str, float]] = {}

        for steps in self._records.values():
            for s in steps:
                total_prompt += s.prompt_tokens
                total_completion += s.completion_tokens
                total_cost += s.cost_usd
                key = f"{s.agent}:{s.action}"
                if key not in by_step:
                    by_step[key] = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "calls": 0}
                by_step[key]["prompt_tokens"] += s.prompt_tokens
                by_step[key]["completion_tokens"] += s.completion_tokens
                by_step[key]["cost_usd"] += s.cost_usd
                by_step[key]["calls"] += 1

        largest_key = max(by_step.keys(), key=lambda k: by_step[k]["cost_usd"]) if by_step else None
        largest_share = (by_step[largest_key]["cost_usd"] / total_cost * 100.0) if (largest_key and total_cost > 0) else 0.0

        return {
            "total_runs": num_runs,
            "avg_prompt_tokens": round(total_prompt / num_runs, 1),
            "avg_completion_tokens": round(total_completion / num_runs, 1),
            "avg_total_tokens": round((total_prompt + total_completion) / num_runs, 1),
            "cost_per_100_runs_usd": round((total_cost / num_runs) * 100, 4),
            "largest_cost_driver": {
                "step": largest_key,
                "share_of_total_cost_pct": round(largest_share, 1),
                "avg_prompt_tokens": round(by_step[largest_key]["prompt_tokens"] / num_runs, 1) if largest_key else 0,
                "avg_completion_tokens": round(by_step[largest_key]["completion_tokens"] / num_runs, 1) if largest_key else 0,
            } if largest_key else None,
            "step_breakdown": {
                k: {
                    "avg_prompt_tokens": round(v["prompt_tokens"] / num_runs, 1),
                    "avg_completion_tokens": round(v["completion_tokens"] / num_runs, 1),
                    "cost_per_100_runs_usd": round((v["cost_usd"] / num_runs) * 100, 4),
                }
                for k, v in by_step.items()
            },
        }


global_cost_tracker = CostTracker()
