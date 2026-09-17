from app.ingestion.parser import parse_document
from app.ingestion.summarizer import summarize_brs

raw_text = parse_document("data/uploads/ShopEase_BRS_v1.docx")
summary = summarize_brs(raw_text)

print(summary.model_dump_json(indent=2))