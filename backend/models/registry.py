"""
Model Registry — Phase 2 implementation.

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
OLLAMA_REASONING_MODEL = os.getenv("OLLAMA_REASONING_MODEL", "qwen2.5:7b")
OLLAMA_CODING_MODEL = os.getenv("OLLAMA_CODING_MODEL", "qwen2.5-coder:7b")
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
    Phase 2: model routing, scoring, and VRAM checks.
    """

    def __init__(self):
        # Register models for Phase 2
        self.models = {
            OLLAMA_REASONING_MODEL: {
                "modality": ["REASONING", "RAG"],
                "vram_gb": 5.0,
                "latency_profile": "low",
                "capabilities": ["text-generation", "instruction-following"]
            },
            OLLAMA_CODING_MODEL: {
                "modality": ["CODING"],
                "vram_gb": 5.0,
                "latency_profile": "low",
                "capabilities": ["text-generation", "code-generation"]
            }
        }
        # Mock available VRAM for Phase 2 testing
        self.available_vram_gb = 12.0

    def check_vram_capacity(self, model_id: str) -> bool:
        """Check if the model fits in currently available VRAM."""
        model_info = self.models.get(model_id)
        if not model_info:
            return False
        return self.available_vram_gb >= model_info["vram_gb"]

    def score_models(self, task_type: str) -> dict[str, float]:
        """Score each model based on its suitability for the task_type."""
        scores = {}
        for model_id, info in self.models.items():
            if not self.check_vram_capacity(model_id):
                scores[model_id] = 0.0
                continue
            
            score = 1.0
            if task_type in info["modality"]:
                score += 10.0  # high boost for matching modality
            else:
                score += 0.5   # fallback score
            
            scores[model_id] = score
            
        return scores

    def select_best_model(self, scores: dict[str, float]) -> str:
        """Select the model with the highest score."""
        if not scores:
            return OLLAMA_REASONING_MODEL
        best_model = max(scores, key=scores.get)
        return best_model if scores[best_model] > 0 else OLLAMA_REASONING_MODEL

    def classify_task(self, prompt: str) -> str:
        """
        Simple keyword classifier for Phase 2.
        Returns 'CODING' if code-related keywords are found, else 'REASONING'.
        """
        keywords = {"python", "code", "debug", "script", "function", "bash", "sql", "query", "react", "regex", "java"}
        prompt_lower = prompt.lower()
        if any(kw in prompt_lower for kw in keywords):
            return "CODING"
        return "REASONING"

    def route_task(self, prompt: str) -> str:
        """
        Phase 2: Route the task to the best model based on classification.
        """
        task_type = self.classify_task(prompt)
        scores = self.score_models(task_type)
        selected = self.select_best_model(scores)
        logger.info(f"Routed task_type '{task_type}' to model '{selected}'. Scores: {scores}")
        return selected

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
