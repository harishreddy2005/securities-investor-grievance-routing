"""Controlled idle-worker registry-expiry regression, without restarting Redis."""
import json
import subprocess
from verify_phase2 import request, APP, wait


def execute(code):
    value=subprocess.check_output(['docker','compose','exec','-T','api','python','-c',code],text=True)
    return json.loads(value)


def main():
    prefix="import json; from app.jobs import connection,queue; from rq import Worker; from rq.registry import StartedJobRegistry; c=connection(); q=queue(c); "
    state=execute(prefix+"print(json.dumps({'queued':q.count,'started':StartedJobRegistry(q.name,connection=c).count}))")
    assert state=={'queued':0,'started':0},'Run this controlled test on an idle stack'
    # Only remove queue metadata from live project workers. Do not delete jobs,
    # worker identity, corpus, AOF, or unrelated Redis keys.
    keys=execute(prefix+"keys=[w.key for w in Worker.all(connection=c) if q.name in w.queue_names()]; print(json.dumps(keys))")
    assert keys,'No live worker registration'
    execute(prefix+"keys="+repr(keys)+"; print(json.dumps([c.hdel(k,'queues') for k in keys]))")
    def repaired():
        state=execute(prefix+"print(json.dumps([q.name in w.queue_names() for w in Worker.all(connection=c) if w.key in "+repr(keys)+"]))")
        if state and all(state):
            request(APP+'/health')
            return True
    wait(repaired,120)
    print('PASS missing Redis worker queue metadata repaired by heartbeat; API ready without a restart')


if __name__=='__main__': main()
