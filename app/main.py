import json
import logging
import time
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from redis.exceptions import RedisError
from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.config import get_settings
from app.guardrails.safety import inspect_input_text
from app.jobs import connection, process_grievance, queue, worker_available, enqueue, IdempotencyConflict
from app.observability.http import install
from app.observability import runtime
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.schemas import FeedbackReceipt, FeedbackSubmission, GrievanceSubmission, JobAccepted, JobStatus, RoutingDecision

app = FastAPI(title="Securities Investor Grievance Routing API", version="0.2.0")
logger = logging.getLogger(__name__)
install(app,"grievance-api")


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)


def redis_connection():
    return connection()


@app.get("/")
def frontend():
    return FileResponse(Path(__file__).parent / "static/index.html")


@app.get("/health")
def health(conn=Depends(redis_connection)):
    try:
        conn.ping()
        manifest = json.loads((get_settings().index_dir / "manifest.json").read_text(encoding="utf-8"))
        available = worker_available(conn)
        healthy = available and manifest["chunks"] > 0
        return JSONResponse(status_code=200 if healthy else 503, content={"status": "healthy" if healthy else "degraded", "redis": True, "worker": available, "index": manifest})
    except (RedisError, OSError, ValueError, KeyError):
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": "Check Redis, worker and corpus ingestion"})


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    errors = [{"loc": list(e["loc"]), "type": e["type"], "msg": e["msg"]} for e in exc.errors()]
    # Do not expose or log complaint text. Phase 0 uses synthetic requests only.
    try:
        conn = app.dependency_overrides.get(redis_connection, redis_connection)()
        conn.lpush("grievance:quarantine", json.dumps({"errors": errors, "body": exc.body}, default=str))
        conn.ltrim("grievance:quarantine", 0, 999)
    except RedisError:
        logger.error("Quarantine unavailable during validation rejection")
    return JSONResponse(status_code=422, content={"detail": errors})


@app.post("/api/v1/grievances", status_code=202, response_model=JobAccepted)
@app.post("/api/v1/grievances/route", status_code=202, response_model=JobAccepted, deprecated=True)
def submit(request: Request, submission: GrievanceSubmission, conn=Depends(redis_connection), idempotency_key: str | None=Header(default=None,min_length=1,max_length=128)):
    # D7 Per-client rate limiting to protect downstream workers and budgets
    client_ip = request.client.host if request.client else "anonymous"
    rl_key = f"grievance:ratelimit:{client_ip}:{int(time.time() // 60)}"
    try:
        current_count = conn.incr(rl_key)
        if current_count == 1:
            conn.expire(rl_key, 60)
        if current_count > get_settings().rate_limit_per_minute:
            raise HTTPException(status_code=429, detail="Rate limit exceeded; retry after 60 seconds")
    except RedisError:
        raise HTTPException(503, "Queue unavailable; retry later") from None

    # L4 Guardrail check on free-text complaint field
    is_safe, guardrail_msg = inspect_input_text(submission.complaint_text)
    if not is_safe:
        err = [{"loc": ["body", "complaint_text"], "type": "guardrail_violation", "msg": guardrail_msg}]
        try:
            conn.lpush("grievance:quarantine", json.dumps({"errors": err, "body": submission.model_dump(mode="json")}, default=str))
            conn.ltrim("grievance:quarantine", 0, 999)
        except RedisError:
            pass
        raise HTTPException(status_code=400, detail=guardrail_msg)

    try:
        with runtime.span("complaint.submit"):
            run_id=enqueue(conn,submission.model_dump(mode="json"),idempotency_key)
    except IdempotencyConflict:
        raise HTTPException(409,"Idempotency-Key was already used with a different complaint") from None
    except RedisError:
        raise HTTPException(503, "Queue unavailable; retry later") from None
    return JobAccepted(run_id=run_id, status="queued", status_url=f"/api/v1/grievances/{run_id}", result_url=f"/api/v1/grievances/{run_id}/result")


