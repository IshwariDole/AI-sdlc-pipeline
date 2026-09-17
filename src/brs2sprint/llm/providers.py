"""Real LLM providers. Imported lazily so the offline/mock path never needs
the SDKs installed.

Groq and Gemini both expose an OpenAI-compatible `/chat/completions` endpoint,
so they share one implementation with OpenAI itself — only the base URL,
default model and API key differ. That keeps this file small and means
adding a fourth OpenAI-compatible provider (Together, Fireworks, local
vLLM/Ollama, etc.) is a five-line subclass.
"""

from __future__ import annotations

from ..config import settings
from .base import LLMClient, LLMRequest, LLMError

DEFAULT_SYSTEM = "You are a precise software requirements engineer."


class AnthropicClient(LLMClient):
    name = "anthropic"
    default_model = "claude-sonnet-4-6"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        super().__init__()
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMError("pip install anthropic") from exc

        key = api_key or settings.anthropic_api_key
        if not key:
            raise LLMError(
                "ANTHROPIC_API_KEY is not set. Add it to .env, or use "
                "--provider groq / --provider gemini for a free-tier alternative."
            )
        self._client = anthropic.Anthropic(api_key=key)
        self.model = model or settings.llm_model or self.default_model

    def _raw(self, req: LLMRequest) -> str:
        try:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=req.max_tokens or settings.max_tokens,
                temperature=settings.temperature if req.temperature is None else req.temperature,
                system=req.system or DEFAULT_SYSTEM,
                messages=[{"role": "user", "content": req.user}],
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            text = str(exc).lower()
            if status == 404 or "not_found" in text:
                raise LLMError(
                    f"anthropic: model '{self.model}' was not found. Pass --model <name> "
                    f"or set LLM_MODEL in .env to a current model string."
                ) from exc
            if status == 401 or "authentication" in text:
                raise LLMError("anthropic: API key was rejected (401). Check ANTHROPIC_API_KEY in .env.") from exc
            if status == 429 or "rate_limit" in text or "credit" in text:
                raise LLMError(
                    "anthropic: rate limit or insufficient credit (429). "
                    "Consider --provider groq or --provider gemini for a free tier."
                ) from exc
            raise LLMError(f"anthropic request failed: {exc}") from exc
        return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")


