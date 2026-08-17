from pydantic import BaseModel, Field
from typing import List


class Stakeholder(BaseModel):
    role: str = Field(description="The stakeholder's role, e.g. 'Business Owner'")
    description: str = Field(description="Brief note on their interest/involvement")


class BRSSummary(BaseModel):
    project_name: str = Field(description="Name of the project or product")
    business_goals: List[str] = Field(description="List of distinct business goals")
    stakeholders: List[Stakeholder] = Field(description="Key stakeholders involved")
    scope_in: List[str] = Field(description="Items explicitly in scope")
    scope_out: List[str] = Field(description="Items explicitly out of scope")
    constraints: List[str] = Field(description="Business, budget, timeline, or compliance constraints")
    assumptions: List[str] = Field(description="Assumptions stated or implied in the document")
    raw_requirements: List[str] = Field(description="Every individual requirement line found in the document, verbatim or lightly cleaned")

class ResearchFinding(BaseModel):
    topic: str = Field(description="The vague point from the BRS that needed research")
    finding: str = Field(description="What was found — concrete, specific information")
    source_note: str = Field(description="Brief note on where this came from, e.g. 'web search'")


class EnrichedBRS(BaseModel):
    summary: BRSSummary
    research_findings: List[ResearchFinding] = Field(default_factory=list)

class UseCase(BaseModel):
    id: str = Field(description="Short identifier, e.g. 'UC-01'")
    title: str = Field(description="Short name of the use case")
    actor: str = Field(description="Who performs this use case, e.g. 'Customer'")
    description: str = Field(description="What happens in this use case")
    preconditions: List[str] = Field(default_factory=list)
    main_flow: List[str] = Field(description="Ordered steps of the main success scenario")


class FunctionalRequirement(BaseModel):
    id: str = Field(description="Requirement ID, e.g. 'FR-01'")
    description: str = Field(description="Clear, testable requirement statement, phrased as 'The system shall...'")
    priority: str = Field(description="High, Medium, or Low")
    source_ref: str = Field(description="Which BRS requirement this traces back to, e.g. 'BR-01'")


class NonFunctionalRequirement(BaseModel):
    id: str = Field(description="Requirement ID, e.g. 'NFR-01'")
    category: str = Field(description="e.g. Performance, Security, Reliability, Usability, Scalability")
    description: str = Field(description="Specific, measurable statement -- avoid vague words like 'fast' or 'reliable'")


class UseCase(BaseModel):
    id: str = Field(description="Use case ID, e.g. 'UC-01'")
    title: str = Field(description="Short name of the use case")
    actor: str = Field(description="Who performs this use case, e.g. 'Customer', 'Admin'")
    description: str = Field(description="One-sentence summary of the use case")
    preconditions: List[str] = Field(default_factory=list, description="What must be true before this use case starts")
    main_flow: List[str] = Field(description="Ordered steps from trigger to outcome")


class SRSDocument(BaseModel):
    project_name: str
    introduction: str = Field(description="1-2 paragraph purpose and overview")
    functional_requirements: List[FunctionalRequirement]
    non_functional_requirements: List[NonFunctionalRequirement]
    use_cases: List[UseCase]
    constraints: List[str]


class RequirementClassification(BaseModel):
    id: str = Field(description="The FR/NFR ID being classified, e.g. 'FR-03'")
    text: str = Field(description="The original requirement text, copied as-is")
    type: str = Field(description="Exactly 'Technical' or 'Non-Technical'")
    subcategory: str = Field(description="If Technical: Frontend, Backend, Database, Integration, Security, Infrastructure, or QA. If Non-Technical: Business Process, Documentation, Training, Compliance/Legal, or Other.")
    reasoning: str = Field(description="One-sentence justification for the classification")


class ClassifiedSRS(BaseModel):
    project_name: str
    classifications: List[RequirementClassification]

class Component(BaseModel):
    name: str = Field(description="Component name, e.g. 'Auth Service', 'Product Catalog API'")
    responsibility: str = Field(description="What this component owns/does")
    related_requirements: List[str] = Field(description="FR/NFR IDs this component fulfills")


class ApiContract(BaseModel):
    endpoint: str = Field(description="e.g. 'POST /api/orders'")
    purpose: str = Field(description="One-line description")
    request_shape: str = Field(description="Key fields expected in the request, brief")
    response_shape: str = Field(description="Key fields returned, brief")


class DbTable(BaseModel):
    name: str = Field(description="Table/collection name")
    key_fields: List[str] = Field(description="Important fields, e.g. 'id (PK)', 'email (unique)'")
    notes: str = Field(description="Relationships or important constraints")


class HLD(BaseModel):
    architecture_overview: str = Field(description="2-3 sentence description of the overall architecture style, e.g. layered monolith, microservices")
    components: List[Component]
    tech_stack_suggestion: List[str] = Field(description="Suggested technologies with brief justification each")
    mermaid_diagram: str = Field(description="A valid Mermaid flowchart (graph TD) showing components and data flow")


class LLD(BaseModel):
    api_contracts: List[ApiContract]
    db_schema: List[DbTable]
    module_notes: str = Field(description="Any important implementation-level notes or edge cases to watch for")


class DesignDocument(BaseModel):
    project_name: str
    hld: HLD
    lld: LLD