from socket import gethostname
from datetime import datetime, timezone

from rq import Worker
from app.jobs import connection

if __name__ == "__main__":
    conn = connection()
    conn.ping()
    worker = Worker.find_by_key("rq:worker:" + gethostname(), connection=conn)
    healthy = worker and worker.last_heartbeat and (datetime.now(timezone.utc)-worker.last_heartbeat).total_seconds() < 120
    raise SystemExit(0 if healthy else 1)
