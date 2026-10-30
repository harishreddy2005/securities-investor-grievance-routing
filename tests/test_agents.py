from datetime import date, timedelta

import pytest

from app.agents.graph import bank_eligibility, route
from app.schemas import GrievanceSubmission


def test_fixed_deposit_reference(reference, retriever, settings):
    result = route(GrievanceSubmission(**reference), retriever, settings)
    assert result.domain == "out_of_jurisdiction"
    assert result.routing == "refer_to_other_regulator"
    assert "Reserve Bank of India" in result.target_authority
    assert result.eligibility == "bank_first"
    assert "writing to the bank" in result.immediate_action
    assert result.timeline_days is None
    sections = {(c.document_id, c.section) for c in result.regulatory_citations}
    assert {("SEBI-SCORES-2023", "5.3"), ("RBI-IOS-2021", "3(1)(j)"), ("RBI-IOS-2021", "9"), ("RBI-IOS-2021", "10(2)(a)")} <= sections
    assert all(retriever.verify(c) for c in result.regulatory_citations)
    assert {e.agent for e in result.agent_trace} == {"investigator", "verifier"}
    assert sum(e.action == "search_regulatory_corpus" for e in result.agent_trace) == 2


@pytest.mark.parametrize("text", [
    "My health insurance claim was rejected and I need to complain.",
    "My bank failed a UPI payment to my broker, and the broker also executed a trade I didn't authorise.",
    "I want a higher fixed deposit interest rate from my bank because their new rate is lower.",
    "My cryptocurrency exchange lost my tokens and won't refund me.",
    "The bank sold me a mutual fund with lower returns than promised.",
])
def test_uncertain_cases_escalate(text, retriever, settings):
    result = route(GrievanceSubmission(complaint_text=text, entity_name="Example"), retriever, settings)
    assert result.uncertain
    assert result.routing == "escalate_to_human"
    assert not result.regulatory_citations


def test_mutual_fund(retriever, settings):
    result = route(GrievanceSubmission(complaint_text="My mutual fund redemption proceeds haven't been paid for 3 weeks", entity_name="Example AMC"), retriever, settings)
    assert result.routing == "assign_to_entity"
    assert result.timeline_days == 21
    assert next(c for c in result.regulatory_citations if c.section == "53").page == 80


def test_missing_evidence_escalates(reference, retriever, settings, monkeypatch):
    monkeypatch.setattr(retriever, "lookup", lambda *args: [])
    original_search = retriever.search
    monkeypatch.setattr(retriever, "search", lambda *a, **k: [c for c in original_search(*a, **k) if c.section != "3(1)(j)"])
    result = route(GrievanceSubmission(**reference), retriever, settings)
    assert result.routing == "escalate_to_human"
    assert not result.regulatory_citations


def test_forged_evidence_escalates(reference, retriever, settings, monkeypatch):
    monkeypatch.setattr(retriever, "verify", lambda c: False)
    assert route(GrievanceSubmission(**reference), retriever, settings).uncertain


@pytest.mark.parametrize("days,response,response_days,expected", [
    (10, "pending", None, "waiting_period"), (30, "none", None, "potentially_eligible"),
    (31, "none", None, "potentially_eligible"), (500, "none", None, "needs_review"),
    (10, "rejected", 2, "potentially_eligible"), (500, "unsatisfactory", 400, "needs_review"),
    (10, "rejected", None, "needs_review"), (10, "resolved", 2, "needs_review"),
])
def test_bank_first_conditions(reference, days, response, response_days, expected):
    reference.update(approached_entity_first=True, entity_complaint_date=date.today()-timedelta(days=days), entity_response=response)
    if response_days is not None:
        reference["entity_response_date"] = date.today()-timedelta(days=response_days)
    assert bank_eligibility(GrievanceSubmission(**reference))[0] == expected
