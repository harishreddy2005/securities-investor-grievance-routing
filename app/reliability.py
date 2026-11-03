"""Bounded retry/deadline policy and Redis-shared circuit breaker."""
import contextvars
import json
import queue
import random
import threading
import time
from uuid import uuid4

import httpx
from redis.exceptions import WatchError

from app.observability.runtime import event, span, agent_activity
from app.observability.metrics import count


class DependencyFailure(RuntimeError):
    def __init__(self, code, dependency):
        self.code, self.dependency = code, dependency
        super().__init__(f"{dependency}: {code}")


def classify(error):
    if isinstance(error, DependencyFailure):
        return error.code
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "timeout"
    if isinstance(error, httpx.HTTPStatusError):
        return "unavailable" if error.response.status_code in {408,429,500,502,503,504} else "invalid_response"
    if isinstance(error, (httpx.TransportError, ConnectionError, OSError)):
        return "unavailable"
    if isinstance(error, (ValueError, TypeError, KeyError)):
        return "invalid_response"
    return "internal_error"


def deadline_call(function, seconds):
    """Caller deadline; daemon work cannot prevent job process exit after timeout."""
    output = queue.Queue(maxsize=1)
    context = contextvars.copy_context()
    def work():
        try:
            output.put((True, context.run(function)))
        except Exception as error:
            output.put((False, error))
    threading.Thread(target=work, daemon=True).start()
    try:
        ok, value = output.get(timeout=seconds)
    except queue.Empty:
        raise TimeoutError("Dependency deadline exceeded") from None
    if not ok:
        raise value
    return value


def retry_call(function, dependency, settings, timeout, *, sleep=time.sleep, jitter=random.uniform):
    for attempt in range(settings.dependency_retries+1):
        with span("dependency."+dependency, dependency=dependency, attempt=attempt+1) as current:
            try:
                return deadline_call(function, timeout)
            except Exception as error:
                code = classify(error)
                current.set_attribute("error_code",code)
                event("dependency_failed", dependency=dependency, attempt=attempt+1, error_code=code)
                if code not in {"timeout","unavailable"} or attempt == settings.dependency_retries:
                    raise DependencyFailure(code, dependency) from None
        count("retries",dependency)
        activity = agent_activity.get()
        if activity:
            count("agent_retries",activity["agent"]+":"+dependency)
        delay = min(settings.retry_cap_seconds, settings.retry_base_seconds * 2**attempt)
        sleep(min(settings.retry_cap_seconds,delay + jitter(0, delay*.25)))


class CircuitBreaker:
    key = "grievance:circuit:llm"

    def __init__(self, conn, settings, clock=time.time):
        self.conn, self.settings, self.clock = conn, settings, clock

    def acquire(self):
        for _ in range(8):
            try:
                with self.conn.pipeline() as pipe:
                    pipe.watch(self.key)
                    raw = pipe.get(self.key)
                    state = json.loads(raw) if raw else {"state":"CLOSED","failures":0,"retry_at":0}
                    now = self.clock()
                    if state["state"] in {"OPEN","HALF_OPEN"}:
                        if now < state["retry_at"]:
                            raise DependencyFailure("circuit_open","llm")
                        token = str(uuid4())
                        state.update(state="HALF_OPEN", token=token, retry_at=now+self.settings.llm_timeout*(self.settings.dependency_retries+1)+10)
                        pipe.multi()
                        pipe.set(self.key,json.dumps(state))
                        pipe.execute()
                        count("circuit_transitions","HALF_OPEN")
                        event("circuit_transition",dependency="llm",state="HALF_OPEN")
                        return token
                    return None
            except WatchError:
                continue
        raise DependencyFailure("unavailable","llm")

    def finish(self, success, token=None):
        for _ in range(8):
            try:
                with self.conn.pipeline() as pipe:
                    pipe.watch(self.key)
                    raw=pipe.get(self.key)
                    state=json.loads(raw) if raw else {"state":"CLOSED","failures":0,"retry_at":0}
                    previous_state=state["state"]
                    if token is not None and state["state"] != "HALF_OPEN":
                        return
                    if state["state"] == "HALF_OPEN" and state.get("token") != token:
                        return
                    # A late success from an earlier CLOSED call must not close OPEN.
                    if state["state"] == "OPEN":
                        return
                    if success:
                        state={"state":"CLOSED","failures":0,"retry_at":0}
                    else:
                        failures=state["failures"]+1
                        opened=token is not None or failures>=self.settings.circuit_failure_threshold
                        state={"state":"OPEN" if opened else "CLOSED", "failures":failures,
                               "retry_at":self.clock()+self.settings.circuit_cooldown_seconds if opened else 0}
                    pipe.multi()
                    pipe.set(self.key,json.dumps(state))
                    pipe.execute()
                    if state["state"] != previous_state:
                        count("circuit_transitions",state["state"])
                    event("circuit_transition",dependency="llm",state=state["state"])
                    return
            except WatchError:
                continue
        raise DependencyFailure("unavailable","llm")
