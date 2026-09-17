#!/usr/bin/env python3
"""CLI entry point.

    python run_pipeline.py data/samples/sample_brs.md
    python run_pipeline.py brs.pdf --provider anthropic --velocity 25 --docx
    python run_pipeline.py brs.pdf --provider groq       # free tier, no card required
    python run_pipeline.py brs.pdf --provider gemini      # free tier, no card required
    python run_pipeline.py brs.docx --stop-after 4        # ingest -> classify only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from brs2sprint.config import settings                      # noqa: E402
from brs2sprint.llm import get_client                       # noqa: E402
from brs2sprint.phases import p5_design, p8_sprints         # noqa: E402
from brs2sprint.pipeline import PipelineOptions, run_pipeline  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="BRS -> SRS -> design -> tickets -> sprints")
    ap.add_argument("source", help="path to a .pdf, .docx, .md or .txt BRS")
    ap.add_argument("--provider", default=None, help="mock | anthropic | openai | groq | gemini")
    ap.add_argument("--model", default=None)
    ap.add_argument("--velocity", type=int, default=settings.team_velocity)
    ap.add_argument("--max-sprints", type=int, default=settings.max_sprints)
    ap.add_argument("--stop-after", type=int, default=9, choices=range(1, 10),
                    help="run phases 1..N only")
    ap.add_argument("--classifier", default="llm", choices=["llm", "transformer"])
    ap.add_argument("--docx", action="store_true", help="also export the SRS as .docx")
    ap.add_argument("--no-csv", action="store_true")
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.model:
        settings.llm_model = args.model

    try:
        client = get_client(args.provider)
    except Exception as exc:
        print(f"! {exc}")
        return 1
    if client.name == "mock" and not args.quiet:
        print("! LLM_PROVIDER=mock — heuristic offline output, not model output.\n"
              "  For real results, set an API key in .env and pass --provider:\n"
              "    anthropic  (ANTHROPIC_API_KEY, paid)\n"
              "    groq       (GROQ_API_KEY, free tier — console.groq.com/keys)\n"
              "    gemini     (GEMINI_API_KEY, free tier — aistudio.google.com/apikey)\n")

    def progress(phase: str, msg: str) -> None:
        if not args.quiet:
            print(f"  {phase:<14} {msg}")

    from brs2sprint.llm.base import LLMError
    try:
        result = run_pipeline(
            args.source, client=client,
            options=PipelineOptions(
                velocity=args.velocity, max_sprints=args.max_sprints,
                stop_after=args.stop_after, classifier=args.classifier,
                export_docx=args.docx, export_csv=not args.no_csv, persist=not args.no_db,
            ),
            progress=progress,
        )
    except LLMError as exc:
        print(f"\n! {exc}")
        return 1

    if args.quiet:
        print(result.run_id)
        return 0

    print("\n" + "=" * 64)
    print(f"RUN {result.run_id}")
    print("=" * 64)
    if result.srs:
        print(f"Requirements : {len(result.srs.requirements)} "
              f"({len(result.srs.technical())} technical, "
              f"{len(result.srs.non_technical())} non-technical)")
    if result.design and result.design.components:
        cov = p5_design.coverage_report(result.srs, result.design)
        print(f"Design       : {len(result.design.components)} components, "
              f"{cov['coverage_pct']}% coverage")
    if result.tickets:
        print(f"Tickets      : {len(result.tickets)} "
              f"({sum(t.story_points for t in result.tickets)} points)")
    if result.plan:
        m = p8_sprints.plan_metrics(result.plan)
        print(f"Sprints      : {m['sprints']} at velocity {result.plan.velocity} "
              f"-> {m['points_per_sprint']} ({m['avg_utilisation_pct']}% utilisation)")
        for w in m["warnings"]:
            print(f"  ! {w}")
    print(f"LLM calls    : {result.llm_calls}")
    print(f"Timings      : {result.timings}")
    print(f"\nArtefacts in {settings.output_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
