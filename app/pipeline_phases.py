from dataclasses import dataclass
from typing import Callable, Any, Optional
from app.design.generator import generate_design
from app.ingestion.summarizer import summarize_brs
from app.ingestion.research_agent import enrich_brs
from app.srs.generator import generate_srs
from app.classifier.classifier import classify_srs
from app.models.schemas import (
    BRSSummary,
    EnrichedBRS,
    SRSDocument,
    ClassifiedSRS,
    DesignDocument,
)


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

def render_design(design):
    import streamlit as st

    # -------------------------
    # HIGH LEVEL DESIGN
    # -------------------------

    st.subheader("🏗️ High-Level Design")

    st.markdown("### Architecture Overview")
    st.write(design.hld.architecture_overview)

    st.markdown("### Components")

    for component in design.hld.components:
        with st.expander(f"📦 {component.name}"):

            st.write(
                f"**Responsibility:** {component.responsibility}"
            )

            if component.technologies:
                st.write(
                    "**Technologies:** "
                    + ", ".join(component.technologies)
                )

            if component.related_requirements:
                st.write(
                    "**Related Requirements:** "
                    + ", ".join(
                        component.related_requirements
                    )
                )

    st.markdown("### Data Flow")

    for step in design.hld.data_flow:
        st.write(f"→ {step}")

    st.markdown("### Technology Stack")

    for technology in design.hld.technology_stack:
        st.write(f"- {technology}")

    # -------------------------
    # MERMAID DIAGRAM
    # -------------------------

    if design.hld.mermaid_diagram:

        st.markdown("### Architecture Diagram")

        st.code(
            design.hld.mermaid_diagram,
            language="mermaid"
        )

    st.divider()

    # -------------------------
    # LOW LEVEL DESIGN
    # -------------------------

    st.subheader("⚙️ Low-Level Design")

    st.markdown("### Modules")

    for module in design.lld.modules:
        st.write(f"- {module}")

    # -------------------------
    # API CONTRACTS
    # -------------------------

    st.markdown("### API Contracts")

    for api in design.lld.api_contracts:

        with st.expander(
            f"{api.method} {api.endpoint}"
        ):

            st.write(f"**Name:** {api.name}")
            st.write(
                f"**Description:** {api.description}"
            )

            if api.request_body:
                st.code(
                    api.request_body,
                    language="json"
                )

            if api.response_body:
                st.code(
                    api.response_body,
                    language="json"
                )

            if api.related_requirements:
                st.write(
                    "**Related Requirements:** "
                    + ", ".join(
                        api.related_requirements
                    )
                )

    # -------------------------
    # DATABASE SCHEMA
    # -------------------------

    st.markdown("### Database Schema")

    for table in design.lld.database_schema:

        with st.expander(f"🗄️ {table.name}"):

            st.write(table.description)

            if table.related_requirements:
                st.write(
                    "**Related Requirements:** "
                    + ", ".join(
                        table.related_requirements
                    )
                )

            columns = []

            for column in table.columns:
                columns.append({
                    "Column": column.name,
                    "Type": column.data_type,
                    "Description": column.description
                })

            if columns:
                st.table(columns)
# --- the actual pipeline definition ---
# Each phase's run_fn takes ONE argument: the previous phase's result.
# Phase 1 is special (it needs a file path, not a previous result) --
# handled separately in the app since it's the entry point.

def run_design(classified: ClassifiedSRS) -> DesignDocument:
    return generate_design(
        classified=classified,
        project_name=classified.project_name
    )
PHASES = [

    Phase("summary", "Phase 1 — Ingestion & Summarization", "01_summary.json",
          BRSSummary, run_fn=summarize_brs, render_fn=render_summary),

    Phase("enriched", "Phase 2 — Research Agent", "02_enriched.json",
          EnrichedBRS, run_fn=enrich_brs, render_fn=render_enriched),

    Phase("srs", "Phase 3 — SRS Generation", "03_srs.json",
          SRSDocument, run_fn=generate_srs, render_fn=render_srs),

    Phase("classified", "Phase 4 — Classification", "04_classified.json",
          ClassifiedSRS, run_fn=classify_srs, render_fn=render_classified),

    Phase(
        "design",
        "Phase 5 — HLD & LLD Design",
        "05_design.json",
        DesignDocument,
        run_fn=run_design,
        render_fn=render_design,
    ),
]