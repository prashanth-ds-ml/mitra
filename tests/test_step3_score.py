"""D-068 step 3: the measuring set and `mitra score`. The checks are automatic; every reference passes its checks,
every start state fails; a run appends one row to results/scores.jsonl and keeps each case's record for the coach."""
import json
import tomllib
from pathlib import Path

from langchain_core.messages import AIMessage
from typer.testing import CliRunner

from app import main
from app.core import harness as H
from app.core import score as S
from app.core import store
from tests.test_chat_core import Model, tc


def _cases(name):
    return {c["id"]: c for c in tomllib.loads((S.SET / name).read_text(encoding="utf-8"))["case"]}


def _runner(llm, tmp_path):
    return S.Runner(llm=llm, harness=H.Harness(), num_ctx=8192, records=store.root() / "score-runs" / "t")


# ── the set itself ───────────────────────────────────────────────────────────

def test_the_set_is_sound_every_reference_passes_every_start_fails():
    assert S.validate() == []


def test_sorting_scores_every_case_without_a_model():
    cases = S.run_sorting()
    assert len(cases) >= 40 and all(c.passed for c in cases), [c.why for c in cases if not c.passed]


# ── the checks ───────────────────────────────────────────────────────────────

def test_writing_checks_facts_signature_length_and_wrong_sign_offs():
    w1 = _cases("writing.toml")["W1_team_mail"]
    ref = w1["reference"]
    assert S.check_writing(w1, ref) == ""
    assert S.check_writing(w1, ref.replace("Regards,\nPrashanth", "Thanks,\nPrashanth")).startswith("signature")
    assert S.check_writing(w1, ref.replace("Regards,\nPrashanth", "Thanks,\nMitra")).startswith("should not")
    assert S.check_writing(w1, ref.replace("`mitra kaggle start`", "start it")) == "missing: kaggle start"
    assert S.check_writing(w1, ref.replace("Hi team,", "Hi team, " + "word " * 200)).startswith("too long")
    assert S.check_writing(w1, "") == "empty answer"


def test_explain_checks_files_facts_wrong_claims_options_and_edits():
    c = _cases("explain.toml")
    root = S.SET / "projects" / "snake"
    x4, i1, r1 = c["X4_wall"], c["I1_harder"], c["R1_review"]
    assert S.check_explain(x4, x4["reference"], root) == ""
    assert S.check_explain(x4, x4["reference"], root, changed=["snake/game.py"]).startswith("changed files")
    assert S.check_explain(x4, "The snake wraps around to the other side (snake/game.py:36). It is over.",
                           root).startswith("wrong claim")
    assert S.check_explain(x4, "It is game over (api.py:2).", root).startswith("did not cite")
    two = "1. Faster (snake/game.py:30)\n2. Obstacles\nPick 1."
    assert S.check_explain(i1, two, root) == "2 options (want 3-5)"
    eight = "\n".join(f"{n}. idea {n} (snake/game.py:{n})" for n in range(1, 9))
    assert S.check_explain(i1, eight, root) == "8 options (want 3-5)"
    wrong = r1["reference"] + "\n3. Food can land somewhere unreachable."
    assert S.check_explain(r1, wrong, root).startswith("wrong claim")


def test_options_are_counted_once_in_any_numbering_style():
    text = "### 1. Speed\ntext 1. more\n**2.** Walls\n3) Food\n   4. Score\n2. again"
    assert S.count_options(text) == 4


# ── runs with a scripted model (the real chat paths) ────────────────────────

def test_a_writing_case_runs_the_reply_path(tmp_path):
    ref = _cases("writing.toml")["W1_team_mail"]["reference"]
    model = Model(AIMessage(content=ref))
    out = S.run_writing(_runner(model, tmp_path), only={"W1_team_mail"})
    assert [(c.id, c.passed, c.steps) for c in out] == [("W1_team_mail", True, 1)]
    assert model.tool_names is None                                     # one call, no tools
    rec = store.root() / "score-runs" / "t" / "W1_team_mail.jsonl"
    rows = [json.loads(x) for x in rec.read_text(encoding="utf-8").splitlines()]
    assert any(r["kind"] == "turn_start" and r["path"] == "reply" for r in rows)


