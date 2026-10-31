import json
from pathlib import Path
from app.config import get_settings
from app.rag.retriever import Retriever
from app.schemas import GrievanceSubmission
from app.agents.graph import route
from app.eval.evaluator import compute_scenario_metrics, aggregate_batch_metrics


def run_evaluation_suite(scenarios_path: Path, prompt_version: str = "v2") -> dict:
    scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))
    settings = get_settings()
    
    retriever = Retriever(settings)

    per_scenario_results = []
    
    for item in scenarios:
        sub = GrievanceSubmission.model_validate(item["input"])
        decision = route(sub, retriever, settings)
        
        metrics = compute_scenario_metrics(
            decision=decision.model_dump(mode="json"),
            expected=item,
            retrieved_citations=[c.model_dump(mode="json") for c in decision.regulatory_citations]
        )
        per_scenario_results.append({
            "id": item["id"],
            "description": item["description"],
            "expected_routing": item["expected_routing"],
            "actual_routing": decision.routing,
            "metrics": metrics
        })

    summary = aggregate_batch_metrics([r["metrics"] for r in per_scenario_results])
    return {
        "prompt_version": prompt_version,
        "summary": summary.model_dump(),
        "scenarios": per_scenario_results
    }


def main():
    path = Path("eval/scenarios.json")
    print(f"Running batch evaluation on 21 scenarios from {path}...")
    results = run_evaluation_suite(path)
    print("\n--- Evaluation Summary Results ---")
    print(f"Total Scenarios Evaluated: {results['summary']['total_evaluated']}")
    print(f"Routing Accuracy:          {results['summary']['correct_routing_accuracy'] * 100:.1f}%")
    print(f"Groundedness:              {results['summary']['groundedness'] * 100:.1f}%")
    print(f"Context Relevance:         {results['summary']['context_relevance'] * 100:.1f}%")
    print(f"Faithfulness:              {results['summary']['faithfulness'] * 100:.1f}%")
    print(f"Hallucination Rate:        {results['summary']['hallucination_rate'] * 100:.1f}%")
    
    out_file = Path("eval/eval_results_v2.json")
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved detailed evaluation metrics to {out_file}")


if __name__ == "__main__":
    main()