def find_job(run_id, conn):
    try:
        UUID(run_id)
    except ValueError:
        raise HTTPException(404, "Run not found") from None
    try:
        return Job.fetch(run_id, connection=conn)
    except NoSuchJobError:
        raise HTTPException(404, "Run not found or expired") from None
    except RedisError:
        raise HTTPException(503, "Job store unavailable") from None


@app.get("/api/v1/grievances/{run_id}", response_model=JobStatus)
def status(run_id: str, conn=Depends(redis_connection)):
    job = find_job(run_id, conn)
    try:
        state = job.get_status(refresh=True).value
    except RedisError:
        raise HTTPException(503, "Job store unavailable") from None
    error = "Processing failed; check worker logs using the run ID and resubmit after recovery." if state in ("failed", "stopped", "canceled") else None
    return JobStatus(run_id=run_id, status=state, error=error)


@app.get("/api/v1/grievances/{run_id}/result", response_model=RoutingDecision)
def result(run_id: str, conn=Depends(redis_connection)):
    job = find_job(run_id, conn)
    try:
        state = job.get_status(refresh=True).value
        if state in ("failed", "stopped", "canceled"):
            raise HTTPException(409, "Job failed; no verified routing result is available")
        if state != "finished":
            raise HTTPException(409, "Result is not ready; poll the status endpoint")
        return RoutingDecision.model_validate(job.return_value())
    except RedisError:
        raise HTTPException(503, "Job store unavailable") from None


@app.post("/api/v1/feedback", status_code=201, response_model=FeedbackReceipt)
def submit_feedback(feedback: FeedbackSubmission, conn=Depends(redis_connection)):
    """L6: Record live caller satisfaction and automated production quality score."""
    is_safe, guardrail_msg = inspect_input_text(feedback.reason)
    if not is_safe:
        raise HTTPException(status_code=400, detail=guardrail_msg)

    try:
        stored_raw = conn.get(f"grievance:outcome:{feedback.run_id}")
        quality_score = 0.75 if feedback.satisfactory else 0.25
        if stored_raw:
            outcome = json.loads(stored_raw)
            has_verified_citations = bool(outcome.get("regulatory_citations"))
            is_verified = outcome.get("reliability_status") == "verified"
            base = 0.5 if feedback.satisfactory else 0.1
            if is_verified:
                base += 0.25
            if has_verified_citations or outcome.get("routing") == "escalate_to_human":
                base += 0.20
            quality_score = round(min(1.0, base), 4)

        entry = {
            "run_id": feedback.run_id,
            "satisfactory": feedback.satisfactory,
            "reason": feedback.reason,
            "corrected_routing": feedback.corrected_routing,
            "automated_quality_score": quality_score,
            "recorded_at": time.time(),
        }
        conn.lpush("grievance:feedback", json.dumps(entry))
        conn.ltrim("grievance:feedback", 0, 999)
        conn.hincrby("grievance:feedback:stats", "satisfactory" if feedback.satisfactory else "unsatisfactory", 1)
        total = conn.llen("grievance:feedback")
        return FeedbackReceipt(
            run_id=feedback.run_id,
            recorded=True,
            automated_quality_score=quality_score,
            total_feedback_count=total,
        )
    except RedisError:
        raise HTTPException(503, "Feedback store unavailable") from None


@app.get("/api/v1/feedback/summary")
def feedback_summary(conn=Depends(redis_connection)):
    """L6: Aggregate live traffic feedback and automated quality scores."""
    try:
        entries = [json.loads(raw) for raw in conn.lrange("grievance:feedback", 0, 99)]
        sat = int(conn.hget("grievance:feedback:stats", "satisfactory") or 0)
        unsat = int(conn.hget("grievance:feedback:stats", "unsatisfactory") or 0)
        total = sat + unsat
        avg_score = round(sum(e["automated_quality_score"] for e in entries) / len(entries), 4) if entries else 0.0
        return {
            "total_feedback": total,
            "satisfactory_count": sat,
            "unsatisfactory_count": unsat,
            "satisfaction_rate": round(sat / total, 4) if total > 0 else 0.0,
            "avg_automated_quality_score": avg_score,
            "recent_samples": entries[:10],
        }
    except RedisError:
        raise HTTPException(503, "Feedback store unavailable") from None
