"""Run with python -m app.worker (Linux Docker uses RQ process isolation)."""
import logging

from rq import SpawnWorker
from socket import gethostname

from app.jobs import connection, queue, resources


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    resources()  # Fail startup explicitly if index or model configuration is invalid.
    conn = connection()
    # Idle dequeue/heartbeat must remain shorter than readiness's 120s window.
    SpawnWorker([queue(conn)], connection=conn, name=gethostname(), worker_ttl=60).work()
