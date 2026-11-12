"""Durable synthetic-data run audit. Payloads never enter exported telemetry."""
import json
import time
from opentelemetry import trace
from app.observability import runtime


def append(kind, value):
    conn=runtime.metric_store.get()
    identifier=runtime.run_id.get()
    if conn is None or not identifier:
        return
    from app.config import get_settings
    context=trace.get_current_span().get_span_context()
    record={**value,"kind":kind,"timestamp":time.time(),
            "trace_id":format(context.trace_id,'032x') if context.is_valid else None}
    pipe=conn.pipeline()
    key='grievance:audit:'+identifier
    pipe.rpush(key,json.dumps(record,default=str))
    pipe.expire(key,get_settings().result_ttl)
    pipe.execute()


def records(conn, identifier):
    return [json.loads(value) for value in conn.lrange('grievance:audit:'+identifier,0,-1)]
