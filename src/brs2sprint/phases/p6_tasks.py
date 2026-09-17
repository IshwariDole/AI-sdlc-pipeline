"""Phase 6 — Task planning (requirement + design -> epic/story/task)."""

from __future__ import annotations

import json

from ..config import settings
from ..llm import LLMClient, LLMRequest
from ..prompts import SYSTEM_PLANNER, PLAN_TASKS
from ..schemas import SRS, Design, Discipline, Task, to_json

FIBONACCI = (1, 2, 3, 5, 8)


def plan_tasks(srs: SRS, design: Design, client: LLMClient) -> list[Task]:
    tech = srs.technical()
    if not tech:
        return []

    payload_reqs = [
        {"req_id": r.req_id, "text": r.text,
         "discipline": r.discipline.value if r.discipline else "backend",
         "priority": r.priority.value,
         "acceptance_criteria": r.acceptance_criteria}
        for r in tech
    ]
    design_blob = to_json({
        "overview": design.overview,
        "components": [c.__dict__ for c in design.components],
        "api_contracts": [a.__dict__ for a in design.api_contracts],
        "db_tables": [t.__dict__ for t in design.db_tables],
    })

    data = client.complete_json(LLMRequest(
        task="plan_tasks",
        system=SYSTEM_PLANNER,
        user=PLAN_TASKS.format(
            requirements=json.dumps(payload_reqs, indent=2, ensure_ascii=False),
            design=design_blob[:20000],
        ),
        payload={"requirements": payload_reqs, "design": design_blob},
        max_tokens=min(8000, settings.max_tokens),
    ))

    tasks: list[Task] = []
    for i, t in enumerate(data.get("tasks") or [], start=1):
        try:
            disc = Discipline(str(t.get("discipline", "backend")).lower())
        except ValueError:
            disc = Discipline.BACKEND
        tasks.append(Task(
            task_id=t.get("task_id") or f"T-{i:03d}",
            title=str(t.get("title", "")).strip(),
            description=str(t.get("description", "")).strip(),
            req_ids=list(t.get("req_ids") or []),
            discipline=disc,
            story_points=_normalize_points(t.get("story_points", 3)),
            depends_on=list(t.get("depends_on") or []),
        ))

    _sanitize_dependencies(tasks)
    return tasks


def _normalize_points(value) -> int:
    """Snap to the nearest Fibonacci value and cap at 8. Models drift into 13,
    20 and 40 despite instructions; oversized tickets break sprint packing."""
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        v = 3
    v = max(1, min(v, 8))
    return min(FIBONACCI, key=lambda f: abs(f - v))


def _sanitize_dependencies(tasks: list[Task]) -> None:
    """Drop self-references, dangling ids, and any edge that would create a
    cycle. Phase 8's topological sort assumes a DAG, so it is enforced here."""
    ids = {t.task_id for t in tasks}
    index = {t.task_id: i for i, t in enumerate(tasks)}

    for t in tasks:
        t.depends_on = [d for d in dict.fromkeys(t.depends_on) if d in ids and d != t.task_id]

    # Break cycles with DFS, removing the back edge we arrive on.
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {t.task_id: WHITE for t in tasks}

    def visit(node: str) -> None:
        colour[node] = GREY
        task = tasks[index[node]]
        for dep in list(task.depends_on):
            if colour[dep] == GREY:
                task.depends_on.remove(dep)          # back edge -> cycle
            elif colour[dep] == WHITE:
                visit(dep)
        colour[node] = BLACK

    for t in tasks:
        if colour[t.task_id] == WHITE:
            visit(t.task_id)


def summarize_plan(tasks: list[Task]) -> dict:
    by_disc: dict[str, int] = {}
    for t in tasks:
        by_disc[t.discipline.value] = by_disc.get(t.discipline.value, 0) + t.story_points
    return {
        "task_count": len(tasks),
        "total_points": sum(t.story_points for t in tasks),
        "points_by_discipline": by_disc,
    }
