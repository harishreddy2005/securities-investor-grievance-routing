"""Single aggregate exporter; scalable RQ workers write bounded Redis metric keys."""
import time
from prometheus_client import CollectorRegistry, start_http_server

from app.jobs import connection
from app.observability.metrics import WorkerCollector
from app.config import get_settings

if __name__ == "__main__":
    registry = CollectorRegistry()
    registry.register(WorkerCollector(connection, get_settings().queue_name))
    start_http_server(9101, registry=registry)
    while True:
        time.sleep(30)
