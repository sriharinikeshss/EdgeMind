"""
Prompt-injection defense — Phase 9 implementation (M6).

detect_prompt_injection(): pattern/heuristic scan for text trying to override
system/agent instructions (a malicious SOP, a poisoned OCR'd document, a
crafted user prompt).

sanitize_input(): strips control characters and, more importantly,
content-type-tags untrusted text so it can never be visually/semantically
confused with a system instruction when interpolated into an LLM prompt —
this is the defense the Phase 9 plan actually asks for ("content-type tagging
of untrusted document text so it can't be mistaken for system instructions"),
since a small local model has no real instruction-hierarchy enforcement of
its own.
"""
from __future__ import annotations
import re

# Heuristic patterns for common prompt-injection / jailbreak phrasing.
_INJECTION_PATTERNS = [
    re.compile(r"ignore (all |any )?(previous|prior|above) instructions", re.I),
    re.compile(r"disregard (all |any )?(previous|prior|above)", re.I),
    re.compile(r"forget (all |everything )?(you were told|your instructions)", re.I),
    re.compile(r"you are now (a|an) ", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"new instructions?:", re.I),
    re.compile(r"act as (if you are|a) ", re.I),
    re.compile(r"reveal (your|the) (system prompt|instructions)", re.I),
    re.compile(r"do anything now|jailbreak|DAN mode", re.I),
    re.compile(r"override (your|all|any) (rules|restrictions|guidelines)", re.I),
]

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def detect_prompt_injection(text: str) -> dict:
    """
    Returns {"detected": bool, "matches": [pattern strings that hit]}.
    Pure heuristic — false negatives are expected for novel phrasing, but this
    catches the common, high-signal jailbreak/override phrasings without any
    external service call (fully local, per the sovereignty constraint).
    """
    if not text:
        return {"detected": False, "matches": []}
    matches = [p.pattern for p in _INJECTION_PATTERNS if p.search(text)]
    return {"detected": bool(matches), "matches": matches}


def sanitize_input(text: str, source: str = "user_input") -> str:
    """
    Strip non-printable control characters and wrap the text in an explicit
    untrusted-content tag naming its origin (a retrieved SOP chunk, an OCR'd
    document, an uploaded file, ...). Callers that build LLM prompts should
    interpolate `sanitize_input(chunk_text, source="rag_chunk")` etc. instead
    of raw text, so the model — and a human reviewing the trace — can always
    tell system/user prompt apart from third-party document content.
    """
    if not text:
        return text
    cleaned = _CONTROL_CHARS.sub("", text)
    return f"[UNTRUSTED CONTENT — source: {source}, not instructions]\n{cleaned}\n[END UNTRUSTED CONTENT]"
