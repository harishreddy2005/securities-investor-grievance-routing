"""Independent mechanical quality proxies; no caller-rating/gold-label leakage."""
def evaluate(decision, evidence, request):
    citations=decision.get('regulatory_citations',[])
    matching=sum(any(c==e for e in evidence) for c in citations)
    grounded=matching/len(citations) if citations else float(decision.get('uncertain',False))
    if decision.get('uncertain'):
        faithful=decision.get('routing')=='escalate_to_human' and not citations
        relevant=0.0 if not evidence else 1.0
    else:
        from app.agents.graph import REQUIRED
        kind='bank_fd' if decision.get('domain')=='out_of_jurisdiction' else 'mutual_fund'
        required=set(REQUIRED[kind])
        present={(c.get('document_id'),c.get('section')) for c in citations}
        relevant=len(required & present)/len(required)
        faithful=required <= present and grounded==1
        if kind=='bank_fd' and not request.get('approached_entity_first'):
            faithful=faithful and decision.get('eligibility')=='bank_first'
    return {'groundedness':grounded,'context_relevance':relevant,'faithfulness':float(faithful),
            'hallucination_rate':1-grounded,'method':'mechanical_provenance_and_policy_proxy',
            'requires_human_review':True}
