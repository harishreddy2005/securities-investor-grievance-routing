from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.worker_health import healthy_worker, Worker


def test_restarted_worker_readiness_ignores_stale_and_other_replica_registrations(monkeypatch):
    now=datetime.now(timezone.utc)
    workers=[SimpleNamespace(name='replica:old',last_heartbeat=now-timedelta(days=8)),
             SimpleNamespace(name='another:active',last_heartbeat=now)]
    monkeypatch.setattr(Worker,'all',lambda connection:workers)
    assert not healthy_worker(object(),'replica',now)
    workers.append(SimpleNamespace(name='replica:new',last_heartbeat=now,queue_names=lambda:['grievances']))
    assert healthy_worker(object(),'replica',now)


def test_heartbeat_restores_expired_queue_registration():
    import fakeredis
    from rq import Queue, Worker
    from app.worker_registration import ReliableSpawnWorker
    conn=fakeredis.FakeRedis()
    worker=ReliableSpawnWorker([Queue('grievances',connection=conn)],connection=conn,name='recovery-test')
    worker.register_birth()
    conn.delete(worker.key)
    worker.heartbeat()
    recovered=Worker.find_by_key(worker.key,connection=conn)
    assert recovered.queue_names()==['grievances']
    assert conn.ttl(worker.key)>0
