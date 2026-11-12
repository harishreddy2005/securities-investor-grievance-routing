import pytest
from app.eval.evaluator import compute_scenario_metrics, aggregate_batch_metrics
from app.eval.cost_tracker import CostTracker, global_cost_tracker
from app.eval.cache import QueryCache, global_query_cache
from app.prompts.loader import load_prompt
from app.agents.graph import route_with_state
from app.schemas import GrievanceSubmission


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


def test_prompt_loader_versions():
    p1 = load_prompt("v1_baseline")
    p2 = load_prompt("v2_modifier_aware")
    assert p1.version == "v1"
    assert p2.version == "v2"
    assert p1.sha256 != p2.sha256
    assert "Para 5.3" in p2.system_prompt


def test_v1_vs_v2_pipeline_and_cost_attribution(reference, retriever, settings):
    global_cost_tracker.reset()
    sub = GrievanceSubmission(**reference)

    # v1_baseline fails on the Section 4.1 cross-regulator trap
    s_v1 = settings.model_copy(update={"prompt_version": "v1_baseline"})
    dec_v1, ev_v1 = route_with_state(sub, retriever, s_v1, run_id="run-v1")
    assert dec_v1.routing == "escalate_to_human"
    assert dec_v1.prompt_version == "baseline_single_pass:v1"

    # v2_modifier_aware resolves the Section 4.1 trap via Para 5.3 modifier lookup
    s_v2 = settings.model_copy(update={"prompt_version": "v2_modifier_aware"})
    dec_v2, ev_v2 = route_with_state(sub, retriever, s_v2, run_id="run-v2")
    assert dec_v2.routing == "refer_to_other_regulator"
    assert dec_v2.prompt_version == "modifier_aware_multipass:v2"
    assert len(ev_v2) > len(ev_v1)

    report = global_cost_tracker.aggregate_report()
    assert report["total_runs"] == 2
    assert report["cost_per_100_runs_usd"] > 0
    assert report["largest_cost_driver"]["step"] in ("verifier:audit_handoff", "investigator:product_entity_hypothesis")


def test_retriever_uses_query_cache(retriever):
    global_query_cache.clear()
    hits1 = retriever. lookup("SEBI-SCORES-2023", "5.3")
    stats1 = global_query_cache.stats()
    assert stats1["misses"] == 1 and stats1["hits"] == 0

    hits2 = retriever.lookup("SEBI-SCORES-2023", "5.3")
    stats2 = global_query_cache.stats()
    assert stats2["hits"] == 1
    assert hits1 == hits2


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
