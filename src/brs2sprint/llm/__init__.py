from __future__ import annotations

from ..config import settings
from .base import LLMClient, LLMRequest, LLMError, extract_json
from .mock import MockClient

__all__ = ["LLMClient", "LLMRequest", "LLMError", "extract_json", "get_client", "MockClient"]


_PROVIDERS = {"mock", "anthropic", "openai", "groq", "gemini"}


def get_client(provider: str | None = None, api_key: str | None = None,
               model: str | None = None) -> LLMClient:
    """Factory. Real SDKs are imported lazily so `mock` needs nothing installed.

    `api_key` lets a caller (e.g. a hosted dashboard) supply a per-request
    key instead of relying on the server's own .env — important for a public
    deployment, where a shared server-side key means every visitor draws
    from the same free-tier quota and one busy visitor rate-limits everyone
    else. When api_key is None, each client falls back to its own .env var.
    """
    provider = (provider or settings.llm_provider).lower()
    if provider == "mock":
        return MockClient()
    if provider == "anthropic":
        from .providers import AnthropicClient
        return AnthropicClient(model=model, api_key=api_key)
    if provider == "openai":
        from .providers import OpenAIClient
        return OpenAIClient(model=model, api_key=api_key)
    if provider == "groq":
        from .providers import GroqClient
        return GroqClient(model=model, api_key=api_key)
    if provider == "gemini":
        from .providers import GeminiClient
        return GeminiClient(model=model, api_key=api_key)
    raise LLMError(f"unknown LLM_PROVIDER: {provider!r} (use {' | '.join(sorted(_PROVIDERS))})")
