"""Smart model routing with automatic fallback across providers."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

import litellm

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    id: str
    name: str
    provider: str  # "google" or "openrouter"
    priority: int = 0  # Lower = tried first
    enabled: bool = True


# Default model chain - tried in priority order
# Google AI Studio (direct) → OpenRouter (popular free models)
DEFAULT_MODELS = [
    # Google AI Studio (direct, free tier)
    ModelConfig(id="gemini/gemini-2.5-flash", name="Gemini 2.5 Flash", provider="google", priority=0),
    ModelConfig(id="gemini/gemini-2.5-pro", name="Gemini 2.5 Pro", provider="google", priority=1),
    ModelConfig(id="gemini/gemini-2.0-flash", name="Gemini 2.0 Flash", provider="google", priority=2),

    # OpenRouter Popular Free Models (ranked by usage)
    ModelConfig(id="openrouter/tencent/hy3:free", name="Tencent HY3 (Free)", provider="openrouter", priority=10),  # #1 most popular
    ModelConfig(id="openrouter/nvidia/nemotron-3-ultra-550b-a55b:free", name="Nemotron 3 Ultra 550B (Free)", provider="openrouter", priority=11),  # #2
    ModelConfig(id="openrouter/nvidia/nemotron-3-super-120b-a12b:free", name="Nemotron 3 Super 120B (Free)", provider="openrouter", priority=12),  # #3
    ModelConfig(id="openrouter/google/gemma-4-31b-it:free", name="Gemma 4 31B (Free)", provider="openrouter", priority=13),  # #4
    ModelConfig(id="openrouter/qwen/qwen3-coder:free", name="Qwen3 Coder (Free)", provider="openrouter", priority=14),  # #5
    ModelConfig(id="openrouter/meta-llama/llama-3.3-70b-instruct:free", name="Llama 3.3 70B (Free)", provider="openrouter", priority=15),  # #6
    ModelConfig(id="openrouter/openai/gpt-oss-120b:free", name="GPT-OSS 120B (Free)", provider="openrouter", priority=16),  # #7
    ModelConfig(id="openrouter/poolside/laguna-m.1:free", name="Laguna M.1 Coding (Free)", provider="openrouter", priority=17),  # #8
]

# Status codes that trigger fallback
FALLBACK_STATUSES = {429, 503, 500, 502, 504}


@dataclass
class ModelRouter:
    """Routes LLM requests across multiple models with automatic fallback.

    Tries models in priority order. On rate limit or service error,
    automatically falls back to the next model in the chain.
    """
    models: list[ModelConfig] = field(default_factory=lambda: DEFAULT_MODELS.copy())
    preferred_model: Optional[str] = None
    api_key: Optional[str] = None

    def __post_init__(self):
        """Load available API keys from environment."""
        self._api_keys = {
            "google": os.environ.get("GEMINI_API_KEY"),
            "openrouter": os.environ.get("OPENROUTER_API_KEY"),
        }

    def _get_api_key(self, model: ModelConfig) -> Optional[str]:
        """Get API key for the model's provider."""
        return self._api_keys.get(model.provider) or self.api_key

    def _is_fallback_needed(self, error: Exception) -> bool:
        """Check if error should trigger fallback to next model."""
        error_str = str(error).lower()

        # Check for rate limit / service errors
        if "429" in error_str or "rate" in error_str:
            return True
        if "503" in error_str or "unavailable" in error_str:
            return True
        if "500" in error_str or "502" in error_str or "504" in error_str:
            return True
        if "resource_exhausted" in error_str:
            return True
        if "quota" in error_str:
            return True

        return False

    def get_available_models(self) -> list[dict]:
        """Return list of available models with their status."""
        result = []
        for model in sorted(self.models, key=lambda m: m.priority):
            has_key = self._get_api_key(model) is not None
            result.append({
                "id": model.id,
                "name": model.name,
                "provider": model.provider,
                "available": model.enabled and has_key,
                "priority": model.priority,
            })
        return result

    def call_with_fallback(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 8192,
        preferred_model: Optional[str] = None,
    ) -> tuple[str, str]:
        """Call LLM with automatic model fallback.

        Args:
            messages: Chat messages to send.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            preferred_model: Override model selection.

        Returns:
            Tuple of (response_text, model_used).

        Raises:
            Exception: If all models fail.
        """
        # Build ordered model list
        models_to_try = []

        # Start with preferred model if specified
        if preferred_model and preferred_model != "demo":
            # Find the model config
            for m in self.models:
                if m.id == preferred_model:
                    models_to_try.append(m)
                    break

        # Add default chain, skipping duplicates
        for model in self.models:
            if model.id not in [m.id for m in models_to_try] and model.enabled:
                models_to_try.append(model)

        # Try each model
        last_error = None
        for model in models_to_try:
            api_key = self._get_api_key(model)
            if not api_key:
                logger.debug("Skipping %s - no API key for %s", model.id, model.provider)
                continue

            try:
                logger.info("Trying model: %s (%s)", model.id, model.provider)

                # Set the right API key based on provider
                kwargs = {
                    "model": model.id,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }

                # OpenRouter uses OPENROUTER_API_KEY
                if model.provider == "openrouter":
                    kwargs["api_key"] = api_key
                else:
                    kwargs["api_key"] = api_key

                response = litellm.completion(
                    **kwargs,
                    stream=False,
                )
                content = response.choices[0].message.content or ""  # type: ignore
                logger.info("Success with model: %s", model.id)
                return content, model.id

            except Exception as exc:
                last_error = exc
                if self._is_fallback_needed(exc):
                    logger.warning("Model %s failed, trying next: %s", model.id, exc)
                    continue
                else:
                    # Non-fallback error (auth, etc.) - raise immediately
                    raise

        # All models failed
        raise Exception(
            f"All models failed. Last error: {last_error}"
        )


# Global router instance
_router: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    """Get or create the global model router."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def reset_router():
    """Reset the global router (useful for testing)."""
    global _router
    _router = None
