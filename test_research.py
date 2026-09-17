from app.ingestion.parser import parse_document
from app.ingestion.summarizer import summarize_brs
from app.ingestion.research_agent import enrich_brs

raw_text = parse_document("data/uploads/ShopEase_BRS_v1.docx")
summary = summarize_brs(raw_text)
enriched = enrich_brs(summary)

print(enriched.model_dump_json(indent=2))