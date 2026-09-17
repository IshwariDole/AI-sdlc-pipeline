"""SQLite persistence (stdlib sqlite3 — no ORM).

Schema is intentionally small: runs, requirements, tickets, sprint assignments.
Full artefacts are also kept as a JSON blob on the run so nothing is lost when
the relational model does not cover a field.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import settings
from .schemas import PipelineResult, to_json

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id       TEXT PRIMARY KEY,
    source_path  TEXT,
    title        TEXT,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    llm_calls    INTEGER DEFAULT 0,
    payload      TEXT
);
CREATE TABLE IF NOT EXISTS requirements (
    run_id     TEXT,
    req_id     TEXT,
    text       TEXT,
    req_type   TEXT,
    priority   TEXT,
    kind       TEXT,
    confidence REAL,
    discipline TEXT,
    PRIMARY KEY (run_id, req_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS tickets (
    run_id       TEXT,
    ticket_id    TEXT,
    title        TEXT,
    description  TEXT,
    labels       TEXT,
    story_points INTEGER,
    depends_on   TEXT,
    epic         TEXT,
    sprint       INTEGER,
    PRIMARY KEY (run_id, ticket_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tickets_sprint ON tickets(run_id, sprint);
"""


@contextmanager
def connect(db_path: str | None = None):
    path = db_path or settings.db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def save_run(result: PipelineResult, db_path: str | None = None) -> None:
    init_db(db_path)
    sprint_of: dict[str, int] = {}
    if result.plan:
        for sp in result.plan.sprints:
            for t in sp.tickets:
                sprint_of[t.ticket_id] = sp.number

    with connect(db_path) as conn:
        conn.execute("DELETE FROM runs WHERE run_id = ?", (result.run_id,))
        conn.execute(
            "INSERT INTO runs (run_id, source_path, title, llm_calls, payload) VALUES (?,?,?,?,?)",
            (result.run_id, result.source_path,
             result.srs.title if result.srs else "",
             result.llm_calls, to_json(result)),
        )
        if result.srs:
            conn.executemany(
                "INSERT INTO requirements VALUES (?,?,?,?,?,?,?,?)",
                [(result.run_id, r.req_id, r.text, r.req_type.value, r.priority.value,
                  r.kind.value if r.kind else None, r.kind_confidence,
                  r.discipline.value if r.discipline else None)
                 for r in result.srs.requirements],
            )
        conn.executemany(
            "INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?)",
            [(result.run_id, t.ticket_id, t.title, t.description, json.dumps(t.labels),
              t.story_points, json.dumps(t.depends_on), t.epic, sprint_of.get(t.ticket_id))
             for t in result.tickets],
        )


def list_runs(db_path: str | None = None) -> list[dict]:
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT run_id, source_path, title, created_at, llm_calls FROM runs "
            "ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def load_run(run_id: str, db_path: str | None = None) -> dict | None:
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute("SELECT payload FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def board(run_id: str, db_path: str | None = None) -> dict[str, list[dict]]:
    """Tickets grouped by sprint, for the Kanban view."""
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE run_id = ? ORDER BY sprint, ticket_id", (run_id,)
        ).fetchall()
    out: dict[str, list[dict]] = {}
    for r in rows:
        key = f"Sprint {r['sprint']}" if r["sprint"] else "Backlog"
        d = dict(r)
        d["labels"] = json.loads(d["labels"] or "[]")
        d["depends_on"] = json.loads(d["depends_on"] or "[]")
        out.setdefault(key, []).append(d)
    return out
