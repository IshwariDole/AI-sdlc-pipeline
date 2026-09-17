"""Orchestrator. Runs phases 1-9 and returns a PipelineResult.

Each phase is independently callable; this module only sequences them and
records timings, so a phase can be tested or replaced in isolation.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import store
from .config import settings
from .llm import LLMClient, get_client
from .phases import p1_ingest, p2_research, p3_srs, p4_classify, p5_design
from .phases import p6_tasks, p7_tickets, p8_sprints, p9_export
from .schemas import PipelineResult

ProgressFn = Callable[[str, str], None]        # (phase, message) -> None


def _noop(phase: str, message: str) -> None:
    print(f"[{phase}] {message}")


@dataclass
class PipelineOptions:
    velocity: int = settings.team_velocity
    max_sprints: int = settings.max_sprints
    stop_after: int = 9                 # run phases 1..stop_after
    classifier: str = "llm"             # llm | transformer
    export_docx: bool = False
    export_csv: bool = True
    persist: bool = True
    exports: list[str] = field(default_factory=list)


def run_pipeline(
    source_path: str,
    client: LLMClient | None = None,
    options: PipelineOptions | None = None,
    progress: ProgressFn = _noop,
) -> PipelineResult:
    opts = options or PipelineOptions()
    client = client or get_client()
    settings.ensure_dirs()

    run_id = f"{Path(source_path).stem[:24]}-{uuid.uuid4().hex[:6]}"
    result = PipelineResult(run_id=run_id, source_path=str(source_path))
    clock: dict[str, float] = {}

    def timed(name: str, fn):
        t0 = time.perf_counter()
        out = fn()
        clock[name] = round(time.perf_counter() - t0, 3)
        return out

    # -- 1 ingestion ------------------------------------------------------
    progress("1/9 ingest", f"reading {source_path}")
    text = timed("load", lambda: p1_ingest.load_document(source_path))
    progress("1/9 ingest", f"{len(text):,} chars; summarizing")
    result.summary = timed("summarize", lambda: p1_ingest.summarize(
        text, client,
        title=Path(source_path).stem.replace("_", " ").title(),
        chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap))
    progress("1/9 ingest", f"{result.summary.chunk_count} chunk(s), "
                           f"{len(result.summary.business_goals)} goal(s)")
    if opts.stop_after < 2:
        return _finish(result, clock, client, opts, progress)

    # -- 2 research -------------------------------------------------------
    progress("2/9 research", "detecting gaps"
             + ("" if settings.research_enabled else " (web research disabled)"))
    result.enriched = timed("research", lambda: p2_research.research(result.summary, client))
    progress("2/9 research", f"{len(result.enriched.findings)} gap(s) recorded")
    if opts.stop_after < 3:
        return _finish(result, clock, client, opts, progress)

    # -- 3 SRS ------------------------------------------------------------
    progress("3/9 SRS", "generating requirements")
    result.srs = timed("srs", lambda: p3_srs.generate_srs(result.enriched, client))
    issues = p3_srs.validate_srs(result.srs)
    progress("3/9 SRS", f"{len(result.srs.requirements)} requirement(s), "
                        f"{len(issues)} quality warning(s)")
    if opts.stop_after < 4:
        return _finish(result, clock, client, opts, progress)

    # -- 4 classify -------------------------------------------------------
    progress("4/9 classify", f"strategy={opts.classifier}")
    classifier = (p4_classify.TransformerClassifier() if opts.classifier == "transformer"
                  else p4_classify.LLMClassifier(client))
    stats = timed("classify", lambda: p4_classify.classify_srs(result.srs, classifier))
    progress("4/9 classify", f"{stats['technical']} technical / "
                             f"{stats['non_technical']} non-technical "
                             f"({stats['low_confidence']} low-confidence)")
    if opts.stop_after < 5:
        return _finish(result, clock, client, opts, progress)

    # -- 5 design ---------------------------------------------------------
    progress("5/9 design", "drafting HLD + LLD")
    result.design = timed("design", lambda: p5_design.generate_design(result.srs, client))
    cov = p5_design.coverage_report(result.srs, result.design)
    progress("5/9 design", f"{len(result.design.components)} component(s), "
                           f"{cov['coverage_pct']}% requirement coverage")
    if opts.stop_after < 6:
        return _finish(result, clock, client, opts, progress)

    # -- 6 tasks ----------------------------------------------------------
    progress("6/9 tasks", "decomposing into tasks")
    result.tasks = timed("tasks", lambda: p6_tasks.plan_tasks(result.srs, result.design, client))
    tsum = p6_tasks.summarize_plan(result.tasks)
    progress("6/9 tasks", f"{tsum['task_count']} task(s), {tsum['total_points']} point(s)")
    if opts.stop_after < 7:
        return _finish(result, clock, client, opts, progress)

    # -- 7 tickets --------------------------------------------------------
    progress("7/9 tickets", "writing tickets")
    result.tickets = timed("tickets", lambda: p7_tickets.generate_tickets(result.tasks, client))
    progress("7/9 tickets", f"{len(result.tickets)} ticket(s)")
    if opts.stop_after < 8:
        return _finish(result, clock, client, opts, progress)

    # -- 8 sprints (no LLM) -----------------------------------------------
    progress("8/9 sprints", f"packing at velocity={opts.velocity}")
    result.plan = timed("sprints", lambda: p8_sprints.allocate_sprints(
        result.tickets, velocity=opts.velocity, max_sprints=opts.max_sprints))
    m = p8_sprints.plan_metrics(result.plan)
    progress("8/9 sprints", f"{m['sprints']} sprint(s), "
                            f"{m['avg_utilisation_pct']}% average utilisation")
    if opts.stop_after < 9:
        return _finish(result, clock, client, opts, progress)

    return _finish(result, clock, client, opts, progress, export=True)


def _finish(result, clock, client, opts, progress, export: bool = False) -> PipelineResult:
    result.timings = clock
    result.llm_calls = client.call_count

    if export:
        progress("9/9 export", "writing artefacts")
        result.exports = []
        paths = [p9_export.export_json(result, settings.output_dir),
                 p9_export.export_markdown(result, settings.output_dir)]
        if opts.export_csv and result.tickets:
            paths.append(p7_tickets.to_csv(
                result.tickets,
                str(Path(settings.output_dir) / f"{result.run_id}_tickets.csv")))
        if opts.export_docx and result.srs:
            try:
                paths.append(p9_export.export_srs_docx(
                    result.srs, settings.output_dir, result.run_id))
            except ImportError as exc:
                progress("9/9 export", f"skipped docx: {exc}")
        opts.exports = paths
        for p in paths:
            progress("9/9 export", Path(p).name)

    if opts.persist:
        try:
            store.save_run(result)
        except Exception as exc:                      # persistence must not fail a run
            progress("store", f"could not persist run: {exc}")

    progress("done", f"run_id={result.run_id} llm_calls={result.llm_calls} "
                     f"total={sum(clock.values()):.2f}s")
    return result
