"""
Model Registry — Phase 2 implementation.

Talks to a local Ollama instance (OpenAI-compatible endpoint).
Falls back to a mock response if Ollama is not reachable (dev/CI convenience).

Ollama endpoint: POST http://ollama:11434/api/generate
"""
import json
import os
import time
import logging
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_REASONING_MODEL = os.getenv("OLLAMA_REASONING_MODEL", "qwen2.5:1.5b")
OLLAMA_CODING_MODEL = os.getenv("OLLAMA_CODING_MODEL", "qwen2.5-coder:1.5b")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))

# Phase 9 (M2): enforce model-hash verification at load time. Off by default so
# dev/CI environments without a manifest entry for every locally-pulled model
# don't hard-fail; set true once the manifest is authoritative for a deployment.
ENFORCE_MODEL_HASH = os.getenv("ENFORCE_MODEL_HASH", "false").lower() == "true"
_MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "model_manifest.json")

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
    Phase 2/5: model routing, scoring, VRAM checks, and multimodal vision dispatch.
    """

    def __init__(self):
        # Register models for Phase 2 and Phase 5
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
            },
            OLLAMA_VISION_MODEL: {
                "modality": ["VISION", "MULTIMODAL"],
                "vram_gb": 6.0,
                "latency_profile": "medium",
                "capabilities": ["vision-understanding", "ocr-grounding", "image-analysis"]
            }
        }
        # Mock available VRAM for Phase 2/5 testing
        self.available_vram_gb = 12.0
        self._manifest = self._load_manifest()
        self._verified_cache: dict[str, bool] = {}

    @staticmethod
    def _load_manifest() -> dict:
        try:
            with open(_MANIFEST_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load model manifest at %s: %s", _MANIFEST_PATH, exc)
            return {}

    def _get_live_digest(self, model_id: str) -> str | None:
        """Query Ollama's own /api/tags (a local call — no external network)
        for the currently-loaded digest of `model_id`."""
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{OLLAMA_BASE_URL}/api/tags")
                resp.raise_for_status()
                for entry in resp.json().get("models", []):
                    if entry.get("model") == model_id or entry.get("name") == model_id:
                        return entry.get("digest")
        except Exception as exc:
            logger.warning("Could not query Ollama for model digest of %s: %s", model_id, exc)
        return None

    def verify_model_hash(self, model_id: str) -> dict:
        """
        Phase 9 (M2): compare the model's live SHA-256 digest (from Ollama)
        against the trusted manifest. Returns
        {"verified": bool, "expected": str|None, "actual": str|None, "detail": str}.
        A model missing from the manifest is NOT verified (fails closed).
        """
        expected = self._manifest.get(model_id)
        actual = self._get_live_digest(model_id)

        if expected is None:
            return {"verified": False, "expected": None, "actual": actual,
                     "detail": f"'{model_id}' is not in the trusted model manifest."}
        if actual is None:
            return {"verified": False, "expected": expected, "actual": None,
                     "detail": f"Could not reach Ollama to read the live digest for '{model_id}'."}
        if actual != expected:
            return {"verified": False, "expected": expected, "actual": actual,
                     "detail": f"Digest mismatch for '{model_id}' — model file may have been tampered with or replaced."}
        return {"verified": True, "expected": expected, "actual": actual, "detail": "Digest matches trusted manifest."}

    def validate_model_source(self, model_id: str) -> bool:
        """A model is only trusted if it's both a registered EdgeMind model
        AND passes hash verification against the manifest."""
        if model_id not in self.models:
            return False
        return self.verify_model_hash(model_id)["verified"]

    def _ensure_model_trusted(self, model_id: str) -> None:
        """Called at load time (execute_prompt). Verifies once per process and
        caches the result. Only hard-fails when ENFORCE_MODEL_HASH=true —
        otherwise logs + audits a warning so dev/CI without a full manifest
        keeps working, while the check itself is fully real and callable
        on-demand via verify_model_hash()/GET /api/sovereignty/report."""
        if model_id in self._verified_cache:
            if not self._verified_cache[model_id] and ENFORCE_MODEL_HASH:
                raise RuntimeError(f"Refusing to serve unverified model '{model_id}' (ENFORCE_MODEL_HASH=true).")
            return
        result = self.verify_model_hash(model_id)
        self._verified_cache[model_id] = result["verified"]
        if not result["verified"]:
            logger.warning("Model '%s' failed hash verification: %s", model_id, result["detail"])
            if ENFORCE_MODEL_HASH:
                raise RuntimeError(f"Refusing to serve unverified model '{model_id}': {result['detail']}")

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

    def classify_task(self, prompt: str, has_image: bool = False) -> str:
        """
        Keyword & modality classifier.
        Returns 'VISION', 'CODING', or 'REASONING'.
        """
        if has_image:
            return "VISION"
        keywords_coding = {"python", "code", "debug", "script", "function", "bash", "sql", "query", "react", "regex", "java"}
        keywords_vision = {"image", "photo", "scan", "ocr", "p&id", "drawing", "schematic", "blueprint", "diagram"}
        prompt_lower = prompt.lower()
        if any(kw in prompt_lower for kw in keywords_vision):
            return "VISION"
        if any(kw in prompt_lower for kw in keywords_coding):
            return "CODING"
        return "REASONING"

    def route_vision_task(self, prompt: str, has_image: bool = True) -> str:
        """
        Phase 5 (M2): Direct route for vision & multimodal tasks.
        """
        scores = self.score_models("VISION")
        selected = self.select_best_model(scores)
        if not self.check_vram_capacity(selected):
            selected = self.fallback_model("VISION")
        logger.info(f"Routed vision task to model '{selected}'")
        return selected

    def route_task(self, prompt: str, has_image: bool = False) -> str:
        """
        Phase 2/3/5: Route the task to the best model based on classification.
        Falls back to fallback_model() if primary model has insufficient VRAM.
        """
        task_type = self.classify_task(prompt, has_image=has_image)
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
            OLLAMA_VISION_MODEL:    15.0,   # ~15 tok/s for vision-language model
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

    def execute_prompt(self, model_id: str, prompt: str, image_b64: str | None = None) -> tuple[str, float]:
        """
        Call Ollama /api/generate.
        Supports multimodal image input (base64 string).
        Returns (response_text, latency_ms).
        Falls back to a mock if Ollama is unreachable.
        """
        self._ensure_model_trusted(model_id)
        payload = {
            "model": model_id,
            "prompt": prompt,
            "stream": False,
        }
        if image_b64:
            payload["images"] = [image_b64]

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
