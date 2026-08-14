from app.models.schemas import SRSDocument, ClassifiedSRS
from app.utils.llm_client import generate_structured

CLASSIFY_PROMPT = """... (keep your existing prompt text exactly as-is) ..."""


def classify_srs(srs: SRSDocument) -> ClassifiedSRS:
    payload = srs.model_dump_json(indent=2)
    result = generate_structured(CLASSIFY_PROMPT.format(data=payload), ClassifiedSRS)
    expected_ids = {fr.id for fr in srs.functional_requirements} | {nfr.id for nfr in srs.non_functional_requirements}
    got_ids = {c.id for c in result.classifications}
    missing = expected_ids - got_ids

    if len(missing) > len(expected_ids) * 0.3:  # more than 30% missing = something's badly wrong
        raise RuntimeError(
            f"Classification looks unreliable: {len(missing)}/{len(expected_ids)} "
            f"requirements missing. Not caching this result. Missing: {missing}"
        )
    elif missing:
        print(f"[classifier] Warning: model skipped these requirements: {missing}")

    return result