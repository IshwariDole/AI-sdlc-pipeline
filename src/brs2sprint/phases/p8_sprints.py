"""Phase 8 — Sprint allocation.

No LLM here, on purpose. This is a deterministic constrained-scheduling
problem and an algorithm solves it correctly, cheaply and reproducibly:

  1. Kahn's algorithm       -> detect and report dependency cycles
  2. Longest-path ranking   -> critical-path-first ordering
  3. Greedy bin packing     -> fill each sprint to the team's velocity,
                               subject to "all dependencies land in an
                               earlier sprint"

Greedy first-fit-decreasing is not optimal (bin packing is NP-hard), but it is
within a known bound of optimal, runs in milliseconds, and produces a plan a
human can reason about — which matters more here than optimality.
"""

from __future__ import annotations

from ..schemas import Sprint, SprintPlan, Ticket


# --------------------------------------------------------------------------
# graph helpers
# --------------------------------------------------------------------------

def detect_cycles(tickets: list[Ticket]) -> list[list[str]]:
    """Return cycles as id lists. Empty list means the graph is a DAG."""
    graph = {t.ticket_id: [d for d in t.depends_on if d != t.ticket_id] for t in tickets}
    cycles: list[list[str]] = []
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {k: WHITE for k in graph}

    def visit(node: str, stack: list[str]) -> None:
        colour[node] = GREY
        stack.append(node)
        for dep in graph.get(node, []):
            if dep not in colour:
                continue
            if colour[dep] == GREY:
                cycles.append(stack[stack.index(dep):] + [dep])
            elif colour[dep] == WHITE:
                visit(dep, stack)
        stack.pop()
        colour[node] = BLACK

    for node in graph:
        if colour[node] == WHITE:
            visit(node, [])
    return cycles


def topological_order(tickets: list[Ticket]) -> list[str]:
    """Kahn's algorithm. Raises on a cycle — callers break cycles first."""
    graph = {t.ticket_id: set(d for d in t.depends_on if d != t.ticket_id) for t in tickets}
    indegree = {k: len(v & set(graph)) for k, v in graph.items()}
    ready = sorted([k for k, v in indegree.items() if v == 0])
    order: list[str] = []

    dependents: dict[str, list[str]] = {k: [] for k in graph}
    for node, deps in graph.items():
        for d in deps:
            if d in dependents:
                dependents[d].append(node)

    while ready:
        node = ready.pop(0)
        order.append(node)
        for child in sorted(dependents[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
        ready.sort()

    if len(order) != len(graph):
        raise ValueError("dependency graph contains a cycle")
    return order


def critical_path_rank(tickets: list[Ticket]) -> dict[str, int]:
    """Longest downstream path (in story points) from each ticket.

    Scheduling the longest chain first is what keeps total sprint count near
    the theoretical minimum — a ticket that blocks eight others must not sit
    waiting behind a leaf task.
    """
    by_id = {t.ticket_id: t for t in tickets}
    dependents: dict[str, list[str]] = {t.ticket_id: [] for t in tickets}
    for t in tickets:
        for d in t.depends_on:
            if d in dependents:
                dependents[d].append(t.ticket_id)

    memo: dict[str, int] = {}

    def longest(node: str, seen: frozenset[str] = frozenset()) -> int:
        if node in memo:
            return memo[node]
        if node in seen:                      # defensive: cycle
            return 0
        own = by_id[node].story_points
        best = max((longest(c, seen | {node}) for c in dependents[node]), default=0)
        memo[node] = own + best
        return memo[node]

    return {t.ticket_id: longest(t.ticket_id) for t in tickets}


# --------------------------------------------------------------------------
# allocator
# --------------------------------------------------------------------------

def allocate_sprints(
    tickets: list[Ticket],
    velocity: int = 20,
    max_sprints: int = 12,
) -> SprintPlan:
    plan = SprintPlan(velocity=velocity)
    if not tickets:
        return plan

    working = list(tickets)

    cycles = detect_cycles(working)
    if cycles:
        broken = set()
        for cycle in cycles:
            if len(cycle) >= 2:
                child, parent = cycle[-1], cycle[-2]
                for t in working:
                    if t.ticket_id == parent and child in t.depends_on:
                        t.depends_on.remove(child)
                        broken.add(f"{parent} -> {child}")
        plan.warnings.append(
            f"Broke {len(broken)} dependency edge(s) to remove cycle(s): {', '.join(sorted(broken))}"
        )

    rank = critical_path_rank(working)
    by_id = {t.ticket_id: t for t in working}

    oversized = [t for t in working if t.story_points > velocity]
    for t in oversized:
        plan.warnings.append(
            f"{t.ticket_id} is {t.story_points} points but sprint capacity is {velocity}; "
            "it gets a sprint of its own and should be split."
        )

    unassigned = {t.ticket_id for t in working}
    assigned_sprint: dict[str, int] = {}
    sprint_no = 0

    while unassigned and sprint_no < max_sprints:
        sprint_no += 1
        sprint = Sprint(number=sprint_no, capacity=velocity)

        # Ready = every dependency already placed in a *strictly earlier* sprint.
        ready = [
            by_id[tid] for tid in unassigned
            if all(dep in assigned_sprint and assigned_sprint[dep] < sprint_no
                   for dep in by_id[tid].depends_on)
        ]
        # Critical path first, then largest — first-fit-decreasing.
        ready.sort(key=lambda t: (-rank[t.ticket_id], -t.story_points, t.ticket_id))

        for t in ready:
            if t.story_points > velocity and not sprint.tickets:
                sprint.tickets.append(t)            # oversized: alone in its sprint
                break
            if t.story_points <= sprint.free_capacity:
                sprint.tickets.append(t)

        if not sprint.tickets:
            plan.warnings.append(
                f"Sprint {sprint_no} could not be filled — remaining work is blocked "
                "or every ready ticket exceeds capacity."
            )
            break

        for t in sprint.tickets:
            assigned_sprint[t.ticket_id] = sprint_no
            unassigned.discard(t.ticket_id)
        plan.sprints.append(sprint)

    if unassigned:
        plan.unscheduled = [by_id[t] for t in sorted(unassigned)]
        plan.warnings.append(
            f"{len(unassigned)} ticket(s) unscheduled after {max_sprints} sprints — "
            "raise MAX_SPRINTS or team velocity."
        )
    return plan


def plan_metrics(plan: SprintPlan) -> dict:
    committed = [s.committed_points for s in plan.sprints]
    total = sum(committed)
    return {
        "sprints": len(plan.sprints),
        "total_points": total,
        "unscheduled_tickets": len(plan.unscheduled),
        "avg_utilisation_pct": round(
            100 * (total / max(len(plan.sprints) * plan.velocity, 1)), 1),
        "points_per_sprint": committed,
        "warnings": plan.warnings,
    }
