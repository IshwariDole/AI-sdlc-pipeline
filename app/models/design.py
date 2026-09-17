from pydantic import BaseModel, Field
from typing import List, Optional


class Component(BaseModel):
    name: str
    responsibility: str
    technologies: List[str] = Field(default_factory=list)
    related_requirements: List[str] = Field(default_factory=list)


class APIContract(BaseModel):
    name: str
    method: str
    endpoint: str
    description: str
    request_body: Optional[str] = None
    response_body: Optional[str] = None
    related_requirements: List[str] = Field(default_factory=list)


class DBColumn(BaseModel):
    name: str
    data_type: str
    description: Optional[str] = None


class DBTable(BaseModel):
    name: str
    description: str
    columns: List[DBColumn] = Field(default_factory=list)
    related_requirements: List[str] = Field(default_factory=list)


class HLD(BaseModel):
    architecture_overview: str

    components: List[Component] = Field(
        default_factory=list
    )

    data_flow: List[str] = Field(
        default_factory=list
    )

    technology_stack: List[str] = Field(
        default_factory=list
    )

    mermaid_diagram: Optional[str] = None


class LLD(BaseModel):

    modules: List[str] = Field(
        default_factory=list
    )

    api_contracts: List[APIContract] = Field(
        default_factory=list
    )

    database_schema: List[DBTable] = Field(
        default_factory=list
    )


class DesignDocument(BaseModel):

    project_name: str

    source_requirements: List[str] = Field(
        default_factory=list
    )

    hld: HLD

    lld: LLD