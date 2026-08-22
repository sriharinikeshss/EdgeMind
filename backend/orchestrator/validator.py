"""
Validator — Phase 3 minimal implementation (M1).

validate_answer() checks non-empty output and optional JSON schema conformance.
Phase 8 will add full grounding score and claim verification.
"""
from __future__ import annotations
import json
import logging

logger = logging.getLogger(__name__)


class Validator:
    """
    Validates the agent's output before it is marked COMPLETED.

    Phase 3: minimal schema/format validation.
    Phase 8: full grounding score, claim verification, artifact validators.
    """

    def validate_answer(self, task_id: str, answer: str, expected_schema: dict | None = None) -> bool:
        """
        Phase 3 check:
        1. Answer must be non-empty.
        2. If expected_schema is provided and answer is JSON, validate structure.
        Returns True if valid, False otherwise.
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
                # If schema is expected but answer isn't valid JSON, fail
                logger.warning("Validation FAILED task %s: answer is not valid JSON", task_id)
                return False

        logger.info("Validation PASSED for task %s", task_id)
        return True

    def extract_claims(self, answer: str) -> list[str]:
        """TODO Phase 8: extract verifiable claims from the answer."""
        raise NotImplementedError("Claim extraction implemented in Phase 8.")

    def verify_claim_against_sources(self, claim: str, sources: list[dict]) -> float:
        """TODO Phase 8: return a grounding score [0, 1] for a single claim."""
        raise NotImplementedError("Claim verification implemented in Phase 8.")

    def calculate_grounding_score(self, claims: list[str], sources: list[dict]) -> float:
        """TODO Phase 8: aggregate grounding score across all claims."""
        raise NotImplementedError("Grounding score implemented in Phase 8.")

    def detect_unsupported_claims(self, claims: list[str], sources: list[dict]) -> list[str]:
        """TODO Phase 8: return claims that have no source support."""
        raise NotImplementedError("Unsupported claim detection implemented in Phase 8.")
