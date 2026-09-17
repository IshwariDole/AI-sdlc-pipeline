# brs2sprint

Turns a **Business Requirements Specification** into a software requirements
spec, a draft design, engineering tickets and a dependency-aware sprint plan.

```
BRS (pdf/docx/md) → 1 Ingest → 2 Research → 3 SRS → 4 Classify
                  → 5 Design (HLD/LLD) → 6 Tasks → 7 Tickets
                  → 8 Sprint allocator → 9 Export / dashboard
```

100% Python. Phases 1–7 use an LLM. **Phase 8 is a plain algorithm** —
topological sort plus greedy bin packing — because sprint allocation is a
deterministic scheduling problem, not a language problem.

---

## Quickstart (no API key, no network)

```bash
python run_pipeline.py data/samples/sample_brs.md --velocity 25 --max-sprints 20
```

That runs all nine phases against the bundled `mock` provider — a deterministic
rule-based stand-in for an LLM. Output lands in `outputs/`.

**With a real model — free tier, no card required:**

```bash
pip install -r requirements.txt
cp .env.example .env          # add GROQ_API_KEY or GEMINI_API_KEY
python run_pipeline.py data/samples/sample_brs.md --provider groq
python run_pipeline.py data/samples/sample_brs.md --provider gemini
```

Get a free key: [console.groq.com/keys](https://console.groq.com/keys) or
[aistudio.google.com/apikey](https://aistudio.google.com/apikey). Both work
with `pip install openai` — Groq and Gemini each expose an OpenAI-compatible
endpoint, so no provider-specific SDK is needed.

**Free-tier model names change often** — both Groq and Gemini have moved or
shut down models with only weeks of notice. If you get a "model not found"
error, the fix is never a code change: check the provider's current model
list and either pass `--model <name>` or set `LLM_MODEL` in `.env`.

- Groq: [console.groq.com/docs/models](https://console.groq.com/docs/models)
- Gemini: [ai.google.dev/gemini-api/docs/models](https://ai.google.dev/gemini-api/docs/models)

**Free-tier token-per-minute limits are also low** — Groq's free
`openai/gpt-oss-120b` tier caps at 8,000 TPM, and phases 3/5/6/7 request up to
`LLM_MAX_TOKENS` tokens per call. If you see a 413/429 mentioning
`rate_limit_exceeded` or "tokens per minute", lower `LLM_MAX_TOKENS` in
`.env` (try 2000) and/or `CHUNK_SIZE`. The error message tells you this
directly rather than showing a raw SDK traceback.

The error message itself tells you this and links the right page — that's a
deliberate design choice, not a fallback: `providers.py` classifies 404 /
401 / 429 responses and raises an actionable one-line message instead of a
raw SDK traceback.

**With Anthropic or OpenAI (paid):**

```bash
pip install anthropic   # or: openai
python run_pipeline.py data/samples/sample_brs.md --provider anthropic
```

**Dashboard / API:**

```bash
streamlit run dashboard/app.py          # upload → SRS → diagrams → sprint board
uvicorn api.main:app --reload           # http://localhost:8000/docs
```

**Deploying the dashboard publicly** (free, via Streamlit Community Cloud):
see [DEPLOY.md](DEPLOY.md). It covers the one decision that actually matters
for a public deployment — each visitor supplies their own free API key
rather than sharing yours, so one busy visitor can't rate-limit everyone
else, and it costs you nothing.

**Tests:**

```bash
python tests/test_sprint_allocator.py   # 12 tests, phase 8 algorithm
python tests/test_pipeline_e2e.py       # 10 tests, cross-phase contracts
python tests/test_eval_dataset.py       # 10 tests, eval set integrity + metrics
python tools/eval_classifier.py         # phase 4 accuracy on a labelled set
```

---

## Why there is a mock provider

The core package has **zero required third-party dependencies**. With
`LLM_PROVIDER=mock` the entire nine-phase pipeline runs on a bare Python
install, offline, in about 10 milliseconds.

This is not a toy detail — it buys three things:

1. **CI that actually tests the pipeline.** Tests assert on structural
   contracts (ids resolve, no ticket is dropped, no ticket is scheduled before
   its dependency) rather than on model wording, so they stay green when you
   swap providers.
2. **A demo that cannot fail live.** No key, no rate limit, no spend.
3. **A clean seam.** Every phase talks to one `LLMClient` interface, so adding
   a provider is one small class.

The mock is **not** an LLM. Its output is keyword heuristics. Always demo real
results with `--provider groq` or `--provider gemini` (free) or
`--provider anthropic` (paid).

---

## CLI

```
python run_pipeline.py SOURCE [options]

  --provider {mock,anthropic,openai,groq,gemini}
  --model MODEL
  --velocity N            story points per sprint (default 20)
  --max-sprints N         give up after N sprints (default 12)
  --stop-after {1..9}     run phases 1..N only — useful while iterating
  --classifier {llm,transformer}
  --docx                  also export the SRS as a Word document
  --no-csv / --no-db / --quiet
```

`--stop-after` is the flag you will use most. Iterating on the SRS prompt costs
three LLM calls instead of nine.

---

## What each phase does

| # | Phase | LLM? | Output |
|---|---|---|---|
| 1 | Ingest | yes | `BRSSummary` — goals, stakeholders, scope, constraints |
| 2 | Research | optional | `EnrichedContext` — detected gaps, optionally researched |
| 3 | SRS | yes | `SRS` — IEEE-830-style requirements, use cases, acceptance criteria |
| 4 | Classify | yes | each requirement tagged technical/non-technical + discipline |
| 5 | Design | yes | `Design` — components, API contracts, DB schema, Mermaid diagrams |
| 6 | Tasks | yes | `Task[]` — decomposition with story points and dependencies |
| 7 | Tickets | yes | `Ticket[]` — acceptance criteria, labels; CSV / Jira export |
| 8 | Sprints | **no** | `SprintPlan` — dependency-respecting, capacity-bounded |
| 9 | Export | no | JSON, Markdown delivery pack, CSV, optional DOCX |

### Phase 1 — a chunking detail that mattered

Naive paragraph chunking split the sample BRS mid-section, so the second chunk
arrived as orphaned bullets with no heading. The extractor could not tell
in-scope items from out-of-scope ones, and **8 of 43 requirements were silently
lost**. `chunk_text` now carries the last-seen heading into the next chunk and
marks it `(continued)`. There is a regression test for it.

That class of bug is the reason phase 1 is worth more attention than it looks
like it deserves: everything downstream inherits its mistakes, and it fails
quietly rather than loudly.

### Phase 4 — measuring the classifier honestly

`tools/eval_classifier.py` scores any classifier against
`data/eval/requirements_labelled.jsonl` (80 labelled requirements). It reports
three slices that matter more than overall accuracy:

- **by difficulty** — easy / medium / hard
- **vocabulary traps** — 26 examples whose surface words point the wrong way
  ("the vendor's API pricing must be renegotiated by procurement" is
  non-technical; "implement the multi-step approval workflow engine" is
  technical). This slice is what separates comprehension from keyword matching.
- **calibration** — does reported confidence track actual accuracy? Phase 4
  uses confidence to flag requirements for human review, so an overconfident
  classifier is worse than an uncertain one.

The bundled keyword baseline scores:

```
accuracy 0.738   macro F1 0.718
easy 0.850   medium 0.654   hard 0.571
trap 0.423   non-trap 0.889   gap 0.466   <- keyword matching, not comprehension
```

That 0.466 trap gap is the baseline this project exists to beat. Run
`python tools/eval_classifier.py --compare mock anthropic` to see a real model
against it. `test_baseline_is_beatable` fails the build if the eval set ever
becomes easy enough for keywords to score above 0.9.

### Phase 8 — the algorithm

1. **Cycle detection** (DFS colouring) — reports and breaks dependency cycles
   rather than hanging or crashing.
2. **Critical-path ranking** — longest downstream chain in story points.
   Scheduling long chains first keeps the sprint count near the minimum;
   a ticket blocking eight others must not wait behind a leaf task.
3. **Greedy first-fit-decreasing bin packing**, subject to *all dependencies
   land in a strictly earlier sprint*.

Greedy is not optimal — bin packing is NP-hard — but it is within a known
bound, runs in milliseconds and produces a plan a human can reason about. That
trade is the right one here, and being able to say why is the point.

---

## Honest limitations

- **The eval set is synthetic, so the headline number is provisional.** 80
  examples written in one sitting by one person. They are internally consistent
  — good enough as a regression test — but not representative of real BRS prose,
  which is longer, vaguer and more compound. `data/eval/LABELLING_GUIDE.md`
  explains how to extend it with real documents, and why you should expect
  scores to drop when you do. That drop is the useful information.
- **Phase 2 is off by default.** Web research is the flakiest phase here: it
  produces plausible text that is hard to verify. Gap *detection* is
  deterministic and always runs; gap *answering* is opt-in.
- **No vector store.** An earlier design called for FAISS/Chroma. This pipeline
  processes one document via map-reduce — it never does semantic search over a
  corpus, so a vector DB would be decoration. Add it when phase 2 retrieves
  from an accumulated knowledge base of past BRS/SRS pairs; that is a genuine
  RAG use case, and the current one is not.
- **Design output is a draft.** It is a starting point for an architect to
  argue with, not a design document to build from.
- **Story point estimates are LLM guesses.** They are consistent, which is
  enough to make the packing algorithm meaningful, but they are not calibrated
  to any real team.

---

## Layout

```
src/brs2sprint/
  schemas.py        dataclasses passed between phases
  config.py         env-based settings
  prompts.py        every prompt template, version-controlled in one place
  pipeline.py       orchestrator, timings, progress callbacks
  store.py          sqlite3 persistence
  llm/
    base.py         LLMClient interface, tolerant JSON extraction, retry
    providers.py    Anthropic / OpenAI
    mock.py         offline deterministic provider
  phases/p1..p9     one module per phase
api/main.py         FastAPI (background jobs, polling, downloads)
dashboard/app.py    Streamlit (Kanban sprint board, Mermaid diagrams)
data/eval/          labelled set + labelling guide (decision rules, edge cases)
tools/              classifier eval + DistilBERT fine-tuning
tests/              32 tests, all runnable offline
```

## Build order

Phases 1–4 are the load-bearing slice: get BRS → classified SRS working
end-to-end before touching 5–9. Then, by return on effort:
6 → 8 → 5 → 9 → 7. Phase 2 last.

A working four-phase pipeline demos better than a half-finished nine-phase one.
