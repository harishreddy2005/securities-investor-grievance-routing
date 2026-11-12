from socket import gethostname
from datetime import datetime, timezone

from rq import Worker
from app.jobs import connection


def healthy_worker(conn, hostname, now=None):
    now=now or datetime.now(timezone.utc)
    return any((w.name==hostname or w.name.startswith(hostname+":"))
               and w.last_heartbeat and 0 <= (now-w.last_heartbeat).total_seconds() < 120
               and bool(w.queue_names())
               for w in Worker.all(connection=conn))


if __name__ == "__main__":
    conn = connection()
    conn.ping()
    raise SystemExit(0 if healthy_worker(conn,gethostname()) else 1)
