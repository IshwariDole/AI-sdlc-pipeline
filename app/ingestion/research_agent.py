import json
from app.models.schemas import BRSSummary, EnrichedBRS, ResearchFinding
from app.utils.llm_client import generate_text

IDENTIFY_PROMPT = """You are a business analyst. Below is a structured summary of a
Business Requirements Specification. Identify up to 3 points that are vague,
underspecified, or would benefit from external research to make them concrete
(e.g. references to "relevant regulations", "major payment gateways", "industry
standards" without naming specifics).

For each, phrase it as a short, specific, googleable research question.
Return ONLY a JSON list of strings. If nothing needs research, return an empty list.

SUMMARY:
{summary_json}
"""


def _identify_research_topics(summary: BRSSummary) -> list[str]:
    prompt = IDENTIFY_PROMPT.format(summary_json=summary.model_dump_json(indent=2))
    raw = generate_text(prompt)
    topics = json.loads(raw)
    return topics[:3]


def _research_topic(topic: str) -> ResearchFinding:
    prompt = (f"Answer this concisely and factually (3-4 sentences max), "
              f"based on your general knowledge. If specifics may be "
              f"outdated, say so briefly: {topic}")
    finding_text = generate_text(prompt)
    return ResearchFinding(
        topic=topic,
        finding=finding_text,
        source_note="Gemini model knowledge (not live web search)",
    )


def enrich_brs(summary: BRSSummary) -> EnrichedBRS:
    topics = _identify_research_topics(summary)

    findings = []
    for topic in topics:
        try:
            findings.append(_research_topic(topic))
        except Exception as e:
            print(f"[research_agent] Skipped topic '{topic}': {e}")

    return EnrichedBRS(summary=summary, research_findings=findings)