"""Phase 5 — HLD / LLD generation, with Mermaid diagram-as-code output."""

from __future__ import annotations

import json
import re

from ..config import settings
from ..llm import LLMClient, LLMRequest
from ..prompts import SYSTEM_ARCHITECT, GENERATE_DESIGN
from ..schemas import SRS, APIContract, Component, DBTable, Design


def generate_design(srs: SRS, client: LLMClient) -> Design:
    tech = srs.technical()
    if not tech:
        return Design(overview="No technical requirements were identified; no design generated.")

    payload_reqs = [
        {"req_id": r.req_id, "text": r.text, "req_type": r.req_type.value,
         "priority": r.priority.value,
         "discipline": r.discipline.value if r.discipline else "backend"}
        for r in tech
    ]
    constraints = [r.text for r in srs.requirements if r.req_type.value == "constraint"]

    data = client.complete_json(LLMRequest(
        task="generate_design",
        system=SYSTEM_ARCHITECT,
        user=GENERATE_DESIGN.format(
            requirements=json.dumps(payload_reqs, indent=2, ensure_ascii=False),
            constraints="\n".join(f"- {c}" for c in constraints) or "(none stated)",
        ),
        payload={"requirements": payload_reqs, "constraints": constraints},
        max_tokens=min(8000, settings.max_tokens),
    ))

    design = Design(
        overview=str(data.get("overview", "")),
        components=[Component(
            name=str(c.get("name", "")),
            responsibility=str(c.get("responsibility", "")),
            tech=str(c.get("tech", "")),
            depends_on=list(c.get("depends_on") or []),
        ) for c in data.get("components") or []],
        data_flow=str(data.get("data_flow", "")),
        api_contracts=[APIContract(
            method=str(a.get("method", "GET")).upper(),
            path=str(a.get("path", "/")),
            summary=str(a.get("summary", "")),
            request_schema=dict(a.get("request_schema") or {}),
            response_schema=dict(a.get("response_schema") or {}),
        ) for a in data.get("api_contracts") or []],
        db_tables=[DBTable(
            name=str(t.get("name", "")),
            columns=dict(t.get("columns") or {}),
            notes=str(t.get("notes", "")),
        ) for t in data.get("db_tables") or []],
        mermaid_hld=_clean_mermaid(str(data.get("mermaid_hld", ""))),
        mermaid_erd=_clean_mermaid(str(data.get("mermaid_erd", ""))),
        covers_req_ids=list(data.get("covers_req_ids") or [r.req_id for r in tech]),
    )

    if not design.mermaid_hld:
        design.mermaid_hld = mermaid_from_components(design)
    return design


def _clean_mermaid(text: str) -> str:
    """Models like to wrap diagrams in fences even when told not to."""
    return re.sub(r"^\s*```(?:mermaid)?|```\s*$", "", text, flags=re.MULTILINE).strip()


def mermaid_from_components(design: Design) -> str:
    """Deterministic fallback so a diagram always renders."""
    def nid(name: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "", name) or "N"

    lines = ["graph TD"]
    for c in design.components:
        lines.append(f'  {nid(c.name)}["{c.name}<br/><i>{c.tech}</i>"]')
    for c in design.components:
        for dep in c.depends_on:
            lines.append(f"  {nid(dep)} --> {nid(c.name)}")
    return "\n".join(lines)


def coverage_report(srs: SRS, design: Design) -> dict:
    """Traceability check: which technical requirements the design misses."""
    covered = set(design.covers_req_ids)
    tech_ids = {r.req_id for r in srs.technical()}
    missing = sorted(tech_ids - covered)
    return {
        "technical_requirements": len(tech_ids),
        "covered": len(tech_ids & covered),
        "uncovered_req_ids": missing,
        "coverage_pct": round(100 * len(tech_ids & covered) / max(len(tech_ids), 1), 1),
    }
