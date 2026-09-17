"""Prompt templates. Kept in one file so prompt engineering is version-
controlled and diffable, rather than scattered through the phase modules.

Every template asks for strict JSON matching the dataclasses in schemas.py.
"""

SYSTEM_ANALYST = (
    "You are a senior business analyst and software requirements engineer. "
    "You are precise, you never invent facts that are not supported by the "
    "source document, and you always return strictly valid JSON with no "
    "commentary and no code fences."
)

SYSTEM_ARCHITECT = (
    "You are a pragmatic staff software architect. You favour boring, proven "
    "technology and you justify each component by the requirement it serves. "
    "You always return strictly valid JSON with no commentary and no code fences."
)

SYSTEM_PLANNER = (
    "You are an experienced engineering manager who decomposes requirements "
    "into small, independently shippable tasks with honest estimates. "
    "You always return strictly valid JSON with no commentary and no code fences."
)

# --------------------------------------------------------------------------

SUMMARIZE_CHUNK = """\
Below is one chunk of a Business Requirements Specification (chunk {i} of {n}).

Extract ONLY what is present in this chunk. Leave arrays empty rather than guessing.

Return JSON with exactly these keys:
{{
  "business_goals": [str],
  "stakeholders": [str],
  "scope_in": [str],
  "scope_out": [str],
  "constraints": [str],
  "assumptions": [str],
  "open_questions": [str]
}}

--- CHUNK ---
{text}
--- END CHUNK ---
"""

REDUCE_SUMMARY = """\
You are merging per-chunk extractions of one BRS into a single summary.
Deduplicate near-identical entries, merge overlapping phrasings, and preserve
the source wording where possible. Do not add anything new.

Return JSON with keys: title, business_goals, stakeholders, scope_in,
scope_out, constraints, assumptions, open_questions.

--- PARTIAL EXTRACTIONS (JSON) ---
{partials}
--- END ---
"""

RESEARCH_GAP = """\
A BRS leaves the following point under-specified:

  "{question}"

Project context:
{context}

Using the search results below, state what an engineering team would need to
assume or verify. Be concrete; cite the URLs you used. If the results do not
answer it, say so and set confidence low.

--- SEARCH RESULTS ---
{results}
--- END ---

Return JSON: {{"answer": str, "sources": [str], "confidence": float 0-1}}
"""

GENERATE_SRS = """\
Convert the enriched business context below into a formal SRS following an
IEEE-830-style structure.

Rules:
- One requirement per atomic, testable statement. Split compound sentences.
- Each requirement gets a stable id REQ-001, REQ-002, ...
- req_type is one of: functional | non_functional | constraint
- priority is MoSCoW: must | should | could | wont
- acceptance_criteria are Given/When/Then and must be objectively verifiable.
- Do not invent requirements that the context does not support.

Return JSON:
{{
  "title": str,
  "introduction": str,
  "overall_description": str,
  "requirements": [
    {{"req_id": str, "text": str, "req_type": str, "priority": str,
      "rationale": str, "acceptance_criteria": [str]}}
  ],
  "use_cases": [
    {{"uc_id": str, "name": str, "actor": str, "preconditions": [str],
      "main_flow": [str], "alt_flows": [str]}}
  ],
  "glossary": {{"term": "definition"}}
}}

--- ENRICHED CONTEXT ---
{context}
--- END ---
"""

CLASSIFY_REQUIREMENTS = """\
Classify each requirement as technical or non_technical.

  technical      = requires engineering work (code, schema, infra, integration,
                   performance, security implementation)
  non_technical  = business, process, legal, training, documentation, commercial
                   or organisational work with no engineering deliverable

Also assign a discipline: backend | frontend | data | devops | qa | design | business

Worked examples:
  "The system shall expire idle sessions after 15 minutes."
      -> technical, backend, confidence 0.95
  "Support staff shall be trained on the new refund policy before launch."
      -> non_technical, business, confidence 0.95
  "The checkout page shall meet WCAG 2.1 AA."
      -> technical, frontend, confidence 0.8 (implementation work, not just policy)
  "Legal shall approve the updated terms of service."
      -> non_technical, business, confidence 0.95

Return JSON:
{{"classifications": [
  {{"req_id": str, "kind": "technical"|"non_technical",
    "confidence": float, "reason": str, "discipline": str}}
]}}

--- REQUIREMENTS ---
{requirements}
--- END ---
"""

GENERATE_DESIGN = """\
Produce a combined HLD and LLD for the technical requirements below.

HLD: components with responsibilities, chosen tech, and dependencies; data flow.
LLD: concrete REST API contracts and a draft relational schema.
Also emit two Mermaid diagrams as plain text (no code fences inside the JSON
string values): a `graph TD` component diagram and an `erDiagram` schema diagram.

Justify every component against at least one requirement id. Prefer a small
number of components over a sprawling microservice diagram.

Return JSON:
{{
  "overview": str,
  "components": [{{"name": str, "responsibility": str, "tech": str, "depends_on": [str]}}],
  "data_flow": str,
  "api_contracts": [{{"method": str, "path": str, "summary": str,
                      "request_schema": {{}}, "response_schema": {{}}}}],
  "db_tables": [{{"name": str, "columns": {{}}, "notes": str}}],
  "mermaid_hld": str,
  "mermaid_erd": str,
  "covers_req_ids": [str]
}}

--- TECHNICAL REQUIREMENTS ---
{requirements}
--- DESIGN CONSTRAINTS ---
{constraints}
--- END ---
"""

PLAN_TASKS = """\
Decompose the technical requirements and design into engineering tasks.

Rules:
- A task is one person's work for at most a few days. Split anything larger.
- story_points use a modified Fibonacci scale: 1, 2, 3, 5, 8. Never exceed 8;
  if it would, split the task.
- depends_on references other task_ids in THIS response only. No cycles.
- Every task links to at least one req_id.

Return JSON:
{{"tasks": [
  {{"task_id": str, "title": str, "description": str, "req_ids": [str],
    "discipline": str, "story_points": int, "depends_on": [str]}}
]}}

--- REQUIREMENTS ---
{requirements}
--- DESIGN ---
{design}
--- END ---
"""

WRITE_TICKETS = """\
Turn each task into a developer-ready ticket.

Rules:
- description states context, the change, and anything explicitly out of scope.
- acceptance_criteria are checkable by a reviewer without asking questions.
- labels include the discipline plus any relevant req ids.
- Preserve task_id -> ticket_id mapping by replacing the "T-" prefix with "TCK-",
  and remap depends_on the same way.

Return JSON:
{{"tickets": [
  {{"ticket_id": str, "title": str, "description": str,
    "acceptance_criteria": [str], "labels": [str], "story_points": int,
    "depends_on": [str], "req_ids": [str], "epic": str}}
]}}

--- TASKS ---
{tasks}
--- END ---
"""
