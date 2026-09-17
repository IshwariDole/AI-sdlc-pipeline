# Architecture notes

Design decisions and the reasoning behind them. Useful for interviews, where
"why" is worth more than "what".

## 1. Dependency direction

```
        phases/  ──uses──>  llm/base.LLMClient  <──implements── llm/providers.py
           │                                    <──implements── llm/mock.py
           │
           └──uses──> schemas.py  (stdlib dataclasses, no deps)

pipeline.py ──sequences──> phases/
api/, dashboard/ ──call──> pipeline.py
```

Nothing in `src/brs2sprint` imports FastAPI, Streamlit, or any LLM SDK at
module load. Provider SDKs are imported inside their constructors, and parsers
inside the function that needs them. Consequences:

- `import brs2sprint` works on a bare Python install.
- Missing `pypdf` fails when you feed it a PDF, with a message naming the fix —
  not at import time for a user who only handles `.md`.
- Tests run without network.

## 2. Why dataclasses and not pydantic

The core has one job: pass structured data between phases. Dataclasses do that
with no dependency. Validation that matters here is semantic — "does this
requirement id exist", "is this dependency graph acyclic" — and pydantic does
not do that for you. Those checks live in `p3_srs.validate_srs`,
`p6_tasks._sanitize_dependencies` and `p8_sprints.detect_cycles`.

If this grew an external API with untrusted input, pydantic would earn its place
at that boundary. It has not yet.

## 3. The LLMRequest split

```python
LLMRequest(task="classify_requirements",   # mock dispatches on this
           system=..., user=...,           # real providers use these
           payload={...})                  # mock uses this
```

One call site serves both a real provider and the offline mock. Without the
split you either mock at the HTTP layer (brittle) or cannot test the pipeline
without a key (worse).

## 4. Failure handling per phase

LLM output is unreliable in specific, predictable ways, so each phase repairs
rather than trusts:

| Failure | Where it is handled |
|---|---|
| JSON wrapped in code fences | `llm/base.extract_json` |
| Unparseable JSON | retry at temperature 0 with a stricter system prompt |
| Duplicate requirement ids | `p3_srs._dedupe_ids` |
| Story points of 13, 20, 40 | `p6_tasks._normalize_points` snaps to Fibonacci ≤ 8 |
| Dependency cycles | `p6_tasks._sanitize_dependencies`, then `p8_sprints.detect_cycles` |
| Dangling `depends_on` ids | dropped in phases 6 and 7 |
| Model forgets `T-` → `TCK-` remap | `p7_tickets._repair_dependencies` re-derives it |
| Ticket larger than sprint capacity | own sprint + warning, never silently dropped |
| Persistence error | caught; the run still returns |

The principle: a partly-degraded result plus a warning beats a stack trace.
Every repair is visible in `plan.warnings` or `validate_srs` output rather than
silent.

## 5. Why phase 8 is not an LLM

Sprint allocation is a constrained scheduling problem with a checkable
definition of correct: no sprint over capacity, no ticket before its
dependencies, nothing scheduled twice, nothing lost. An algorithm gives you
determinism, sub-millisecond runtime, zero cost, and 12 unit tests that assert
correctness directly.

An LLM would give you none of those and would occasionally schedule a ticket
before its blocker. Knowing where the LLM stops is the interesting engineering
judgement in this project.

## 6. Traceability

Ids chain forward and are validated at every hop:

```
REQ-001 ──> Task T-001 (req_ids) ──> Ticket TCK-001 (req_ids) ──> Sprint 1
```

This is what makes "which sprint delivers requirement REQ-014?" answerable, and
what `test_every_ticket_traces_back_to_a_requirement` enforces.

## 7. Known extension points

- `Classifier` ABC (phase 4) — the fine-tuned model is a drop-in swap, scored
  by the same harness as the prompt baseline.
- `LLMClient` ABC — add a provider in ~20 lines.
- `store.py` — swap sqlite3 for Postgres by changing `connect()`.
- Phase 2 — the real upgrade is retrieving from an accumulated corpus of past
  BRS/SRS pairs, which would make a vector store genuinely load-bearing rather
  than decorative.