def test_a_hung_model_fails_its_case_and_the_run_goes_on(tmp_path, monkeypatch):
    """Live 2026-11-11: a model stream hung for 12 minutes and the whole score run with it."""
    import threading

    gate = threading.Event()

    class Hangs(Model):
        def stream(self, messages):
            gate.wait(5)
            yield AIMessage(content="late")

    monkeypatch.setitem(S.CASE_TIMEOUT_S, "writing", 0.3)
    before = set(threading.enumerate())
    out = S.run_writing(_runner(Hangs(), tmp_path), only={"W1_team_mail", "W2_leave_mail"})
    gate.set()
    for t in set(threading.enumerate()) - before:  # the hung cases finish here, inside this test's MITRA_HOME
        t.join(5)                                    # (a late write after the test leaked into the real store)
    assert [(c.id, c.passed) for c in out] == [("W1_team_mail", False), ("W2_leave_mail", False)]
    assert all(c.why.startswith("TimeoutError: timed out after") for c in out)


def test_a_timed_out_turn_stops_before_its_next_tool(tmp_path, monkeypatch):
    """Review 2026-11-11: an abandoned case kept running tools in a deleted workspace while the next case ran."""
    import threading

    gate, ran = threading.Event(), []

    class SlowThenTool(Model):
        def stream(self, messages):
            self.calls += 1
            gate.wait(5)
            yield AIMessage(content="", tool_calls=[tc("write_file", self.calls, path="x.py", content="x = 1\n")])

    monkeypatch.setitem(S.CASE_TIMEOUT_S, "small", 0.3)
    task = S.load_tasks(only={"D1"})[0]
    r = _runner(SlowThenTool(), tmp_path)
    real_session = r.session

    def session(ws, case_id):
        s = real_session(ws, case_id)
        orig = s._run
        s._run = lambda name, args, *a: ran.append(name) or orig(name, args, *a)
        sessions.append(s)
        return s

    sessions = []
    monkeypatch.setattr(r, "session", session)
    before = set(threading.enumerate())
    out = S.run_coding(r, [task])
    gate.set()
    for t in set(threading.enumerate()) - before:
        t.join(5)
    assert not out[0].passed and out[0].why.startswith("TimeoutError")
    assert sessions[0].cancelled and ran == []                  # the late tool call was not run
    assert r.llm.calls == 1                                    # and no wrap-up call after it


def test_an_explain_case_runs_the_explainer_and_fails_an_edit(tmp_path):
    good = Model(AIMessage(content="", tool_calls=[tc("read_file", 1, path="snake/game.py")]),
                 AIMessage(content=_cases("explain.toml")["X4_wall"]["reference"]))
    out = S.run_explain(_runner(good, tmp_path), only={"X4_wall"})
    assert [(c.id, c.passed, c.steps) for c in out] == [("X4_wall", True, 2)]
    assert set(good.tool_names) == {"list_files", "read_file", "search"}


def test_a_coding_task_is_graded_by_hidden_tests(tmp_path):
    task = S.load_tasks(only={"D1"})[0]
    solution = (task.dir / "solution" / "clean.py").read_text(encoding="utf-8")
    start = (task.dir / "start" / "clean.py").read_text(encoding="utf-8")
    fixer = Model(AIMessage(content="", tool_calls=[tc("read_file", 1, path="clean.py")]),
                  AIMessage(content="", tool_calls=[tc("write_file", 2, path="clean.py", content=solution)]),
                  AIMessage(content="Done."))
    lazy = Model(AIMessage(content="", tool_calls=[tc("read_file", 1, path="clean.py")]),
                 AIMessage(content="", tool_calls=[tc("edit_file", 2, path="clean.py", old="out = []",
                                                      new="out = []  # todo")]),
                 AIMessage(content="Done."))
    good = S.run_coding(_runner(fixer, tmp_path), [task])[0]
    bad = S.run_coding(_runner(lazy, tmp_path), [task])[0]
    assert good.passed and good.why == "" and good.steps == 3
    assert not bad.passed and bad.why
    assert "out = []" in start                                            # the edit above really applied


