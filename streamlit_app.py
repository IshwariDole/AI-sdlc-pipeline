import streamlit as st
from pathlib import Path

from app.ingestion.parser import parse_document
from app.utils.storage import save_json, load_json
from app.pipeline_phases import PHASES

st.set_page_config(page_title="AI-SDLC Pipeline", layout="wide")
st.title("AI-SDLC Pipeline")
st.caption("BRS → Summary → Research → SRS → Classification")

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Load any cached results into session_state, once
for phase in PHASES:
    if phase.key not in st.session_state:
        st.session_state[phase.key] = load_json(phase.schema, phase.filename)


def run_phase(phase, input_value):
    with st.spinner(f"Running {phase.title}..."):
        try:
            result = phase.run_fn(input_value)
            save_json(result, phase.filename)
            st.session_state[phase.key] = result
            st.success(f"{phase.title.split('—')[1].strip()} complete.")
        except Exception as e:
            st.error(f"{phase.title} failed: {e}")


# ---------- Phase 1 is special: needs a file upload, not a previous phase ----------
st.header(PHASES[0].title)
uploaded_file = st.file_uploader("Upload a BRS (.docx or .pdf)", type=["docx", "pdf"])

if uploaded_file and st.button("Run Phase 1: Parse & Summarize"):
    save_path = UPLOAD_DIR / uploaded_file.name
    save_path.write_bytes(uploaded_file.getvalue())
    raw_text = parse_document(str(save_path))
    run_phase(PHASES[0], raw_text)

if st.session_state[PHASES[0].key]:
    with st.expander("View Output", expanded=True):
        PHASES[0].render_fn(st.session_state[PHASES[0].key])

# ---------- Phases 2 onward: generic loop, each fed by the one before it ----------
for i in range(1, len(PHASES)):
    phase = PHASES[i]
    prev_phase = PHASES[i - 1]

    st.header(phase.title)

    prev_result = st.session_state[prev_phase.key]
    if prev_result:
        if st.button(f"Run {phase.title.split('—')[0].strip()}"):
            run_phase(phase, prev_result)
    else:
        st.info(f"Run {prev_phase.title.split('—')[0].strip()} first.")

    if st.session_state[phase.key]:
        with st.expander("View Output", expanded=True):
            phase.render_fn(st.session_state[phase.key])