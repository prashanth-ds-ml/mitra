from pathlib import Path

from evaluate import evaluate


def test_accuracy_on_the_sample():
    out = evaluate(Path(__file__).resolve().parents[1] / "preds.jsonl")
    assert out["n"] == 5 and out["accuracy"] == 0.6
