"""Tests for the evaluation dataset and metric implementations.

A labelled set silently rots: a bad line, a typo'd label, an accidental
duplicate. These tests make the dataset a maintained artefact rather than a
file someone appended to once.
"""

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from eval_classifier import DATA, binary_metrics, calibration, evaluate, load  # noqa: E402


def test_dataset_loads_and_is_well_formed():
    rows = load(DATA)
    assert len(rows) >= 50, "eval set is too small to mean anything"
    for r in rows:
        assert r["text"].strip()
        assert r["label"] in ("technical", "non_technical")
        assert r.get("difficulty") in ("easy", "medium", "hard", None)


def test_ids_are_unique():
    rows = load(DATA)
    dupes = [i for i, c in Counter(r["id"] for r in rows).items() if c > 1]
    assert not dupes, f"duplicate ids: {dupes}"


def test_texts_are_unique():
    rows = load(DATA)
    dupes = [t for t, c in Counter(r["text"].strip().lower() for r in rows).items() if c > 1]
    assert not dupes, f"duplicate texts: {dupes}"


def test_classes_are_not_badly_imbalanced():
    rows = load(DATA)
    counts = Counter(r["label"] for r in rows)
    ratio = min(counts.values()) / max(counts.values())
    assert ratio > 0.6, f"class imbalance {dict(counts)} — accuracy would be misleading"


def test_hard_examples_explain_themselves():
    """A 'hard' label without a rationale is an unreviewable judgement call."""
    for r in load(DATA):
        if r.get("difficulty") == "hard":
            assert r.get("note", "").strip(), f"{r['id']} is hard but has no note"


def test_trap_subset_is_substantial():
    rows = load(DATA)
    traps = [r for r in rows if r.get("trap")]
    assert len(traps) >= 15, "too few vocabulary traps to measure comprehension"
    labels = Counter(r["label"] for r in traps)
    assert len(labels) == 2, "traps must run in both directions, or they test only one failure mode"


def test_binary_metrics_on_known_input():
    pairs = [("technical", "technical")] * 3 + \
            [("technical", "non_technical")] * 1 + \
            [("non_technical", "non_technical")] * 4 + \
            [("non_technical", "technical")] * 2
    m = binary_metrics(pairs)
    assert m["confusion"] == {"tp": 3, "tn": 4, "fp": 2, "fn": 1}
    assert m["accuracy"] == 0.7
    assert m["precision_technical"] == 0.6      # 3/5
    assert m["recall_technical"] == 0.75        # 3/4


def test_perfect_and_inverted_predictions():
    gold = ["technical", "non_technical"] * 5
    assert binary_metrics([(g, g) for g in gold])["accuracy"] == 1.0
    flip = {"technical": "non_technical", "non_technical": "technical"}
    assert binary_metrics([(g, flip[g]) for g in gold])["accuracy"] == 0.0


def test_calibration_detects_overconfidence():
    rows = [{"confidence": 0.99, "correct": i < 5} for i in range(10)]
    buckets = calibration(rows)
    assert buckets and buckets[-1]["gap"] > 0.4, "should flag confident-but-wrong"


def test_baseline_is_beatable():
    """The keyword baseline must NOT score near-perfect.

    If it does, the eval set has become too easy and stops distinguishing
    comprehension from pattern matching — which is the whole point of it.
    """
    res = evaluate("mock", load(DATA))
    assert res["overall"]["accuracy"] < 0.9, \
        "keyword baseline scores too high — add harder examples"
    assert res["trap_subset"]["accuracy"] < res["non_trap_subset"]["accuracy"], \
        "traps are not actually trapping the keyword baseline"


if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
