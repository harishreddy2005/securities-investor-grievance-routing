"""RQ persists queued payloads, status, failures, and results in Redis."""
import json
import logging
import hashlib
import time
from uuid import uuid4
from functools import lru_cache

from redis import Redis, ConnectionPool
from rq import Queue, Worker, get_current_job
from redis.exceptions import WatchError
from opentelemetry import context, trace

from app.config import get_settings
from app.observability import runtime
from app.observability.metrics import count, observe
from app.reliability import DependencyFailure

logger = logging.getLogger(__name__)


def connection():
    return Redis.from_url(get_settings().redis_url, socket_connect_timeout=get_settings().redis_timeout, socket_timeout=get_settings().redis_timeout)


class IdempotencyConflict(ValueError):
    pass


def enqueue(conn, payload, idempotency_key=None):
    settings = get_settings()
    fingerprint = hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    mapping = "grievance:idempotency:"+hashlib.sha256(idempotency_key.encode()).hexdigest() if idempotency_key else None
    for _ in range(8):
        try:
            with conn.pipeline() as pipe:
                if mapping:
                    pipe.watch(mapping)
                    previous = pipe.get(mapping)
                    if previous:
                        previous=json.loads(previous)
                        if previous["fingerprint"] != fingerprint:
                            raise IdempotencyConflict("Idempotency-Key was already used with a different complaint")
                        return previous["run_id"]
                identifier=str(uuid4())
                metadata={"carrier":runtime.carrier(), "correlation_id":runtime.correlation_id.get(), "submitted_at":time.time()}
                pipe.multi()
                queue(conn).enqueue_call(process_grievance,args=(payload,identifier),kwargs={"telemetry":metadata},
                    job_id=identifier, description="process_grievance",result_ttl=settings.result_ttl,
                    failure_ttl=settings.result_ttl,ttl=settings.result_ttl,pipeline=pipe)
                if mapping:
                    pipe.set(mapping,json.dumps({"fingerprint":fingerprint,"run_id":identifier}),ex=settings.result_ttl)
                pipe.execute()
                return identifier
        except WatchError:
            continue
    from redis.exceptions import ConnectionError as RedisConnectionError
    raise RedisConnectionError("Submission contention; retry with the same idempotency key")


def queue(conn=None):
    settings = get_settings()
    return Queue(settings.queue_name, connection=conn if conn is not None else connection(),
                 default_timeout=settings.job_timeout)


@lru_cache
def resources():
    from app.agents.graph import build_graph
    from app.llm import Model
    from app.rag.retriever import Retriever
    settings = get_settings()
    return build_graph(Retriever(settings), Model(settings))


def process_grievance(payload: dict, run_id: str, telemetry=None):
    from app.schemas import GrievanceSubmission, RoutingDecision
    from app.agents.graph import escalate
    settings=get_settings()
    runtime.initialize("grievance-worker",settings)
    job=get_current_job()
    if job:
        # RQ enlarges its queue socket timeout for blocking dequeue. Use a
        # separate pool for bounded result/lease/metrics operations.
        source=job.connection.connection_pool
        options={**source.connection_kwargs,"socket_timeout":settings.redis_timeout,"socket_connect_timeout":settings.redis_timeout}
        conn=Redis(connection_pool=ConnectionPool(connection_class=source.connection_class,**options))
    else:
        conn=connection()
    telemetry=telemetry or {}
    parent=context.attach(runtime.extract(telemetry.get("carrier",{})))
    run_token=runtime.run_id.set(run_id)
    correlation_token=runtime.correlation_id.set(telemetry.get("correlation_id",run_id))
    metrics_token=runtime.metric_store.set(conn)
    started=time.monotonic()
    cache_key="grievance:outcome:"+run_id
    lock_key="grievance:execution:"+run_id
    lock_token=str(uuid4())
    acquired=False
    try:
        with runtime.span("job.process"):
            previous=conn.get(cache_key)
            if previous:
                return json.loads(previous)
            acquired=bool(conn.set(lock_key,lock_token,nx=True,ex=settings.job_timeout+30))
            if not acquired:
                raise RuntimeError("A duplicate execution is already in progress")
            # Close the check/acquire race with an execution that just completed.
            previous=conn.get(cache_key)
            if previous:
                return json.loads(previous)
            runtime.event("job_started")
            try:
                request = GrievanceSubmission.model_validate(payload)
                state = resources().invoke({"request": request.model_dump(mode="json")}, {"recursion_limit": 6})
                result = RoutingDecision.model_validate(state["result"]).model_dump(mode="json")
            except DependencyFailure as error:
                result=escalate("A required dependency is unavailable; a grievance officer must review the complaint before routing.",
                    [{"agent":"verifier","action":"dependency_failure","detail":error.dependency+": "+error.code}]).model_dump(mode="json")
                result.update(reliability_status="degraded",error_code=error.code)
                count("errors",error.code)
                runtime.event("job_degraded",error_code=error.code)
            with runtime.span("result.store"):
                # Single durable application outcome, independent of repeated deliveries.
                # Lock ownership and outcome publication are committed atomically.
                with conn.pipeline() as pipe:
                    pipe.watch(lock_key,cache_key)
                    if pipe.get(lock_key) != lock_token.encode():
                        raise RuntimeError("Execution lease lost; outcome not published")
                    pipe.multi()
                    pipe.set(cache_key,json.dumps(result),ex=settings.result_ttl,nx=True)
                    pipe.execute()
            outcome="escalated" if result["uncertain"] else "success"
            count("jobs",outcome)
            observe("job_duration",time.monotonic()-started)
            observe("end_to_end_duration",max(0,time.time()-telemetry.get("submitted_at",time.time())))
            runtime.event("job_finished",outcome=outcome)
            return result
    except Exception:
        count("jobs","failed")
        count("errors","internal_error")
        runtime.event("job_failed",error_code="internal_error")
        raise
    finally:
        if acquired:
            try:
                with conn.pipeline() as pipe:
                    pipe.watch(lock_key)
                    if pipe.get(lock_key)==lock_token.encode():
                        pipe.multi()
                        pipe.delete(lock_key)
                        pipe.execute()
            except Exception:
                pass
        runtime.flush()
        runtime.metric_store.reset(metrics_token)
        runtime.correlation_id.reset(correlation_token)
        runtime.run_id.reset(run_token)
        context.detach(parent)


def worker_available(conn):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return any(w.last_heartbeat and (now-w.last_heartbeat).total_seconds() < 120
               for w in Worker.all(connection=conn) if get_settings().queue_name in w.queue_names())
