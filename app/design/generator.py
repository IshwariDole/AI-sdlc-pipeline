from app.models.schemas import ClassifiedSRS, DesignDocument
from app.utils.llm_client import generate_structured


DESIGN_PROMPT = """
You are a Senior Solutions Architect.

Your task is to generate a High-Level Design (HLD) and Low-Level
Design (LLD) based ONLY on the provided TECHNICAL requirements.

PROJECT NAME:
{project_name}

TECHNICAL REQUIREMENTS:
{data}

IMPORTANT RULES:

1. Only design for TECHNICAL requirements.
   Ignore Non-Technical requirements completely.

2. Group related requirements into logical system components.
   Do NOT create one component for every requirement.

3. Each component should clearly describe:
   - its name
   - its responsibility
   - technologies used
   - related requirement IDs

4. The High-Level Design should include:
   - architecture overview
   - logical components
   - data flow
   - technology stack suggestion
   - Mermaid architecture diagram

5. The Mermaid diagram MUST:
   - start with "graph TD"
   - use valid Mermaid flowchart syntax
   - contain 8 to 12 nodes maximum
   - show meaningful data or control flow

6. The Low-Level Design should include:
   - modules
   - API contracts
   - database schema

7. API contracts should represent the main operations required
   by the technical requirements.

8. Database tables should represent the main data entities
   required by the system.

9. Maintain requirement traceability.
   Components, APIs, and database entities should reference
   the relevant requirement IDs wherever supported by the schema.

Return ONLY valid JSON matching the DesignDocument schema.
"""


def generate_design(
    classified: ClassifiedSRS,
    project_name: str = "AI-SDLC Project"
) -> DesignDocument:

    # Filter only technical requirements
    technical_items = [
        item
        for item in classified.classifications
        if item.type.lower() == "technical"
    ]

    if not technical_items:
        raise ValueError(
            "No technical requirements found to design for."
        )

    # Convert requirements into clean text for the LLM
    lines = "\n".join(
        f"{item.id} [{item.subcategory}]: {item.text}"
        for item in technical_items
    )

    # Create prompt
    prompt = DESIGN_PROMPT.format(
        project_name=project_name,
        data=lines
    )

    # Generate structured design
    response = generate_structured(
        prompt=prompt,
        schema=DesignDocument
    )

    return response