import pytest
from app.eval.evaluator import compute_scenario_metrics, aggregate_batch_metrics
from app.eval.cost_tracker import CostTracker
from app.eval.cache import QueryCache


def test_evaluator_metrics():
    expected = {
        "expected_routing": "refer_to_other_regulator",
        "expected_target_authority": "Reserve Bank of India — Integrated Ombudsman Scheme, 2021",
        "expected_citations": ["SEBI-SCORES-2023 §5.3", "RBI-IOS-2021 cl.3(1)(j)"]
    }
    decision = {
        "routing": "refer_to_other_regulator",
        "target_authority": "Reserve Bank of India — Integrated Ombudsman Scheme, 2021",
        "regulatory_citations": [
            {"document_id": "SEBI-SCORES-2023", "section": "5.3", "quote": "Purview of RBI excluded"},
            {"document_id": "RBI-IOS-2021", "section": "3(1)(j)", "quote": "Regulated Entity bank"}
        ]
    }
    metrics = compute_scenario_metrics(decision, expected, decision["regulatory_citations"])
    assert metrics["groundedness"] == 1.0
    assert metrics["context_relevance"] == 1.0
    assert metrics["faithfulness"] == 1.0
    assert metrics["hallucination_rate"] == 0.0
    assert metrics["correct"] == 1.0


def test_cost_tracker():
    tracker = CostTracker()
    run_id = "test-run-123"
    rec1 = tracker.record_step(run_id, "investigator", "product_hypothesis", "I invested in fixed deposit", "bank_fd")
    rec2 = tracker.record_step(run_id, "verifier", "verify_citations", "Verify citations", "supported: true")
    
    assert rec1.prompt_tokens > 0
    assert rec1.cost_usd > 0
    summary = tracker.get_run_summary(run_id)
    assert summary is not None
    assert summary.total_tokens == rec1.prompt_tokens + rec1.completion_tokens + rec2.prompt_tokens + rec2.completion_tokens
    cost_100 = tracker.estimate_cost_per_100_runs(run_id)
    assert cost_100 > 0


def test_query_cache():
    cache = QueryCache(default_ttl_seconds=10)
    assert cache.get("test", "key1") is None
    cache.set("test", "key1", {"result": "cached_val"})
    assert cache.get("test", "key1") == {"result": "cached_val"}
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.5