class _OpenAICompatibleClient(LLMClient):
    """Base for any provider speaking the OpenAI chat-completions wire format.

    Subclasses set `name`, `default_model`, `base_url` and `env_var`.
    """

    name = "openai-compatible"
    default_model = ""
    base_url: str | None = None       # None = OpenAI's own endpoint
    env_var = "OPENAI_API_KEY"
    supports_json_mode = True         # some OpenAI-compatible servers reject response_format

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        super().__init__()
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMError("pip install openai") from exc

        key = api_key or self._configured_key()
        if not key:
            raise LLMError(
                f"{self.env_var} is not set. Add it to .env "
                f"(get a free key at {self._signup_hint()})."
            )
        kwargs = {"api_key": key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)
        self.model = model or settings.llm_model or self.default_model

    def _configured_key(self) -> str:
        raise NotImplementedError

    def _signup_hint(self) -> str:
        return ""

    def _raw(self, req: LLMRequest) -> str:
        kwargs = dict(
            model=self.model,
            max_tokens=req.max_tokens or settings.max_tokens,
            temperature=settings.temperature if req.temperature is None else req.temperature,
            messages=[
                {"role": "system", "content": req.system or DEFAULT_SYSTEM},
                {"role": "user", "content": req.user},
            ],
        )
        if req.json_output and self.supports_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as first_exc:
            # Some OpenAI-compatible servers/models 400 on response_format
            # rather than ignoring it — retry once without it before giving up.
            if "response_format" in kwargs:
                try:
                    kwargs.pop("response_format")
                    resp = self._client.chat.completions.create(**kwargs)
                except Exception as second_exc:
                    raise LLMError(self._explain(second_exc)) from second_exc
            else:
                raise LLMError(self._explain(first_exc)) from first_exc
        return resp.choices[0].message.content or ""

    def _explain(self, exc: Exception) -> str:
        """Turn a raw SDK exception into an actionable one-line message.

        Free-tier providers move models between tiers and deprecate them with
        little notice, so a wrong-model-name 404 is the single most likely
        failure once auth works. Surface that distinctly from other errors.
        """
        status = getattr(exc, "status_code", None)
        text = str(exc).lower()
        if status == 404 or "model_not_found" in text or "does not exist" in text:
            return (
                f"{self.name}: model '{self.model}' was not found or is not "
                f"available on your plan. Model catalogues change often on "
                f"free tiers — pass --model <name> or set LLM_MODEL in .env "
                f"to a current one. {self._model_list_hint()}"
            )
        if status == 401 or "unauthorized" in text or "invalid api key" in text:
            return f"{self.name}: API key was rejected (401). Check {self.env_var} in .env."
        if (status in (429, 413) or "rate_limit_exceeded" in text or "rate limit" in text
                or "tokens per minute" in text or " tpm" in text or "quota" in text):
            return (
                f"{self.name}: request exceeded your plan's rate or token-per-minute "
                f"limit ({status or 'rate_limit'}). This is a free-tier ceiling, not a bug — "
                f"a single call's (prompt + LLM_MAX_TOKENS) tokens exceeded the per-minute "
                f"budget. Fix by lowering LLM_MAX_TOKENS in .env (try 2000), lowering "
                f"CHUNK_SIZE for phase 1, or waiting ~60s between runs. "
                f"Original: {exc}"
            )
        return f"{self.name} request failed: {exc}"

    def _model_list_hint(self) -> str:
        return ""


class OpenAIClient(_OpenAICompatibleClient):
    name = "openai"
    default_model = "gpt-4o-mini"
    env_var = "OPENAI_API_KEY"

    def _configured_key(self) -> str:
        return settings.openai_api_key

    def _signup_hint(self) -> str:
        return "platform.openai.com"


class GroqClient(_OpenAICompatibleClient):
    """Groq — free developer tier, very fast inference (LPU hardware).

    Model names churn: Groq moves models between free/enterprise tiers and
    deprecates old ones with little notice. If the default 404s, check
    https://console.groq.com/docs/models (or `curl .../v1/models` — see that
    page) for what's currently on the free/developer plan, and either pass
    --model explicitly or update LLM_MODEL in .env.
    """
    name = "groq"
    default_model = "openai/gpt-oss-120b"
    base_url = "https://api.groq.com/openai/v1"
    env_var = "GROQ_API_KEY"

    def _configured_key(self) -> str:
        return settings.groq_api_key

    def _signup_hint(self) -> str:
        return "console.groq.com/keys"

    def _model_list_hint(self) -> str:
        return "Current models: https://console.groq.com/docs/models"


class GeminiClient(_OpenAICompatibleClient):
    """Google Gemini via its OpenAI-compatible endpoint — free tier available.

    Model names churn even faster here: Google has shut down entire model
    generations (2.0 Flash included) with a few months' notice. If the
    default 404s, check https://ai.google.dev/gemini-api/docs/models for the
    current free-tier Flash/Flash-Lite model, and either pass --model
    explicitly or update LLM_MODEL in .env.
    """
    name = "gemini"
    default_model = "gemini-3.1-flash-lite"
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    env_var = "GEMINI_API_KEY"
    supports_json_mode = False   # the compat layer is inconsistent about this; ask in-prompt instead

    def _configured_key(self) -> str:
        return settings.gemini_api_key

    def _signup_hint(self) -> str:
        return "aistudio.google.com/apikey"

    def _model_list_hint(self) -> str:
        return "Current models: https://ai.google.dev/gemini-api/docs/models"
