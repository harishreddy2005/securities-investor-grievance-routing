import json
from datetime import date
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.agents.tools import make_tools
from app.eval.cost_tracker import global_cost_tracker
from app.guardrails.safety import inspect_input_text, inspect_output_decision
from app.llm import Hypothesis, Model
from app.observability.runtime import instrument_agent, run_id as runtime_run_id
from app.prompts.loader import load_prompt
from app.schemas import Citation, GrievanceSubmission, RoutingDecision

REQUIRED = {
    "bank_fd": [("SEBI-SCORES-2023", "5.3"), ("RBI-IOS-2021", "3(1)(j)"),
                ("RBI-IOS-2021", "3(1)(f)"), ("RBI-IOS-2021", "9"),
                ("RBI-IOS-2021", "10(2)(a)"), ("RBI-IOS-2021", "10(1)(a)")],
    "mutual_fund": [("SEBI-MF-1996", "53"), ("SEBI-MF-1996", "60A"), ("SEBI-SCORES-2023", "1.2")],
}


class AgentState(TypedDict, total=False):
    request: dict
    hypothesis: dict
    evidence: list[dict]
    trace: list[dict]
    result: dict
    run_id: str
    guardrail_error: str


def escalate(reason, trace, product="not established", entity_type="not established", prompt_version="phase0-v1"):
    return RoutingDecision(domain="unclassified", routing="escalate_to_human",
        target_authority="Human grievance officer", immediate_action="Request human review",
        product=product, entity_type=entity_type, rationale=reason, uncertain=True,
        next_steps=["Ask a grievance officer to establish the product, responsible entity and applicable framework."],
        verification="No unsupported routing recommendation issued.", prompt_version=prompt_version, agent_trace=trace)


def bank_eligibility(request: GrievanceSubmission):
    if not request.approached_entity_first:
        return "bank_first", "First complain in writing to the bank. Keep the complaint receipt and promised-rate evidence."
    if request.entity_response == "resolved":
        return "needs_review", "The bank reports resolution. Ask a grievance officer to clarify any outstanding deficiency."
    if not request.entity_complaint_date:
        return "needs_review", "Confirm the date the bank received your written complaint and obtain its response."
    elapsed = (date.today() - request.entity_complaint_date).days
    if request.entity_response in ("rejected", "unsatisfactory"):
        if not request.entity_response_date:
            return "needs_review", "Provide the bank response date to check the one-year filing limit."
        # Calendar anniversaries, including leap-day responses.
        response = request.entity_response_date
        try:
            deadline = response.replace(year=response.year+1)
        except ValueError:
            deadline = response.replace(year=response.year+1, day=28)
        if date.today() > deadline:
            return "needs_review", "The usual one-year limit from the reply may have expired; obtain human review of admissibility."
        return "potentially_eligible", "An unsatisfactory or rejected bank reply may allow approaching the RBI Ombudsman, subject to all other Scheme conditions."
    if elapsed < 30:
        return "waiting_period", f"Wait until 30 days after the bank received the written complaint ({30-elapsed} days remain), unless a rejection or unsatisfactory reply arrives earlier."
    complaint = request.entity_complaint_date
    try:
        anniversary = complaint.replace(year=complaint.year+1)
    except ValueError:
        anniversary = complaint.replace(year=complaint.year+1, day=28)
    from datetime import timedelta
    if date.today() > anniversary + timedelta(days=30):
        return "needs_review", "The usual one-year-and-30-day no-reply filing limit may have expired; obtain human review."
    return "potentially_eligible", "With no reply for at least 30 days, you may approach the RBI Ombudsman, subject to the other Scheme conditions."


