"""Configuration settings for SANGYAN AI backend."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Ollama settings
    ollama_base_url: str = "http://localhost:11434"
    default_request_timeout: float = 120.0
    response_model: str = "gemma3:1b"
    response_generation_timeout: float = 2.5

    # Logging settings
    log_level: str = "INFO"
    log_sensitive_data: bool = False

    # Database settings
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "AI_DATABASE_URL"),
    )
    database_echo: bool = False

    # Evaluation settings
    eval_temperature: float = 0.0


settings = Settings()
