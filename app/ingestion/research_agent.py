import os
import json
from google import genai
from dotenv import load_dotenv

from app.models.schemas import BRSSummary, EnrichedBRS, ResearchFinding

load_dotenv()

GEMINI_MODEL = "gemini-3.5-flash"
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


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
    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=IDENTIFY_PROMPT.format(summary_json=summary.model_dump_json(indent=2)),
        config={"response_mime_type": "application/json"},
    )
    topics = json.loads(response.text)
    return topics[:3]  # hard cap -- keep this cheap and fast for now

def _research_topic(topic: str) -> ResearchFinding:
    """
    Answers a research question using the model's own knowledge.
    (Note: live Google Search grounding was tested but is currently
    unreliable/rate-limited on the free tier -- see project README.)
    """
    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=f"Answer this concisely and factually (3-4 sentences max), "
                  f"based on your general knowledge. If specifics may be "
                  f"outdated, say so briefly: {topic}",
    )
    return ResearchFinding(
        topic=topic,
        finding=response.text.strip(),
        source_note="Gemini model knowledge (not live web search)",
    )

def enrich_brs(summary: BRSSummary) -> EnrichedBRS:
    """
    Identifies vague points in the BRS summary and researches each one.
    """
    topics = _identify_research_topics(summary)

    findings = []
    for topic in topics:
        try:
            findings.append(_research_topic(topic))
        except Exception as e:
            # One failed research call shouldn't kill the whole pipeline --
            # we skip it and keep going. This matters a lot more once you
            # chain 9 phases together: a single flaky network call must not
            # take down everything after it.
            print(f"[research_agent] Skipped topic '{topic}': {e}")

    return EnrichedBRS(summary=summary, research_findings=findings)