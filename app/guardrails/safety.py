import re
from typing import Tuple


INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"system\s*prompt",
    r"you\s+are\s+now\s+(an?|a\s+new)\s+",
    r"jailbreak",
    r"dan\s+mode",
    r"prompt\s+injection",
    r"bypass\s+(the\s+)?guardrails?",
    r"act\s+as\s+a\s+developer",
    r"reveal\s+(all\s+)?secret",
    r"override\s+(all\s+)?rules",
]

INJECTION_REGEX = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

# Basic profanity / toxicity filter keywords
TOXIC_PATTERNS = [
    r"\bfuck\b",
    r"\bshit\b",
    r"\bbitch\b",
    r"\basshole\b",
    r"\bbastard\b",
    r"\bkill\s+yourself\b",
    r"\bhate\s+speech\b",
]

TOXIC_REGEX = re.compile("|".join(TOXIC_PATTERNS), re.IGNORECASE)

# Disallowed model output actions: system must never award money, promise refund, or formally dispose of complaint
UNAUTHORIZED_OUTPUT_PATTERNS = [
    r"claim\s+(is\s+)?approved\s+for\s+payout",
    r"awarding\s+compensation\s+of",
    r"refund\s+(is\s+)?guaranteed",
    r"complaint\s+(is\s+)?hereby\s+disposed",
    r"we\s+have\s+settled\s+the\s+dispute",
]

UNAUTHORIZED_OUTPUT_REGEX = re.compile("|".join(UNAUTHORIZED_OUTPUT_PATTERNS), re.IGNORECASE)


def inspect_input_text(text: str) -> Tuple[bool, str]:
    """
    Checks free-text fields for Prompt Injection (L4) and Toxic content.
    Returns (is_safe, failure_reason).
    """
    if not text:
        return True, ""
    
    if INJECTION_REGEX.search(text):
        return False, "Prompt injection attempt detected: text attempts to override system instructions."

    if TOXIC_REGEX.search(text):
        return False, "Toxic or abusive language detected in complaint text."

    return True, ""


def inspect_output_decision(rationale: str, immediate_action: str) -> Tuple[bool, str]:
    """
    Checks generated response fields to verify that the system is not issuing
    unauthorized determinations (disposals, monetary compensations, or binding awards).
    Returns (is_safe, failure_reason).
    """
    combined = f"{rationale} {immediate_action}"
    if UNAUTHORIZED_OUTPUT_REGEX.search(combined):
        return False, "Output violated authority boundary: system cannot dispose complaints or award payouts directly."

    return True, ""
