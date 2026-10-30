"""RQ persists queued payloads, status, failures, and results in Redis."""
import json
import logging
from functools import lru_cache

from redis import Redis
from rq import Queue, Worker

from app.config import get_settings

logger = logging.getLogger(__name__)


def connection():
    return Redis.from_url(get_settings().redis_url, socket_connect_timeout=3, socket_timeout=5)


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


def process_grievance(payload: dict, run_id: str):
    from app.schemas import GrievanceSubmission, RoutingDecision
    logger.info(json.dumps({"event": "job_started", "run_id": run_id}))
    try:
        request = GrievanceSubmission.model_validate(payload)
        state = resources().invoke({"request": request.model_dump(mode="json")}, {"recursion_limit": 6})
        result = RoutingDecision.model_validate(state["result"]).model_dump(mode="json")
        logger.info(json.dumps({"event": "job_finished", "run_id": run_id, "routing": result["routing"]}))
        return result
    except Exception:
        logger.exception(json.dumps({"event": "job_failed", "run_id": run_id}))
        # RQ records the failure; an error must never become a successful route.
        raise


def worker_available(conn):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return any(w.last_heartbeat and (now-w.last_heartbeat).total_seconds() < 120
               for w in Worker.all(connection=conn) if get_settings().queue_name in w.queue_names())
