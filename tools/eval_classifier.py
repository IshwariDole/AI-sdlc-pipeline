#!/usr/bin/env python3
"""Score a Phase-4 classifier against a labelled set.

    python tools/eval_classifier.py                      # keyword baseline (mock)
    python tools/eval_classifier.py --provider anthropic
    python tools/eval_classifier.py --compare mock groq gemini
    python tools/eval_classifier.py --json > results.json
    python tools/eval_classifier.py --errors-only

Reports overall metrics plus three slices that matter more than the headline
number:

  * by difficulty  — easy/medium/hard. A classifier that only scores well on
                     easy examples is a keyword matcher with extra steps.
  * trap subset    — examples whose surface vocabulary points the wrong way
                     ("the vendor's API pricing must be renegotiated" is
                     procurement, not engineering). This is the slice that
                     actually separates comprehension from pattern matching.
  * calibration    — does reported confidence track accuracy? An overconfident
                     classifier is worse than an uncertain one, because phase 4
                     uses confidence to flag requirements for human review.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brs2sprint.llm import get_client                       # noqa: E402
from brs2sprint.phases.p4_classify import LLMClassifier     # noqa: E402
from brs2sprint.schemas import Requirement                  # noqa: E402

DATA = ROOT / "data" / "eval" / "requirements_labelled.jsonl"
POSITIVE = "technical"


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------

def load(path: Path) -> list[dict]:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{n}: invalid JSON — {exc}")
        missing = {"id", "text", "label"} - row.keys()
        if missing:
            raise SystemExit(f"{path}:{n}: missing field(s) {sorted(missing)}")
        if row["label"] not in ("technical", "non_technical"):
            raise SystemExit(f"{path}:{n}: bad label {row['label']!r}")
        rows.append(row)
    if not rows:
        raise SystemExit(f"{path}: no examples found")
    return rows


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------

def binary_metrics(pairs: list[tuple[str, str]]) -> dict:
    """pairs = [(gold, pred), ...]. Positive class is `technical`."""
    tp = sum(1 for g, p in pairs if g == POSITIVE and p == POSITIVE)
    tn = sum(1 for g, p in pairs if g != POSITIVE and p != POSITIVE)
    fp = sum(1 for g, p in pairs if g != POSITIVE and p == POSITIVE)
    fn = sum(1 for g, p in pairs if g == POSITIVE and p != POSITIVE)

    def prf(tp_, fp_, fn_):
        pr = tp_ / (tp_ + fp_) if tp_ + fp_ else 0.0
        rc = tp_ / (tp_ + fn_) if tp_ + fn_ else 0.0
        f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
        return round(pr, 3), round(rc, 3), round(f1, 3)

    p_t, r_t, f_t = prf(tp, fp, fn)
    p_n, r_n, f_n = prf(tn, fn, fp)        # non-technical treated as positive
    return {
        "n": len(pairs),
        "accuracy": round((tp + tn) / len(pairs), 3) if pairs else 0.0,
        "precision_technical": p_t, "recall_technical": r_t, "f1_technical": f_t,
        "precision_non_technical": p_n, "recall_non_technical": r_n, "f1_non_technical": f_n,
        "macro_f1": round((f_t + f_n) / 2, 3),
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
    }


def calibration(rows: list[dict],
                bins=((0.0, 0.6), (0.6, 0.8), (0.8, 0.95), (0.95, 1.01))) -> list[dict]:
    out = []
    for lo, hi in bins:
        sel = [r for r in rows if lo <= r["confidence"] < hi]
        if not sel:
            continue
        acc = sum(1 for r in sel if r["correct"]) / len(sel)
        mean_conf = sum(r["confidence"] for r in sel) / len(sel)
        out.append({
            "bucket": f"{lo:.2f}-{hi:.2f}", "n": len(sel),
            "mean_confidence": round(mean_conf, 3),
            "accuracy": round(acc, 3),
            "gap": round(mean_conf - acc, 3),
        })
    return out


def evaluate(provider: str | None, data: list[dict]) -> dict:
    client = get_client(provider)
    reqs = [Requirement(req_id=r["id"], text=r["text"]) for r in data]
    LLMClassifier(client).classify(reqs)

    rows = []
    for req, gold_row in zip(reqs, data):
        pred = req.kind.value
        rows.append({
            "id": gold_row["id"], "text": gold_row["text"],
            "gold": gold_row["label"], "pred": pred,
            "correct": pred == gold_row["label"],
            "confidence": round(req.kind_confidence, 3),
            "difficulty": gold_row.get("difficulty", "unknown"),
            "trap": gold_row.get("trap"),
            "note": gold_row.get("note", ""),
            "reason": req.kind_reason,
        })

    pairs = [(r["gold"], r["pred"]) for r in rows]
    result = {
        "classifier": client.name,
        "llm_calls": client.call_count,
        "overall": binary_metrics(pairs),
        "by_difficulty": {},
        "trap_subset": None,
        "non_trap_subset": None,
        "calibration": calibration(rows),
        "errors": [r for r in rows if not r["correct"]],
        "rows": rows,
    }

    by_diff = defaultdict(list)
    for r in rows:
        by_diff[r["difficulty"]].append((r["gold"], r["pred"]))
    for diff in ("easy", "medium", "hard", "unknown"):
        if diff in by_diff:
            result["by_difficulty"][diff] = binary_metrics(by_diff[diff])

    traps = [(r["gold"], r["pred"]) for r in rows if r["trap"]]
    non_traps = [(r["gold"], r["pred"]) for r in rows if not r["trap"]]
    if traps:
        result["trap_subset"] = binary_metrics(traps)
    if non_traps:
        result["non_trap_subset"] = binary_metrics(non_traps)
    return result


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def report(res: dict, errors_only: bool = False) -> None:
    o = res["overall"]
    print(f"\nclassifier: {res['classifier']}   n={o['n']}   llm_calls={res['llm_calls']}")

    if not errors_only:
        print("=" * 68)
        print(f"  accuracy                {o['accuracy']}")
        print(f"  macro F1                {o['macro_f1']}")
        print(f"  technical      P/R/F1   {o['precision_technical']} / "
              f"{o['recall_technical']} / {o['f1_technical']}")
        print(f"  non-technical  P/R/F1   {o['precision_non_technical']} / "
              f"{o['recall_non_technical']} / {o['f1_non_technical']}")
        c = o["confusion"]
        print(f"  confusion               tp={c['tp']} tn={c['tn']} fp={c['fp']} fn={c['fn']}")

        print("\n  by difficulty")
        for diff, m in res["by_difficulty"].items():
            print(f"    {diff:<9} n={m['n']:<4} acc={m['accuracy']:<7} macroF1={m['macro_f1']}")

        if res["trap_subset"]:
            t, nt = res["trap_subset"], res["non_trap_subset"]
            print("\n  vocabulary traps  (surface words point the wrong way)")
            print(f"    trap      n={t['n']:<4} acc={t['accuracy']:<7} macroF1={t['macro_f1']}")
            print(f"    non-trap  n={nt['n']:<4} acc={nt['accuracy']:<7} macroF1={nt['macro_f1']}")
            delta = round(nt["accuracy"] - t["accuracy"], 3)
            print(f"    gap       {delta}   <- a large gap means keyword matching, not comprehension")

        if res["calibration"]:
            print("\n  calibration  (gap = mean confidence - actual accuracy)")
            for b in res["calibration"]:
                flag = "   OVERCONFIDENT" if b["gap"] > 0.15 else ""
                print(f"    {b['bucket']}  n={b['n']:<4} conf={b['mean_confidence']:<7} "
                      f"acc={b['accuracy']:<7} gap={b['gap']}{flag}")

    errs = res["errors"]
    print(f"\n  errors ({len(errs)}/{o['n']})")
    if not errs:
        print("    none")
    for e in errs:
        print(f"    {e['id']}  gold={e['gold']:<14} pred={e['pred']:<14} "
              f"conf={e['confidence']:<6} [{e['difficulty']}"
              f"{'/trap' if e['trap'] else ''}]")
        print(f"          {e['text'][:88]}")
        if e["note"]:
            print(f"          note: {e['note'][:84]}")
    print()


def compare(results: list[dict]) -> None:
    print("\n" + "=" * 68)
    print(f"  {'classifier':<14}{'acc':>7}{'macroF1':>10}{'trap acc':>10}{'hard acc':>10}{'calls':>8}")
    print("-" * 68)
    for r in results:
        trap = r["trap_subset"]["accuracy"] if r["trap_subset"] else 0.0
        hard = r["by_difficulty"].get("hard", {}).get("accuracy", 0.0)
        print(f"  {r['classifier']:<14}{r['overall']['accuracy']:>7}"
              f"{r['overall']['macro_f1']:>10}{trap:>10}{hard:>10}{r['llm_calls']:>8}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=None)
    ap.add_argument("--compare", nargs="+", metavar="PROVIDER",
                    help="score several providers side by side")
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--errors-only", action="store_true")
    args = ap.parse_args()

    data = load(args.data)

    if args.compare:
        results = []
        for prov in args.compare:
            try:
                results.append(evaluate(prov, data))
            except Exception as exc:
                print(f"! {prov}: {type(exc).__name__}: {exc}")
        if args.json:
            print(json.dumps([{k: v for k, v in r.items() if k != "rows"}
                              for r in results], indent=2))
        else:
            for r in results:
                report(r, errors_only=True)
            compare(results)
        return 0

    res = evaluate(args.provider, data)
    if args.json:
        print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=2))
    else:
        report(res, errors_only=args.errors_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
