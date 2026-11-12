"""Dependency-free lifecycle validation and exact benchmark statistics."""
import math
import time
from collections import Counter
from uuid import UUID, uuid4

SLO_SECONDS = 8.0
REFERENCE = {
    'entity_name':'Synthetic Benchmark Bank',
    'complaint_text':"I invested in a fixed deposit through my bank's app. The interest credited is lower than what I was promised. I want to complain to SEBI.",
    'approached_entity_first':False,
}


class LifecycleError(RuntimeError):
    """Fixed error identifiers only; no response bodies or submitted fields."""


def validate_result(result):
    if (result.get('routing')!='refer_to_other_regulator'
        or result.get('eligibility')!='bank_first'
        or 'Reserve Bank of India' not in result.get('target_authority','')
        or 'writing to the bank' not in result.get('immediate_action','')
        or result.get('uncertain') is not False
        or result.get('reliability_status')!='verified'):
        raise LifecycleError('incorrect_or_degraded_routing')
    citations=result.get('regulatory_citations',[])
    required={('SEBI-SCORES-2023','5.3'),('RBI-IOS-2021','9'),('RBI-IOS-2021','10(2)(a)')}
    if not required <= {(c.get('document_id'),c.get('section')) for c in citations}:
        raise LifecycleError('missing_reference_evidence')
    if not all(c.get('quote') and isinstance(c.get('page'),int) and c['page']>0
               and len(c.get('sha256',''))==64 for c in citations):
        raise LifecycleError('invalid_citation_metadata')
    if {e.get('agent') for e in result.get('agent_trace',[])}!={'investigator','verifier'}:
        raise LifecycleError('missing_agent_participation')


def complete(request, *, timeout=180, poll_interval=.25, clock=time.monotonic, sleep=time.sleep,
             accepted_id=None, started_at=None):
    started=clock() if started_at is None else started_at
    accepted={'run_id':accepted_id} if accepted_id is not None else request(
        'POST','/api/v1/grievances',payload=REFERENCE,expected=202,headers={'Idempotency-Key':str(uuid4())})
    try:
        identifier=str(UUID(accepted['run_id']))
    except (KeyError,ValueError,TypeError):
        raise LifecycleError('invalid_submission_response') from None
    path='/api/v1/grievances/'+identifier
    first_started=None
    while clock()-started < timeout:
        status=request('GET',path)['status']
        if status in {'failed','stopped','canceled'}:
            raise LifecycleError('job_'+status)
        if status=='started' and first_started is None:
            first_started=clock()
        if status=='finished':
            result=request('GET',path+'/result')
            validate_result(result)
            elapsed=clock()-started
            if elapsed>timeout:
                raise LifecycleError('lifecycle_timeout')
            return {'run_id':identifier,'latency_seconds':elapsed,
                    'estimated_cost_usd':(result.get('cost_summary') or {}).get('total_cost_usd',0),
                    'billed_cost_usd':sum(s.get('billed_cost_usd',0) for s in (result.get('cost_summary') or {}).get('steps',[])),
                    # Polling observes the first started status; this includes
                    # submission overhead and can overestimate queue wait by a poll.
                    'observed_queue_wait_seconds':None if first_started is None else first_started-started}
        if status not in {'queued','started','scheduled','deferred'}:
            raise LifecycleError('unexpected_job_state')
        sleep(min(poll_interval,max(0,timeout-(clock()-started))))
    raise LifecycleError('lifecycle_timeout')


def percentile(values, quantile):
    return sorted(values)[max(0,math.ceil(len(values)*quantile)-1)] if values else None


def summarize(samples, elapsed, *, submitted=None):
    successful=[s for s in samples if s['success']]
    latencies=[s['latency_seconds'] for s in successful]
    failed=len(samples)-len(successful)
    unfinished=max(0,(submitted if submitted is not None else len(samples))-len(samples))
    p95=percentile(latencies,.95)
    violations=failed+unfinished+sum(t>SLO_SECONDS for t in latencies)
    total=len(samples)+unfinished
    return {
        'completed':len(samples),'successful':len(successful),'failed':failed,
        'unfinished':unfinished,'elapsed_seconds':elapsed,
        'complete_rps':len(successful)/elapsed if elapsed>0 else 0,
        'p50_seconds':percentile(latencies,.5),'p95_seconds':p95,
        'slo_seconds':SLO_SECONDS,
        'slo_met':p95 is not None and p95<=SLO_SECONDS and failed==0 and unfinished==0,
        'slo_violations':violations,
        'slo_violation_ratio':violations/total if total else None,
        'estimated_cost_per_run_usd':sum(s.get('estimated_cost_usd',0) for s in successful)/len(successful) if successful else None,
        'billed_cost_per_run_usd':sum(s.get('billed_cost_usd',0) for s in successful)/len(successful) if successful else None,
        'failure_codes':dict(Counter(s.get('error','unknown') for s in samples if not s['success'])),
        'queue_wait_p50_seconds':percentile([s['observed_queue_wait_seconds'] for s in successful if s.get('observed_queue_wait_seconds') is not None],.5),
    }
