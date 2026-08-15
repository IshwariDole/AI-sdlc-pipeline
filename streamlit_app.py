import streamlit as st
from pathlib import Path

from app.ingestion.parser import parse_document
from app.ingestion.summarizer import summarize_brs
from app.ingestion.research_agent import enrich_brs
from app.srs.generator import generate_srs
from app.classifier.classifier import classify_srs
from app.utils.storage import save_json, load_json
from app.models.schemas import BRSSummary, EnrichedBRS, SRSDocument, ClassifiedSRS

st.set_page_config(page_title="AI-SDLC Pipeline", layout="wide")
st.title("AI-SDLC Pipeline")
st.caption("BRS → Summary → Research → SRS → Classification")

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# session_state holds this run's results in memory so phase buttons
# don't need to reload from disk on every rerun of the script
if "summary" not in st.session_state:
    st.session_state.summary = load_json(BRSSummary, "01_summary.json")
if "enriched" not in st.session_state:
    st.session_state.enriched = load_json(EnrichedBRS, "02_enriched.json")
if "srs" not in st.session_state:
    st.session_state.srs = load_json(SRSDocument, "03_srs.json")
if "classified" not in st.session_state:
    st.session_state.classified = load_json(ClassifiedSRS, "04_classified.json")


# ---------- Phase 1: Upload + Summarize ----------
st.header("Phase 1 — Ingestion & Summarization")

uploaded_file = st.file_uploader("Upload a BRS (.docx or .pdf)", type=["docx", "pdf"])

if uploaded_file and st.button("Run Phase 1: Parse & Summarize"):
    save_path = UPLOAD_DIR / uploaded_file.name
    save_path.write_bytes(uploaded_file.getvalue())

    with st.spinner("Parsing document and calling LLM..."):
        try:
            raw_text = parse_document(str(save_path))
            summary = summarize_brs(raw_text)
            save_json(summary, "01_summary.json")
            st.session_state.summary = summary
            st.success("Summary generated.")
        except Exception as e:
            st.error(f"Phase 1 failed: {e}")

if st.session_state.summary:
    with st.expander("View Summary Output", expanded=True):
        st.json(st.session_state.summary.model_dump())


# ---------- Phase 2: Research Agent ----------
st.header("Phase 2 — Research Agent")

if st.session_state.summary:
    if st.button("Run Phase 2: Enrich with Research"):
        with st.spinner("Identifying gaps and researching..."):
            try:
                enriched = enrich_brs(st.session_state.summary)
                save_json(enriched, "02_enriched.json")
                st.session_state.enriched = enriched
                st.success("Research findings added.")
            except Exception as e:
                st.error(f"Phase 2 failed: {e}")
else:
    st.info("Run Phase 1 first.")

if st.session_state.enriched:
    with st.expander("View Research Findings", expanded=True):
        for f in st.session_state.enriched.research_findings:
            st.markdown(f"**{f.topic}**")
            st.write(f.finding)
            st.caption(f.source_note)
            st.divider()


# ---------- Phase 3: SRS Generator ----------
st.header("Phase 3 — SRS Generation")

if st.session_state.enriched:
    if st.button("Run Phase 3: Generate SRS"):
        with st.spinner("Drafting formal SRS..."):
            try:
                srs = generate_srs(st.session_state.enriched)
                save_json(srs, "03_srs.json")
                st.session_state.srs = srs
                st.success("SRS generated.")
            except Exception as e:
                st.error(f"Phase 3 failed: {e}")
else:
    st.info("Run Phase 2 first.")

if st.session_state.srs:
    with st.expander("View SRS", expanded=True):
        st.subheader("Functional Requirements")
        st.table([fr.model_dump() for fr in st.session_state.srs.functional_requirements])
        st.subheader("Non-Functional Requirements")
        st.table([nfr.model_dump() for nfr in st.session_state.srs.non_functional_requirements])


# ---------- Phase 4: Classifier ----------
st.header("Phase 4 — Technical / Non-Technical Classification")

if st.session_state.srs:
    if st.button("Run Phase 4: Classify Requirements"):
        with st.spinner("Classifying requirements..."):
            try:
                classified = classify_srs(st.session_state.srs)
                save_json(classified, "04_classified.json")
                st.session_state.classified = classified
                st.success("Classification complete.")
            except Exception as e:
                st.error(f"Phase 4 failed: {e}")
else:
    st.info("Run Phase 3 first.")

if st.session_state.classified:
    with st.expander("View Classifications", expanded=True):
        rows = [c.model_dump() for c in st.session_state.classified.classifications]
        st.table(rows)

        tech_count = sum(1 for c in st.session_state.classified.classifications if c.type == "Technical")
        nontech_count = len(rows) - tech_count
        col1, col2 = st.columns(2)
        col1.metric("Technical", tech_count)
        col2.metric("Non-Technical", nontech_count)