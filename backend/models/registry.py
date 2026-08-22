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
OLLAMA_REASONING_MODEL = os.getenv("OLLAMA_REASONING_MODEL", "qwen2.5:1.5b")
OLLAMA_CODING_MODEL = os.getenv("OLLAMA_CODING_MODEL", "qwen2.5-coder:1.5b")
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
        Phase 2/3: Route the task to the best model based on classification.
        Falls back to fallback_model() if primary model has insufficient VRAM.
        """
        task_type = self.classify_task(prompt)
        scores = self.score_models(task_type)
        selected = self.select_best_model(scores)
        if not self.check_vram_capacity(selected):
            selected = self.fallback_model(task_type)
        logger.info(f"Routed task_type '{task_type}' to model '{selected}'. Scores: {scores}")
        return selected

    def estimate_latency(self, model_id: str, prompt_token_count: int = 500) -> float:
        """
        Phase 3 (M2): Estimate latency in milliseconds for a given model and prompt size.
        Uses a simple heuristic: tokens / throughput_tokens_per_sec * 1000.
        """
        # Approximate throughputs (tokens/sec) per model at 4-bit quantization on a consumer GPU
        throughput_map = {
            OLLAMA_REASONING_MODEL: 25.0,   # ~25 tok/s for 7B reasoning
            OLLAMA_CODING_MODEL:    20.0,   # ~20 tok/s for 7B coder
        }
        throughput = throughput_map.get(model_id, 15.0)
        estimated_ms = (prompt_token_count / throughput) * 1000
        logger.debug("Estimated latency for %s: %.0f ms (%d tokens)", model_id, estimated_ms, prompt_token_count)
        return estimated_ms

    def fallback_model(self, task_type: str) -> str:
        """
        Phase 3 (M2): Return a fallback model when the primary model has insufficient VRAM.
        Always falls back to the reasoning model since it is more general-purpose.
        """
        logger.warning("VRAM insufficient — falling back to reasoning model for task_type '%s'", task_type)
        return OLLAMA_REASONING_MODEL

    def health_check_model(self, model_id: str) -> bool:
        """
        Phase 3 (M2): Check whether Ollama can reach the model.
        Returns True if healthy, False otherwise.
        """
        import httpx
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={"model": model_id, "prompt": "ping", "stream": False},
                )
                return resp.status_code == 200
        except Exception as exc:
            logger.warning("Health check failed for model %s: %s", model_id, exc)
            return False

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
            if os.getenv("OLLAMA_MOCK_FALLBACK", "true").lower() != "true":
                raise
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

    def execute_embedding(self, model_id: str, prompt: str) -> list[float]:
        """
        Execute an embedding request against the local Ollama instance.
        Throws exception on failure (unless mock fallback is configured).
        """
        payload = {
            "model": model_id,
            "prompt": prompt,
        }
        try:
            with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
                resp = client.post(f"{OLLAMA_BASE_URL}/api/embeddings", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("embedding", [])
        except Exception as exc:
            if os.getenv("OLLAMA_MOCK_FALLBACK", "false").lower() != "true":
                raise
            logger.warning("Ollama unreachable for embedding. Using mock zero vector.")
            return [0.0] * 768

# Module-level singleton
registry = ModelRegistry()
