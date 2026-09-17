# Labelling guide — technical vs non-technical requirements

Read this before adding examples. An eval set whose labels are inconsistent is
worse than no eval set: it produces a confident number that measures nothing.

## The decision rule

> **Does satisfying this requirement produce an engineering deliverable —
> code, schema, configuration, infrastructure or an integration?**
>
> Yes → `technical`.  No → `non_technical`.

Apply the rule to *the requirement*, not to the project around it. Almost
everything in a software project eventually touches software; that is not the
question. The question is whether an engineer must build something to close it.

## Tie-breakers, in priority order

1. **Who closes the ticket?** If the answer is "an engineer merges a PR", it is
   technical. If it is "a manager signs a document" or "a trainer runs a
   session", it is non-technical.
2. **Ignore vocabulary.** "API", "database" and "system" appear constantly in
   non-technical requirements about procurement, policy and training. "Approval",
   "policy" and "audit" appear constantly in technical requirements about
   workflow engines and logging. Vocabulary is the single biggest source of
   labelling error — and the thing a keyword classifier gets wrong.
3. **Compliance and regulation are usually technical.** "Must comply with
   GDPR" requires encryption, retention jobs and export endpoints. But "Legal
   must confirm our GDPR position" is non-technical — the deliverable is an
   opinion, not a system.
4. **Documentation splits.** User-facing docs and training material are
   non-technical. Machine-readable artefacts an engineer produces (OpenAPI
   specs, schema migrations, runbooks in the repo) are technical.
5. **Procurement of a technical thing is still procurement.** "Negotiate the
   SMS vendor contract" is non-technical even though the vendor sells an API.
   "Integrate the SMS vendor's API" is technical.

## Edge cases and how this set resolves them

| Pattern | Label | Why |
|---|---|---|
| "Must comply with \<regulation\>" | technical | Implementation work follows |
| "\<Role\> must approve/sign off X" | non_technical | Deliverable is a decision |
| "Staff shall be trained on X" | non_technical | Deliverable is a session |
| "Publish a user guide" | non_technical | Deliverable is prose for humans |
| "Document the API in OpenAPI" | technical | Deliverable is a spec artefact |
| "Accessibility to WCAG 2.1 AA" | technical | Requires frontend implementation |
| "Budget capped at X" | non_technical | Commercial constraint |
| "Hosting must stay in-country" | technical | Drives infrastructure choices |
| "Agree a rollback plan with managers" | non_technical | Deliverable is an agreement |
| "Implement automated rollback" | technical | Deliverable is a pipeline |

When a requirement genuinely contains both ("train staff and add an audit log"),
**split it into two examples**. Compound requirements are a phase-3 defect, not
a phase-4 classification problem, and labelling them either way teaches the
classifier something false.

## Fields

```json
{"id": "E001",
 "text": "The system shall expire idle sessions after 15 minutes.",
 "label": "technical",
 "discipline": "backend",
 "difficulty": "easy",
 "trap": null,
 "note": ""}
```

- `difficulty` — `easy` (unambiguous), `medium` (needs the rule), `hard`
  (reasonable people could disagree; `note` must explain the call).
- `trap` — set to `vocabulary` when the surface words point the wrong way.
  This is the subset that separates a real classifier from keyword matching, so
  it is scored separately.
- `discipline` — secondary label; not scored by the binary metrics.

## Extending this set — the part that matters

The bundled examples were written by one person in one sitting. They are
internally consistent, which makes them useful as a regression test, and
**unrepresentative, which makes the headline score untrustworthy.**

To get a number you can defend:

1. Find 3–5 real BRS documents (government tender documents and university
   project specs are freely available and realistically messy).
2. Run `python run_pipeline.py <doc> --stop-after 3` to extract requirements.
3. Label the output by hand using the rule above, *before* looking at what the
   classifier predicted. Looking first will anchor you.
4. Append to `requirements_labelled.jsonl` with `"source": "<doc name>"`.
5. If you can, have someone else label 30 of them independently and measure
   agreement. Below ~90% agreement, your labels are the problem, not the model.

Real requirements are longer, vaguer and more compound than anything written
from memory. Expect scores to drop when you add them. That drop is the useful
information.
