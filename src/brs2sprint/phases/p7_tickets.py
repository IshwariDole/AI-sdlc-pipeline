"""Phase 7 — Ticket generation, plus an optional Jira push."""

from __future__ import annotations

import json
import os

from ..config import settings
from ..llm import LLMClient, LLMRequest
from ..prompts import SYSTEM_PLANNER, WRITE_TICKETS
from ..schemas import Task, Ticket


def generate_tickets(tasks: list[Task], client: LLMClient) -> list[Ticket]:
    if not tasks:
        return []

    payload = [{
        "task_id": t.task_id, "title": t.title, "description": t.description,
        "req_ids": t.req_ids, "discipline": t.discipline.value,
        "story_points": t.story_points, "depends_on": t.depends_on,
    } for t in tasks]

    data = client.complete_json(LLMRequest(
        task="write_tickets",
        system=SYSTEM_PLANNER,
        user=WRITE_TICKETS.format(tasks=json.dumps(payload, indent=2, ensure_ascii=False)),
        payload={"tasks": payload},
        max_tokens=min(8000, settings.max_tokens),
    ))

    tickets = [Ticket(
        ticket_id=t.get("ticket_id") or f"TCK-{i:03d}",
        title=str(t.get("title", "")).strip(),
        description=str(t.get("description", "")).strip(),
        acceptance_criteria=list(t.get("acceptance_criteria") or []),
        labels=list(t.get("labels") or []),
        story_points=int(t.get("story_points", 3) or 3),
        depends_on=list(t.get("depends_on") or []),
        req_ids=list(t.get("req_ids") or []),
        epic=str(t.get("epic", "")),
    ) for i, t in enumerate(data.get("tickets") or [], start=1)]

    _repair_dependencies(tickets, tasks)
    return tickets


def _repair_dependencies(tickets: list[Ticket], tasks: list[Task]) -> None:
    """The model is asked to remap T- ids to TCK- ids. It sometimes forgets, so
    the mapping is re-derived from the task list and dangling edges dropped."""
    mapping = {t.task_id: t.task_id.replace("T-", "TCK-") for t in tasks}
    valid = {t.ticket_id for t in tickets}
    for tk in tickets:
        fixed = [mapping.get(d, d) for d in tk.depends_on]
        tk.depends_on = [d for d in dict.fromkeys(fixed) if d in valid and d != tk.ticket_id]


# --------------------------------------------------------------------------
# optional Jira export
# --------------------------------------------------------------------------

def push_to_jira(tickets: list[Ticket], project_key: str | None = None) -> list[str]:
    """Create issues in Jira Cloud. Needs JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN.

    Scope note: this is a demo-factor nicety, not a core feature. It is kept
    isolated so an auth problem here cannot affect the pipeline.
    """
    try:
        from jira import JIRA
    except ImportError as exc:
        raise ImportError("pip install jira") from exc

    url = os.getenv("JIRA_URL")
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    key = project_key or os.getenv("JIRA_PROJECT_KEY")
    if not all([url, email, token, key]):
        raise RuntimeError("Set JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY")

    client = JIRA(server=url, basic_auth=(email, token))
    created: list[str] = []
    remote: dict[str, str] = {}

    for t in tickets:
        body = t.description + "\n\nAcceptance criteria:\n" + \
            "\n".join(f"- {a}" for a in t.acceptance_criteria)
        issue = client.create_issue(
            project=key, summary=t.title[:250], description=body,
            issuetype={"name": "Task"}, labels=[l.replace(" ", "-") for l in t.labels],
        )
        remote[t.ticket_id] = issue.key
        created.append(issue.key)

    for t in tickets:                       # link dependencies after all exist
        for dep in t.depends_on:
            if dep in remote and t.ticket_id in remote:
                client.create_issue_link("Blocks", remote[dep], remote[t.ticket_id])

    return created


def to_csv(tickets: list[Ticket], path: str) -> str:
    """Jira/Trello-importable CSV — no API credentials required."""
    import csv
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Ticket ID", "Epic", "Summary", "Description",
                    "Acceptance Criteria", "Labels", "Story Points", "Depends On", "Requirements"])
        for t in tickets:
            w.writerow([t.ticket_id, t.epic, t.title, t.description,
                        " | ".join(t.acceptance_criteria), ",".join(t.labels),
                        t.story_points, ",".join(t.depends_on), ",".join(t.req_ids)])
    return path
