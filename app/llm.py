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
        fd = any(word in text for word in ("fixed deposit", "term deposit", "recurring deposit"))
        securities = any(word in text for word in ("broker", "mutual fund", "trade", "demat", "shares"))
        # Unregulated or out-of-corpus products (F7)
        unregulated = any(word in text for word in ("crypto", "bitcoin", "ethereum", "chit fund", "real estate plot", "forex betting", "algorithmic trading bot"))
        if unregulated:
            return dict(kind="unregulated", product="unregulated financial product", entity_type="outside corpus")
        # Check if bank is simply the destination of proceeds rather than the respondent
        is_bank_destination = "to my bank" in text or "into my bank" in text or "in my bank account" in text
        if bank and securities and not is_bank_destination:
            return dict(kind="mixed", product="multiple or ambiguous products", entity_type="multiple or uncertain")
        shortfall = any(word in text for word in ("lower", "less", "shortfall", "underpaid", "difference"))
        promised = any(word in text for word in ("promised", "agreed", "contracted"))
        # A dispute seeking a higher commercial interest rate without prior contractual promise is commercial judgment
        commercial_decision = "want a higher" in text or "new rate is lower" in text
        if bank and fd and "interest" in text and (shortfall or promised) and not commercial_decision:
            return dict(kind="bank_fd", product="bank fixed/term/recurring deposit", entity_type="bank")
        mf_redemption = any(word in text for word in ("redemption", "repurchase", "proceeds", "systematic withdrawal"))
        if "mutual fund" in text and mf_redemption:
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
