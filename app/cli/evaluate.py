import json
import time
from pathlib import Path
from app.config import get_settings
from app.rag.retriever import Retriever
from app.schemas import GrievanceSubmission
from app.agents.graph import route_with_state
from app.eval.evaluator import compute_scenario_metrics, aggregate_batch_metrics
from app.eval.cost_tracker import global_cost_tracker
from app.eval.cache import global_query_cache


def run_evaluation_suite(scenarios_path: Path, prompt_version: str = "v2_modifier_aware") -> dict:
    scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))
    base_settings = get_settings()
    run_settings = base_settings.model_copy(update={"prompt_version": prompt_version, "llm_stub_url": ""})

    retriever = Retriever(run_settings)
    global_cost_tracker.reset()

    per_scenario_results = []
    started = time.perf_counter()

    for item in scenarios:
        sub = GrievanceSubmission.model_validate(item["input"])
        run_id = f"{prompt_version}-{item['id']}"
        decision, raw_evidence = route_with_state(sub, retriever, run_settings, run_id=run_id)

        metrics = compute_scenario_metrics(
            decision=decision.model_dump(mode="json"),
            expected=item,
            retrieved_citations=raw_evidence,
        )
        cost_summary = global_cost_tracker.get_run_summary(run_id)
        per_scenario_results.append({
            "id": item["id"],
            "description": item["description"],
            "expected_routing": item["expected_routing"],
            "actual_routing": decision.routing,
            "prompt_version": decision.prompt_version,
            "retrieved_chunk_count": len(raw_evidence),
            "verified_citation_count": len(decision.regulatory_citations),
            "metrics": metrics,
            "cost": cost_summary.model_dump() if cost_summary else None,
        })

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    summary = aggregate_batch_metrics([r["metrics"] for r in per_scenario_results])
    cost_report = global_cost_tracker.aggregate_report()
    return {
        "prompt_version": prompt_version,
        "elapsed_ms": elapsed_ms,
        "summary": summary.model_dump(),
        "cost_attribution": cost_report,
        "cache_stats": global_query_cache.stats(),
        "scenarios": per_scenario_results,
    }


def main():
    path = Path("eval/scenarios.json")
    scenarios_count = len(json.loads(path.read_text(encoding="utf-8")))
    print(f"Running L2/L3 Before-vs-After Evaluation on {scenarios_count} scenarios from {path}...\n")

    # 1. Run v1_baseline (Before deliberate change: single-pass surface RAG)
    global_query_cache.clear()
    res_v1 = run_evaluation_suite(path, prompt_version="v1_baseline")
    Path("eval/eval_results_v1.json").write_text(json.dumps(res_v1, indent=2), encoding="utf-8")

    # 2. Run v2_modifier_aware Cold Cache (After deliberate change: 2-pass modifier-aware agent)
    global_query_cache.clear()
    res_v2_cold = run_evaluation_suite(path, prompt_version="v2_modifier_aware")

    # 3. Run v2_modifier_aware Warm Cache (D7 cache latency & hit-rate measurement)
    res_v2_warm = run_evaluation_suite(path, prompt_version="v2_modifier_aware")
    Path("eval/eval_results_v2.json").write_text(json.dumps(res_v2_cold, indent=2), encoding="utf-8")

    s1 = res_v1["summary"]
    s2 = res_v2_cold["summary"]

    comparison = {
        "scenarios_evaluated": scenarios_count,
        "before_v1_baseline": s1,
        "after_v2_modifier_aware": s2,
        "deltas": {
            "correct_routing_accuracy": round(s2["correct_routing_accuracy"] - s1["correct_routing_accuracy"], 4),
            "groundedness": round(s2["groundedness"] - s1["groundedness"], 4),
            "context_relevance": round(s2["context_relevance"] - s1["context_relevance"], 4),
            "faithfulness": round(s2["faithfulness"] - s1["faithfulness"], 4),
            "hallucination_rate": round(s2["hallucination_rate"] - s1["hallucination_rate"], 4),
        },
        "cost_attribution_v2": res_v2_cold["cost_attribution"],
        "caching_effect_d7": {
            "cold_suite_latency_ms": res_v2_cold["elapsed_ms"],
            "warm_suite_latency_ms": res_v2_warm["elapsed_ms"],
            "latency_reduction_pct": round(
                (1.0 - res_v2_warm["elapsed_ms"] / max(0.01, res_v2_cold["elapsed_ms"])) * 100.0, 1
            ),
            "warm_cache_stats": res_v2_warm["cache_stats"],
        },
    }
    Path("eval/comparison_report.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")

    print("=== L2 & L3: Prompt & Pipeline Comparison (v1_baseline vs v2_modifier_aware) ===")
    print(f"{'Metric':<28} | {'v1_baseline (Before)':<22} | {'v2_modifier_aware (After)':<25} | {'Delta':<10}")
    print("-" * 94)
    for key, label in [
        ("correct_routing_accuracy", "Routing Accuracy"),
        ("groundedness", "Groundedness"),
        ("context_relevance", "Context Relevance"),
        ("faithfulness", "Faithfulness"),
        ("hallucination_rate", "Hallucination Rate"),
    ]:
        v1_val = s1[key] * 100
        v2_val = s2[key] * 100
        delta = (s2[key] - s1[key]) * 100
        sign = "+" if delta >= 0 else ""
        print(f"{label:<28} | {v1_val:>19.1f}%  | {v2_val:>22.1f}%  | {sign}{delta:.1f}%")

    print("\n=== L5: Token & Cost Attribution (v2_modifier_aware) ===")
    cost = res_v2_cold["cost_attribution"]
    print(f"Avg Prompt Tokens / Run:     {cost['avg_prompt_tokens']}")
    print(f"Avg Completion Tokens / Run: {cost['avg_completion_tokens']}")
    print(f"Estimated Cost / 100 Runs:   ${cost['cost_per_100_runs_usd']:.4f} USD")
    if cost.get("largest_cost_driver"):
        drv = cost["largest_cost_driver"]
        print(f"Largest Cost Driver:         {drv['step']} ({drv['share_of_total_cost_pct']}% of total cost)")

    print("\n=== D7: QueryCache Effect (Cold vs Warm Suite Execution) ===")
    d7 = comparison["caching_effect_d7"]
    print(f"Cold Cache Latency ({scenarios_count} runs): {d7['cold_suite_latency_ms']:.1f} ms")
    print(f"Warm Cache Latency ({scenarios_count} runs): {d7['warm_suite_latency_ms']:.1f} ms (-{d7['latency_reduction_pct']}%)")
    print(f"Cache Hit Rate (after warm): {d7['warm_cache_stats']['hit_rate'] * 100:.1f}%")


if __name__ == "__main__":
    main()
