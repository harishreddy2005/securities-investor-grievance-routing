"""Run reproducible 1-vs-3-worker Locust matrix; retain evidence, restore services.

No Redis flush, volume deletion, source mutation, commit or push. Requires a
running normal stack and a built loadtest image. See docs/PHASE4_SLO.md.
"""
import argparse
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def docker(*args, **kwargs):
    return subprocess.run(['docker',*args],cwd=ROOT,check=True,**kwargs)


def output(*args):
    return docker(*args,capture_output=True,text=True).stdout


def get(url):
    with urllib.request.urlopen(url,timeout=5) as response:
        return json.load(response)


def metrics():
    expressions={
        'queue_depth':'grievance_queue_depth{job="workers"}',
        'worker_cpu_cores':'sum by (name) (rate(container_cpu_usage_seconds_total{job="cadvisor",name=~".*-worker-[0-9]+"}[30s]))',
        'worker_memory_bytes':'sum by (name) (container_memory_working_set_bytes{job="cadvisor",name=~".*-worker-[0-9]+"})',
        'api_cpu_cores':'sum(rate(container_cpu_usage_seconds_total{job="cadvisor",name=~".*-api-[0-9]+"}[30s]))',
        'redis_cpu_cores':'sum(rate(container_cpu_usage_seconds_total{job="cadvisor",name=~".*-redis-[0-9]+"}[30s]))',
        'stub_cpu_cores':'sum(rate(container_cpu_usage_seconds_total{job="cadvisor",name=~".*-llm-stub-[0-9]+"}[30s]))',
    }
    values={'timestamp':time.time()}
    def sample(item):
        name,expr=item
        try:
            data=get('http://127.0.0.1:9090/api/v1/query?'+urllib.parse.urlencode({'query':expr}))
            return name,[{'name':r['metric'].get('name',name),'value':float(r['value'][1])}
                         for r in data['data']['result']],None
        except Exception as error:
            return name,[],type(error).__name__
    with ThreadPoolExecutor(max_workers=len(expressions)) as pool:
        for name,rows,error in pool.map(sample,expressions.items()):
            values[name]=rows
            if error:
                values[name+'_error']=error
    return values


def idle(timeout=210):
    code="import json; from app.jobs import connection,queue; from rq.registry import StartedJobRegistry; c=connection(); q=queue(c); print(json.dumps({'queued':q.count,'started':StartedJobRegistry(q.name,connection=c).count}))"
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        state=json.loads(output('compose','exec','-T','api','python','-c',code))
        if state['queued']==state['started']==0:
            return
        print('Waiting for existing work:',state,flush=True)
        time.sleep(3)
    raise RuntimeError('Existing queue did not drain; refusing to mix benchmark cases')


def warmup(base):
    # Separate excluded run ensures the stack works before measured traffic.
    import sys
    sys.path.insert(0,str(ROOT))
    from loadtests.lifecycle import complete
    def request(method,path,payload=None,expected=200,headers=None):
        data=None if payload is None else json.dumps(payload).encode()
        req=urllib.request.Request(base+path,data=data,method=method,
            headers={'Content-Type':'application/json',**(headers or {})})
        with urllib.request.urlopen(req,timeout=10) as response:
            if response.status!=expected:
                raise RuntimeError('Warmup HTTP failure')
            return json.load(response)
    complete(request)


