"""Harness settings (self-improvement step 1): load, save with history, and their effect on the loop and chat."""
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core import chat as C
from app.core import harness as H
from app.core import loop as L
from app.core import tools as T


def test_missing_or_broken_file_means_defaults(tmp_path):
    assert H.load(tmp_path / "nope.toml").version == 0
    bad = tmp_path / "bad.toml"
    bad.write_text("rules = [unclosed", encoding="utf-8")
    h = H.load(bad)
    assert h.rules == [] and h.limit("chat_max_steps") == 40


def test_save_bumps_version_keeps_history_and_round_trips(tmp_path):
    active = tmp_path / "harness.toml"
    h = H.Harness(rules=["A command that failed twice the same way: read the error, then change the command."],
                  tools={"run_command": "Run one command (no pipes)."}, limits={"max_repeats": 3})
    hist = H.save(h, "learned from E-033", active)
    back = H.load(active)
    assert back.version == 1 and back.note == "learned from E-033"
    assert back.rules == h.rules and back.tools == h.tools and back.limit("max_repeats") == 3
    assert hist.exists() and hist.parent.name == "history"
    H.save(back, "second", active)
    assert H.load(active).version == 2 and len(list(hist.parent.iterdir())) == 2


def test_bad_values_are_clamped_and_unknown_limits_dropped(tmp_path):
    p = tmp_path / "h.toml"
    p.write_text('rules = ["  ok  ", ""]\n[limits]\nmax_repeats = -5\nchat_max_steps = 9999\nbogus = 3\n', encoding="utf-8")
    h = H.load(p)
    assert h.rules == ["ok"] and h.limit("max_repeats") == 1 and h.limit("chat_max_steps") == 200
    assert "bogus" not in h.limits


def test_rules_and_tool_overrides_reach_the_model_in_solve(tmp_path):
    seen = {}

    class Model:
        def bind_tools(self, specs):
            seen["specs"] = {s["name"]: s["description"] for s in specs}
            return self

        def invoke(self, messages):
            seen["system"] = messages[0].content
            return AIMessage(content="", tool_calls=[{"name": "run_tests", "args": {}, "id": "1"}])

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    h = H.Harness(rules=["Run the tests first."], tools={"run_tests": "Run the tests now."})
    res = L.solve("x", T.Workspace(tmp_path, test_command="python -m pytest -q tests"), Model(), harness=h)
    assert res.status == "passed"
    assert "Rules learned from earlier runs:\n- Run the tests first." in seen["system"]
    assert seen["specs"]["run_tests"] == "Run the tests now."


def test_chat_uses_the_harness_limits_and_tool_texts(tmp_path):
    seen = {}

    class Model:
        def bind_tools(self, specs):
            seen["desc"] = next(s["description"] for s in specs if s["name"] == "read_file")
            return self

        def stream(self, messages):
            yield AIMessage(content="", tool_calls=[{"name": "search", "args": {"pattern": f"p{len(messages)}"},
                                                     "id": str(len(messages))}])

    def stream(chunks, step=1):
        msg = None
        for c in chunks:
            msg = c
        return SimpleNamespace(message=msg, text=msg.content if msg else "", stopped=False, printed=True)

    hooks = C.Hooks(stream=stream, show=lambda *a: None, confirm=lambda *a: True, run_shell=lambda c: ("", True),
                    web_search=lambda q: "", fetch_url=lambda u: "", mcp_find=lambda q: "", mcp_call=lambda *a: "")
    h = H.Harness(tools={"read_file": "Read it."}, limits={"chat_max_steps": 3})
    res = C.ChatSession(workspace=tmp_path, llm=Model(), hooks=hooks, harness=h).turn(
        [SystemMessage(content="s"), HumanMessage(content="go")])
    assert seen["desc"] == "Read it." and res.stopped and "step limit (3" in res.stop_reason
