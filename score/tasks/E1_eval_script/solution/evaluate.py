"""Evaluate classifier predictions: python evaluate.py preds.jsonl"""
import json
import sys


def _div(a, b):
    return a / b if b else 0.0


def evaluate(path):
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    labels = sorted({r["label"] for r in rows} | {r["pred"] for r in rows if r.get("pred") is not None})
    per, f1s = {}, []
    for lab in labels:
        tp = sum(1 for r in rows if r["label"] == lab and r.get("pred") == lab)
        support = sum(1 for r in rows if r["label"] == lab)
        p, rec = _div(tp, sum(1 for r in rows if r.get("pred") == lab)), _div(tp, support)
        f1 = _div(2 * p * rec, p + rec)
        f1s.append(f1)
        per[lab] = {"precision": round(p, 4), "recall": round(rec, 4), "f1": round(f1, 4), "support": support}
    correct = sum(1 for r in rows if r.get("pred") is not None and r.get("pred") == r["label"])
    return {"n": len(rows), "accuracy": round(_div(correct, len(rows)), 4), "per_label": per,
            "macro_f1": round(_div(sum(f1s), len(f1s)), 4)}


if __name__ == "__main__":
    print(json.dumps(evaluate(sys.argv[1])))
