import json
import subprocess
import sys
from pathlib import Path

from evaluate import evaluate

ROOT = Path(__file__).resolve().parents[1]


def write(tmp_path, rows):
    p = tmp_path / "p.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def test_per_label_metrics_and_macro_f1():
    out = evaluate(ROOT / "preds.jsonl")
    spam, ham = out["per_label"]["spam"], out["per_label"]["ham"]
    assert spam == {"precision": 1.0, "recall": 0.5, "f1": 0.6667, "support": 2}
    assert ham == {"precision": 0.6667, "recall": 0.6667, "f1": 0.6667, "support": 3}
    assert out["macro_f1"] == 0.6667


def test_a_label_never_predicted_has_zero_precision(tmp_path):
    out = evaluate(write(tmp_path, [{"label": "a", "pred": "b"}, {"label": "b", "pred": "b"}]))
    assert out["per_label"]["a"] == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 1}
    assert out["per_label"]["b"] == {"precision": 0.5, "recall": 1.0, "f1": 0.6667, "support": 1}
    assert out["accuracy"] == 0.5 and out["macro_f1"] == 0.3333


def test_a_pred_only_label_is_listed(tmp_path):
    out = evaluate(write(tmp_path, [{"label": "a", "pred": "c"}, {"label": "a", "pred": "a"}]))
    assert out["per_label"]["c"] == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0}
    assert set(out["per_label"]) == {"a", "c"}


def test_a_missing_pred_is_wrong(tmp_path):
    out = evaluate(write(tmp_path, [{"label": "a"}, {"label": "a", "pred": "a"}]))
    assert out["n"] == 2 and out["accuracy"] == 0.5 and out["per_label"]["a"]["recall"] == 0.5


def test_the_command_line_prints_json():
    run = subprocess.run([sys.executable, "evaluate.py", "preds.jsonl"], cwd=ROOT, capture_output=True, text=True,
                         timeout=60)
    assert run.returncode == 0 and json.loads(run.stdout)["accuracy"] == 0.6
