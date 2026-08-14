import json
import re
import time
from google import genai
from google.genai.errors import ClientError
from google.genai.errors import ServerError

from app.config import GEMINI_API_KEY, GEMINI_MODEL

_client = genai.Client(api_key=GEMINI_API_KEY)


def _extract_retry_seconds(error_message: str, default: float = 20.0) -> float:
    """Gemini's 429 errors usually include 'Please retry in 48.37...s' --
    parse that instead of guessing a fixed wait time."""
    match = re.search(r"retry in ([\d.]+)s", error_message)
    return float(match.group(1)) + 1 if match else default


def _call_with_retry(fn, max_attempts: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except ServerError as e:
            if attempt < max_attempts:
                wait = 10 * attempt  # simple backoff: 10s, 20s, 30s
                print(f"[llm_client] Server busy (503). Waiting {wait}s (attempt {attempt}/{max_attempts})...")
                time.sleep(wait)
            else:
                raise
        except ClientError as e:
            msg = str(e)
            if "PerDay" in msg or "GenerateRequestsPerDayPerProjectPerModel" in msg:
                raise RuntimeError(
                    "Daily free-tier quota exhausted for this model. "
                    "This resets roughly at midnight Pacific Time. "
                    "Try again tomorrow, or switch GEMINI_MODEL in config.py "
                    "to a model with a higher daily quota."
                ) from e
            if "RESOURCE_EXHAUSTED" in msg and attempt < max_attempts:
                wait = _extract_retry_seconds(msg)
                print(f"[llm_client] Rate limited (per-minute). Waiting {wait:.0f}s (attempt {attempt}/{max_attempts})...")
                time.sleep(wait)
            else:
                raise
def generate_structured(prompt: str, schema):
    """For calls that need JSON matching a Pydantic schema."""
    def do_call():
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": schema},
        )
        data = json.loads(response.text)
        return schema.model_validate(data)

    return _call_with_retry(do_call)


def generate_text(prompt: str) -> str:
    """For plain-text calls (e.g. research agent's per-topic answers)."""
    def do_call():
        response = _client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text.strip()

    return _call_with_retry(do_call)