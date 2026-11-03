import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import Request
from opentelemetry import context, trace
from app.config import get_settings
from app.observability import runtime
from app.observability.metrics import REQUESTS, LATENCY


def install(app, service):
    previous=app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        runtime.initialize(service,get_settings())
        try:
            async with previous(application):
                yield
        finally:
            runtime.flush()
    app.router.lifespan_context=lifespan

    @app.middleware("http")
    async def observe_http(request: Request, call_next):
        if request.url.path in {"/metrics","/health"}:
            return await call_next(request)
        started = time.monotonic()
        try:
            cid = str(UUID(request.headers.get("x-correlation-id","")))
        except ValueError:
            cid = str(uuid4())
        correlation = runtime.correlation_id.set(cid)
        parent = context.attach(runtime.extract(dict(request.headers)))
        method = request.method if request.method in {"GET","POST","PUT","DELETE","PATCH","HEAD","OPTIONS"} else "OTHER"
        status = 500
        route = "unmatched"
        try:
            with runtime.span("http.request", **{"http.method":method}) as current:
                response = await call_next(request)
                status = response.status_code
                route = getattr(request.scope.get("route"), "path", "unmatched")
                current.set_attribute("http.route",route)
                current.set_attribute("http.status_code",status)
                response.headers["X-Correlation-ID"] = cid
                span_context = trace.get_current_span().get_span_context()
                if span_context.is_valid:
                    response.headers["X-Trace-ID"] = format(span_context.trace_id,"032x")
                runtime.event("http_completed",outcome="success" if status<500 else "error",duration_seconds=time.monotonic()-started)
                return response
        finally:
            if route != "/metrics":
                REQUESTS.labels(method,route,str(status)).inc()
                LATENCY.labels(method,route).observe(time.monotonic()-started)
            context.detach(parent)
            runtime.correlation_id.reset(correlation)
