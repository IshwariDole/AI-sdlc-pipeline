from app.models.schemas import EnrichedBRS, SRSDocument
from app.utils.llm_client import generate_structured

SRS_PROMPT = """You are a senior business analyst producing a formal Software
Requirements Specification (SRS) from an enriched business requirements summary.

Follow these rules strictly:
- Every functional requirement must be atomic (one clear capability per requirement),
  testable, and phrased as "The system shall...".
- Trace every functional requirement back to a source BRS requirement ID where possible.
- Non-functional requirements must be specific and measurable. Never use vague words
  like "fast", "reliable", "user-friendly" without a concrete metric or threshold.
  Where the source material is vague, propose a reasonable, industry-typical
  measurable target and note that it is a proposed default.
- Derive use cases from the functional requirements and stakeholders -- each use
  case should have a clear actor, trigger, and outcome.
- Do not invent requirements unrelated to the source material.

ENRICHED BRS DATA:
{data}
"""


def generate_srs(enriched: EnrichedBRS) -> SRSDocument:
    payload = enriched.model_dump_json(indent=2)
    prompt = SRS_PROMPT.format(data=payload)
    return generate_structured(prompt, SRSDocument)