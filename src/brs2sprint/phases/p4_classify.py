"""Phase 4 — Technical / non-technical classification.

Two strategies behind one interface:
  * LLMClassifier        — few-shot prompt, batched. The MVP default.
  * TransformerClassifier — fine-tuned DistilBERT head, loaded if available.

Keeping them behind a common `classify()` signature is the point: the v2 ML
model is a drop-in swap, and both can be scored against the same labelled set
(see tools/eval_classifier.py).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..llm import LLMClient, LLMRequest
from ..prompts import SYSTEM_ANALYST, CLASSIFY_REQUIREMENTS
from ..schemas import SRS, Discipline, ReqKind, Requirement

BATCH_SIZE = 20


class Classifier(ABC):
    name = "base"

    @abstractmethod
    def classify(self, requirements: list[Requirement]) -> None:
        """Mutates each Requirement in place: kind, kind_confidence,
        kind_reason, discipline."""


class LLMClassifier(Classifier):
    name = "llm-fewshot"

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    def classify(self, requirements: list[Requirement]) -> None:
        import json
        by_id = {r.req_id: r for r in requirements}

        for start in range(0, len(requirements), BATCH_SIZE):
            batch = requirements[start:start + BATCH_SIZE]
            payload = [{"req_id": r.req_id, "text": r.text, "req_type": r.req_type.value}
                       for r in batch]
            data = self.client.complete_json(LLMRequest(
                task="classify_requirements",
                system=SYSTEM_ANALYST,
                user=CLASSIFY_REQUIREMENTS.format(
                    requirements=json.dumps(payload, indent=2, ensure_ascii=False)),
                payload={"requirements": payload},
            ))
            for c in data.get("classifications") or []:
                req = by_id.get(c.get("req_id"))
                if req is None:
                    continue
                req.kind = ReqKind.TECHNICAL if str(c.get("kind", "")).startswith("tech") \
                    else ReqKind.NON_TECHNICAL
                req.kind_confidence = float(c.get("confidence", 0.5) or 0.5)
                req.kind_reason = str(c.get("reason", ""))
                try:
                    req.discipline = Discipline(str(c.get("discipline", "backend")).lower())
                except ValueError:
                    req.discipline = Discipline.BACKEND

        # Anything the model skipped still needs a value.
        for r in requirements:
            if r.kind is None:
                r.kind = ReqKind.TECHNICAL
                r.kind_confidence = 0.0
                r.kind_reason = "unclassified by model; defaulted to technical"
                r.discipline = Discipline.BACKEND


class TransformerClassifier(Classifier):
    """v2 path: a fine-tuned sequence classifier.

    Train with tools/train_classifier.py, then set CLASSIFIER=transformer.
    Falls back loudly rather than silently if the model is missing.
    """
    name = "distilbert"

    def __init__(self, model_dir: str = "models/req-classifier") -> None:
        try:
            from transformers import pipeline  # type: ignore
        except ImportError as exc:
            raise ImportError("pip install transformers torch") from exc
        self._pipe = pipeline("text-classification", model=model_dir, top_k=None)

    def classify(self, requirements: list[Requirement]) -> None:
        texts = [r.text for r in requirements]
        for req, scores in zip(requirements, self._pipe(texts)):
            best = max(scores, key=lambda s: s["score"])
            req.kind = ReqKind.TECHNICAL if "tech" in best["label"].lower() \
                and "non" not in best["label"].lower() else ReqKind.NON_TECHNICAL
            req.kind_confidence = round(float(best["score"]), 3)
            req.kind_reason = f"{self.name}: {best['label']}"
            req.discipline = Discipline.BACKEND if req.kind == ReqKind.TECHNICAL else Discipline.BUSINESS


def classify_srs(srs: SRS, classifier: Classifier) -> dict[str, int]:
    classifier.classify(srs.requirements)
    low_conf = [r.req_id for r in srs.requirements if r.kind_confidence < 0.6]
    return {
        "total": len(srs.requirements),
        "technical": len(srs.technical()),
        "non_technical": len(srs.non_technical()),
        "low_confidence": len(low_conf),
    }