def test_a_run_appends_one_row_with_versions_and_cases(tmp_path):
    results = tmp_path / "scores.jsonl"
    ref = _cases("writing.toml")["W2_leave_mail"]["reference"]
    row = S.run(("sorting", "writing"), runner=_runner(Model(*[AIMessage(content=ref)] * 3), tmp_path),
                model="m", cwd=tmp_path, results=results)
    saved = json.loads(results.read_text(encoding="utf-8"))
    assert saved == row and row["mitra_version"] == S.mitra_version() and row["harness_version"] == 0
    assert row["notes_version"] and row["model"] == "m" and row["backend"] == "laptop"
    assert row["score"]["sorting"][0] == row["score"]["sorting"][1] >= 40
    assert row["score"]["writing"] == [1, 3]                               # only the leave mail fits that answer
    assert S.summary(row["score"]).startswith("sorting ") and " · writing 1/3" in S.summary(row["score"])


def test_mitra_score_command_sorting_and_history(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "RESULTS", tmp_path / "scores.jsonl")
    cli = CliRunner()
    first = cli.invoke(main.cli, ["score", "--only", "sorting"])
    assert first.exit_code == 0 and "score: sorting" in first.output
    hist = cli.invoke(main.cli, ["score", "--history"])
    assert hist.exit_code == 0 and "sorting" in hist.output
    assert len((tmp_path / "scores.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    monkeypatch.setattr(S, "validate", lambda: ["task X: the start state already passes"])
    check = cli.invoke(main.cli, ["score", "--validate"])
    assert check.exit_code == 1 and "start state already passes" in check.output


def test_the_score_runs_on_the_laptop_while_kaggle_is_active_unless_remote(tmp_path, monkeypatch):
    """E-082 (live 2026-11-11): config.load points at an active Kaggle remote, so the first "laptop" scores ran on
    the user's Kaggle session at 256K."""
    from app import config
    from app import remote as remote_mod

    remote_cfg = {"ollama_local_base_url": "https://tunnel.example/tok", "num_ctx": 262144, "remote": "kaggle",
                  "_local": {"ollama_local_base_url": None, "num_ctx": None}}
    monkeypatch.setattr(config, "load", lambda *a, **k: dict(remote_cfg))
    monkeypatch.setattr(config, "load_context_choice", lambda m: 131072)
    monkeypatch.setattr(config, "get_model_facts", lambda m: {"context": 262144})
    monkeypatch.setattr(remote_mod, "active", lambda: {"url": "https://tunnel.example/tok", "num_ctx": 262144})
    monkeypatch.setattr(S, "RESULTS", tmp_path / "scores.jsonl")
    made = []
    monkeypatch.setattr(main, "get_local_llm", lambda m, **k: made.append(k) or Model())
    monkeypatch.setattr(S, "run", lambda cats, runner=None, **k: {"score": {}, "seconds": 1, "records": "",
                                                                  "backend": runner.backend})
    cli = CliRunner()
    assert cli.invoke(main.cli, ["score", "--only", "writing", "--model", "m"]).exit_code == 0
    assert cli.invoke(main.cli, ["score", "--only", "writing", "--model", "m", "--remote"]).exit_code == 0
    assert made[0]["base_url"] == "http://127.0.0.1:11434" and made[0]["num_ctx"] == 131072
    assert made[1]["base_url"] == "https://tunnel.example/tok" and made[1]["num_ctx"] == 262144


def test_the_snake_fixture_is_the_level_reference_without_its_hidden_hints():
    first = (S.SET / "projects" / "snake" / "snake" / "game.py").read_text(encoding="utf-8").splitlines()[0]
    assert "Reference" not in first and "never shown" not in first
    assert not list(Path(S.SET / "projects").rglob("test_*.py"))
