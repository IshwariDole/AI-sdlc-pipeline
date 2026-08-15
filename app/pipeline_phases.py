from dataclasses import dataclass
from typing import Callable, Any, Optional

from app.ingestion.summarizer import summarize_brs
from app.ingestion.research_agent import enrich_brs
from app.srs.generator import generate_srs
from app.classifier.classifier import classify_srs
from app.models.schemas import BRSSummary, EnrichedBRS, SRSDocument, ClassifiedSRS



@dataclass
class Phase:
    key: str                       # session_state key, e.g. "summary"
    title: str                     # UI header
    filename: str                  # cache filename, e.g. "01_summary.json"
    schema: type                   # Pydantic model for load/validate
    run_fn: Callable[[Any], Any]   # function that takes previous phase's output
    render_fn: Callable[[Any], None]  # how to display the result in Streamlit


# --- render functions (kept separate so they're easy to find/edit) ---

def render_summary(summary):
    import streamlit as st
    st.json(summary.model_dump())


def render_enriched(enriched):
    import streamlit as st
    for f in enriched.research_findings:
        st.markdown(f"**{f.topic}**")
        st.write(f.finding)
        st.caption(f.source_note)
        st.divider()


def render_srs(srs):
    import streamlit as st
    st.subheader("Functional Requirements")
    st.table([fr.model_dump() for fr in srs.functional_requirements])
    st.subheader("Non-Functional Requirements")
    st.table([nfr.model_dump() for nfr in srs.non_functional_requirements])


def render_classified(classified):
    import streamlit as st
    rows = [c.model_dump() for c in classified.classifications]
    st.table(rows)
    tech = sum(1 for c in classified.classifications if c.type == "Technical")
    col1, col2 = st.columns(2)
    col1.metric("Technical", tech)
    col2.metric("Non-Technical", len(rows) - tech)


# --- the actual pipeline definition ---
# Each phase's run_fn takes ONE argument: the previous phase's result.
# Phase 1 is special (it needs a file path, not a previous result) --
# handled separately in the app since it's the entry point.

PHASES = [
    Phase("summary", "Phase 1 — Ingestion & Summarization", "01_summary.json",
          BRSSummary, run_fn=summarize_brs, render_fn=render_summary),

    Phase("enriched", "Phase 2 — Research Agent", "02_enriched.json",
          EnrichedBRS, run_fn=enrich_brs, render_fn=render_enriched),

    Phase("srs", "Phase 3 — SRS Generation", "03_srs.json",
          SRSDocument, run_fn=generate_srs, render_fn=render_srs),

    Phase("classified", "Phase 4 — Classification", "04_classified.json",
          ClassifiedSRS, run_fn=classify_srs, render_fn=render_classified),
]