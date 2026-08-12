import os
import json
from google import genai
from dotenv import load_dotenv

from app.models.schemas import BRSSummary

load_dotenv()

GEMINI_MODEL = "gemini-3.5-flash"

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


SYSTEM_INSTRUCTION = """You are a business analyst assistant. You will be given
the raw text of a Business Requirements Specification (BRS) document.

Extract and structure the information according to the provided schema.
Rules:
- Do not invent information that isn't stated or clearly implied in the document.
- If a section is missing from the document, return an empty list for it.
- Keep each list item concise (one sentence per item where possible).
- For raw_requirements, extract every individual requirement, even from tables.
"""


def summarize_brs(raw_text: str) -> BRSSummary:
    """
    Sends raw BRS text to Gemini and returns a validated, structured summary.
    """
    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=f"{SYSTEM_INSTRUCTION}\n\nBRS DOCUMENT TEXT:\n\n{raw_text}",
        config={
            "response_mime_type": "application/json",
            "response_schema": BRSSummary,
        },
    )

    # response.parsed gives us the SDK's own attempt at building the Pydantic
    # object. We still explicitly re-validate below rather than trusting it
    # blindly -- cheap insurance, and makes failures explicit instead of silent.
    data = json.loads(response.text)
    return BRSSummary.model_validate(data)