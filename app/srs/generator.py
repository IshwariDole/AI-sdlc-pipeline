import os
import json
from google import genai
from dotenv import load_dotenv

from app.models.schemas import EnrichedBRS, SRSDocument

load_dotenv()

GEMINI_MODEL = "gemini-3.5-flash"
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


SRS_PROMPT = """You are a senior business analyst converting a Business
Requirements Specification into a formal Software Requirements Specification
(SRS), loosely following IEEE 830 structure.

STRICT RULES:
- Every functional requirement MUST have a source_ref pointing to the
  BR-xx requirement (or business goal) it comes from. Do not invent
  requirements with no basis in the input data below.
- Functional requirements should be atomic (one behavior per requirement),
  formally worded as "The system shall...".
- Derive non-functional requirements from the assumptions, constraints,
  and any informal quality expectations mentioned (e.g. "should feel fast"
  becomes a measurable performance NFR where reasonable).
- Generate 3-6 realistic use cases covering the main actors and flows implied
  by the requirements. Do not invent actors that aren't mentioned or implied.
- Carry forward the original constraints, and add any newly discovered ones
  from the research findings.

INPUT DATA (BRS summary + research findings):
{input_json}
"""


def generate_srs(enriched: EnrichedBRS) -> SRSDocument:
    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=SRS_PROMPT.format(input_json=enriched.model_dump_json(indent=2)),
        config={
            "response_mime_type": "application/json",
            "response_schema": SRSDocument,
        },
    )
    data = json.loads(response.text)
    return SRSDocument.model_validate(data)