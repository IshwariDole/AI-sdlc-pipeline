import json

from app.models.schemas import EnrichedBRS, SRSDocument
from app.utils.llm_client import generate_structured


# ============================================================
# SMALL CUSTOM SCHEMA FOR GROQ
# ============================================================

SRS_SCHEMA_HINT = """
{
  "project_name": "string",
  "introduction": "brief project overview",
  "functional_requirements": [
    {
      "id": "FR-01",
      "description": "The system shall ...",
      "priority": "High",
      "source_ref": "BR-01"
    }
  ],
  "non_functional_requirements": [
    {
      "id": "NFR-01",
      "category": "Performance",
      "description": "specific measurable requirement"
    }
  ],
  "use_cases": [
    {
      "id": "UC-01",
      "title": "short title",
      "actor": "User",
      "description": "one sentence",
      "preconditions": ["condition"],
      "main_flow": [
        "step 1",
        "step 2"
      ]
    }
  ],
  "constraints": [
    "constraint"
  ]
}
"""


# ============================================================
# SRS GENERATION PROMPT
# ============================================================

SRS_PROMPT = """
You are a senior business analyst.

Convert the following enriched business requirements into a concise
Software Requirements Specification (SRS).

STRICT RULES:

1. Use ONLY information supported by the supplied BRS data.

2. Functional Requirements:
   - Generate between 5 and 8 requirements.
   - Each requirement must be atomic and testable.
   - Each description must start with:
     "The system shall ..."
   - Keep each description under 25 words.
   - Use IDs: FR-01, FR-02, FR-03, etc.
   - Use priority: High, Medium, or Low.
   - source_ref should reference the closest original BRS requirement.

3. Non-Functional Requirements:
   - Generate between 3 and 5 requirements.
   - Use IDs: NFR-01, NFR-02, etc.
   - Categories may include Performance, Security,
     Reliability, Usability, or Scalability.
   - Requirements must be measurable where possible.
   - Keep descriptions under 25 words.

4. Use Cases:
   - Generate between 3 and 6 important use cases.
   - Use IDs: UC-01, UC-02, etc.
   - Keep titles and descriptions short.
   - Each use case should contain 2 to 5 main flow steps.
   - Keep preconditions concise.

5. Introduction:
   - Maximum 3 sentences.

6. Constraints:
   - Include only actual or clearly implied constraints.
   - Keep each constraint concise.

7. Do not:
   - Repeat requirements.
   - Add unrelated features.
   - Add explanations outside the JSON.
   - Generate excessive detail.

ENRICHED BRS DATA:

{data}
"""


# ============================================================
# SRS GENERATION FUNCTION
# ============================================================

def generate_srs(enriched: EnrichedBRS) -> SRSDocument:
    """
    Generate a concise Software Requirements Specification
    from the enriched BRS.
    """

    # Convert Pydantic model to dictionary
    data = enriched.model_dump()

    # Compact JSON to reduce token usage
    payload = json.dumps(
        data,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    # Build final prompt
    prompt = SRS_PROMPT.format(
        data=payload
    )

    # Generate and validate structured output
    return generate_structured(
        prompt=prompt,
        schema=SRSDocument,
        schema_hint=SRS_SCHEMA_HINT,
    )