"""Protect end-to-end measurement from counting enqueue or escalation as success."""
from uuid import uuid4
import pytest

from loadtests.lifecycle import complete, summarize, LifecycleError


def decision():
    return dict(routing='refer_to_other_regulator',eligibility='bank_first',
        target_authority='Reserve Bank of India',immediate_action='First complain in writing to the bank',
        uncertain=False,reliability_status='verified',
        regulatory_citations=[dict(document_id=d,section=s,quote='verified passage',page=1,sha256='a'*64)
                             for d,s in [('SEBI-SCORES-2023','5.3'),('RBI-IOS-2021','9'),('RBI-IOS-2021','10(2)(a)')]],
        agent_trace=[{'agent':'investigator'},{'agent':'verifier'}])


def test_timer_includes_submission_queue_processing_and_result_fetch():
    now=[0.0]
    statuses=iter(['queued','started','finished'])
    calls=[]
    def request(method,path,**kwargs):
        calls.append((method,path))
        now[0]+=1
        if method=='POST': return {'run_id':str(uuid4())}
        if path.endswith('/result'): return decision()
        return {'status':next(statuses)}
    result=complete(request,clock=lambda:now[0],sleep=lambda delay:now.__setitem__(0,now[0]+delay),poll_interval=.5)
    assert result['latency_seconds']==6
    assert result['observed_queue_wait_seconds']==3.5
    assert len(calls)==5


@pytest.mark.parametrize('mutation',[{'reliability_status':'degraded'}, {'regulatory_citations':[]},
                                     {'eligibility':'potentially_eligible'},{'agent_trace':[]}])
def test_invalid_reference_result_is_a_failure(mutation):
    def request(method,path,**kwargs):
        if method=='POST': return {'run_id':str(uuid4())}
        if path.endswith('/result'): return {**decision(),**mutation}
        return {'status':'finished'}
    with pytest.raises(LifecycleError): complete(request)


def test_timeout_never_becomes_success():
    now=[0.0]
    def request(method,path,**kwargs):
        return {'run_id':str(uuid4())} if method=='POST' else {'status':'queued'}
    with pytest.raises(LifecycleError,match='lifecycle_timeout'):
        complete(request,timeout=1,clock=lambda:now[0],sleep=lambda delay:now.__setitem__(0,now[0]+delay))


def test_accepted_drain_keeps_original_timer_and_never_resubmits():
    identifier=str(uuid4()); now=[7.0]; calls=[]
    def request(method,path,**kwargs):
        assert method=='GET'
        calls.append(path); now[0]+=1
        return decision() if path.endswith('/result') else {'status':'finished'}
    result=complete(request,accepted_id=identifier,started_at=0,clock=lambda:now[0])
    assert result['latency_seconds']==9 and len(calls)==2
    assert result['run_id']==identifier


def test_accepted_drain_does_not_reset_expired_deadline():
    with pytest.raises(LifecycleError,match='lifecycle_timeout'):
        complete(lambda *a,**k:pytest.fail('Expired run must not be resubmitted'),
                 accepted_id=str(uuid4()),started_at=0,timeout=5,clock=lambda:10)


def test_exact_percentiles_throughput_failures_and_unfinished():
    samples=[{'success':True,'latency_seconds':t,'observed_queue_wait_seconds':.5} for t in range(1,21)]
    result=summarize(samples,100,submitted=21)
    assert result['p50_seconds']==10 and result['p95_seconds']==19
    assert result['complete_rps']==.2 and result['unfinished']==1
    assert result['slo_violations']==13 and not result['slo_met']
    assert not summarize([],1)['slo_met']
    assert summarize([{'success':True,'latency_seconds':8}],1)['slo_met']
    assert not summarize([{'success':False,'latency_seconds':1}],1)['slo_met']
