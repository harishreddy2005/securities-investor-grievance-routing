"""Developer-only HTTP smoke harness when Docker is unavailable.

Uses fakeredis's TCP server and RQ SimpleWorker, not the production Redis daemon
or process-isolated Docker worker. Installs require requirements-dev.txt.
"""
import concurrent.futures
import argparse
from contextlib import nullcontext
import os
from pathlib import Path
import socket
import sys
import threading
import time

# Also permit invoking this script directly from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fakeredis
import uvicorn
from rq import SimpleWorker
from rq.timeouts import TimerDeathPenalty

from scripts.smoke_test import run
from scripts.smoke_test import request as smoke_request


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class LocalWorker(SimpleWorker):
    death_penalty_class = TimerDeathPenalty


def main(semantic=False):
    redis_server = fakeredis.TcpFakeServer(("127.0.0.1", 0), server_type="redis")
    redis_server.daemon_threads = True
    redis_server.block_on_close = False
    redis_thread = threading.Thread(target=redis_server.serve_forever, daemon=True)
    redis_thread.start()
    api_port, stub_port = free_port(), free_port()
    servers = []
    # Keep the development index under ignored data/: Windows retains native
    # vector-index file handles until process exit, so in-process deletion fails.
    index_path = "data/local-e2e-semantic" if semantic else "data/local-e2e"
    with nullcontext(str(Path(index_path).resolve())) as directory:
        os.environ.update(REDIS_URL=f"redis://127.0.0.1:{redis_server.server_address[1]}/0",
                          INDEX_DIR=directory, CORPUS_DIR="corpus/raw",
                          EMBEDDING_PROVIDER="chroma" if semantic else "test_hash", LLM_PROVIDER="stub",
                          EMBEDDING_CACHE_DIR="data/models",
                          ANONYMIZED_TELEMETRY="False",
                          LLM_STUB_URL=f"http://127.0.0.1:{stub_port}", STUB_FAIL="false")
        from app.config import get_settings
        from app.jobs import connection, queue
        from app.rag.ingest import ingest
        get_settings.cache_clear()
        ingest(get_settings())
        for target, port in [("app.main:app", api_port), ("app.stub:app", stub_port)]:
            server = uvicorn.Server(uvicorn.Config(target, host="127.0.0.1", port=port, log_level="warning"))
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            servers.append((server, thread))
        try:
            deadline = time.monotonic()+15
            while not all(s.started for s, _ in servers):
                if time.monotonic() > deadline:
                    raise RuntimeError("Local HTTP servers did not start")
                time.sleep(.05)
            conn = connection()
            worker = LocalWorker([queue(conn)], connection=conn)
            def ready_then_smoke():
                deadline = time.monotonic()+10
                while time.monotonic() < deadline:
                    try:
                        smoke_request(f"http://127.0.0.1:{api_port}", "/health")
                        break
                    except AssertionError:
                        time.sleep(.1)
                run(f"http://127.0.0.1:{api_port}", 45)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(ready_then_smoke)
                worker.work(burst=False, max_jobs=4, max_idle_time=15, logging_level="WARNING")
                future.result(timeout=60)
            print(f"Local HTTP e2e passed ({'semantic' if semantic else 'test'} embeddings + TCP fakeredis + SimpleWorker).")
        finally:
            for server, thread in servers:
                server.should_exit = True
                thread.join(timeout=5)
            redis_server.shutdown()
            redis_server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--semantic", action="store_true", help="Use actual local semantic embeddings; first use downloads weights")
    main(parser.parse_args().semantic)
