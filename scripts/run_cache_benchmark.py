"""Deployed cache-on/off p95 and cost comparison, never offline suite timing."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--duration',type=int,default=60)
    args=parser.parse_args()
    results={}
    for mode in ['off','on']:
        subprocess.run([sys.executable,'scripts/run_scale_benchmark.py','--duration',str(args.duration),
            '--users','3','--workers','3','--cache-mode',mode,'--api-rate-limit','10000',
            '--report-name','cache-'+mode],check=True)
        data=json.loads(Path('data/phase4/cache-'+mode+'.json').read_text())
        results[mode]=data['cases'][0]
    off,on=results['off'],results['on']
    report={'duration_seconds_per_case':args.duration,'workers':3,'users':3,
        'api_rate_limit_per_minute':10000,'off':{k:v for k,v in off.items() if k not in ['samples','resources']},
        'on':{k:v for k,v in on.items() if k not in ['samples','resources']},
        'p95_reduction_pct':(1-on['p95_seconds']/off['p95_seconds'])*100,
        'estimated_cost_change_usd_per_run':on['estimated_cost_per_run_usd']-off['estimated_cost_per_run_usd'],
        'note':'Warm shared retrieval cache versus disabled cache; closed-loop local sample, not a production capacity claim. Stub billed API cost remains zero.'}
    Path('data/phase4/cache-effect.json').write_text(json.dumps(report,indent=2)+'\n')
    print('CACHE_EFFECT '+json.dumps({k:v for k,v in report.items() if k not in ['on','off']}),flush=True)


if __name__=='__main__': main()
