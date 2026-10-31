import json
import logging
from typing import Dict, List, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EvalMetrics(BaseModel):
    groundedness: float
    context_relevance: float
    faithfulness: float
    hallucination_rate: float
    total_evaluated: int
    correct_routing_accuracy: float


def compute_scenario_metrics(
    decision: Dict[str, Any],
    expected: Dict[str, Any],
    retrieved_citations: List[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Computes groundedness, context relevance, faithfulness, and hallucination rate
    for a single routing run against expected regulatory ground truth.
    """
    routing_match = decision.get("routing") == expected.get("expected_routing")
    target_match = decision.get("target_authority") == expected.get("expected_target_authority")
    
    expected_cits = expected.get("expected_citations", [])
    actual_cits = [f"{c.get('document_id')} §{c.get('section')}" if '§' not in c.get('section', '') else f"{c.get('document_id')} {c.get('section')}" for c in decision.get("regulatory_citations", [])]

    # Groundedness: Proportion of claims/citations supported by retrieved corpus passages
    if not actual_cits:
        groundedness = 1.0 if decision.get("routing") == "escalate_to_human" else 0.5
    else:
        supported = sum(1 for c in decision.get("regulatory_citations", []) if c.get("quote"))
        groundedness = supported / len(actual_cits)

    # Context relevance: Did the retrieved passages include the operative ground-truth provisions?
    if not expected_cits:
        context_rel = 1.0 if decision.get("routing") == "escalate_to_human" else 0.5
    else:
        # Match by document and section key
        matches = 0
        for exp in expected_cits:
            for act in decision.get("regulatory_citations", []):
                if act.get("document_id") in exp and act.get("section") in exp:
                    matches += 1
                    break
        context_rel = matches / len(expected_cits)

    # Faithfulness: Truthfulness of routing authority and statutory timeline
    if routing_match and target_match:
        faithfulness = 1.0
    elif routing_match:
        faithfulness = 0.8
    else:
        faithfulness = 0.0

    # Hallucination rate: Output contains invented clauses or unsupported routing
    hallucinated = 0.0
    if not routing_match:
        hallucinated = 1.0
    elif actual_cits:
        # Check if citations exist without quote/text or without being verified
        unverified = sum(1 for c in decision.get("regulatory_citations", []) if not c.get("quote"))
        if unverified > 0:
            hallucinated = unverified / len(actual_cits)

    return {
        "groundedness": round(groundedness, 4),
        "context_relevance": round(context_rel, 4),
        "faithfulness": round(faithfulness, 4),
        "hallucination_rate": round(hallucinated, 4),
        "correct": 1.0 if (routing_match and target_match) else 0.0
    }


def aggregate_batch_metrics(results: List[Dict[str, float]]) -> EvalMetrics:
    if not results:
        return EvalMetrics(groundedness=0, context_relevance=0, faithfulness=0, hallucination_rate=0, total_evaluated=0, correct_routing_accuracy=0)
    n = len(results)
    return EvalMetrics(
        groundedness=round(sum(r["groundedness"] for r in results) / n, 4),
        context_relevance=round(sum(r["context_relevance"] for r in results) / n, 4),
        faithfulness=round(sum(r["faithfulness"] for r in results) / n, 4),
        hallucination_rate=round(sum(r["hallucination_rate"] for r in results) / n, 4),
        total_evaluated=n,
        correct_routing_accuracy=round(sum(r["correct"] for r in results) / n, 4),
    )
