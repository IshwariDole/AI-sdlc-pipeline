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