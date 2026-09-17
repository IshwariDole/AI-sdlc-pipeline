"""Streamlit dashboard.

    pip install streamlit
    streamlit run dashboard/app.py

Runs the pipeline in-process (no API server needed). Shows: business summary ->
SRS table -> Mermaid diagrams -> sprint board.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st  # noqa: E402

# Bridge Streamlit's own secrets store into os.environ *before* importing
# brs2sprint.config, which reads its settings from os.environ once at import
# time. This lets a hosted deployment configure things like TEAM_VELOCITY or
# a fallback API key via Streamlit Cloud's "Secrets" panel instead of a
# .env file, with zero change to how config.py itself works. Deliberately
# best-effort: st.secrets raises if no secrets.toml exists at all, which is
# the normal case for local development — that's fine, .env still applies.
try:
    for _k, _v in st.secrets.items():
        os.environ.setdefault(_k, str(_v))
except Exception:
    pass

from brs2sprint import store                                   # noqa: E402
from brs2sprint.config import settings                         # noqa: E402
from brs2sprint.llm import get_client                          # noqa: E402
from brs2sprint.phases import p5_design, p8_sprints            # noqa: E402
from brs2sprint.phases.p9_export import full_markdown          # noqa: E402
from brs2sprint.pipeline import PipelineOptions, run_pipeline  # noqa: E402

st.set_page_config(page_title="brs2sprint", layout="wide", page_icon="📋")

# Set BRS2SPRINT_HOSTED=1 (as a Streamlit Cloud env var or secret) when this
# app is running somewhere other than your own machine. It only changes the
# messaging shown below — it never changes what data is stored or where.
HOSTED = os.getenv("BRS2SPRINT_HOSTED", "").lower() in ("1", "true", "yes")

PROVIDER_SIGNUP = {
    "groq": "https://console.groq.com/keys",
    "gemini": "https://aistudio.google.com/apikey",
    "anthropic": "https://console.anthropic.com/",
    "openai": "https://platform.openai.com/api-keys",
}


def mermaid(code: str, height: int = 460) -> None:
    if not code.strip():
        st.info("No diagram generated.")
        return
    st.components.v1.html(
        f"""
        <div class="mermaid" style="background:#fff;padding:12px;border-radius:8px">{code}</div>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
        <script>mermaid.initialize({{startOnLoad:true, theme:'neutral'}});</script>
        """,
        height=height, scrolling=True,
    )


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("brs2sprint")
    st.caption("BRS → SRS → design → tickets → sprints")
    if HOSTED:
        st.info(
            "This is a shared public demo. Use your own free API key below — "
            "it's used only for your run and is never stored or logged.",
            icon="🔒",
        )

    PROVIDERS = ["mock", "groq", "gemini", "anthropic", "openai"]
    provider = st.selectbox("LLM provider", PROVIDERS,
                            index=PROVIDERS.index(settings.llm_provider)
                            if settings.llm_provider in PROVIDERS else 0)

    user_api_key: str | None = None
    if provider == "mock":
        st.warning("Mock provider: heuristic offline output, not model output.")
    else:
        signup = PROVIDER_SIGNUP.get(provider, "")
        placeholder = "Falls back to the server's key, if one is set" if not HOSTED \
            else "Required — this server has no shared key"
        user_api_key = st.text_input(
            f"{provider.upper()}_API_KEY", type="password", placeholder=placeholder,
            help=f"Not stored, not logged — held only in memory for this run. "
                 f"Get a free key: {signup}" if signup else "Not stored, not logged.",
        )
        if provider in ("groq", "gemini"):
            st.caption(f"Free tier — [get a key]({signup})")

    velocity = st.number_input("Team velocity (points/sprint)", 1, 200, settings.team_velocity)
    max_sprints = st.number_input("Max sprints", 1, 52, settings.max_sprints)
    stop_after = st.slider("Run phases 1 through…", 1, 9, 9)

    uploaded = st.file_uploader("Business Requirements document",
                                type=["pdf", "docx", "md", "txt"])
    sample = Path(__file__).resolve().parents[1] / "data" / "samples" / "sample_brs.md"
    use_sample = st.button("Use sample BRS", use_container_width=True, disabled=not sample.exists())
    go = st.button("Run pipeline", type="primary", use_container_width=True,
                   disabled=uploaded is None)

    st.divider()
    previous = store.list_runs()
    if previous:
        if HOSTED:
            st.caption("⏳ Run history is temporary on this shared demo and "
                      "may be cleared when the app restarts.")
        picked = st.selectbox("Load a previous run", ["—"] + [r["run_id"] for r in previous])
        if picked != "—" and st.button("Load", use_container_width=True):
            st.session_state["loaded"] = store.load_run(picked)
            st.session_state.pop("result", None)

# ---------------------------------------------------------------- run
source: str | None = None
if go and uploaded is not None:
    tmp = Path(tempfile.mkdtemp()) / uploaded.name
    tmp.write_bytes(uploaded.getvalue())
    source = str(tmp)
elif use_sample:
    source = str(sample)

if source and provider != "mock" and not user_api_key and not getattr(settings, f"{provider}_api_key", ""):
    st.error(
        f"Enter your {provider.upper()}_API_KEY in the sidebar to run against a real model — "
        f"nothing is sent anywhere until you do. Get a free key: {PROVIDER_SIGNUP.get(provider, '')}"
    )
    source = None

if source:
    bar = st.progress(0.0, text="starting…")
    steps = {"1/9": .11, "2/9": .22, "3/9": .33, "4/9": .44, "5/9": .55,
             "6/9": .66, "7/9": .77, "8/9": .88, "9/9": .96, "done": 1.0}

    def progress(phase: str, msg: str) -> None:
        bar.progress(steps.get(phase.split()[0], 0.5), text=f"{phase} — {msg}")

    try:
        client = get_client(provider, api_key=user_api_key or None)
        st.session_state["result"] = run_pipeline(
            source, client=client,
            options=PipelineOptions(velocity=int(velocity), max_sprints=int(max_sprints),
                                    stop_after=int(stop_after)),
            progress=progress,
        )
        st.session_state.pop("loaded", None)
        bar.empty()
    except Exception as exc:
        bar.empty()
        # LLMError messages are already written to be shown directly to a
        # non-technical user — no traceback, no internal file paths.
        from brs2sprint.llm.base import LLMError
        if isinstance(exc, LLMError):
            st.error(str(exc))
        else:
            st.error(f"Pipeline failed: {type(exc).__name__}: {exc}")

result = st.session_state.get("result")
if result is None and "loaded" not in st.session_state:
    st.title("Upload a BRS to begin")
    st.markdown(
        "This tool turns a business requirements document into a software "
        "requirements spec, a draft design, engineering tickets and a dependency-aware "
        "sprint plan.\n\n"
        "Phases 1–7 use an LLM. **Phase 8 (sprint allocation) is a plain algorithm** — "
        "topological sort plus greedy bin packing — because it is a deterministic "
        "scheduling problem, not a language problem."
    )
    st.stop()

# ---------------------------------------------------------------- display
if result is not None:
    srs, design, plan = result.srs, result.design, result.plan
    summary, tickets = result.summary, result.tickets
    run_id = result.run_id
else:                                        # loaded from DB (plain dicts)
    d = st.session_state["loaded"]
    st.info("Viewing a stored run. Diagrams and tables are rendered from saved JSON.")
    st.json(d, expanded=False)
    st.stop()

st.title(srs.title if srs else summary.title)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Requirements", len(srs.requirements) if srs else 0)
c2.metric("Technical", len(srs.technical()) if srs else 0)
c3.metric("Tickets", len(tickets))
c4.metric("Sprints", len(plan.sprints) if plan else 0)

tabs = st.tabs(["Summary", "SRS", "Design", "Sprint board", "Export"])

with tabs[0]:
    if summary:
        a, b = st.columns(2)
        with a:
            st.subheader("Business goals")
            for g in summary.business_goals:
                st.markdown(f"- {g}")
            st.subheader("Stakeholders")
            for s in summary.stakeholders:
                st.markdown(f"- {s}")
        with b:
            st.subheader("Constraints")
            for c in summary.constraints:
                st.markdown(f"- {c}")
            st.subheader("Out of scope")
            for c in summary.scope_out:
                st.markdown(f"- {c}")
    if result.enriched and result.enriched.findings:
        st.subheader("Identified gaps")
        for f in result.enriched.findings:
            with st.expander(f.question):
                st.write(f.answer)
                st.caption(f"confidence {f.confidence}")

with tabs[1]:
    if srs:
        st.dataframe(
            [{"ID": r.req_id, "Type": r.req_type.value, "Priority": r.priority.value,
              "Kind": r.kind.value if r.kind else "-",
              "Discipline": r.discipline.value if r.discipline else "-",
              "Confidence": r.kind_confidence, "Requirement": r.text}
             for r in srs.requirements],
            use_container_width=True, hide_index=True,
        )
        low = [r for r in srs.requirements if r.kind_confidence < 0.6]
        if low:
            st.warning(f"{len(low)} requirement(s) classified with low confidence — review these.")

with tabs[2]:
    if design and design.components:
        st.write(design.overview)
        st.subheader("Component diagram")
        mermaid(design.mermaid_hld)
        st.subheader("Data model")
        mermaid(design.mermaid_erd, height=380)
        if design.api_contracts:
            st.subheader("API contracts")
            st.dataframe([{"Method": a.method, "Path": a.path, "Summary": a.summary}
                          for a in design.api_contracts],
                         use_container_width=True, hide_index=True)
        cov = p5_design.coverage_report(srs, design)
        st.caption(f"Requirement coverage: {cov['coverage_pct']}% "
                   f"({len(cov['uncovered_req_ids'])} uncovered)")
    else:
        st.info("No design generated.")

with tabs[3]:
    if plan and plan.sprints:
        m = p8_sprints.plan_metrics(plan)
        st.caption(f"{m['sprints']} sprints · velocity {plan.velocity} · "
                   f"{m['avg_utilisation_pct']}% average utilisation")
        for w in plan.warnings:
            st.warning(w)
        cols = st.columns(min(len(plan.sprints), 4))
        for i, sp in enumerate(plan.sprints):
            with cols[i % len(cols)]:
                st.markdown(f"**Sprint {sp.number}** — {sp.committed_points}/{sp.capacity} pts")
                st.progress(min(sp.committed_points / max(sp.capacity, 1), 1.0))
                for t in sp.tickets:
                    with st.container(border=True):
                        st.markdown(f"**{t.ticket_id}** · {t.story_points} pts")
                        st.caption(t.title)
                        if t.labels:
                            st.caption(" ".join(f"`{l}`" for l in t.labels[:3]))
        if plan.unscheduled:
            st.subheader("Unscheduled backlog")
            st.dataframe([{"ID": t.ticket_id, "Title": t.title, "Points": t.story_points}
                          for t in plan.unscheduled],
                         use_container_width=True, hide_index=True)
    else:
        st.info("No sprint plan generated.")

with tabs[4]:
    md = full_markdown(result)
    st.download_button("Delivery pack (.md)", md, f"{run_id}_delivery_pack.md",
                       "text/markdown", use_container_width=True)
    out = Path(settings.output_dir) / f"{run_id}_tickets.csv"
    if out.exists():
        st.download_button("Tickets (.csv)", out.read_bytes(), out.name,
                           "text/csv", use_container_width=True)
    st.code(md[:4000] + ("\n…" if len(md) > 4000 else ""), language="markdown")
