from app.models.schemas import ClassifiedSRS, DesignDocument
from app.utils.llm_client import generate_structured

DESIGN_PROMPT = """You are a solutions architect producing a High-Level Design (HLD)
and Low-Level Design (LLD) from a set of classified technical requirements.

Rules:
- Only design for TECHNICAL requirements. Ignore any Non-Technical items entirely.
- Group related requirements into logical components (e.g. Auth Service, Catalog
  Service, Payment Integration) rather than one component per requirement.
- The tech_stack_suggestion should be reasonable and typical for the described
  requirements -- name real, current technologies, not placeholders.
- mermaid_diagram MUST be valid Mermaid flowchart syntax starting with "graph TD",
  showing components as nodes and data/control flow as labeled arrows between them.
  Keep it to 8-12 nodes maximum for readability.
- LLD api_contracts should cover the main operations implied by the technical
  requirements (not necessarily one per requirement).
- db_schema should reflect the data entities implied by the requirements.

TECHNICAL REQUIREMENTS:
{data}
"""


def generate_design(classified: ClassifiedSRS) -> DesignDocument:
    technical_items = [c for c in classified.classifications if c.type == "Technical"]

    if not technical_items:
        raise ValueError("No technical requirements found to design for.")

    lines = "\n".join(f"{c.id} [{c.subcategory}]: {c.text}" for c in technical_items)
    prompt = DESIGN_PROMPT.format(data=lines)

    return generate_structured(prompt, DesignDocument)