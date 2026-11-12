"""Deterministic, zero-key model substitute for the Phase 0/1/3 workflow.

The investigator and verifier call separate structured tasks. Supports both
v1_baseline (single-pass surface prompt) and v2_modifier_aware (multi-pass
product-vs-entity decomposition) prompt artifacts for L2/L3 evaluation.
"""
import re
import json
import time

import httpx
from pydantic import Field

from app.prompts.loader import load_prompt
from app.schemas import StrictModel


class Hypothesis(StrictModel):
    kind: str = Field(pattern=r"^(bank_fd|mutual_fund|mixed|unregulated|unknown)$")
    product: str
    entity_type: str


def stub_response(task: str, payload: dict) -> dict:
    if task == "investigate":
        text = payload["complaint_text"].lower()
        prompt_ver = payload.get("prompt_version", "v2")
        bank = bool(re.search(r"\bbank(?:ing|['’]s)?\b", text))

        # v1_baseline: Naive single-pass surface classifier (Before deliberate change, L2/L3).
        # Trusts the user's claimed named_regulator on surface text and lacks modifier decomposition.
        if prompt_ver == "v1":
            if payload.get("named_regulator") == "SEBI" and bank and "complain to sebi" in text:
                return dict(kind="unknown", product="surface regulator conflict", entity_type="not established")
            if bank and "fixed deposit" in text and "interest" in text and "promised" in text and payload.get("named_regulator") != "SEBI":
                return dict(kind="bank_fd", product="bank fixed deposit", entity_type="bank")
            if "mutual fund" in text and "redemption" in text and not bank:
                return dict(kind="mutual_fund", product="mutual fund redemption", entity_type="amc")
            return dict(kind="unknown", product="not established", entity_type="not established")

        # v2_modifier_aware: Multi-pass structural decomposition (After deliberate change, L2/L3).
        fd = any(word in text for word in ("fixed deposit", "term deposit", "recurring deposit"))
        securities = any(word in text for word in ("broker", "mutual fund", "trade", "demat", "shares"))
        unregulated = any(word in text for word in ("crypto", "bitcoin", "ethereum", "chit fund", "real estate plot", "forex betting", "algorithmic trading bot"))
        if unregulated:
            return dict(kind="unregulated", product="unregulated financial product", entity_type="outside corpus")
        # Check if bank is explicitly phrased as destination of proceeds rather than respondent
        is_bank_destination = "to my bank" in text or "into my bank" in text or "in my bank account" in text
        if ('bank statement' in text and 'no neft arrived from the amc' in text
            and not re.search(r'bank\s+(?:also\s+|has\s+)?(?:failed|refused|blocked)',text)):
            is_bank_destination=True
        if bank and securities and not is_bank_destination:
            return dict(kind="mixed", product="multiple or ambiguous products", entity_type="multiple or uncertain")
        shortfall = any(word in text for word in ("lower", "less", "shortfall", "underpaid", "difference"))
        promised = any(word in text for word in ("promised", "agreed", "contracted"))
        # Commercial rate-setting complaints fall under RBI-IOS Clause 10(1)(a) exclusion
        commercial_decision = "want a higher" in text or "new rate is lower" in text
        deposit_return = 'interest' in text or 'maturity payout' in text or bool(re.search(r'\d+(?:\.\d+)?%\s*p\.?a\.?',text))
        if bank and fd and deposit_return and (shortfall or promised) and not commercial_decision:
            return dict(kind="bank_fd", product="bank fixed/term/recurring deposit", entity_type="bank")
        mf_redemption = any(word in text for word in ("redemption", "repurchase", "proceeds", "systematic withdrawal"))
        if "mutual fund" in text and mf_redemption:
            return dict(kind="mutual_fund", product="mutual fund redemption", entity_type="amc")
        return dict(kind="unknown", product="not established", entity_type="not established")
    if task == "verify":
        # The verifier confirms a candidate whose mechanical evidence audit succeeded.
        return {"supported": bool(payload["evidence_valid"])}
    raise ValueError("Unknown model task")


class Model:
    def __init__(self, settings):
        self.settings = settings
        self.prompt = load_prompt(getattr(settings, "prompt_version", "v2_modifier_aware"))
        if settings.llm_provider != "stub":
            raise ValueError("Phase 0 supports LLM_PROVIDER=stub only")
        self.url = settings.llm_stub_url.rstrip("/")

    def call(self, task: str, payload: dict) -> dict:
        from app.observability import runtime
        from app.audit import append
        from app.eval.cost_tracker import global_cost_tracker
        call_payload={**payload,"prompt_version":self.prompt.version,
                      "system_prompt":self.prompt.system_prompt,
                      "task_prompt":self.prompt.investigate_prompt if task=='investigate' else self.prompt.verify_prompt}
        def measured(function):
            started=time.monotonic()
            response=None
            outcome='error'
            try:
                response=function()
                outcome='success'
                return response
            finally:
                activity=runtime.agent_activity.get()
                agent=activity['agent'] if activity else ('investigator' if task=='investigate' else 'verifier')
                action='product_entity_hypothesis' if task=='investigate' else 'audit_handoff'
                global_cost_tracker.record_step(runtime.run_id.get() or 'direct',agent,action,
                    json.dumps(call_payload,sort_keys=True),json.dumps(response,sort_keys=True) if response is not None else '')
                append('model_call',{'agent':agent,'task':task,'prompt_version':self.prompt.version,
                    'prompt_sha256':self.prompt.sha256,'duration_seconds':time.monotonic()-started,
                    'outcome':outcome,'request':call_payload,'response':response})
        if not self.url:
            return measured(lambda:stub_response(task,call_payload))
        from redis import Redis
        from redis.exceptions import RedisError
        from app.reliability import CircuitBreaker, DependencyFailure, retry_call
        from app.observability.runtime import carrier, correlation_id
        conn = Redis.from_url(self.settings.redis_url, socket_connect_timeout=self.settings.redis_timeout, socket_timeout=self.settings.redis_timeout)
        breaker = CircuitBreaker(conn, self.settings)
        try:
            token = breaker.acquire()
        except RedisError:
            raise DependencyFailure("unavailable", "llm") from None

        def invoke():
            response = httpx.post(self.url + "/infer", json={"task": task, "payload": call_payload},
                                  timeout=self.settings.llm_timeout, headers={**carrier(), "X-Correlation-ID": correlation_id.get()})
            response.raise_for_status()
            body = response.json()
            if task == "investigate":
                Hypothesis.model_validate(body)
            elif task == "verify" and (not isinstance(body, dict) or type(body.get("supported")) is not bool):
                raise ValueError("Malformed verifier response")
            return body

        try:
            value = retry_call(lambda:measured(invoke), "llm", self.settings, self.settings.llm_timeout)
        except DependencyFailure:
            try:
                breaker.finish(False, token)
            except RedisError:
                pass
            raise
        try:
            breaker.finish(True, token)
        except RedisError:
            raise DependencyFailure("unavailable", "llm") from None
        return value
