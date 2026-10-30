import os
import time
from typing import Literal

from fastapi import FastAPI, HTTPException

from app.llm import stub_response
from app.schemas import StrictModel

app = FastAPI(title="Phase 0 deterministic model stub")


class Inference(StrictModel):
    task: Literal["investigate", "verify"]
    payload: dict


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/infer")
def infer(request: Inference):
    if os.getenv("STUB_FAIL", "false").lower() == "true":
        raise HTTPException(503, "Stub failure injection enabled")
    time.sleep(min(max(float(os.getenv("STUB_DELAY_SECONDS", "0.1")), 0), 10))
    return stub_response(request.task, request.payload)
