"""
Validator — Phase 0 scaffold (M1).

In Phase 3 a minimal validate_answer() (non-empty, schema check) is added.
In Phase 8 the full grounding/calculation/artifact-specific validators are wired.
"""
from __future__ import annotations


class Validator:
    """
    Validates the agent's output before it is marked COMPLETED.

    Phase 1: not used.
    Phase 3: minimal schema/format validation.
    Phase 8: full grounding score, claim verification, artifact validators.
    """

    def validate_answer(self, task_id: str, answer: str, expected_schema: dict | None = None) -> bool:
        """
        Phase 3 minimal check: answer is non-empty.
        Phase 8 adds grounding score threshold.
        """
        raise NotImplementedError("Minimal validator implemented in Phase 3.")

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
