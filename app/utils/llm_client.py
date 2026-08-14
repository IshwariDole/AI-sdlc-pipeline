import json
import re
import time
from google import genai
from google.genai.errors import ClientError, ServerError
from groq import Groq

from app.config import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL

_gemini = genai.Client(api_key=GEMINI_API_KEY)
_groq = Groq(api_key=GROQ_API_KEY)


def _extract_retry_seconds(error_message: str, default: float = 20.0) -> float:
    match = re.search(r"retry in ([\d.]+)s", error_message)
    return float(match.group(1)) + 1 if match else default


def _gemini_is_exhausted_or_down(fn, max_attempts: int = 2):
    """
    Tries Gemini a couple of times for transient issues (per-minute limits,
    momentary 503s). Returns None on success is NOT possible here -- instead
    this either returns the result, or raises _SwitchToFallback to signal
    "stop trying Gemini, use Groq instead."
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except ServerError:
            if attempt < max_attempts:
                print(f"[llm_client] Gemini busy (503). Quick retry {attempt}/{max_attempts}...")
                time.sleep(5)
            else:
                print("[llm_client] Gemini still unavailable. Falling back to Groq.")
                raise _SwitchToFallback()
        except ClientError as e:
            msg = str(e)
            if "PerDay" in msg or "GenerateRequestsPerDayPerProjectPerModel" in msg:
                print("[llm_client] Gemini daily quota exhausted. Falling back to Groq.")
                raise _SwitchToFallback()
            if "RESOURCE_EXHAUSTED" in msg and attempt < max_attempts:
                wait = _extract_retry_seconds(msg)
                print(f"[llm_client] Gemini rate limited. Waiting {wait:.0f}s...")
                time.sleep(wait)
            else:
                print("[llm_client] Gemini error. Falling back to Groq.")
                raise _SwitchToFallback()


class _SwitchToFallback(Exception):
    pass


def generate_structured(prompt: str, schema):
    """Tries Gemini first (native schema support). Falls back to Groq
    (JSON mode + manual Pydantic validation) if Gemini is unavailable."""

    def try_gemini():
        response = _gemini.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": schema},
        )
        data = json.loads(response.text)
        return schema.model_validate(data)

    try:
        return _gemini_is_exhausted_or_down(try_gemini)
    except _SwitchToFallback:
        pass

    # --- Groq fallback ---
    schema_hint = json.dumps(schema.model_json_schema(), indent=2)
    groq_prompt = (
        f"{prompt}\n\n"
        f"Respond with ONLY valid JSON matching this schema, no other text:\n{schema_hint}"
    )
    response = _groq.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": groq_prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    return schema.model_validate(data)


def generate_text(prompt: str) -> str:
    """Same fallback pattern for plain-text calls."""

    def try_gemini():
        response = _gemini.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text.strip()

    try:
        return _gemini_is_exhausted_or_down(try_gemini)
    except _SwitchToFallback:
        pass

    response = _groq.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()