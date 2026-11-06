"""`mitra improve` (self-improvement step 3): proposal parsing, A/B decision, keep/drop, attempts log."""
import json
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage

from app.core import analyze as A
from app.core import dashboard as D
from app.core import harness as H
from app.core import improve as I

TOOLS = {"run_tests", "read_file", "run_command"}


def test_parse_change_accepts_valid_and_rejects_bad_proposals():
    h = H.Harness(rules=["Read the error first."])
    ch, _ = I.parse_change('<think>hmm</think>Sure: {"kind": "rule", "text": "After a command fails, change it.", '
                           '"why": "repeats"}', h, TOOLS)
    assert ch.kind == "rule" and ch.text == "After a command fails, change it."
    assert I.parse_change('{"kind": "rule", "text": "read the error first."}', h, TOOLS)[1] == "rule already exists"
    assert "unknown tool" in I.parse_change('{"kind": "tool", "name": "rm_rf", "text": "x"}', h, TOOLS)[1]
    assert "unknown limit" in I.parse_change('{"kind": "limit", "name": "bogus", "value": 3}', h, TOOLS)[1]
    assert "unchanged" in I.parse_change('{"kind": "limit", "name": "max_repeats", "value": 2}', h, TOOLS)[1]
    assert I.parse_change("no json here", h, TOOLS)[0] is None
    ch, _ = I.parse_change('{"kind": "limit", "name": "max_failures", "value": 3}', h, TOOLS)
    assert ch.apply(h).limit("max_failures") == 3 and h.limit("max_failures") == 4  # apply copies


def test_decide_needs_more_passes_without_much_more_cost():
    base = I.Score(passed=2, total=5, tokens_in=100_000)
    assert I.decide(base, I.Score(passed=3, total=5, tokens_in=110_000))[0]
    assert not I.decide(base, I.Score(passed=3, total=5, tokens_in=150_000))[0]
    assert not I.decide(base, I.Score(passed=2, total=5, tokens_in=50_000))[0]


class Proposer:
    def __init__(self, *answers):
        self.answers = list(answers)

    def invoke(self, messages):
        return AIMessage(content=self.answers.pop(0))


def _report():
    rep = A.Report(units=3)
    rep.pattern("repeated_failing_command").add("4x cd x && pytest")
    return rep


def _fake_eval(results):
    """evaluate() stand-in: the first call is the base run, the second the candidate."""
    calls = []

    def ev(h, llm, **kw):
        calls.append(h)
        return results[len(calls) - 1]
    return ev, calls


def test_improve_keeps_a_better_change_and_logs_it(tmp_path, monkeypatch):
    monkeypatch.setenv("MITRA_HOME", str(tmp_path))
    monkeypatch.setenv("MITRA_HARNESS", str(tmp_path / "harness.toml"))
    ev, calls = _fake_eval([I.Score(1, 5, 1000), I.Score(3, 5, 1100)])
    monkeypatch.setattr(I, "evaluate", ev)
    prop = Proposer("not json", '{"kind": "rule", "text": "Change a failing command before running it again.", '
                                '"why": "stops repeats"}')
    entry = I.improve(_report(), proposer=prop, builder=None, bench=object(), say=lambda t: None)
    assert entry["result"] == "kept" and entry["new_version"] == 1
    assert H.load().rules == ["Change a failing command before running it again."]
    assert calls[0].rules == [] and calls[1].rules == H.load().rules
    logged = I.attempts()
    assert len(logged) == 1 and logged[0]["base"]["passed"] == 1 and logged[0]["candidate"]["passed"] == 3
    page = D.render([], A.Report(), [], H.load(), logged)
    assert "Change a failing command" in page and "1/5 → 3/5" in page and "kept" in page


def test_improve_drops_a_change_that_does_not_help(tmp_path, monkeypatch):
    monkeypatch.setenv("MITRA_HOME", str(tmp_path))
    monkeypatch.setenv("MITRA_HARNESS", str(tmp_path / "harness.toml"))
    monkeypatch.setattr(I, "evaluate", _fake_eval([I.Score(2, 5, 1000), I.Score(2, 5, 900)])[0])
    prop = Proposer('{"kind": "limit", "name": "max_failures", "value": 3, "why": "stop sooner"}')
    entry = I.improve(_report(), proposer=prop, builder=None, bench=object(), say=lambda t: None)
    assert entry["result"] == "dropped" and H.load().version == 0
    assert I.attempts()[0]["change"] == "limit max_failures = 3"


def test_dry_run_and_no_problems_change_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("MITRA_HOME", str(tmp_path))
    monkeypatch.setattr(I, "evaluate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no benchmark")))
    prop = Proposer('{"kind": "rule", "text": "Run tests after writing code.", "why": "x"}')
    assert I.improve(_report(), proposer=prop, builder=None, dry_run=True, say=lambda t: None)["result"] == "dry_run"
    assert I.improve(A.Report(), proposer=prop, builder=None, say=lambda t: None)["result"] == "skipped"
    assert I.attempts() == []


