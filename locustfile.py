"""Closed-loop synthetic FD lifecycle load. See docs/PHASE4_SLO.md.

Use the Compose loadtest profile or scripts/run_scale_benchmark.py. The custom
GRIEVANCE/complete metric is authoritative; HTTP totals also include polling.
"""
from locust import HttpUser, task, events, constant
import gevent
import json
import os
import re
from pathlib import Path
import time

from loadtests.lifecycle import complete, summarize, LifecycleError

samples=[]
pending=[]
submitted=0
started_at=None
ended_at=None


@events.test_start.add_listener
def start(environment, **kwargs):
    global submitted, started_at, ended_at
    samples.clear()
    pending.clear()
    submitted=0
    started_at=time.monotonic()
    ended_at=None


@events.test_stop.add_listener
def stop(environment, **kwargs):
    global ended_at
    # A stopping greenlet may be cancelled inside an in-flight HTTP operation.
    # Accepted IDs remain real queued jobs: collect their outcomes, never resubmit.
    from locust.clients import HttpSession
    from types import SimpleNamespace
    with HttpSession(base_url=environment.host,request_event=environment.events.request,
                     user=SimpleNamespace(context=lambda:{})) as session:
        def request(method,path,payload=None,expected=200,headers=None):
            name='/api/v1/grievances/{run_id}/result' if path.endswith('/result') else '/api/v1/grievances/{run_id}'
            with session.request(method,path,name=name,timeout=5,catch_response=True) as response:
                if response.status_code!=expected:
                    response.failure('drain_http_'+str(response.status_code))
                    raise LifecycleError('drain_http_'+str(response.status_code))
                return response.json()
        for item in pending:
            sample,begin=item
            error=None
            try:
                sample.update(complete(request,accepted_id=sample['run_id'],started_at=begin,
                    timeout=float(os.getenv('BENCHMARK_TIMEOUT','180')),sleep=gevent.sleep))
                sample.update(success=True,error=None,drained_after_stop=True)
            except Exception as caught:
                code=str(caught) if isinstance(caught,LifecycleError) else type(caught).__name__
                sample.update(success=False,error=code)
                error=LifecycleError(code)
            sample['latency_seconds']=time.monotonic()-begin
            samples.append(sample)
            environment.events.request.fire(request_type='GRIEVANCE',name='complete',
                response_time=sample['latency_seconds']*1000,response_length=0,exception=error,context={})
    ended_at=time.monotonic()


@events.quitting.add_listener
def report(environment, **kwargs):
    elapsed=(ended_at or time.monotonic())-(started_at or time.monotonic())
    summary=summarize(samples,elapsed,submitted=submitted)
    http_count=sum(s.num_requests for (name,method),s in environment.stats.entries.items() if method!='GRIEVANCE')
    summary.update(http_requests=http_count,http_rps=http_count/elapsed if elapsed>0 else 0,
                   samples=samples,client_users=int(os.getenv('BENCHMARK_USERS','0')),
                   worker_count=int(os.getenv('BENCHMARK_WORKERS','0')))
    path=Path(os.getenv('BENCHMARK_RESULT','/results/result.json'))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print('LIFECYCLE_RESULT '+json.dumps({k:v for k,v in summary.items() if k!='samples'}),flush=True)


class GrievanceUser(HttpUser):
    wait_time=constant(.1)

    def http(self,method,path,payload=None,expected=200,headers=None):
        name='/api/v1/grievances' if method=='POST' else (
            '/api/v1/grievances/{run_id}/result' if path.endswith('/result') else '/api/v1/grievances/{run_id}')
        with self.client.request(method,path,json=payload,headers=headers,name=name,
                                 timeout=5,catch_response=True) as response:
            if response.status_code!=expected:
                error=LifecycleError('http_'+str(response.status_code))
                response.failure(str(error))
                raise error
            try:
                body=response.json()
            except ValueError:
                response.failure('invalid_json')
                raise LifecycleError('invalid_json') from None
            if method=='POST':
                self.accepted_run_id=body.get('run_id')
                trace_id=response.headers.get('X-Trace-ID','')
                self.submission_trace_id=trace_id if re.fullmatch('[0-9a-f]{32}',trace_id) else None
                # Explicit regression fixture only; never enabled in benchmarks.
                if os.getenv('BENCHMARK_FORCE_CANCEL_ONCE')=='1':
                    raise gevent.GreenletExit()
            return body

    @task
    def grievance(self):
        global submitted
        submitted+=1
        begin=time.monotonic()
        sample={'success':False,'error':'interrupted'}
        self.submission_trace_id=None
        self.accepted_run_id=None
        drain=False
        exception=None
        try:
            sample.update(complete(self.http,timeout=float(os.getenv('BENCHMARK_TIMEOUT','180')),
                                   poll_interval=.25,sleep=gevent.sleep))
            sample.update(success=True,error=None,trace_id=self.submission_trace_id)
        except gevent.GreenletExit:
            if self.accepted_run_id:
                drain=True
                sample.update(run_id=self.accepted_run_id,trace_id=self.submission_trace_id)
                pending.append((sample,begin))
            else:
                exception=LifecycleError('interrupted')
            raise
        except Exception as error:
            # Only fixed public test codes enter artifacts; no bodies/credentials.
            code=str(error) if isinstance(error,LifecycleError) else type(error).__name__
            sample['error']=code
            exception=LifecycleError(code)
        finally:
            sample['latency_seconds']=time.monotonic()-begin
            if not drain:
                samples.append(sample)
                self.environment.events.request.fire(request_type='GRIEVANCE',name='complete',
                    response_time=sample['latency_seconds']*1000,response_length=0,
                    exception=exception,context={})
