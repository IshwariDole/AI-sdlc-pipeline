from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from app.design.generator import generate_design
from app.models.schemas import DesignDocument
from app.ingestion.parser import parse_document
from app.ingestion.summarizer import summarize_brs
from app.ingestion.research_agent import enrich_brs
from app.srs.generator import generate_srs
from app.classifier.classifier import classify_srs
from app.utils.storage import save_json, load_json
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.models.schemas import BRSSummary, EnrichedBRS, SRSDocument, ClassifiedSRS
import streamlit as st
app = FastAPI(title="AI-SDLC Pipeline API")

# React runs on a different port (localhost:3000/5173) than FastAPI
# (localhost:8000) -- browsers block cross-port requests by default
# (CORS). This explicitly allows your local React dev server through.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")

@app.post("/api/phase1/summarize")
async def run_phase1(file: UploadFile = File(...)):
    try:
        save_path = UPLOAD_DIR / file.filename
        content = await file.read()
        save_path.write_bytes(content)

        raw_text = parse_document(str(save_path))
        summary = summarize_brs(raw_text)
        save_json(summary, "01_summary.json")
        return summary.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/phase2/research")
async def run_phase2():
    summary = load_json(BRSSummary, "01_summary.json")
    if not summary:
        raise HTTPException(status_code=400, detail="Run Phase 1 first.")
    try:
        enriched = enrich_brs(summary)
        save_json(enriched, "02_enriched.json")
        return enriched.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/phase3/srs")
async def run_phase3():
    enriched = load_json(EnrichedBRS, "02_enriched.json")
    if not enriched:
        raise HTTPException(status_code=400, detail="Run Phase 2 first.")
    try:
        srs = generate_srs(enriched)
        save_json(srs, "03_srs.json")
        return srs.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/phase4/classify")
async def run_phase4():
    srs = load_json(SRSDocument, "03_srs.json")
    if not srs:
        raise HTTPException(status_code=400, detail="Run Phase 3 first.")
    try:
        classified = classify_srs(srs)
        save_json(classified, "04_classified.json")
        return classified.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/phase5/design")
async def run_phase5():
    classified = load_json(ClassifiedSRS, "04_classified.json")
    if not classified:
        raise HTTPException(status_code=400, detail="Run Phase 4 first.")
    try:
        design = generate_design(classified)
        save_json(design, "05_design.json")
        return design.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/results/{phase}")
async def get_results(phase: str):
    """Lets the frontend re-fetch already-cached results on page load,
    e.g. after a refresh, without re-running any LLM calls."""
    mapping = {
    "summary": (BRSSummary, "01_summary.json"),
    "enriched": (EnrichedBRS, "02_enriched.json"),
    "srs": (SRSDocument, "03_srs.json"),
    "classified": (ClassifiedSRS, "04_classified.json"),
    "design": (DesignDocument, "05_design.json"),
}
    if phase not in mapping:
        raise HTTPException(status_code=404, detail="Unknown phase.")
    schema, filename = mapping[phase]
    result = load_json(schema, filename)
    if result is None:
        return None
    return result.model_dump()