def test_evaluate_solves_and_grades_each_task_in_a_fresh_copy(tmp_path):
    graded = []

    class Bench:
        def prepare(self, task, dest):
            (dest / "tests").mkdir(parents=True)
            (dest / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")

        def grade(self, task, ws, python=None):
            graded.append(ws.exists() and bool(python))
            return SimpleNamespace(passed=task.id == "T01", infra_error=None)

    class Model:
        def bind_tools(self, specs):
            return self

        def invoke(self, messages):
            return AIMessage(content="", tool_calls=[{"name": "run_tests", "args": {}, "id": "1"}])

    tasks = [SimpleNamespace(id="T01", prompt="fix"), SimpleNamespace(id="T02", prompt="add")]
    seen = []
    score = I.evaluate(H.Harness(), Model(), tasks=tasks, bench=Bench(), record_root=tmp_path / "rec",
                       on_task=lambda tid, ok, res: seen.append((tid, ok)))
    assert score.passed == 1 and score.total == 2 and graded == [True, True]
    assert seen == [("T01", True), ("T02", False)]
    assert (tmp_path / "rec" / "T01.jsonl").exists()
    assert json.loads((tmp_path / "rec" / "T01.jsonl").read_text(encoding="utf-8").splitlines()[0])["kind"] == "start"


def test_the_real_bench_loads_and_has_a_tune_half():
    bench = I.load_bench()
    tune = [t for t in bench.load_tasks() if t.split == "tune"]
    assert len(tune) == 5 and all(t.prompt.strip() for t in tune)


def test_a_broken_grader_stops_the_ab_and_changes_nothing(tmp_path, monkeypatch):
    """E-035: grading ran in Mitra's own Python (no fastapi), so every task 'failed' and the A/B meant nothing."""
    monkeypatch.setenv("MITRA_HOME", str(tmp_path))
    monkeypatch.setenv("MITRA_HARNESS", str(tmp_path / "harness.toml"))

    class Bench:
        def prepare(self, task, dest):
            (dest / "tests").mkdir(parents=True)

        def grade(self, task, ws, python=None):
            return SimpleNamespace(passed=False, infra_error="pytest exit code 4", output_tail="No module named 'fastapi'")

    monkeypatch.setattr(I, "solve", lambda *a, **k: SimpleNamespace(tokens_in=1, seconds=1, status="passed", steps=1))
    prop = Proposer('{"kind": "rule", "text": "Run tests after writing code.", "why": "x"}')
    entry = I.improve(_report(), proposer=prop, builder=None, bench=Bench(),
                      tasks=[SimpleNamespace(id="T01", prompt="fix")], say=lambda t: None)
    assert entry["result"] == "bench_error" and "fastapi" in entry["reason"]
    assert H.load().version == 0 and I.attempts()[0]["result"] == "bench_error"


def test_failed_hidden_tests_are_named_in_the_score():
    tail = "x\nFAILED tests/test_hidden_t01.py::test_more_than_two_decimals_rejected - ValueError\n1 failed"
    assert I._failed_tests(tail) == "FAILED tests/test_hidden_t01.py::test_more_than_two_decimals_rejected - ValueError"


def test_a_failed_model_call_is_a_bench_error_not_a_model_fail(tmp_path, monkeypatch):
    class Bench:
        def prepare(self, task, dest):
            (dest / "tests").mkdir(parents=True)

        def grade(self, task, ws, python=None):
            raise AssertionError("must not grade after a model error")

    monkeypatch.setattr(I, "solve", lambda *a, **k: SimpleNamespace(
        status="error", summary="The model call failed twice. Is Ollama running?", tokens_in=0, seconds=0, steps=0))
    try:
        I.evaluate(H.Harness(), None, tasks=[SimpleNamespace(id="T01", prompt="x")], bench=Bench())
    except I.BenchError as exc:
        assert "Ollama" in str(exc)
    else:
        raise AssertionError("expected BenchError")


def test_the_proposer_is_unloaded_and_candidate_records_carry_the_next_version(tmp_path, monkeypatch):
    monkeypatch.setenv("MITRA_HOME", str(tmp_path))
    monkeypatch.setenv("MITRA_HARNESS", str(tmp_path / "harness.toml"))
    unloaded, versions = [], []
    monkeypatch.setattr(I, "unload", lambda llm: unloaded.append(llm))

    def ev(h, llm, **kw):
        versions.append(h.version)
        return I.Score(1, 5, 100)
    monkeypatch.setattr(I, "evaluate", ev)
    prop = Proposer('{"kind": "rule", "text": "Run tests after writing code.", "why": "x"}')
    I.improve(_report(), proposer=prop, builder=object(), bench=object(), say=lambda t: None)
    assert unloaded == [prop] and versions == [0, 1]


def test_machine_check_needs_ram_for_the_biggest_model_only():
    sizes = {"qwen3.5:4b": 3.4, "qwen3.5:latest": 6.6}
    assert I.machine_problems(["qwen3.5:latest", "qwen3.5:4b"], sizes=sizes, loaded=[], free_gb=10.0) == []
    low = I.machine_problems(["qwen3.5:latest", "qwen3.5:4b"], sizes=sizes, loaded=[], free_gb=7.8)
    assert len(low) == 1 and "9.6 GB needed" in low[0] and "--proposer qwen3.5:4b" in low[0]
    assert I.machine_problems(["qwen3.5:latest"], sizes=sizes, loaded=["qwen3.5:latest"], free_gb=1.0) == []
    assert "not installed" in I.machine_problems(["qwen3.5:9b"], sizes=sizes, loaded=[], free_gb=50)[0]


def test_a_tool_text_longer_than_the_harness_keeps_is_rejected():
    long = "z" * (H.MAX_TOOL_CHARS + 1)
    assert "too long" in I.parse_change(json.dumps({"kind": "tool", "name": "read_file", "text": long}),
                                        H.Harness(), TOOLS)[1]