def render_report(report):
    rows=['# Phase 4 measured benchmark','',
          'Generated from real Docker Locust results. SLO declared in docs/PHASE4_SLO.md before measurements.',
          '',f"Timestamp: {report['timestamp']}; commit: `{report['commit']}`.",
          f"Docker: {report['docker']['cpus']} CPUs, {report['docker']['memory_bytes']/1024**3:.2f} GiB RAM.",
          f"Active duration: {report['duration_seconds']} seconds/case; stub delay: 0.1 seconds/call.",'',
          f"Benchmark API quota: {report.get('api_rate_limit_per_minute',60)}/minute per IP; base settings restored afterward.",'',
          '| Workers | Clients | OK / failed / unfinished | Complete RPS | HTTP RPS | p50 s | p95 s | Queue p50 s | Max queue | SLO |',
          '|---|---|---|---|---|---|---|---|---|---|']
    def fmt(value): return 'n/a' if value is None else f'{value:.3f}'
    for case in report['cases']:
        rows.append(f"| {case['worker_count']} | {case['client_users']} | {case['successful']} / {case['failed']} / {case['unfinished']} | {fmt(case['complete_rps'])} | {fmt(case['http_rps'])} | {fmt(case['p50_seconds'])} | {fmt(case['p95_seconds'])} | {fmt(case['queue_wait_p50_seconds'])} | {case['max_queue_depth']} | {'MET' if case['slo_met'] else 'MISSED'} |")
    rows+=['','Throughput includes graceful drain. HTTP RPS includes status polling and is not complaint RPS.',
           'Percentiles use exact nearest-rank completed successful lifecycles; failed/unfinished work fails the SLO.',
           'These are short closed-loop demonstration measurements, not production capacity or a statistically precise tail estimate.','']
    for workers in sorted({c['worker_count'] for c in report['cases']}):
        cases=sorted((c for c in report['cases'] if c['worker_count']==workers),key=lambda c:c['client_users'])
        missed=next((c for c in cases if not c['slo_met']),None)
        boundary='not found in tested range' if missed is None else (
            '<= '+str(missed['client_users']) if missed==cases[0] else str(missed['client_users']))
        rows.append(f'- First tested SLO failure for {workers} worker(s): {boundary} concurrent clients.')
    return '\n'.join(rows)+'\n'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--duration',type=int,default=120)
    parser.add_argument('--users',type=int,nargs='+',default=[1,3,6])
    parser.add_argument('--workers',type=int,nargs='+',default=[1,3])
    parser.add_argument('--fail-on-slo',action='store_true',help='Exit 2 after all cases if any case misses the declared SLO')
    parser.add_argument('--cache-mode',choices=['on','off'],default='on')
    parser.add_argument('--report-name',default='benchmark')
    parser.add_argument('--api-rate-limit',type=int,default=10000,
                        help='Benchmark-only per-IP quota; base application settings are restored afterward')
    args=parser.parse_args()
    if shutil.disk_usage(ROOT).free < 512*1024**2:
        raise RuntimeError('Less than 512 MiB free: free disk space before recording a benchmark; no data was deleted')
    if not args.report_name.replace('-','').replace('_','').isalnum():
        parser.error('Report name must contain letters, digits, dashes or underscores')
    if not 1<=args.api_rate_limit<=10000:
        parser.error('API quota must be between 1 and 10000')
    if args.duration<5 or min(args.users+args.workers)<1:
        parser.error('Duration >=5 and positive users/workers are required')
    folder=ROOT/'data'/'phase4'
    folder.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    override=folder/'compose.benchmark.json'
    override.write_text(json.dumps({'services':{'llm-stub':{'environment':{
        'STUB_FAIL':'false','STUB_DELAY_SECONDS':'0.1'}},'worker':{'environment':{'ENABLE_QUERY_CACHE':str(args.cache_mode=='on').lower()}},
        'api':{'environment':{'RATE_LIMIT_PER_MINUTE':str(args.api_rate_limit)}}}}),encoding='utf-8')
    compose=['compose','-f','docker-compose.yml','-f',str(override)]
    report={'timestamp':stamp,'duration_seconds':args.duration,'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'host_platform':platform.platform(),
            'docker':json.loads(output('info','--format','{"cpus":{{.NCPU}},"memory_bytes":{{.MemTotal}},"server_version":"{{.ServerVersion}}"}')),
            'cases':[]}
    source_files=['locustfile.py','loadtests/lifecycle.py','app/worker.py','app/worker_health.py']
    report['source_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source_files}
    report['app_image']=output('compose','images','-q','api').strip()
    report['cache_mode']=args.cache_mode
    report['api_rate_limit_per_minute']=args.api_rate_limit
    readiness=get('http://127.0.0.1:8000/health')
    if readiness.get('index',{}).get('embedding_provider')!='chroma':
        raise RuntimeError('Benchmark requires real semantic Chroma ONNX embeddings')
    idle()
    try:
        for workers in args.workers:
            docker(*compose,'up','-d','--no-deps','--scale',f'worker={workers}',
                   '--wait','--wait-timeout','180','worker','llm-stub','api')
            ids=output('compose','ps','-q','worker').splitlines()
            if len(ids)!=workers:
                raise RuntimeError('Requested worker scale was not reached')
            idle()
            warmup('http://127.0.0.1:8000')
            for users in args.users:
                idle()
                name=f'{stamp}-w{workers}-u{users}'
                env={**os.environ,'BENCHMARK_NAME':name,'BENCHMARK_USERS':str(users),
                     'BENCHMARK_WORKERS':str(workers),
                     'LOADTEST_UID':str(os.getuid() if hasattr(os,'getuid') else 1000),
                     'LOADTEST_GID':str(os.getgid() if hasattr(os,'getgid') else 1000)}
                container_name='grievance-load-'+name.lower()
                command=['docker',*compose,'--profile','loadtest','run','--rm','--no-deps','-T','--name',container_name,'loadtest',
                         '--headless','--host','http://api:8000','--users',str(users),'--spawn-rate',str(users),
                         '--run-time',str(args.duration)+'s','--stop-timeout','210',
                         '--csv','/results/'+name,'--csv-full-history']
                # Name only this test's container so interruption can stop it,
                # rather than leaving traffic running after the CLI exits.
                resource_samples=[]
                print(f'Starting {workers} workers / {users} clients for {args.duration}s',flush=True)
                with (folder/(name+'.log')).open('w',encoding='utf-8') as log:
                    process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
                    limit=time.monotonic()+args.duration+270
                    try:
                        while process.poll() is None:
                            resource_samples.append(metrics())
                            if time.monotonic()>limit:
                                raise RuntimeError('Load generator exceeded bounded execution time')
                            time.sleep(3)
                    finally:
                        if process.poll() is None:
                            subprocess.run(['docker','stop','--time','215',container_name],cwd=ROOT,
                                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=240)
                            process.terminate()
                            process.wait(timeout=20)
                if process.returncode not in {0,1}:
                    raise RuntimeError('Locust failed; inspect '+name+'.log')
                result_path=folder/(name+'.json')
                if not result_path.exists():
                    raise RuntimeError('Locust produced no lifecycle result; inspect '+name+'.log')
                case=json.loads(result_path.read_text())
                if case['completed']==0:
                    raise RuntimeError('No completed lifecycle samples')
                case['max_queue_depth']=max((x['value'] for sample in resource_samples for x in sample['queue_depth']),default=None)
                case['active_load_seconds']=args.duration
                case['graceful_drain_seconds']=max(0,case['elapsed_seconds']-args.duration)
                case['worker_container_ids']=ids
                case['resources']=resource_samples
                case['artifact_prefix']=name
                # Retain one sampled trace for diagnosis of queue vs process
                # initialization vs agent work. No complaint attributes added.
                example=next((s.get('trace_id') for s in case['samples'] if s.get('trace_id')),None)
                if example:
                    try:
                        trace=get('http://127.0.0.1:16686/api/traces/'+example)
                        (folder/(name+'-trace.json')).write_text(json.dumps(trace,indent=2)+'\n',encoding='utf-8')
                        case['example_trace_id']=example
                    except Exception as error:
                        case['trace_collection_error']=type(error).__name__
                report['cases'].append(case)
                (folder/(args.report_name+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
                (folder/(args.report_name+'.md')).write_text(render_report(report),encoding='utf-8')
                print(json.dumps({k:v for k,v in case.items() if k not in {'samples','resources','worker_container_ids'}}),flush=True)
                idle()
    finally:
        print('Restoring one worker and original stub settings; volumes retained.',flush=True)
        docker('compose','up','-d','--no-deps','--scale','worker=1','--wait','--wait-timeout','180','worker','llm-stub','api')
    print('Benchmark complete: data/phase4/'+args.report_name+'.md',flush=True)
    if any(c['failed'] or c['unfinished'] for c in report['cases']):
        raise SystemExit('Benchmark observed failed/unfinished lifecycles; inspect results')
    if args.fail_on_slo and any(not c['slo_met'] for c in report['cases']):
        raise SystemExit(2)


if __name__=='__main__':
    main()
