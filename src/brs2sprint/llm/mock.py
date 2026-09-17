"""Offline, deterministic, rule-based stand-in for an LLM.

Why this exists:
  1. The whole pipeline is runnable and demo-able with no API key, no network
     and no spend — useful in CI, in interviews, and on a plane.
  2. It pins the JSON shape of every phase, so tests assert on structure
     rather than on model behaviour.

It is NOT an LLM. Output quality is heuristic. Set LLM_PROVIDER=anthropic for
real results.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .base import LLMClient, LLMRequest

TECH_MARKERS = [
    "api", "endpoint", "database", "schema", "query", "cache", "index", "encrypt",
    "authenticate", "authentication", "authorisation", "authorization", "token", "oauth",
    "latency", "throughput", "response time", "uptime", "availability", "scalab",
    "integrate", "integration", "webhook", "sync", "migrate", "deploy", "pipeline",
    "server", "service", "microservice", "queue", "log", "backup", "search",
    "upload", "notification", "dashboard", "mobile app", "web app", "sso", "rest",
    "payload", "concurrency", "https", "tls", "encrypt at rest", "hl7", "export",
]
NON_TECH_MARKERS = [
    "train", "policy", "policies", "documentation", "user guide", "user manual",
    "marketing", "onboarding process", "legal", "contract", "sign off", "sign-off",
    "approval", "approve", "budget", "vendor", "procurement", "governance",
    "workshop", "change management", "communication plan", "hiring", "process owner",
    "impact assessment", "brand", "pricing", "commercial", "must be published",
    "rollback", "rollout", "goes live", "go live", "shall be agreed", "finalised by",
]
DISCIPLINE_MARKERS = {
    "frontend": ["ui", "screen", "page", "dashboard", "form", "responsive", "mobile app", "wcag", "accessib"],
    "data": ["report", "analytics", "etl", "warehouse", "schema", "migration", "dataset"],
    "devops": ["deploy", "uptime", "availability", "backup", "monitor", "ci/cd", "scal", "infrastructure"],
    "qa": ["test", "validation", "verify", "quality"],
    "business": NON_TECH_MARKERS,
}

_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
_BULLET = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+(.*)$")
_NUMBERED_HEADING = re.compile(r"^\d+(\.\d+)*\.?\s+\S.{0,58}$")


def _is_heading_line(stripped: str) -> bool:
    """Recognises Markdown headings, colon-suffixed labels, and the numbered
    heading style Word documents commonly use ("3.1 In Scope") which has
    neither a leading '#' nor a trailing colon. Excludes lines ending in
    terminal punctuation so numbered *sentences* ("1. Do the thing.") are
    not mistaken for section headings."""
    if stripped.startswith("#"):
        return True
    if stripped.endswith(":") and len(stripped) < 60:
        return True
    if _NUMBERED_HEADING.match(stripped) and not stripped.endswith((".", "?", "!")):
        return True
    return False


def _sid(text: str, n: int = 6) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def _bullets(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        m = _BULLET.match(line)
        if m and len(m.group(1).strip()) > 8:
            out.append(m.group(1).strip())
    return out


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if len(s.strip()) > 25]


def _statements(text: str) -> list[str]:
    """Bullets if the doc has them, otherwise sentences."""
    b = _bullets(text)
    return b if len(b) >= 3 else _sentences(text)


def _score(text: str, markers: list[str]) -> int:
    low = text.lower()
    return sum(1 for m in markers if m in low)


def _section(text: str, *names: str, exclude: tuple[str, ...] = ()) -> list[str]:
    """Pull bullets that live under a heading matching any of `names`.

    `exclude` prevents near-miss headings from matching: "Out of scope"
    contains "scope", so the in-scope lookup must explicitly exclude it.

    Falls back to raw non-heading lines when a matched section has content
    but nothing that looks like an explicit bullet — e.g. a requirements
    table converted to "ID | text | priority" rows, which carries no bullet
    marker to match against.
    """
    lines, bulleted, raw, capture = text.splitlines(), [], [], False
    for line in lines:
        stripped = line.strip()
        if _is_heading_line(stripped):
            low = stripped.lower()
            capture = any(n in low for n in names) and not any(x in low for x in exclude)
            continue
        if capture and stripped:
            m = _BULLET.match(line)
            if m:
                bulleted.append(m.group(1).strip())
            else:
                raw.append(stripped)
    return bulleted or raw


class MockClient(LLMClient):
    name = "mock"

    def _raw(self, req: LLMRequest) -> str:
        handler = getattr(self, f"_t_{req.task}", None)
        if handler is None:
            return "{}"
        import json
        return json.dumps(handler(req.payload), ensure_ascii=False)

    # ---------------- phase 1 ----------------

    def _t_summarize_chunk(self, p: dict[str, Any]) -> dict:
        text = p.get("text", "")
        return {
            "business_goals": (_section(text, "goal", "objective") or _statements(text))[:4],
            "stakeholders": _section(text, "stakeholder", "actor", "user")[:6],
            "scope_in": _section(
                text, "in scope", "scope", "requirement", "feature",
                exclude=("out of scope", "not in scope"),
            )[:25],
            "scope_out": _section(text, "out of scope", "not in scope")[:8],
            "constraints": _section(text, "constraint", "limitation", "non-functional")[:6],
            "assumptions": _section(text, "assumption")[:5],
            "open_questions": [s for s in _statements(text) if "?" in s or "tbd" in s.lower()][:5],
        }

    def _t_reduce_summary(self, p: dict[str, Any]) -> dict:
        parts: list[dict] = p.get("partials", [])
        merged: dict[str, list[str]] = {}
        for key in ("business_goals", "stakeholders", "scope_in", "scope_out",
                    "constraints", "assumptions", "open_questions"):
            seen, vals = set(), []
            for part in parts:
                for v in part.get(key, []) or []:
                    k = v.lower().strip()
                    if k not in seen:
                        seen.add(k)
                        vals.append(v)
            merged[key] = vals[:40]
        merged["title"] = p.get("title", "Business Requirements Summary")
        return merged

    # ---------------- phase 2 ----------------

    def _t_research_gap(self, p: dict[str, Any]) -> dict:
        q = p.get("question", "")
        return {
            "answer": (
                f"[offline stub] No web research performed for: {q}. "
                "Enable RESEARCH_ENABLED=true with a Tavily key and a real LLM provider."
            ),
            "sources": [],
            "confidence": 0.1,
        }

    # ---------------- phase 3 ----------------

    def _t_generate_srs(self, p: dict[str, Any]) -> dict:
        ctx = p.get("context", "")
        stmts = _statements(ctx)
        seen, reqs = set(), []
        for s in stmts:
            key = s.lower()[:70]
            if key in seen:
                continue
            seen.add(key)
            low = s.lower()
            if any(m in low for m in ("uptime", "latency", "response time", "availability",
                                      "scalab", "secure", "encrypt", "performance", "concurrent")):
                rtype = "non_functional"
            elif any(m in low for m in ("must comply", "constraint", "budget", "deadline", "must use")):
                rtype = "constraint"
            else:
                rtype = "functional"
            priority = "must" if low.startswith(("the system must", "must", "shall")) or " must " in low else "should"
            reqs.append({
                "req_id": f"REQ-{len(reqs) + 1:03d}",
                "text": s.rstrip("."),
                "req_type": rtype,
                "priority": priority,
                "rationale": "Derived from the business requirements document.",
                "acceptance_criteria": [
                    f"Given the system is available, when the scenario in {s[:40].strip()}… is exercised, "
                    "then the documented behaviour is observed.",
                ],
            })
        actors = p.get("stakeholders") or ["End user"]
        use_cases = [{
            "uc_id": f"UC-{i + 1:03d}",
            "name": r["text"][:60],
            "actor": actors[i % len(actors)],
            "preconditions": ["User is authenticated."],
            "main_flow": ["User initiates the action.", "System validates input.", "System persists and confirms."],
            "alt_flows": ["Validation fails -> system returns a descriptive error."],
        } for i, r in enumerate(reqs[:5])]
        return {
            "title": p.get("title", "Software Requirements Specification"),
            "introduction": "This SRS is generated from the supplied BRS and follows an IEEE-830-style structure.",
            "overall_description": "; ".join(p.get("business_goals", [])[:3]),
            "requirements": reqs,
            "use_cases": use_cases,
            "glossary": {},
        }

    # ---------------- phase 4 ----------------

    def _t_classify_requirements(self, p: dict[str, Any]) -> dict:
        out = []
        for r in p.get("requirements", []):
            text = r.get("text", "")
            t, nt = _score(text, TECH_MARKERS), _score(text, NON_TECH_MARKERS)
            technical = t >= nt
            total = max(t + nt, 1)
            conf = round(0.5 + 0.5 * abs(t - nt) / total, 2)
            disc = "backend"
            for name, markers in DISCIPLINE_MARKERS.items():
                if _score(text, markers) > 0:
                    disc = name
                    break
            if not technical:
                disc = "business"
            out.append({
                "req_id": r.get("req_id"),
                "kind": "technical" if technical else "non_technical",
                "confidence": conf,
                "reason": f"keyword score technical={t} non_technical={nt}",
                "discipline": disc,
            })
        return {"classifications": out}

    # ---------------- phase 5 ----------------

    def _t_generate_design(self, p: dict[str, Any]) -> dict:
        reqs = p.get("requirements", [])
        comps = [
            {"name": "API Gateway", "responsibility": "Routing, auth, rate limiting", "tech": "FastAPI", "depends_on": []},
            {"name": "Core Service", "responsibility": "Business rules and orchestration", "tech": "Python", "depends_on": ["API Gateway"]},
            {"name": "Persistence", "responsibility": "Relational storage", "tech": "PostgreSQL", "depends_on": ["Core Service"]},
            {"name": "Worker", "responsibility": "Async and scheduled jobs", "tech": "Celery + Redis", "depends_on": ["Persistence"]},
        ]
        apis = [{
            "method": "POST" if i % 2 == 0 else "GET",
            "path": "/api/v1/" + re.sub(r"[^a-z0-9]+", "-", r.get("text", "")[:24].lower()).strip("-"),
            "summary": r.get("text", "")[:80],
            "request_schema": {"payload": "object"},
            "response_schema": {"status": "string", "data": "object"},
        } for i, r in enumerate(reqs[:6])]
        tables = [
            {"name": "users", "columns": {"id": "uuid pk", "email": "text unique", "created_at": "timestamptz"}, "notes": ""},
            {"name": "audit_log", "columns": {"id": "bigserial pk", "actor_id": "uuid fk", "action": "text", "at": "timestamptz"}, "notes": ""},
        ]
        hld = "graph TD\n" + "\n".join(
            f'  {_sid(c["name"], 4)}["{c["name"]}<br/>{c["tech"]}"]' for c in comps
        ) + "\n" + "\n".join(
            f'  {_sid(d, 4)} --> {_sid(c["name"], 4)}' for c in comps for d in c["depends_on"]
        )
        erd = "erDiagram\n" + "\n".join(
            f"  {t['name'].upper()} {{\n" + "\n".join(
                f"    string {col}" for col in t["columns"]
            ) + "\n  }" for t in tables
        )
        return {
            "overview": "Layered service: gateway -> core service -> persistence, with async workers.",
            "components": comps,
            "data_flow": "Client -> API Gateway -> Core Service -> Persistence; long-running work is queued to Worker.",
            "api_contracts": apis,
            "db_tables": tables,
            "mermaid_hld": hld,
            "mermaid_erd": erd,
            "covers_req_ids": [r.get("req_id") for r in reqs],
        }

    # ---------------- phase 6 ----------------

    def _t_plan_tasks(self, p: dict[str, Any]) -> dict:
        tasks, n = [], 0
        for r in p.get("requirements", []):
            rid, text = r.get("req_id"), r.get("text", "")
            disc = r.get("discipline", "backend")
            base = len(text) // 60 + 2
            blueprint = [
                ("Design & spec", disc, min(base, 3), []),
                ("Implement", disc, min(base + 2, 8), ["Design & spec"]),
                ("Test", "qa", max(base - 1, 1), ["Implement"]),
            ]
            local: dict[str, str] = {}
            for label, d, pts, deps in blueprint:
                n += 1
                tid = f"T-{n:03d}"
                local[label] = tid
                tasks.append({
                    "task_id": tid,
                    "title": f"{label}: {text[:55]}",
                    "description": f"{label} work for {rid} — {text}",
                    "req_ids": [rid],
                    "discipline": d,
                    "story_points": pts,
                    "depends_on": [local[x] for x in deps if x in local],
                })
        return {"tasks": tasks}

    # ---------------- phase 7 ----------------

    def _t_write_tickets(self, p: dict[str, Any]) -> dict:
        out = []
        for t in p.get("tasks", []):
            title = t.get("title", "")
            out.append({
                "ticket_id": t.get("task_id", "").replace("T-", "TCK-"),
                "title": title,
                "description": t.get("description", ""),
                "acceptance_criteria": [
                    "Implementation matches the linked requirement.",
                    "Unit tests cover the happy path and one failure path.",
                    "Change is documented in the module README.",
                ],
                "labels": [t.get("discipline", "backend")] + t.get("req_ids", []),
                "story_points": t.get("story_points", 3),
                "depends_on": [d.replace("T-", "TCK-") for d in t.get("depends_on", [])],
                "req_ids": t.get("req_ids", []),
                "epic": (t.get("req_ids") or ["GENERAL"])[0],
            })
        return {"tickets": out}
