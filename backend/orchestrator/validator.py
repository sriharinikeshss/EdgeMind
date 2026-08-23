"""
Validator — Phase 8 full implementation (M1/M3/M4/M5).

validate_answer() checks non-empty output and optional JSON schema conformance (Phase 3).
Phase 8 adds:
  - extract_claims() / verify_claim_against_sources() / calculate_grounding_score() /
    detect_unsupported_claims(): text-claim grounding against RAG source chunks
    (list[dict] with a "text" key) or a plain source string.
  - detect_hallucination_risk(): cross-checks claims against Phase 5's structured
    vision extraction (words/key_values/tags) instead of RAG text.
  - validate_calculations(): independently re-runs a calculation in the sandbox
    and diffs it against the model's stated result.
  - validate_artifact(): delegates to validation/artifact_validators.py — the
    format-specific + hash-integrity gate every generated artifact must pass.
  - llm_judge_grounding(): optional local-LLM grounding judge for ambiguous
    cases, used in place of / alongside the word-overlap heuristic.
"""
from __future__ import annotations
import json
import logging
import re

logger = logging.getLogger(__name__)

_MIN_CLAIM_WORDS = 4
_UNSUPPORTED_THRESHOLD = 0.3


class Validator:
    """
    Validates the agent's output before it is marked COMPLETED.

    Phase 3: minimal schema/format validation (validate_answer).
    Phase 8: grounding score, claim verification, calculation re-checking,
    artifact-format validators, and vision-hallucination detection.
    """

    # ── Phase 3 ──────────────────────────────────────────────────────────────

    def validate_answer(self, task_id: str, answer: str, expected_schema: dict | None = None) -> bool:
        """
        1. Answer must be non-empty.
        2. If expected_schema is provided and answer is JSON, validate structure.
        """
        if not answer or not answer.strip():
            logger.warning("Validation FAILED for task %s: empty answer", task_id)
            return False

        if expected_schema:
            try:
                data = json.loads(answer)
                for key in expected_schema.get("required", []):
                    if key not in data:
                        logger.warning("Validation FAILED task %s: missing key '%s'", task_id, key)
                        return False
            except (json.JSONDecodeError, TypeError):
                logger.warning("Validation FAILED task %s: answer is not valid JSON", task_id)
                return False

        logger.info("Validation PASSED for task %s", task_id)
        return True

    # ── Phase 8: claim grounding ─────────────────────────────────────────────

    def extract_claims(self, answer: str) -> list[str]:
        """Split model output into candidate factual claims: sentences long
        enough to assert something verifiable (short fragments/headings are dropped)."""
        if not answer or not answer.strip():
            return []
        sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
        return [s.strip() for s in sentences if s.strip() and len(s.strip().split()) >= _MIN_CLAIM_WORDS]

    def verify_claim_against_sources(self, claim: str, sources: list[dict] | str | None) -> float:
        """Word-overlap grounding score in [0, 1] for one claim against source
        text. `sources` may be RAG chunk dicts ({"text": ...}), a plain string
        (e.g. a rag_search step's already-formatted citation text), or None."""
        if not claim:
            return 0.0
        source_text = self._sources_to_text(sources)
        if not source_text.strip():
            return 0.0

        claim_words = {w for w in re.findall(r"[a-z0-9]+", claim.lower()) if len(w) > 2}
        source_words = {w for w in re.findall(r"[a-z0-9]+", source_text.lower()) if len(w) > 2}
        if not claim_words:
            return 0.0
        return round(min(len(claim_words & source_words) / len(claim_words), 1.0), 3)

    def calculate_grounding_score(self, claims: list[str], sources: list[dict] | str | None) -> float:
        """Aggregate grounding score across all claims. No claims made → trivially
        1.0 (there is nothing to fail grounding on)."""
        if not claims:
            return 1.0
        scores = [self.verify_claim_against_sources(c, sources) for c in claims]
        return round(sum(scores) / len(scores), 3)

    def detect_unsupported_claims(
        self, claims: list[str], sources: list[dict] | str | None, threshold: float = _UNSUPPORTED_THRESHOLD
    ) -> list[str]:
        return [c for c in claims if self.verify_claim_against_sources(c, sources) < threshold]

    @staticmethod
    def _sources_to_text(sources: list[dict] | str | None) -> str:
        if not sources:
            return ""
        if isinstance(sources, str):
            return sources
        if isinstance(sources, list):
            return " ".join((s.get("text", "") if isinstance(s, dict) else str(s)) for s in sources)
        return str(sources)

    def llm_judge_grounding(self, claim: str, sources: list[dict] | str | None) -> float:
        """Phase 8 (M2, optional): use the local reasoning model as an LLM-judge
        for grounding instead of word overlap, for ambiguous/borderline claims.
        Fully local (routed through ModelRegistry/Ollama) — no external calls."""
        from models.registry import registry, OLLAMA_REASONING_MODEL

        source_text = self._sources_to_text(sources)[:2000]
        if not source_text.strip() or not claim:
            return 0.0
        prompt = (
            "You are a strict fact-checking judge. Given SOURCE TEXT and a CLAIM, respond with ONLY "
            "a number between 0 and 1 — how well the SOURCE TEXT supports the CLAIM "
            "(1 = fully supported, 0 = not supported at all). No other text.\n\n"
            f"SOURCE TEXT:\n{source_text}\n\nCLAIM:\n{claim}\n\nScore:"
        )
        try:
            output, _ = registry.execute_prompt(OLLAMA_REASONING_MODEL, prompt)
            match = re.search(r"(\d(?:\.\d+)?)", output)
            return max(0.0, min(1.0, float(match.group(1)))) if match else 0.0
        except Exception as exc:
            logger.warning("llm_judge_grounding failed (%s); defaulting to 0.0", exc)
            return 0.0

    # ── Phase 8 (M4): vision hallucination detection ────────────────────────

    def detect_hallucination_risk(self, claims: list[str], visual_extraction: dict | None) -> list[str]:
        """Flag claims that assert a number/tag not present anywhere in Phase 5's
        structured extraction (words/key_values/component & instrument tags) —
        the anti-hallucination check for vision-grounded tasks."""
        if not claims:
            return []
        if not visual_extraction:
            return list(claims)

        evidence_text = " ".join(filter(None, [
            visual_extraction.get("full_text", ""),
            " ".join(f"{k} {v}" for k, v in (visual_extraction.get("key_values") or {}).items()),
            " ".join(c.get("tag", "") for c in (visual_extraction.get("components") or [])),
            " ".join(i.get("tag", "") for i in (visual_extraction.get("instruments") or [])),
        ])).lower()

        flagged = []
        for claim in claims:
            tokens = re.findall(r"[a-z0-9\-]{3,}", claim.lower())
            numeric_or_tag_tokens = [t for t in tokens if any(ch.isdigit() for ch in t)]
            if numeric_or_tag_tokens and not any(t in evidence_text for t in numeric_or_tag_tokens):
                flagged.append(claim)
        return flagged

    # ── Phase 8 (M1/M5): calculation re-checking ────────────────────────────

    def validate_calculations(self, code: str, stated_result: str, timeout_seconds: int = 10) -> dict:
        """Independently re-run `code` in the sandbox and diff its stdout against
        the model's stated_result (exact string match, or numeric match within
        tolerance). Returns a detail dict rather than a bare bool so the caller
        can feed the mismatch back into replan()."""
        from sandbox.manager import sandbox_manager

        result = sandbox_manager.execute_python(code, timeout_seconds=timeout_seconds)
        actual = (result.get("stdout") or "").strip()
        stated = (stated_result or "").strip()
        valid = bool(actual) and result.get("exit_code") == 0 and (actual == stated or self._numbers_match(actual, stated))
        return {
            "valid": valid,
            "actual_output": actual,
            "stated_result": stated,
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code"),
        }

    @staticmethod
    def _numbers_match(a: str, b: str, tol: float = 1e-6) -> bool:
        match_a = re.search(r"-?\d+(?:\.\d+)?", a)
        match_b = re.search(r"-?\d+(?:\.\d+)?", b)
        if not match_a or not match_b:
            return False
        return abs(float(match_a.group()) - float(match_b.group())) < tol

    # ── Phase 8 (M5): artifact-format validation ────────────────────────────

    def validate_artifact(self, artifact_meta: dict, required_sections: list[str] | None = None) -> dict:
        """Delegates to validation/artifact_validators.py — kept as a Validator
        method so callers only need one import for all Phase 8 checks."""
        from validation.artifact_validators import validate_artifact
        return validate_artifact(artifact_meta, required_sections=required_sections)
