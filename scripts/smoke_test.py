"""Standard-library HTTP smoke test. Run inside the API container or on host."""
import argparse
import json
import time
import urllib.error
import urllib.request


def request(base, path, payload=None, expected=200):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base+path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status, content = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, content = error.code, error.read()
    assert status == expected, f"{path}: expected {expected}, got {status}: {content[:500]!r}"
    return json.loads(content) if content else None


def run(base, timeout):
    request(base, "/health")
    with urllib.request.urlopen(base+"/", timeout=10) as response:
        assert b"Investor Grievance Router" in response.read()
    request(base, "/api/v1/grievances", {"complaint_text": "tiny", "entity_name": "Test"}, 422)
    request(base, "/api/v1/grievances", {"complaint_text": "A synthetic complaint about bank service.", "entity_name": "Test", "approached_entity_first": True, "entity_complaint_date": "1202-01-01"}, 422)
    scenarios = [
        ("I invested in a fixed deposit through my bank's app. The interest credited is lower than what I was promised. I want to complain to SEBI.", "refer_to_other_regulator"),
        ("My mutual fund redemption proceeds haven't been paid for 3 weeks.", "assign_to_entity"),
        ("My health insurance claim was rejected and I need to complain.", "escalate_to_human"),
        ("My bank failed a UPI payment to my broker, and the broker also executed a trade I didn't authorise.", "escalate_to_human"),
    ]
    for text, expected in scenarios:
        job = request(base, "/api/v1/grievances", {"complaint_text": text, "entity_name": "Synthetic Example", "approached_entity_first": False}, 202)
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            state = request(base, job["status_url"])
            assert state["status"] not in ("failed", "stopped", "canceled"), state
            if state["status"] == "finished":
                break
            time.sleep(.5)
        else:
            raise AssertionError(f"Timeout waiting for {job['run_id']}")
        result = request(base, job["result_url"])
        assert result["routing"] == expected, result
        if expected == "refer_to_other_regulator":
            assert "Reserve Bank of India" in result["target_authority"]
            assert result["eligibility"] == "bank_first"
            assert "writing to the bank" in result["immediate_action"]
            required = {("SEBI-SCORES-2023", "5.3"), ("RBI-IOS-2021", "3(1)(j)"), ("RBI-IOS-2021", "9"), ("RBI-IOS-2021", "10(2)(a)")}
            assert required <= {(c["document_id"], c["section"]) for c in result["regulatory_citations"]}
            assert {e["agent"] for e in result["agent_trace"]} == {"investigator", "verifier"}
        if expected != "escalate_to_human":
            assert all(c["quote"] and c["page"] > 0 and len(c["sha256"]) == 64 for c in result["regulatory_citations"])
        print("PASS", job["run_id"], expected)
    print("PASS Phase 0 HTTP smoke test")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    run(args.base_url.rstrip("/"), args.timeout)
