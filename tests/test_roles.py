"""Role routing and swapping (D-049..D-052): model, context, tools, MCP servers and thinking per role."""
import json
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app import config
from app.core import chat as C
from app.core import roles as R


def test_defaults_follow_d051_and_fall_back_to_the_chat_model(monkeypatch):
    monkeypatch.setattr(config, "load_last_model", lambda: "qwen3.5:latest")
    have = {"qwen3.5:latest", "mimo-v2.6:9b", "deepseek-r1:8b"}
    assert R.resolve("planner", {}, have) == ("deepseek-r1:8b", "default")
    assert R.resolve("builder", {}, have) == ("qwen3.5:latest", "default")
    assert R.resolve("chat", {}, have) == ("qwen3.5:latest", "chat model")
    model, source = R.resolve("planner", {}, {"qwen3.5:latest"})  # not downloaded yet: nothing breaks
    assert model == "qwen3.5:latest" and "not installed" in source


def test_your_choice_and_mitra_toml_win(monkeypatch):
    monkeypatch.setattr(config, "load_last_model", lambda: "qwen3.5:latest")
    have = {"qwen3.5:latest", "qwen3.5:4b", "mimo-v2.6:9b"}
    R.save_choice("builder", "qwen3.5:4b")
    assert R.resolve("builder", {}, have) == ("qwen3.5:4b", "your choice")
    assert R.resolve("builder", {"roles": {"builder": "mimo-v2.6:9b"}}, have) == ("mimo-v2.6:9b", "mitra.toml")
    R.save_choice("builder", "default")
    assert R.resolve("builder", {}, have)[1] == "default"
    assert json.loads(R._file().read_text(encoding="utf-8")) == {}


def test_every_role_runs_at_its_models_maximum_context(monkeypatch):
    facts = {"qwen3.5:4b": 262_144, "deepseek-r1:8b": 131_072}
    monkeypatch.setattr(config, "get_model_facts", lambda m: {"context": facts.get(m, 0), "parameters": 4_600_000_000})
    assert R.context_for("qwen3.5:4b") == 262_144        # was 128K by default: no cap for the first days (D-052)
    assert R.context_for("deepseek-r1:8b") == 131_072    # its own maximum is the ceiling
    config.save_context_choice("qwen3.5:4b", 65_536)
    assert R.context_for("qwen3.5:4b") == 65_536         # your /context choice still wins
    assert R.context_for("qwen3.5:4b", {"num_ctx": 32_768}) == 32_768  # and mitra.toml over both


def test_routes_carry_tools_mcp_thinking_and_read_only(monkeypatch):
    monkeypatch.setattr(config, "get_model_facts", lambda m: {"context": 262_144})
    b = R.route("builder", {}, {"mimo-v2.6:9b"})
    assert b["read_only"] == ("tests",) and "run_command" in b["tools"] and b["mcp"] == ("context7", "serena", "shadcn")
    p = R.route("planner", {}, {"deepseek-r1:8b"})
    assert p["thinking"] == "on" and "write_file" not in p["tools"] and "serena" in p["mcp"]
    assert R.route("chat", {}, set())["tools"] is None and "all tools" in R.describe(R.route("chat", {}, set()))


def test_allowed_trial_models_pass_the_compatibility_check():
    facts = {"capabilities": ("completion", "tools", "thinking"), "family": "qwen3", "parameters": 8_200_000_000,
             "context": 131_072}
    assert config.compatibility_problem(facts, "deepseek-r1:8b") is None
    assert config.compatibility_problem(dict(facts, family="qwen35"), "mimo-v2.6:9b") is None
    assert config.compatibility_problem(facts, "llama3.1:8b")  # others still need D-032


class _Model:
    model = "x"

    def __init__(self):
        self.bound = []

    def bind_tools(self, specs):
        self.bound.append([s["name"] for s in specs])
        return self

    def stream(self, messages):
        return iter([AIMessage(content="ok")])


def _session(tmp_path, model):
    hooks = C.Hooks(stream=lambda chunks, step=1: (lambda m: SimpleNamespace(
                        message=m, text=m.content, stopped=False, printed=True, seconds=0.1, thinking=""))(
                        next(iter(chunks))),
                    show=lambda *a: None, confirm=lambda *a: True, run_shell=lambda c: ("", True),
                    web_search=lambda q: "", fetch_url=lambda u: "", mcp_find=lambda q: "", mcp_call=lambda *a: "called")
    return C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks)


def test_switching_role_changes_tools_mcp_read_only_and_model_and_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "get_model_facts", lambda m: {"context": 262_144})
    m1, m2 = _Model(), _Model()
    s = _session(tmp_path, m1)
    s.apply_route(R.route("planner", {}, {"deepseek-r1:8b"}), llm=m2, num_ctx=131_072)
    s.turn([SystemMessage(content="s"), HumanMessage(content="plan it")])
    assert s.llm is m2 and s.num_ctx == 131_072 and set(m2.bound[0]) <= set(R.TOOLS["planner"])
    assert "write_file" not in m2.bound[0]
    out, ok = s._run("mcp_call", {"server": "semgrep", "tool": "scan"}, None)
    assert not ok and "not available to the planner role" in out
    out, ok = s._run("mcp_call", {"server": "context7", "tool": "docs", "arguments": {}}, None)
    assert ok and out == "called"
    s.apply_route(R.route("builder", {}, {"mimo-v2.6:9b"}))
    assert s.ws.read_only == ("tests",)
    (tmp_path / "tests").mkdir()
    import pytest
    from app.core import tools as T
    with pytest.raises(T.ToolError):
        s.ws.check_writable(tmp_path / "tests" / "test_x.py")
    rows = [json.loads(x) for x in next((tmp_path / ".mitra" / "runs").glob("chat-*.jsonl")).read_text(
        encoding="utf-8").splitlines()]
    routes = [r for r in rows if r["kind"] == "route"]
    assert [r["role"] for r in routes] == ["planner", "builder"] and routes[0]["mcp"][0] == "context7"
    assert next(r for r in rows if r["kind"] == "turn_start")["role"] == "planner"


def test_mcp_search_is_limited_to_the_roles_servers():
    import inspect

    from app import mcp
    assert "servers" in inspect.signature(mcp.search_tools).parameters


def test_commands_are_wired_in_the_chat():
    import inspect

    from app import main
    src = inspect.getsource(main._chat)
    for needed in ('cmd.startswith("/role ")', '"/model roles"', 'cmd.startswith("/model role ")',
                   '"/model use "', "def _apply_role", "chat.apply_route(", "servers=chat.allowed_mcp"):
        assert needed in src, needed
