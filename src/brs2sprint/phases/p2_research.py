"""Phase 2 — Research agent (optional, off by default).

Deliberately gated behind RESEARCH_ENABLED. Web research is the flakiest and
least load-bearing phase in this pipeline: it is easy to produce plausible
filler that is hard to evaluate. When disabled, gaps are still *detected* and
recorded as open questions, which is the part that actually matters downstream.
"""

from __future__ import annotations

from ..config import settings
from ..llm import LLMClient, LLMRequest
from ..prompts import SYSTEM_ANALYST, RESEARCH_GAP
from ..schemas import BRSSummary, EnrichedContext, ResearchFinding

VAGUE_MARKERS = (
    "tbd", "to be decided", "to be determined", "etc", "and so on", "as needed",
    "appropriate", "suitable", "user-friendly", "fast", "secure", "scalable",
    "industry standard", "best practice", "compliant", "modern", "robust",
)


def detect_gaps(summary: BRSSummary, limit: int = 5) -> list[str]:
    """Cheap, deterministic, no LLM call: flag statements that are too vague to
    be turned into a testable requirement."""
    gaps: list[str] = list(summary.open_questions)
    pool = summary.business_goals + summary.constraints + summary.scope_in
    for item in pool:
        low = item.lower()
        if any(m in low for m in VAGUE_MARKERS):
            gaps.append(f"Under-specified: {item}")
    seen, out = set(), []
    for g in gaps:
        if g.lower() not in seen:
            seen.add(g.lower())
            out.append(g)
    return out[:limit]


def _search(query: str, max_results: int = 4) -> list[dict]:
    """Tavily search. Returns [] if the key is missing or the call fails —
    research must never be able to break the pipeline."""
    if not settings.tavily_api_key:
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=settings.tavily_api_key)
        resp = client.search(query=query, max_results=max_results)
        return resp.get("results", [])
    except Exception:
        return []


def research(summary: BRSSummary, client: LLMClient) -> EnrichedContext:
    gaps = detect_gaps(summary)
    findings: list[ResearchFinding] = []

    if not settings.research_enabled:
        # Record the gap without pretending to have answered it.
        findings = [
            ResearchFinding(question=g, answer="Not researched (RESEARCH_ENABLED=false).",
                            sources=[], confidence=0.0)
            for g in gaps
        ]
        return EnrichedContext(summary=summary, findings=findings)

    context = "; ".join(summary.business_goals[:3])
    for gap in gaps:
        results = _search(gap)
        blob = "\n".join(
            f"- {r.get('title', '')} ({r.get('url', '')}): {str(r.get('content', ''))[:400]}"
            for r in results
        ) or "(no results)"
        data = client.complete_json(LLMRequest(
            task="research_gap",
            system=SYSTEM_ANALYST,
            user=RESEARCH_GAP.format(question=gap, context=context, results=blob),
            payload={"question": gap, "context": context, "results": results},
        ))
        findings.append(ResearchFinding(
            question=gap,
            answer=str(data.get("answer", "")),
            sources=list(data.get("sources") or [r.get("url", "") for r in results]),
            confidence=float(data.get("confidence", 0.5) or 0.5),
        ))

    return EnrichedContext(summary=summary, findings=findings)
