"""Deterministic, zero-key model substitute for the Phase 0 demo.

The investigator and verifier call separate structured tasks. Real provider
adapters and broader classification are subsequent phases, not silent fallbacks.
"""
import re

import httpx
from pydantic import Field

from app.schemas import StrictModel


class Hypothesis(StrictModel):
    kind: str = Field(pattern=r"^(bank_fd|mutual_fund|mixed|unregulated|unknown)$")
    product: str
    entity_type: str


def stub_response(task: str, payload: dict) -> dict:
    if task == "investigate":
        text = payload["complaint_text"].lower()
        bank = bool(re.search(r"\bbank(?:ing|['’]s)?\b", text))
        fd = "fixed deposit" in text or "term deposit" in text
        securities = any(word in text for word in ("broker", "mutual fund", "trade", "demat", "shares"))
        # Unregulated or out-of-corpus products (F7)
        unregulated = any(word in text for word in ("crypto", "bitcoin", "ethereum", "chit fund", "real estate plot"))
        if unregulated:
            return dict(kind="unregulated", product="unregulated financial product", entity_type="outside corpus")
        if bank and securities:
            return dict(kind="mixed", product="multiple or ambiguous products", entity_type="multiple or uncertain")
        shortfall = any(word in text for word in ("lower", "less", "shortfall", "underpaid"))
        promised = any(word in text for word in ("promised", "agreed", "contracted"))
        if bank and fd and "interest" in text and shortfall and promised:
            return dict(kind="bank_fd", product="bank fixed deposit", entity_type="bank")
        if "mutual fund" in text and "redemption" in text and not bank:
            return dict(kind="mutual_fund", product="mutual fund redemption", entity_type="amc")
        return dict(kind="unknown", product="not established", entity_type="not established")
    if task == "verify":
        # The stub only confirms a candidate whose mechanical evidence audit
        # succeeded. It never supplies regulatory excerpts or clause identifiers.
        return {"supported": bool(payload["evidence_valid"])}
    raise ValueError("Unknown model task")


class Model:
    def __init__(self, settings):
        if settings.llm_provider != "stub":
            raise ValueError("Phase 0 supports LLM_PROVIDER=stub only")
        self.url = settings.llm_stub_url.rstrip("/")

    def call(self, task: str, payload: dict) -> dict:
        if not self.url:
            return stub_response(task, payload)
        response = httpx.post(self.url + "/infer", json={"task": task, "payload": payload}, timeout=20)
        response.raise_for_status()
        return response.json()
