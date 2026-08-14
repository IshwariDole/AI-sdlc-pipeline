from app.ingestion.parser import parse_document
from app.ingestion.summarizer import summarize_brs
from app.ingestion.research_agent import enrich_brs
from app.srs.generator import generate_srs
from app.classifier.classifier import classify_srs

raw_text = parse_document("data/uploads/ShopEase_BRS_v1.docx")
summary = summarize_brs(raw_text)
enriched = enrich_brs(summary)
srs = generate_srs(enriched)
classified = classify_srs(srs)

print(classified.model_dump_json(indent=2))