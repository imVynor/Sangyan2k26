"""Model registry and factory for SANGYAN AI backend.

Enables application code to request logical model aliases (e.g. 'qwen_reasoning', 'gemma_fast')
without hardcoding model names or provider-specific initialization.
Designed for seamless addition of cloud providers (e.g. Gemini) in future phases.
"""

from typing import Any
from ai.app.models.ollama import OllamaProvider
from ai.app.models.provider import LLMProvider

# Canonical model registry mapping logical capability aliases to provider & underlying model
MODELS: dict[str, dict[str, Any]] = {
    "qwen_reasoning": {
        "provider": "ollama",
        "model": "qwen3.8:27b",
        "description": "High-capacity reasoning model for deep epistemic case understanding",
    },
    "gemma_fast": {
        "provider": "ollama",
        "model": "gemma4:12b",
        "description": "Fast model for low-latency triage and structured fact extraction",
    },
}


def register_model(alias: str, provider: str, model: str, description: str = "") -> None:
    """Register or override a model configuration alias dynamically."""
    MODELS[alias] = {
        "provider": provider,
        "model": model,
        "description": description,
    }


def get_model_config(alias: str) -> dict[str, Any]:
    """Retrieve configuration metadata for a registered model alias."""
    if alias not in MODELS:
        available = ", ".join(repr(k) for k in MODELS.keys())
        raise KeyError(f"Unknown model alias '{alias}'. Available models: {available}")
    return MODELS[alias]


def list_registered_models() -> dict[str, dict[str, Any]]:
    """List all currently registered models."""
    return dict(MODELS)


def get_model(alias: str, **provider_kwargs: Any) -> LLMProvider:
    """Factory function to instantiate an LLMProvider for a given model alias.
    
    Args:
        alias: The registered model alias (e.g. 'qwen_reasoning', 'gemma_fast')
        provider_kwargs: Optional provider-specific overrides (e.g. timeout, base_url, client)
        
    Returns:
        Configured LLMProvider instance.
        
    Raises:
        KeyError: If alias is not registered.
        ValueError: If provider backend is not implemented.
    """
    config = get_model_config(alias)
    provider_type = config.get("provider", "").lower()
    model_name = config["model"]

    if provider_type == "ollama":
        return OllamaProvider(model_name=model_name, **provider_kwargs)
    elif provider_type == "gemini":
        # Placeholder for Phase 1+ Gemini cloud provider integration
        raise NotImplementedError("Gemini provider will be activated in future phases.")
    else:
        raise ValueError(f"Unsupported provider '{provider_type}' for model alias '{alias}'")
