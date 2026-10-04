"""Configuration settings for SANGYAN AI backend."""

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Local Ollama remains available for embeddings.
    ollama_base_url: str = "http://localhost:11434"
    default_request_timeout: float = 120.0

    # Gemini is used only to polish deterministic citizen-facing explanations.
    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    gemini_model: str = "gemini-2.5-flash"
    response_generation_timeout: float = 8.0

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
