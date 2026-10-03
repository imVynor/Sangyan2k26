"""Structured logger for SANGYAN AI backend.

Ensures:
- Model, latency, success/failure, and validation events are recorded.
- Sensitive user case information is NOT logged by default.
"""

import logging
import sys
from typing import Any
from ai.app.config.settings import settings


def setup_logger(name: str = "sangyan.ai") -> logging.Logger:
    """Configure and return the application logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(level)
    return logger


logger = setup_logger()


def log_llm_event(
    event: str,
    model: str,
    latency_ms: float | None = None,
    success: bool = True,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a structured log line for LLM operations without logging user PII."""
    payload: dict[str, Any] = {
        "event": event,
        "model": model,
        "success": success,
    }
    if latency_ms is not None:
        payload["latency_ms"] = round(latency_ms, 2)
    if extra:
        # Sanitize extra fields to ensure no raw user prompts are logged inadvertently
        for k, v in extra.items():
            if not settings.log_sensitive_data and k in {"prompt", "content", "narrative", "user_text"}:
                payload[k] = "[REDACTED_PII]"
            else:
                payload[k] = v

    if success:
        logger.info(f"LLM_EVENT | {payload}")
    else:
        logger.error(f"LLM_EVENT | {payload}")
