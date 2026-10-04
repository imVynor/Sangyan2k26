"""Tests for model registry and factory functions."""

import pytest
from ai.app.models.ollama import OllamaProvider
from ai.app.models.registry import (
    get_model,
    get_model_config,
    list_registered_models,
    register_model,
)


def test_registry_contains_default_models():
    models = list_registered_models()
    assert "qwen_reasoning" in models
    assert "gemma_fast" in models
    assert models["qwen_reasoning"]["model"] == "qwen3.8:27b"
    assert models["gemma_fast"]["model"] == "gemma4:12b"


def test_get_model_config():
    config = get_model_config("qwen_reasoning")
    assert config["provider"] == "ollama"
    assert config["model"] == "qwen3.8:27b"


def test_get_model_config_unknown_raises():
    with pytest.raises(KeyError) as exc_info:
        get_model_config("unknown_model_alias")
    assert "Unknown model alias" in str(exc_info.value)


def test_get_model_instantiates_ollama():
    provider = get_model("gemma_fast", timeout=30.0)
    assert isinstance(provider, OllamaProvider)
    assert provider.model_name == "gemma4:12b"
    assert provider.timeout == 30.0


def test_register_dynamic_model():
    register_model(
        alias="custom_test_model",
        provider="ollama",
        model="llama3:8b",
        description="Test model registration",
    )
    config = get_model_config("custom_test_model")
    assert config["model"] == "llama3:8b"

    provider = get_model("custom_test_model")
    assert provider.model_name == "llama3:8b"


def test_unsupported_provider_raises():
    register_model(
        alias="unsupported_alias",
        provider="unsupported_provider",
        model="dummy",
    )
    with pytest.raises(ValueError) as exc_info:
        get_model("unsupported_alias")
    assert "Unsupported provider" in str(exc_info.value)
