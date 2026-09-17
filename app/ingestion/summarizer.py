from app.models.schemas import BRSSummary
from app.utils.llm_client import generate_structured

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
    prompt = f"{SYSTEM_INSTRUCTION}\n\nBRS DOCUMENT TEXT:\n\n{raw_text}"
    return generate_structured(prompt, BRSSummary)