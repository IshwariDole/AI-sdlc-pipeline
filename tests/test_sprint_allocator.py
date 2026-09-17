"""Tests for phase 8 — the algorithmic core. Run: python -m pytest tests/ -q
(also runs standalone: python tests/test_sprint_allocator.py)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brs2sprint.phases.p8_sprints import (          # noqa: E402
    allocate_sprints, critical_path_rank, detect_cycles, plan_metrics, topological_order,
)
from brs2sprint.schemas import Ticket               # noqa: E402


def T(tid, points=3, deps=None):
    return Ticket(ticket_id=tid, title=tid, description="", story_points=points,
                  depends_on=deps or [])


def test_empty_input():
    plan = allocate_sprints([], velocity=20)
    assert plan.sprints == [] and plan.unscheduled == []


def test_respects_capacity():
    tickets = [T(f"TCK-{i:03d}", 8) for i in range(6)]
    plan = allocate_sprints(tickets, velocity=20)
    for s in plan.sprints:
        assert s.committed_points <= 20, f"sprint {s.number} over capacity"
    assert sum(len(s.tickets) for s in plan.sprints) == 6


def test_dependencies_land_in_earlier_sprints():
    tickets = [T("A", 5), T("B", 5, ["A"]), T("C", 5, ["B"]), T("D", 5, ["C"])]
    plan = allocate_sprints(tickets, velocity=20)
    where = {t.ticket_id: s.number for s in plan.sprints for t in s.tickets}
    assert where["A"] < where["B"] < where["C"] < where["D"]
    # A pure chain cannot be compressed: 4 links -> 4 sprints regardless of capacity.
    assert len(plan.sprints) == 4


def test_independent_tickets_pack_together():
    tickets = [T(f"T{i}", 5) for i in range(4)]
    plan = allocate_sprints(tickets, velocity=20)
    assert len(plan.sprints) == 1 and plan.sprints[0].committed_points == 20


def test_no_ticket_scheduled_twice():
    tickets = [T("A", 3), T("B", 3, ["A"]), T("C", 3, ["A"]), T("D", 3, ["B", "C"])]
    plan = allocate_sprints(tickets, velocity=6)
    seen = [t.ticket_id for s in plan.sprints for t in s.tickets]
    assert len(seen) == len(set(seen)) == 4


def test_cycle_is_detected_and_broken():
    tickets = [T("A", 3, ["C"]), T("B", 3, ["A"]), T("C", 3, ["B"])]
    assert detect_cycles(tickets)
    plan = allocate_sprints(tickets, velocity=10)
    assert any("cycle" in w.lower() for w in plan.warnings)
    assert sum(len(s.tickets) for s in plan.sprints) == 3   # still fully scheduled


def test_oversized_ticket_gets_own_sprint_and_warning():
    tickets = [T("BIG", 34), T("SMALL", 2)]
    plan = allocate_sprints(tickets, velocity=10)
    assert any("BIG" in w for w in plan.warnings)
    big_sprint = next(s for s in plan.sprints if any(t.ticket_id == "BIG" for t in s.tickets))
    assert len(big_sprint.tickets) == 1


def test_max_sprints_leaves_work_unscheduled():
    tickets = [T("A", 5), T("B", 5, ["A"]), T("C", 5, ["B"])]
    plan = allocate_sprints(tickets, velocity=5, max_sprints=2)
    assert len(plan.unscheduled) == 1 and plan.unscheduled[0].ticket_id == "C"


def test_topological_order_is_valid():
    tickets = [T("A"), T("B", deps=["A"]), T("C", deps=["A"]), T("D", deps=["B", "C"])]
    order = topological_order(tickets)
    pos = {tid: i for i, tid in enumerate(order)}
    for t in tickets:
        for d in t.depends_on:
            assert pos[d] < pos[t.ticket_id]


def test_topological_order_raises_on_cycle():
    tickets = [T("A", deps=["B"]), T("B", deps=["A"])]
    try:
        topological_order(tickets)
    except ValueError:
        return
    raise AssertionError("expected ValueError on cyclic graph")


def test_critical_path_prioritises_long_chains():
    tickets = [T("HEAD", 1, []), T("MID", 1, ["HEAD"]), T("TAIL", 1, ["MID"]), T("LEAF", 1, [])]
    rank = critical_path_rank(tickets)
    assert rank["HEAD"] > rank["LEAF"]
    plan = allocate_sprints(tickets, velocity=1)
    assert plan.sprints[0].tickets[0].ticket_id == "HEAD"   # chain scheduled first


def test_metrics_are_consistent():
    tickets = [T(f"T{i}", 4) for i in range(10)]
    plan = allocate_sprints(tickets, velocity=20)
    m = plan_metrics(plan)
    assert m["total_points"] == 40
    assert sum(m["points_per_sprint"]) == 40
    assert 0 <= m["avg_utilisation_pct"] <= 100


if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL  {name}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