def build_graph(retriever, model):
    prompt_artifact = getattr(model, "prompt", load_prompt("v2_modifier_aware"))
    p_ver = f"{prompt_artifact.name}:{prompt_artifact.version}"

    def investigator(state: AgentState):
        request = GrievanceSubmission.model_validate(state["request"])
        active_run_id = state.get("run_id") or runtime_run_id.get() or str(uuid4())
        trace = []

        # L4 Defense-in-depth input guardrail inside agent workflow
        is_safe, guardrail_reason = inspect_input_text(request.complaint_text)
        if not is_safe:
            trace.append(dict(agent="investigator", action="input_guardrail_blocked", detail=guardrail_reason))
            return dict(
                run_id=active_run_id,
                hypothesis=Hypothesis(kind="unknown", product="blocked_by_guardrail", entity_type="blocked_by_guardrail").model_dump(),
                evidence=[],
                trace=trace,
                guardrail_error=guardrail_reason,
            )

        inspect, search, lookup = make_tools(retriever, request, trace)
        fields = inspect.invoke({})
        evidence = search.invoke({"query": request.complaint_text})
        hypothesis = Hypothesis.model_validate(model.call("investigate", fields))
        trace.append(dict(agent="investigator", action="product_entity_hypothesis", detail=hypothesis.model_dump_json()))

        if prompt_artifact.version == "v1":
            # v1_baseline: Single-pass retrieval without Para 5.3 modifier check or second-pass search
            if hypothesis.kind == "mutual_fund":
                for document, section in REQUIRED["mutual_fund"]:
                    evidence += lookup.invoke({"document_id": document, "section": section})
        else:
            # v2_modifier_aware: Read the modifier before choosing a second framework search.
            # The complaint's named regulator never overrides the established product.
            if hypothesis.kind in REQUIRED:
                evidence += lookup.invoke({"document_id": "SEBI-SCORES-2023", "section": "5.3"})
                if hypothesis.kind == "bank_fd":
                    query, doc = "bank Regulated Entity deficiency in service grounds complaint prior written complaint 30 days", "RBI-IOS-2021"
                else:
                    query, doc = "asset management company redemption proceeds investor grievances redress 21 calendar days", "SEBI-MF-1996"
                evidence += search.invoke({"query": query, "document_id": doc})
                for document, section in REQUIRED[hypothesis.kind]:
                    evidence += lookup.invoke({"document_id": document, "section": section})

        dedup_evidence = list({c["chunk_id"]: c for c in evidence}.values())

        # L5 Token and cost attribution for Investigator step
        formatted_inv_prompt = (
            f"{prompt_artifact.system_prompt}\n\n"
            + prompt_artifact.investigate_prompt.format(
                complaint_text=request.complaint_text,
                entity_name=request.entity_name,
                named_regulator=request.named_regulator,
            )
            + "\n\nRetrieved Passages:\n"
            + json.dumps([{"doc": c["document_id"], "sec": c["section"], "quote": c["quote"]} for c in dedup_evidence])
        )
        global_cost_tracker.record_step(
            run_id=active_run_id,
            agent="investigator",
            action="product_entity_hypothesis",
            prompt_text=formatted_inv_prompt,
            completion_text=hypothesis.model_dump_json(),
        )

        return dict(run_id=active_run_id, hypothesis=hypothesis.model_dump(), evidence=dedup_evidence, trace=trace)

    def verifier(state: AgentState):
        active_run_id = state.get("run_id") or runtime_run_id.get() or str(uuid4())
        hypothesis = Hypothesis.model_validate(state["hypothesis"])
        trace = list(state["trace"])
        trace.append(dict(agent="verifier", action="audit_handoff", detail="Check required evidence coverage and match every citation to persisted PDF text"))

        if state.get("guardrail_error"):
            esc = escalate(state["guardrail_error"], trace, hypothesis.product, hypothesis.entity_type, prompt_version=p_ver)
            return {"result": esc.model_dump(mode="json")}

        if hypothesis.kind not in REQUIRED:
            if hypothesis.kind == "mixed":
                reason = "Complaint splits across regulators (e.g. banking channel and securities intermediary)."
            elif hypothesis.kind == "unregulated":
                reason = "Entity type or financial product falls outside regulatory corpus (unregulated or unlisted asset)."
            else:
                reason = "The regulatory corpus and model cannot establish this product and routing with sufficient evidence."
            esc = escalate(reason, trace, hypothesis.product, hypothesis.entity_type, prompt_version=p_ver)
            global_cost_tracker.record_step(
                run_id=active_run_id,
                agent="verifier",
                action="audit_handoff",
                prompt_text=f"{prompt_artifact.verify_prompt}\nHypothesis: {hypothesis.model_dump_json()}",
                completion_text=esc.model_dump_json(),
            )
            return {"result": esc.model_dump(mode="json")}

        citations = [Citation.model_validate(c) for c in state["evidence"]]
        by_section = {(c.document_id, c.section): c for c in citations}
        required = REQUIRED[hypothesis.kind]
        valid = all(key in by_section for key in required) and all(retriever.verify(c) for c in citations)
        verification = model.call("verify", {"evidence_valid": valid, "kind": hypothesis.kind})
        if not valid or verification.get("supported") is not True:
            esc = escalate("Evidence verification failed or a required provision was not retrieved.", trace, prompt_version=p_ver)
            global_cost_tracker.record_step(
                run_id=active_run_id,
                agent="verifier",
                action="audit_handoff",
                prompt_text=f"{prompt_artifact.verify_prompt}\nEvidence valid: {valid}",
                completion_text=esc.model_dump_json(),
            )
            return {"result": esc.model_dump(mode="json")}

        citations = [by_section[key] for key in required]
        request = GrievanceSubmission.model_validate(state["request"])
        if hypothesis.kind == "bank_fd":
            eligibility, action = bank_eligibility(request)
            decision = RoutingDecision(domain="out_of_jurisdiction", routing="refer_to_other_regulator",
                target_authority="Reserve Bank of India — Integrated Ombudsman Scheme, 2021",
                immediate_action=action, eligibility=eligibility, product=hypothesis.product,
                entity_type=hypothesis.entity_type,
                rationale="The product is inferred from the complaint to be a bank fixed deposit. The bank is a Regulated Entity under RBI-IOS 3(1)(j). Crediting less than the promised interest is treated as an alleged deficiency in service under 3(1)(f) and clause 9. SCORES 5.3 excludes RBI matters. Clause 10(1)(a)'s commercial-judgment exclusion was considered: this complaint concerns failure to honour a promised rate, rather than setting a rate. The Scheme does not name fixed deposits or interest explicitly. Coverage of the particular bank and all maintainability conditions require confirmation.",
                regulatory_citations=citations,
                next_steps=[action, "Keep the FD confirmation, promised rate, interest calculations and the bank's reply.",
                    "RBI-IOS 10(2)(a) normally requires filing within one year of the reply, or one year and 30 days from the written complaint if no reply arrives. A grievance officer must check remaining maintainability conditions."],
                verification="Required provisions retrieved; all citation text and metadata match the persisted corpus.",
                prompt_version=p_ver, agent_trace=trace)
        else:
            decision = RoutingDecision(domain="mutual_fund", routing="assign_to_entity",
                target_authority="Asset Management Company (AMC) grievance officer", immediate_action="Complain to the responsible AMC in writing.",
                product=hypothesis.product, entity_type=hypothesis.entity_type, timeline_days=21,
                rationale="The complaint describes unpaid mutual fund redemption proceeds. Regulation 53 addresses redemption payments; Regulation 60A requires the AMC to redress investor grievances within 21 calendar days. SCORES paragraph 1.2 also specifies 21 calendar days for complaint resolution. This is the grievance redressal timeline, not a new redemption-payment deadline.",
                regulatory_citations=citations, next_steps=["Send the redemption request reference and account statement to the AMC grievance officer.", "If unresolved, seek review through the applicable SCORES process."],
                verification="Required provisions retrieved; all citation text and metadata match the persisted corpus.",
                prompt_version=p_ver, agent_trace=trace)

        # L4 Output Guardrail check on generated rationale and immediate_action
        out_safe, out_reason = inspect_output_decision(decision.rationale, decision.immediate_action)
        if not out_safe:
            trace.append(dict(agent="verifier", action="output_guardrail_blocked", detail=out_reason))
            esc = escalate(out_reason, trace, hypothesis.product, hypothesis.entity_type, prompt_version=p_ver)
            return {"result": esc.model_dump(mode="json")}

        # L5 Token and cost attribution for Verifier step
        verify_prompt_text = (
            f"{prompt_artifact.system_prompt}\n\n{prompt_artifact.verify_prompt}\n\n"
            + json.dumps([{"doc": c.document_id, "sec": c.section, "quote": c.quote} for c in citations])
        )
        global_cost_tracker.record_step(
            run_id=active_run_id,
            agent="verifier",
            action="audit_handoff",
            prompt_text=verify_prompt_text,
            completion_text=decision.model_dump_json(),
        )
        return {"result": decision.model_dump(mode="json")}

    graph = StateGraph(AgentState)
    graph.add_node("investigator", instrument_agent(investigator,"investigator"))
    graph.add_node("verifier", instrument_agent(verifier,"verifier"))
    graph.add_edge(START, "investigator")
    graph.add_edge("investigator", "verifier")
    graph.add_edge("verifier", END)
    return graph.compile()


def route_with_state(request: GrievanceSubmission, retriever, settings, run_id: str | None = None) -> tuple[RoutingDecision, list[dict]]:
    rid = run_id or str(uuid4())
    state = build_graph(retriever, Model(settings)).invoke(
        {"request": request.model_dump(mode="json"), "run_id": rid},
        {"recursion_limit": 6},
    )
    return RoutingDecision.model_validate(state["result"]), state.get("evidence", [])


def route(request: GrievanceSubmission, retriever, settings) -> RoutingDecision:
    decision, _ = route_with_state(request, retriever, settings)
    return decision
