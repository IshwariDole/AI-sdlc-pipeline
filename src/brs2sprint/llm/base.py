"""Provider-agnostic LLM interface.

Every call is described by an LLMRequest carrying both the rendered prompt
(used by real providers) and the structured `payload` (used by the offline
mock provider). That split is what lets the entire pipeline run end-to-end
with no API key and no network.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


@dataclass
class LLMRequest:
    task: str
    system: str = ""
    user: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    json_output: bool = True
    max_tokens: int | None = None
    temperature: float | None = None


class LLMError(RuntimeError):
    pass


def extract_json(text: str) -> Any:
    """Tolerant JSON extraction: strips code fences, then falls back to
    slicing the outermost {...} or [...] block."""
    cleaned = _FENCE.sub("", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(opener), cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError(f"could not parse JSON from model output:\n{text[:500]}")


class LLMClient(ABC):
    """Implement `_raw` in a provider; `complete_json` is shared."""

    name = "base"

    def __init__(self) -> None:
        self.call_count = 0

    @abstractmethod
    def _raw(self, req: LLMRequest) -> str:
        ...

    def complete(self, req: LLMRequest) -> str:
        self.call_count += 1
        return self._raw(req)

    def complete_json(self, req: LLMRequest, retries: int = 2) -> Any:
        last: Exception | None = None
        for attempt in range(retries + 1):
            text = self.complete(req)
            try:
                return extract_json(text)
            except LLMError as exc:
                last = exc
                # nudge the model harder on retry
                req = LLMRequest(
                    task=req.task,
                    system=req.system + "\n\nReturn ONLY valid JSON. No prose, no code fences.",
                    user=req.user,
                    payload=req.payload,
                    json_output=True,
                    max_tokens=req.max_tokens,
                    temperature=0.0,
                )
        raise LLMError(f"{self.name}: JSON parsing failed after {retries + 1} attempts") from last
