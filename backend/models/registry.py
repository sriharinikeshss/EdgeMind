"""
Model Registry — Phase 1 implementation.

Talks to a local Ollama instance (OpenAI-compatible endpoint).
Falls back to a mock response if Ollama is not reachable (dev/CI convenience).

Ollama endpoint: POST http://ollama:11434/api/generate
"""
import os
import time
import logging
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")  # default reasoning model
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))


class TaskRequest(BaseModel):
    prompt: str


class TaskResponse(BaseModel):
    task_id: str
    status: str
    response: str
    model_used: str
    latency_ms: float = 0.0


class ModelRegistry:
    """
    Phase 1: single model, no routing yet.
    Phase 2 will add route_task(), score_models(), check_vram_capacity() etc.
    """

    def route_task(self, prompt: str) -> str:
        """Always returns the default reasoning model in Phase 1."""
        return OLLAMA_MODEL

    def execute_prompt(self, model_id: str, prompt: str) -> tuple[str, float]:
        """
        Call Ollama /api/generate.
        Returns (response_text, latency_ms).
        Falls back to a mock if Ollama is unreachable.
        """
        payload = {
            "model": model_id,
            "prompt": prompt,
            "stream": False,
        }
        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
                resp = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
                latency_ms = (time.monotonic() - t0) * 1000
                response_text = data.get("response", "").strip()
                logger.info("Ollama responded in %.0f ms (model=%s)", latency_ms, model_id)
                return response_text, latency_ms
        except Exception as exc:  # noqa: BLE001
            latency_ms = (time.monotonic() - t0) * 1000
            logger.warning(
                "Ollama unreachable (%s). Using mock fallback. Latency so far: %.0f ms",
                exc,
                latency_ms,
            )
            mock_text = (
                f"[MOCK — Ollama not running] "
                f"Response from {model_id} for prompt: '{prompt[:80]}...'"
            )
            return mock_text, latency_ms


# Module-level singleton
registry = ModelRegistry()

