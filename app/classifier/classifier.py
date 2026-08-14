from app.models.schemas import SRSDocument, ClassifiedSRS, RequirementClassification
from app.utils.llm_client import generate_structured

CLASSIFY_PROMPT = """You are a delivery lead splitting SRS requirements into
Technical vs Non-Technical work items.

Definitions:
- Technical: requires software engineering effort -- code, infrastructure,
  database work, third-party API integration, or QA/testing effort.
- Non-Technical: requires business/process action but NOT software engineering
  -- e.g. staff training, drafting a policy document, manual vendor onboarding,
  legal review, content writing.

Examples:
- "The system shall allow customers to reset their password via email." -> Technical, Backend
- "Store staff shall receive training on using the admin dashboard." -> Non-Technical, Training
- "The system shall encrypt personal data at rest." -> Technical, Security
- "The company shall publish an updated privacy policy before launch." -> Non-Technical, Compliance/Legal

Classify EVERY requirement below. Do not skip any -- there are exactly {count} items.

REQUIREMENTS:
{data}
"""


class _Batch(ClassifiedSRS):
    pass  # same shape, just used per-chunk


def _classify_batch(project_name: str, items: list) -> list[RequirementClassification]:
    lines = "\n".join(f"{item.id}: {item.description if hasattr(item, 'description') else item.category + ' - ' + item.description}"
                       for item in items)
    prompt = CLASSIFY_PROMPT.format(count=len(items), data=lines)
    result = generate_structured(prompt, ClassifiedSRS)
    return result.classifications


def classify_srs(srs: SRSDocument, batch_size: int = 6) -> ClassifiedSRS:
    all_items = list(srs.functional_requirements) + list(srs.non_functional_requirements)
    all_classifications = []

    for i in range(0, len(all_items), batch_size):
        batch = all_items[i:i + batch_size]
        print(f"[classifier] Classifying batch {i // batch_size + 1} ({len(batch)} items)...")
        all_classifications.extend(_classify_batch(srs.project_name, batch))

    expected_ids = {item.id for item in all_items}
    got_ids = {c.id for c in all_classifications}
    missing = expected_ids - got_ids
    if len(missing) > len(expected_ids) * 0.3:
        raise RuntimeError(
            f"Classification looks unreliable: {len(missing)}/{len(expected_ids)} "
            f"requirements missing. Not caching this result. Missing: {missing}"
        )
    elif missing:
        print(f"[classifier] Warning: model skipped these requirements: {missing}")

    return ClassifiedSRS(project_name=srs.project_name, classifications=all_classifications)