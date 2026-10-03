"""Provider-agnostic abstract base interface for LLM backends."""

from abc import ABC, abstractmethod
from typing import TypeVar
from pydantic import BaseModel

from ai.app.models.schemas import Message, LLMResponse

T = TypeVar("T", bound=BaseModel)


class LLMProviderError(Exception):
    """Base exception for provider errors."""
    pass


class LLMConnectionError(LLMProviderError):
    """Raised when the provider endpoint cannot be reached."""
    pass


class LLMTimeoutError(LLMProviderError):
    """Raised when a request to the provider times out."""
    pass


class LLMModelNotFoundError(LLMProviderError):
    """Raised when the requested model is not found in the provider."""
    pass


class LLMProvider(ABC):
    """Abstract interface defining operations for any LLM provider (Ollama, Gemini, etc.).
    
    Implementations must strictly adhere to provider-agnostic schemas and avoid
    leaking internal provider types.
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate a response from the LLM.
        
        Args:
            messages: List of conversation messages (roles: system, user, assistant).
            response_schema: Optional Pydantic model for structured output guidance.
            temperature: Sampling temperature (0.0 for deterministic output).
            max_tokens: Optional token generation limit.
            
        Returns:
            LLMResponse containing content, latency, and token metrics.
        """
        ...

    @abstractmethod
    async def generate_structured(
        self,
        messages: list[Message],
        response_model: type[T],
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> T:
        """Generate structured output and validate against a target Pydantic model.
        
        Args:
            messages: List of conversation messages.
            response_model: Target Pydantic schema class.
            temperature: Sampling temperature (default 0.0).
            max_tokens: Optional token generation limit.
            
        Returns:
            Validated instance of response_model.
            
        Raises:
            JSONParsingError: If raw output is not valid JSON.
            SchemaValidationError: If JSON does not conform to response_model.
            LLMProviderError: On underlying transport or provider failures.
        """
        ...

    @abstractmethod
    async def check_health(self) -> bool:
        """Check if provider is reachable and operational."""
        ...
