"""Phase 3 — SRS generation (IEEE-830-flavoured)."""

from __future__ import annotations

from ..config import settings
from ..llm import LLMClient, LLMRequest
from ..prompts import SYSTEM_ANALYST, GENERATE_SRS
from ..schemas import SRS, EnrichedContext, Priority, Requirement, ReqType, UseCase


def _enum(cls, value, default):
    try:
        return cls(str(value).strip().lower())
    except (ValueError, AttributeError):
        return default


def generate_srs(enriched: EnrichedContext, client: LLMClient) -> SRS:
    data = client.complete_json(LLMRequest(
        task="generate_srs",
        system=SYSTEM_ANALYST,
        user=GENERATE_SRS.format(context=enriched.as_prompt_context()),
        payload={
            "context": enriched.as_prompt_context(),
            "title": enriched.summary.title,
            "business_goals": enriched.summary.business_goals,
            "stakeholders": enriched.summary.stakeholders,
        },
        max_tokens=min(8000, settings.max_tokens),
    ))

    requirements: list[Requirement] = []
    for i, r in enumerate(data.get("requirements") or [], start=1):
        requirements.append(Requirement(
            req_id=r.get("req_id") or f"REQ-{i:03d}",
            text=str(r.get("text", "")).strip(),
            req_type=_enum(ReqType, r.get("req_type"), ReqType.FUNCTIONAL),
            priority=_enum(Priority, r.get("priority"), Priority.SHOULD),
            rationale=str(r.get("rationale", "")),
            acceptance_criteria=list(r.get("acceptance_criteria") or []),
        ))

    use_cases = [
        UseCase(
            uc_id=u.get("uc_id") or f"UC-{i:03d}",
            name=str(u.get("name", "")),
            actor=str(u.get("actor", "User")),
            preconditions=list(u.get("preconditions") or []),
            main_flow=list(u.get("main_flow") or []),
            alt_flows=list(u.get("alt_flows") or []),
        )
        for i, u in enumerate(data.get("use_cases") or [], start=1)
    ]

    srs = SRS(
        title=data.get("title") or enriched.summary.title or "Software Requirements Specification",
        introduction=str(data.get("introduction", "")),
        overall_description=str(data.get("overall_description", "")),
        requirements=requirements,
        use_cases=use_cases,
        glossary=dict(data.get("glossary") or {}),
    )
    _dedupe_ids(srs)
    return srs


def _dedupe_ids(srs: SRS) -> None:
    """Models occasionally repeat an id. Ids are used as foreign keys by every
    later phase, so uniqueness is enforced here rather than debugged later."""
    seen: set[str] = set()
    for i, r in enumerate(srs.requirements, start=1):
        if r.req_id in seen or not r.req_id:
            r.req_id = f"REQ-{i:03d}"
            while r.req_id in seen:
                i += 1
                r.req_id = f"REQ-{i:03d}"
        seen.add(r.req_id)


def validate_srs(srs: SRS) -> list[str]:
    """Quality gate. Returned as warnings rather than exceptions — a partly
    weak SRS is still more useful than a crashed run."""
    issues: list[str] = []
    if not srs.requirements:
        issues.append("SRS contains no requirements.")
    for r in srs.requirements:
        if len(r.text) < 15:
            issues.append(f"{r.req_id}: requirement text is too short to be testable.")
        if not r.acceptance_criteria:
            issues.append(f"{r.req_id}: no acceptance criteria.")
        if " and " in r.text.lower() and r.text.lower().count(" and ") > 1:
            issues.append(f"{r.req_id}: looks compound; consider splitting into atomic requirements.")
    ids = [r.req_id for r in srs.requirements]
    if len(ids) != len(set(ids)):
        issues.append("Duplicate requirement ids detected.")
    return issues
