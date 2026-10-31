import json
import logging
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from redis.exceptions import RedisError
from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.config import get_settings
from app.guardrails.safety import inspect_input_text
from app.jobs import connection, process_grievance, queue, worker_available
from app.schemas import GrievanceSubmission, JobAccepted, JobStatus, RoutingDecision

app = FastAPI(title="Securities Investor Grievance Routing API", version="0.2.0")
logger = logging.getLogger(__name__)


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
def submit(submission: GrievanceSubmission, conn=Depends(redis_connection)):
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

    run_id = str(uuid4())
    settings = get_settings()
    try:
        queue(conn).enqueue(process_grievance, submission.model_dump(mode="json"), run_id,
                            job_id=run_id, result_ttl=settings.result_ttl,
                            failure_ttl=settings.result_ttl, ttl=settings.result_ttl)
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
