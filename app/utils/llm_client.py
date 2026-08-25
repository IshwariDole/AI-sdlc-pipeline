import json
import re
import time

from google import genai
from google.genai.errors import ClientError, ServerError
from groq import Groq, RateLimitError

from app.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
)


# ============================================================
# LLM CLIENT INITIALIZATION
# ============================================================

_gemini = genai.Client(api_key=GEMINI_API_KEY)
_groq = Groq(api_key=GROQ_API_KEY)


# ============================================================
# EXCEPTIONS
# ============================================================

class _SwitchToFallback(Exception):
    """Signal that Gemini should be abandoned and Groq used instead."""
    pass


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _extract_retry_seconds(
    error_message: str,
    default: float = 10.0
) -> float:
    """
    Extract retry time from provider error messages.

    Supports messages such as:
    'Please try again in 3.6825s'
    'retry in 5s'
    """

    patterns = [
        r"try again in ([\d.]+)s",
        r"retry in ([\d.]+)s",
    ]

    for pattern in patterns:
        match = re.search(pattern, error_message, re.IGNORECASE)

        if match:
            return float(match.group(1)) + 1

    return default


def _clean_json_content(content: str) -> str:
    """
    Removes accidental markdown code fences from LLM output.
    """

    content = content.strip()

    if content.startswith("```json"):
        content = content[len("```json"):]

    elif content.startswith("```"):
        content = content[len("```"):]

    if content.endswith("```"):
        content = content[:-3]

    return content.strip()


# ============================================================
# GEMINI FALLBACK HANDLER
# ============================================================

def _gemini_is_exhausted_or_down(
    fn,
    max_attempts: int = 2
):
    """
    Try Gemini first.

    Handles:
    - Temporary 503 server errors
    - Rate limits
    - Daily quota exhaustion

    Falls back to Groq when Gemini cannot continue.
    """

    for attempt in range(1, max_attempts + 1):

        try:
            return fn()

        except ServerError:

            if attempt < max_attempts:

                print(
                    f"[llm_client] Gemini busy (503). "
                    f"Quick retry {attempt}/{max_attempts}..."
                )

                time.sleep(5)

            else:

                print(
                    "[llm_client] Gemini still unavailable. "
                    "Falling back to Groq."
                )

                raise _SwitchToFallback()

        except ClientError as e:

            msg = str(e)

            # Daily quota exhausted
            if (
                "PerDay" in msg
                or "GenerateRequestsPerDayPerProjectPerModel" in msg
            ):

                print(
                    "[llm_client] Gemini daily quota exhausted. "
                    "Falling back to Groq."
                )

                raise _SwitchToFallback()

            # Temporary rate limit
            if (
                "RESOURCE_EXHAUSTED" in msg
                and attempt < max_attempts
            ):

                wait = _extract_retry_seconds(
                    msg,
                    default=10
                )

                print(
                    f"[llm_client] Gemini rate limited. "
                    f"Waiting {wait:.1f}s..."
                )

                time.sleep(wait)

            else:

                print(
                    "[llm_client] Gemini error. "
                    "Falling back to Groq."
                )

                raise _SwitchToFallback()


