"""Data contracts passed between pipeline phases.

Deliberately stdlib-only (dataclasses, not pydantic) so the core pipeline has
zero third-party dependencies. Adapters at the edges (parsers, LLM providers,
FastAPI, Streamlit) are where the dependencies live.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict, is_dataclass
from enum import Enum
from typing import Any


# --------------------------------------------------------------------------
# enums
# --------------------------------------------------------------------------

class ReqKind(str, Enum):
    TECHNICAL = "technical"
    NON_TECHNICAL = "non_technical"


class ReqType(str, Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    CONSTRAINT = "constraint"


class Priority(str, Enum):
    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "wont"


class Discipline(str, Enum):
    BACKEND = "backend"
    FRONTEND = "frontend"
    DATA = "data"
    DEVOPS = "devops"
    QA = "qa"
    DESIGN = "design"
    BUSINESS = "business"


# --------------------------------------------------------------------------
# phase 1 — ingestion
# --------------------------------------------------------------------------

@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    order: int
    char_start: int = 0
    char_end: int = 0


@dataclass
class BRSSummary:
    """Phase 1 output."""
    title: str = ""
    business_goals: list[str] = field(default_factory=list)
    stakeholders: list[str] = field(default_factory=list)
    scope_in: list[str] = field(default_factory=list)
    scope_out: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    raw_char_count: int = 0
    chunk_count: int = 0


# --------------------------------------------------------------------------
# phase 2 — research
# --------------------------------------------------------------------------

@dataclass
class ResearchFinding:
    question: str
    answer: str
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.5


@dataclass
class EnrichedContext:
    """Phase 2 output: summary + gap-filling findings."""
    summary: BRSSummary
    findings: list[ResearchFinding] = field(default_factory=list)

    def as_prompt_context(self) -> str:
        lines = [f"# {self.summary.title}", "", "## Business goals"]
        lines += [f"- {g}" for g in self.summary.business_goals]
        lines += ["", "## Stakeholders"] + [f"- {s}" for s in self.summary.stakeholders]
        lines += ["", "## In scope"] + [f"- {s}" for s in self.summary.scope_in]
        lines += ["", "## Out of scope"] + [f"- {s}" for s in self.summary.scope_out]
        lines += ["", "## Constraints"] + [f"- {c}" for c in self.summary.constraints]
        if self.findings:
            lines += ["", "## Research findings"]
            for f_ in self.findings:
                lines.append(f"- Q: {f_.question}\n  A: {f_.answer}")
        return "\n".join(lines)


# --------------------------------------------------------------------------
# phase 3 / 4 — SRS + classification
# --------------------------------------------------------------------------

@dataclass
class Requirement:
    req_id: str
    text: str
    req_type: ReqType = ReqType.FUNCTIONAL
    priority: Priority = Priority.SHOULD
    rationale: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    # filled by phase 4
    kind: ReqKind | None = None
    kind_confidence: float = 0.0
    kind_reason: str = ""
    discipline: Discipline | None = None


@dataclass
class UseCase:
    uc_id: str
    name: str
    actor: str
    preconditions: list[str] = field(default_factory=list)
    main_flow: list[str] = field(default_factory=list)
    alt_flows: list[str] = field(default_factory=list)


@dataclass
class SRS:
    """Phase 3 output, IEEE-830-flavoured."""
    title: str = ""
    introduction: str = ""
    overall_description: str = ""
    requirements: list[Requirement] = field(default_factory=list)
    use_cases: list[UseCase] = field(default_factory=list)
    glossary: dict[str, str] = field(default_factory=dict)

    def technical(self) -> list[Requirement]:
        return [r for r in self.requirements if r.kind == ReqKind.TECHNICAL]

    def non_technical(self) -> list[Requirement]:
        return [r for r in self.requirements if r.kind == ReqKind.NON_TECHNICAL]


# --------------------------------------------------------------------------
# phase 5 — design
# --------------------------------------------------------------------------

@dataclass
class Component:
    name: str
    responsibility: str
    tech: str = ""
    depends_on: list[str] = field(default_factory=list)


@dataclass
class APIContract:
    method: str
    path: str
    summary: str
    request_schema: dict[str, str] = field(default_factory=dict)
    response_schema: dict[str, str] = field(default_factory=dict)


@dataclass
class DBTable:
    name: str
    columns: dict[str, str] = field(default_factory=dict)
    notes: str = ""


@dataclass
class Design:
    """Phase 5 output (HLD + LLD)."""
    overview: str = ""
    components: list[Component] = field(default_factory=list)
    data_flow: str = ""
    api_contracts: list[APIContract] = field(default_factory=list)
    db_tables: list[DBTable] = field(default_factory=list)
    mermaid_hld: str = ""
    mermaid_erd: str = ""
    covers_req_ids: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# phase 6 / 7 — tasks + tickets
# --------------------------------------------------------------------------

@dataclass
class Task:
    task_id: str
    title: str
    description: str
    req_ids: list[str] = field(default_factory=list)
    discipline: Discipline = Discipline.BACKEND
    story_points: int = 3
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Ticket:
    ticket_id: str
    title: str
    description: str
    acceptance_criteria: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    story_points: int = 3
    depends_on: list[str] = field(default_factory=list)
    req_ids: list[str] = field(default_factory=list)
    epic: str = ""


# --------------------------------------------------------------------------
# phase 8 — sprints
# --------------------------------------------------------------------------

@dataclass
class Sprint:
    number: int
    tickets: list[Ticket] = field(default_factory=list)
    capacity: int = 20

    @property
    def committed_points(self) -> int:
        return sum(t.story_points for t in self.tickets)

    @property
    def free_capacity(self) -> int:
        return self.capacity - self.committed_points


@dataclass
class SprintPlan:
    sprints: list[Sprint] = field(default_factory=list)
    unscheduled: list[Ticket] = field(default_factory=list)
    velocity: int = 20
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# full run
# --------------------------------------------------------------------------

@dataclass
class PipelineResult:
    run_id: str
    source_path: str
    summary: BRSSummary | None = None
    enriched: EnrichedContext | None = None
    srs: SRS | None = None
    design: Design | None = None
    tasks: list[Task] = field(default_factory=list)
    tickets: list[Ticket] = field(default_factory=list)
    plan: SprintPlan | None = None
    timings: dict[str, float] = field(default_factory=dict)
    llm_calls: int = 0


# --------------------------------------------------------------------------
# (de)serialisation helpers
# --------------------------------------------------------------------------

def _default(o: Any) -> Any:
    if isinstance(o, Enum):
        return o.value
    if is_dataclass(o):
        return asdict(o)
    raise TypeError(f"not serialisable: {type(o)}")


def to_json(obj: Any, indent: int = 2) -> str:
    """Dataclass tree -> JSON string (enums flattened to their values)."""
    if is_dataclass(obj):
        obj = asdict(obj)
    return json.dumps(obj, indent=indent, default=_default, ensure_ascii=False)
