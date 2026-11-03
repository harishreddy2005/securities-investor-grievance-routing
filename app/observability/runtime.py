"""Explicit safe telemetry: no request bodies, query text, URLs or exception messages."""
import contextvars
import json
import logging
import os
import time
from contextlib import contextmanager

from opentelemetry import propagate, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

correlation_id = contextvars.ContextVar("correlation_id", default="")
run_id = contextvars.ContextVar("run_id", default="")
metric_store = contextvars.ContextVar("metric_store", default=None)
agent_activity = contextvars.ContextVar("agent_activity", default=None)
_provider = None
_pid = None


class SafeJSONFormatter(logging.Formatter):
    def format(self, record):
        context = trace.get_current_span().get_span_context()
        # Application events use fixed identifiers and an allowlisted field set.
        # Third-party messages/tracebacks can contain credentials or complaint data.
        fields = getattr(record, "safe_fields", {})
        data = {"level": record.levelname, "logger": record.name,
                "event": record.msg if getattr(record, "safe_event", False) else "library_event",
                "correlation_id": correlation_id.get(), "run_id": run_id.get(),
                "trace_id": format(context.trace_id, "032x") if context.is_valid else "",
                "span_id": format(context.span_id, "016x") if context.is_valid else ""}
        data.update({k: v for k, v in fields.items() if k in {"dependency", "attempt", "error_code", "outcome", "state", "duration_seconds"}})
        if record.exc_info:
            data["exception_type"] = record.exc_info[0].__name__
        return json.dumps(data)


def event(name, **fields):
    logging.getLogger("grievance").info(name, extra={"safe_event": True, "safe_fields": fields})


def initialize(service, settings):
    global _provider, _pid
    handler = logging.StreamHandler()
    handler.setFormatter(SafeJSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "rq.worker", "rq.job"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    if not settings.telemetry_enabled or _pid == os.getpid():
        return
    _pid = os.getpid()
    _provider = TracerProvider(resource=Resource.create({"service.name": service}))
    exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint, timeout=settings.telemetry_export_timeout)
    _provider.add_span_processor(BatchSpanProcessor(exporter, schedule_delay_millis=300))
    trace.set_tracer_provider(_provider)


def flush():
    if _provider:
        _provider.force_flush(timeout_millis=2500)


@contextmanager
def span(name, **attributes):
    # Disable automatic exception recording: exception strings may contain secrets.
    with trace.get_tracer("grievance").start_as_current_span(name, record_exception=False, set_status_on_exception=False) as current:
        for key, value in attributes.items():
            if key in {"agent", "dependency", "operation", "outcome", "error_code", "attempt", "http.method", "http.route", "http.status_code"}:
                current.set_attribute(key, value)
        if run_id.get():
            current.set_attribute("run_id", run_id.get())
        if correlation_id.get():
            current.set_attribute("correlation_id", correlation_id.get())
        try:
            yield current
        except Exception:
            current.set_status(trace.Status(trace.StatusCode.ERROR))
            raise


def carrier():
    value = {}
    propagate.inject(value)
    return {k: v for k, v in value.items() if k == "traceparent"}


def extract(value):
    return propagate.extract({k: v for k, v in value.items() if k == "traceparent"})


def instrument_agent(function, name):
    def wrapped(state):
        started = time.monotonic()
        outcome = "success"
        activity = {"agent":name,"tools":0}
        activity_token = agent_activity.set(activity)
        try:
            with span("agent." + name, agent=name):
                if name == "verifier":
                    with span("verification"):
                        return function(state)
                return function(state)
        except Exception:
            outcome = "error"
            raise
        finally:
            from app.observability.metrics import observe, count
            observe("agent_duration", time.monotonic()-started, name)
            count("agent", name + ":" + outcome)
            observe("agent_steps", 1, name)
            observe("agent_tools", activity["tools"], name)
            agent_activity.reset(activity_token)
    return wrapped


def record_tool():
    activity = agent_activity.get()
    if activity is not None:
        activity["tools"] += 1