# ============================================================
# GROQ STRUCTURED OUTPUT
# ============================================================
def _generate_structured_with_groq(
    prompt: str,
    schema,
    schema_hint: str | None = None,
    max_retries: int = 3,
):
    """
    Generate structured JSON using Groq.
    Handles rate limits, empty responses, and JSON errors.
    """

    schema_hint = """
{
  "project_name": "string",
  "introduction": "string",
  "functional_requirements": [
    {
      "id": "FR-01",
      "description": "The system shall ...",
      "priority": "High | Medium | Low",
      "source_ref": "BR-01"
    }
  ],
  "non_functional_requirements": [
    {
      "id": "NFR-01",
      "category": "Performance | Security | Reliability | Usability | Scalability",
      "description": "specific measurable requirement"
    }
  ],
  "use_cases": [
    {
      "id": "UC-01",
      "title": "string",
      "actor": "string",
      "description": "string",
      "preconditions": ["string"],
      "main_flow": ["step 1", "step 2"]
    }
  ],
  "constraints": ["string"]
}
"""

    groq_prompt = (
        f"{prompt}\n\n"
        "IMPORTANT:\n"
        "Return ONLY a valid JSON object.\n"
        "Do not return markdown.\n"
        "Do not return explanations.\n"
        "Do not return an empty response.\n"
        "Do not use code fences.\n\n"
        f"JSON SCHEMA:\n{schema_hint}"
    )

    last_error = None

    for attempt in range(1, max_retries + 1):

        try:

            print(
                f"[llm_client] Groq structured generation "
                f"attempt {attempt}/{max_retries}..."
            )

            response = _groq.chat.completions.create(
    model=GROQ_MODEL,
    messages=[
        {
            "role": "system",
            "content": (
                "You are a JSON API. "
                "Your response must contain exactly one "
                "valid JSON object matching the requested schema. "
                "Be concise and keep descriptions short."
            ),
        },
        {
            "role": "user",
            "content": groq_prompt,
        },
    ],
    temperature=0.2,
    max_completion_tokens=3000,
)

            # Debug information
            print(
                "[llm_client] Groq finish reason:",
                response.choices[0].finish_reason
            )

            content = response.choices[0].message.content

            if content is None or not content.strip():

                last_error = ValueError(
                    "Groq returned an empty response."
                )

                if attempt < max_retries:

                    wait_time = 3 * attempt

                    print(
                        f"[llm_client] Empty response. "
                        f"Waiting {wait_time}s before retry..."
                    )

                    time.sleep(wait_time)

                    continue

                raise last_error

            content = _clean_json_content(content)

            data = json.loads(content)

            return schema.model_validate(data)

        except RateLimitError as e:

            last_error = e

            if attempt == max_retries:
                raise

            wait_time = _extract_retry_seconds(
                str(e),
                default=10.0 * attempt,
            )

            print(
                f"[llm_client] Groq rate limited. "
                f"Waiting {wait_time:.1f}s before retry..."
            )

            time.sleep(wait_time)

        except (json.JSONDecodeError, ValueError) as e:

            last_error = e

            if attempt == max_retries:
                raise

            wait_time = 3 * attempt

            print(
                f"[llm_client] Invalid/empty Groq response: {e}"
            )

            print(
                f"[llm_client] Retrying in {wait_time}s..."
            )

            time.sleep(wait_time)

    raise last_error


# ============================================================
# STRUCTURED GENERATION
# ============================================================

def generate_structured(
    prompt: str,
    schema,
):
    """
    Generate structured data.

    Flow:

    Gemini
        ↓
    If successful → return validated Pydantic object

    If Gemini unavailable/quota exhausted
        ↓
    Groq fallback
        ↓
    JSON parsing
        ↓
    Pydantic validation
    """

    def try_gemini():

        response = _gemini.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )

        data = json.loads(response.text)

        return schema.model_validate(data)

    try:

        return _gemini_is_exhausted_or_down(
            try_gemini
        )

    except _SwitchToFallback:

        print(
            f"[llm_client] Using Groq model: {GROQ_MODEL}"
        )

        return _generate_structured_with_groq(
            prompt=prompt,
            schema=schema,
        )


# ============================================================
# GROQ TEXT OUTPUT
# ============================================================

def _generate_text_with_groq(
    prompt: str,
    max_retries: int = 3,
) -> str:
    """
    Generate plain text using Groq with rate-limit retry.
    """

    for attempt in range(1, max_retries + 1):

        try:

            response = _groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            content = response.choices[0].message.content

            if not content:
                raise ValueError(
                    "Groq returned an empty response."
                )

            return content.strip()

        except RateLimitError as e:

            if attempt == max_retries:

                print(
                    "[llm_client] Groq rate limit retries exhausted."
                )

                raise e

            wait_time = _extract_retry_seconds(
                str(e),
                default=10.0 * attempt,
            )

            print(
                f"[llm_client] Groq rate limited. "
                f"Waiting {wait_time:.1f}s "
                f"before retry {attempt + 1}/{max_retries}..."
            )

            time.sleep(wait_time)


# ============================================================
# TEXT GENERATION
# ============================================================

def generate_text(
    prompt: str,
) -> str:
    """
    Generate plain text.

    Gemini is attempted first.
    Groq is used automatically as fallback.
    """

    def try_gemini():

        response = _gemini.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        return response.text.strip()

    try:

        return _gemini_is_exhausted_or_down(
            try_gemini
        )

    except _SwitchToFallback:

        print(
            f"[llm_client] Using Groq model: {GROQ_MODEL}"
        )

        return _generate_text_with_groq(
            prompt=prompt
        )