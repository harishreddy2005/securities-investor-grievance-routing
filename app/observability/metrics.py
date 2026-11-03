"""RQ child/replica-safe worker metrics persisted in Redis, never per-job labels."""
import math
from prometheus_client import Counter, Histogram
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, HistogramMetricFamily

from app.observability.runtime import metric_store

REQUESTS = Counter("grievance_http_requests_total", "API requests", ["method", "route", "status"])
LATENCY = Histogram("grievance_http_duration_seconds", "API request latency", ["method", "route"], buckets=(.01,.05,.1,.25,.5,1,2,5,10))
BUCKETS = (.01,.05,.1,.25,.5,1,2,5,10,30,60,120,300,math.inf)
PREFIX = "grievance:metrics:"


def count(metric, label, backend=None):
    conn = backend if backend is not None else metric_store.get()
    if conn is None:
        return
    try:
        conn.hincrby(PREFIX+metric, label, 1)
    except Exception:
        pass  # Telemetry must not turn an otherwise valid job into a failure.


def observe(metric, value, label="all", backend=None):
    conn = backend if backend is not None else metric_store.get()
    if conn is None:
        return
    try:
        pipe = conn.pipeline()
        key = PREFIX+metric+":"+label
        pipe.hincrbyfloat(key, "sum", value)
        pipe.hincrby(key, "count", 1)
        for boundary in BUCKETS:
            if value <= boundary:
                pipe.hincrby(key, str(boundary), 1)
        pipe.execute()
    except Exception:
        pass


def decoded(values):
    return {k.decode() if isinstance(k,bytes) else k: float(v) for k,v in values.items()}


class WorkerCollector:
    def __init__(self, connection_factory, queue_name="grievances"):
        self.factory, self.queue_name = connection_factory, queue_name

    def collect(self):
        conn = self.factory()
        ready = GaugeMetricFamily("grievance_metrics_backend_up", "Redis metrics connection")
        try:
            conn.ping()
            queue = GaugeMetricFamily("grievance_queue_depth", "Queued complaints")
            queue.add_metric([], conn.llen("rq:queue:"+self.queue_name))
            yield queue
            for metric, help_text, labels, values in [
                ("jobs", "Completed jobs", ["outcome"], ["success","escalated","failed"]),
                ("errors", "Classified errors", ["code"], ["timeout","unavailable","invalid_response","circuit_open","internal_error"]),
                ("retries", "Dependency retries", ["dependency"], ["llm","retrieval"]),
                ("circuit_transitions", "Circuit transitions", ["state"], ["CLOSED","OPEN","HALF_OPEN"]),
                ("agent", "Agent calls", ["agent","outcome"], [f"{a}:{o}" for a in ["investigator","verifier"] for o in ["success","error"]]),
                ("agent_retries", "Per-agent dependency retries", ["agent","dependency"], [f"{a}:{d}" for a in ["investigator","verifier"] for d in ["llm","retrieval"]]),
            ]:
                family = CounterMetricFamily("grievance_"+metric, help_text, labels=labels)
                data = decoded(conn.hgetall(PREFIX+metric))
                for label in values:
                    family.add_metric(label.split(":"), data.get(label,0))
                yield family
            for metric, title, labels in [("job_duration","Job processing duration",["all"]),
                                           ("end_to_end_duration","Submission to durable outcome",["all"]),
                                           ("agent_duration","Agent latency",["investigator","verifier"]),
                                           ("agent_steps","Graph steps per agent run",["investigator","verifier"]),
                                           ("agent_tools","Tool calls per agent run",["investigator","verifier"])]:
                suffix = "_seconds" if metric.endswith("duration") else ""
                family = HistogramMetricFamily("grievance_"+metric+suffix, title, labels=[] if labels==["all"] else ["agent"])
                for label in labels:
                    data = decoded(conn.hgetall(PREFIX+metric+":"+label))
                    buckets = [("+Inf" if math.isinf(b) else str(b), data.get(str(b),0)) for b in BUCKETS]
                    family.add_metric([] if label=="all" else [label], buckets=buckets, sum_value=data.get("sum",0))
                yield family
            import json
            raw = conn.get("grievance:circuit:llm")
            state = json.loads(raw)["state"] if raw else "CLOSED"
            family = GaugeMetricFamily("grievance_circuit_state", "Dependency circuit: one active state", labels=["dependency","state"])
            for name in ["CLOSED","OPEN","HALF_OPEN"]:
                family.add_metric(["llm",name], int(state==name))
            yield family
            ready.add_metric([],1)
            yield ready
        except Exception:
            ready.add_metric([],0)
            yield ready
