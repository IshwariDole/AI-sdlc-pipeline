#!/usr/bin/env python3
"""Phase 4 v2 — fine-tune DistilBERT for technical/non-technical classification.

    pip install transformers torch datasets scikit-learn
    python tools/train_classifier.py --data data/labelled_requirements.jsonl

Input format — one JSON object per line:
    {"text": "The system shall expire idle sessions after 15 minutes.",
     "label": "technical"}

Honest note on when this is worth doing: a few-shot LLM prompt already handles
this task well. Fine-tuning wins on (a) per-call cost at volume, (b) latency,
(c) running without an API. It does NOT automatically win on accuracy — you
need a few hundred labelled examples before it beats a good prompt. Score both
with tools/eval_classifier.py before claiming the ML model is better.

A practical bootstrap: run the LLM classifier over real BRS documents, correct
its output by hand, and use that as the training set.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

LABELS = ["non_technical", "technical"]


def load_jsonl(path: Path) -> tuple[list[str], list[int]]:
    texts, labels = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        texts.append(row["text"])
        labels.append(LABELS.index(row["label"]))
    return texts, labels


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--out", default="models/req-classifier")
    ap.add_argument("--base", default="distilbert-base-uncased")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    args = ap.parse_args()

    import numpy as np
    from datasets import Dataset
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support
    from sklearn.model_selection import train_test_split
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                              DataCollatorWithPadding, Trainer, TrainingArguments)

    texts, labels = load_jsonl(args.data)
    if len(texts) < 40:
        print(f"! only {len(texts)} examples — expect a weak model. "
              "Aim for 300+ before comparing against the prompt baseline.")

    # Stratify: requirement sets are usually heavily skewed toward technical.
    x_tr, x_te, y_tr, y_te = train_test_split(
        texts, labels, test_size=0.2, random_state=42,
        stratify=labels if len(set(labels)) > 1 else None)

    tok = AutoTokenizer.from_pretrained(args.base)

    def encode(batch):
        return tok(batch["text"], truncation=True, max_length=192)

    ds_tr = Dataset.from_dict({"text": x_tr, "label": y_tr}).map(encode, batched=True)
    ds_te = Dataset.from_dict({"text": x_te, "label": y_te}).map(encode, batched=True)

    model = AutoModelForSequenceClassification.from_pretrained(
        args.base, num_labels=2,
        id2label={i: l for i, l in enumerate(LABELS)},
        label2id={l: i for i, l in enumerate(LABELS)},
    )

    def metrics(pred):
        preds = np.argmax(pred.predictions, axis=1)
        p, r, f1, _ = precision_recall_fscore_support(
            pred.label_ids, preds, average="binary", zero_division=0)
        return {"accuracy": accuracy_score(pred.label_ids, preds),
                "precision": p, "recall": r, "f1": f1}

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=args.out, num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch_size,
            per_device_eval_batch_size=args.batch_size,
            learning_rate=args.lr, eval_strategy="epoch", save_strategy="epoch",
            load_best_model_at_end=True, metric_for_best_model="f1",
            logging_steps=20, report_to=[],
        ),
        train_dataset=ds_tr, eval_dataset=ds_te,
        data_collator=DataCollatorWithPadding(tok),
        compute_metrics=metrics,
    )
    trainer.train()
    print(trainer.evaluate())

    Path(args.out).mkdir(parents=True, exist_ok=True)
    trainer.save_model(args.out)
    tok.save_pretrained(args.out)
    print(f"\nsaved to {args.out}\nrun: python run_pipeline.py <brs> --classifier transformer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
