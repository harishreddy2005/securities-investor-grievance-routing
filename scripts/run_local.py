"""Run the Securities Investor Grievance Routing app locally without Docker.

Starts:
1. Deterministic LLM stub on http://127.0.0.1:8001
2. FastAPI app and Web UI on http://127.0.0.1:8000
3. Background RQ worker processing the grievance queue via in-memory FakeRedis
"""
import argparse
from pathlib import Path
import os
import sys
import threading
import time
from unittest.mock import patch

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import fakeredis
from redis import Redis
from rq import SimpleWorker
from rq.timeouts import TimerDeathPenalty
import uvicorn

from app.worker_registration import RegistrationMixin


class LocalWorker(RegistrationMixin, SimpleWorker):
    death_penalty_class = TimerDeathPenalty


def main():
    parser = argparse.ArgumentParser(description="Run the grievance routing app locally")
    parser.add_argument("--port", type=int, default=8000, help="Web UI and API port (default: 8000)")
    parser.add_argument("--stub-port", type=int, default=8001, help="LLM stub port (default: 8001)")
    parser.add_argument("--semantic", action="store_true", default=True, help="Use semantic ONNX embeddings (default: True)")
    parser.add_argument("--test-hash", dest="semantic", action="store_false", help="Use lightweight test hash embeddings")
    args = parser.parse_args()

    # Shared in-memory Redis instance
    redis_server = fakeredis.FakeServer()
    redis_patch = patch.object(Redis, "from_url", side_effect=lambda *a, **k: fakeredis.FakeRedis(server=redis_server))
    redis_patch.start()

    # Select index path
    if args.semantic:
        if (REPO_ROOT / "data/semantic-index/manifest.json").exists():
            index_path = str(REPO_ROOT / "data/semantic-index")
        else:
            index_path = str(REPO_ROOT / "data/local-e2e-semantic")
        provider = "chroma"
    else:
        index_path = str(REPO_ROOT / "data/local-e2e")
        provider = "test_hash"

    os.environ.update(
        REDIS_URL="redis://localhost:6379/0",
        QUEUE_NAME="grievances",
        INDEX_DIR=index_path,
        CORPUS_DIR=str(REPO_ROOT / "corpus/raw"),
        EMBEDDING_PROVIDER=provider,
        LLM_PROVIDER="stub",
        EMBEDDING_CACHE_DIR=str(REPO_ROOT / "data/models"),
        ANONYMIZED_TELEMETRY="False",
        TELEMETRY_ENABLED="false",
        LLM_STUB_URL=f"http://127.0.0.1:{args.stub_port}",
        STUB_FAIL="false",
    )

    from app.config import get_settings
    from app.jobs import connection, queue
    from app.rag.ingest import ingest

    get_settings.cache_clear()
    settings = get_settings()

    print(f"[*] Checking/preparing corpus index at {index_path} ({provider})...")
    ingest(settings)
    print("[+] Corpus index ready.")

    # Start LLM stub in a daemon thread
    stub_server = uvicorn.Server(uvicorn.Config("app.stub:app", host="127.0.0.1", port=args.stub_port, log_level="warning"))
    stub_thread = threading.Thread(target=stub_server.run, daemon=True)
    stub_thread.start()

    # Start background RQ worker
    conn = connection()
    worker = LocalWorker([queue(conn)], connection=conn)
    worker._install_signal_handlers = lambda: None
    worker_thread = threading.Thread(target=lambda: worker.work(burst=False, logging_level="WARNING"), daemon=True)
    worker_thread.start()
    print("[+] Background grievance worker started.")

    # Start API server in main thread
    print("\n" + "=" * 60)
    print("  Securities Investor Grievance Router is running!")
    print(f"  Web UI:        http://localhost:{args.port}")
    print(f"  API Docs:      http://localhost:{args.port}/docs")
    print(f"  Health Check:  http://localhost:{args.port}/health")
    print("  Press Ctrl+C to stop.")
    print("=" * 60 + "\n")

    api_server = uvicorn.Server(uvicorn.Config("app.main:app", host="0.0.0.0", port=args.port, log_level="info"))
    try:
        api_server.run()
    except (KeyboardInterrupt, SystemExit):
        print("\nStopping servers...")
    finally:
        redis_patch.stop()


if __name__ == "__main__":
    main()
