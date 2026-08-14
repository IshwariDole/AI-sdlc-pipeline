from app.utils.storage import save_json, load_json
from app.ingestion.parser import parse_document
from app.ingestion.summarizer import summarize_brs
from app.ingestion.research_agent import enrich_brs
from app.srs.generator import generate_srs
from app.classifier.classifier import classify_srs

from app.models.schemas import BRSSummary, EnrichedBRS, SRSDocument, ClassifiedSRS

BRS_PATH = "data/uploads/ShopEase_BRS_v1.docx"


def get_summary() -> BRSSummary:
    cached = load_json(BRSSummary, "01_summary.json")
    if cached:
        print("[pipeline] Using cached summary")
        return cached
    raw_text = parse_document(BRS_PATH)
    summary = summarize_brs(raw_text)
    save_json(summary, "01_summary.json")
    return summary


def get_enriched() -> EnrichedBRS:
    cached = load_json(EnrichedBRS, "02_enriched.json")
    if cached:
        print("[pipeline] Using cached enriched BRS")
        return cached
    enriched = enrich_brs(get_summary())
    save_json(enriched, "02_enriched.json")
    return enriched


def get_srs() -> SRSDocument:
    cached = load_json(SRSDocument, "03_srs.json")
    if cached:
        print("[pipeline] Using cached SRS")
        return cached
    srs = generate_srs(get_enriched())
    save_json(srs, "03_srs.json")
    return srs


def get_classified() -> ClassifiedSRS:
    cached = load_json(ClassifiedSRS, "04_classified.json")
    if cached:
        print("[pipeline] Using cached classification")
        return cached
    classified = classify_srs(get_srs())
    save_json(classified, "04_classified.json")
    return classified


if __name__ == "__main__":
    classified = get_classified()
    print(classified.model_dump_json(indent=2))