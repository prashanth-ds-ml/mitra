"""D-062 end to end: the real chat loop with scripted input, a fake model and a Kaggle that is up or down.

Start on Kaggle → plan mode moves read work to the laptop → back to auto mode moves write work to Kaggle →
Kaggle dies → laptop + report + the message goes back to the input box.
"""
import pathlib

import pytest
from langchain_core.messages import AIMessage

from app import config, fit, main, remote
from app.core import roles
from tests.test_chat_core import Model

KAGGLE_URL = "https://k.trycloudflare.com/tok"


class Inputs:
    """Stand-in for the prompt_toolkit input box: scripted lines; records the text put back in the box."""

    script: list = []
    defaults: list = []

    def __init__(self, *a, **k):
        self.toolbar = k.get("toolbar")

    def prompt(self, default=""):
        Inputs.defaults.append(default)
        if self.toolbar:
            Inputs.toolbars.append("".join(t for _, t in self.toolbar()))
        step = Inputs.script.pop(0) if Inputs.script else "exit"
        if callable(step):
            return step()
        return step


@pytest.fixture
def harness(tmp_path, monkeypatch):
    ws = tmp_path / "proj"
    ws.mkdir()
    (ws / ".git").mkdir()
    monkeypatch.chdir(ws)
    state = {"up": True, "llms": []}

    def fake_llm(model, temperature=0.2, *, base_url=None, num_ctx=None, **kw):
        state["llms"].append((model, base_url, num_ctx))
        m = Model(*[AIMessage(content=f"answer {i}") for i in range(20)])
        m.base_url, m.model = base_url, model
        return m

    inventory = [config.LocalModelInfo(name="mimo-v2.6:9b", context=262144),
                 config.LocalModelInfo(name="qwen3.5:4b", context=262144)]
    monkeypatch.setattr(main, "get_local_llm", fake_llm)
    monkeypatch.setattr(main, "show_banner", lambda: None)
    monkeypatch.setattr(main, "_print_memory_fit", lambda *a, **k: None)
    monkeypatch.setattr(main, "_rebuild_dashboard", lambda quiet=False: None)
    monkeypatch.setattr(main, "probe_ollama", lambda *a, **k: (True, "ok"))
    monkeypatch.setattr(main.ui, "InputBox", Inputs)
    monkeypatch.setattr(main.ui.notify, "ready", lambda c: None)
    monkeypatch.setattr(config, "get_local_model_inventory", lambda **k: list(inventory))
    monkeypatch.setattr(config, "get_gpu_memory_info", lambda: None)
    monkeypatch.setattr(config, "get_gpu_vram_gib", lambda: 8.0)
    monkeypatch.setattr(config, "get_model_facts", lambda name: {"context": 262144, "parameters": 9e9,
                                                                 "capabilities": ("completion", "tools")})
    monkeypatch.setattr(roles, "installed", lambda: {"mimo-v2.6:9b", "qwen3.5:4b"})
    monkeypatch.setattr(fit, "check", lambda m, c, **k: fit.Fit("remote" if remote.active() and not k.get("local")
                                                                  else "ok", m, c, 1.0, 1.0, 10.0, 9.0))
    monkeypatch.setattr(remote, "probe", lambda url, timeout=20: ([{"name": "mimo-v2.6:9b"}], "")
                        if state["up"] else ([], "getaddrinfo failed"))
    monkeypatch.setattr(main.mcp_registry, "discover", lambda *a, **k: [], raising=False)
    from app import kaggle
    monkeypatch.setattr(kaggle, "quota", lambda api: {"used_h": 2.0, "total_h": 30.0, "left_h": 28.0,
                                                      "refresh": None})
    monkeypatch.setattr(kaggle, "client", lambda: object())
    from app import backend
    backend.save_prefs(onboarded=True, kaggle_offer="later")
    config.save_last_model("mimo-v2.6:9b")
    Inputs.defaults, Inputs.toolbars = [], []
    yield state, ws
    remote.clear()


def test_switching_between_kaggle_and_the_laptop(harness, capsys):
    state, ws = harness
    remote.set_remote(KAGGLE_URL, 262144, "kaggle")

    def kaggle_dies():
        state["up"] = False
        return "change the code"

    Inputs.script = ["/mode plan", "explain the code", "/mode auto", "write the feature", kaggle_dies, "exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())  # the terminal wraps long lines
    # read work went to the laptop, write work back to Kaggle
    assert "plan mode: read work on the laptop → laptop" in out
    assert "write work on the remote GPU → kaggle" in out
    bases = [b for _, b, _ in state["llms"]]
    assert KAGGLE_URL in bases and "http://localhost:11434" in bases
    # Kaggle died: laptop, report, the message back in the input box
    assert "the Kaggle GPU stopped answering" in out and "Kaggle ended ·" in out
    reports = list((ws / ".mitra" / "reports").glob("kaggle-ended-*.md"))
    assert len(reports) == 1 and "explain the code" in reports[0].read_text(encoding="utf-8")
    assert Inputs.defaults[-1] == "change the code"
    assert remote.active() is None  # a dead Kaggle address is forgotten
    assert any("☁ kaggle" in t for t in Inputs.toolbars) and any("💻 laptop" in t for t in Inputs.toolbars)


def test_kaggle_dead_at_start_reports_on_the_last_session(harness, capsys):
    state, ws = harness
    runs = ws / ".mitra" / "runs"
    runs.mkdir(parents=True)
    (runs / "chat-20261110.jsonl").write_text(
        '{"kind": "session"}\n{"kind": "turn_start", "turn": 1, "user": "build the paddle"}\n'
        '{"kind": "turn_end", "turn": 1, "outcome": "tests_passed", "changed": []}\n', encoding="utf-8")
    remote.set_remote(KAGGLE_URL, 262144, "kaggle")
    state["up"] = False
    Inputs.script = ["exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())
    assert "ended while Mitra was closed" in out and "build the paddle" in out
    assert list((ws / ".mitra" / "reports").glob("kaggle-ended-*.md"))


def test_write_work_without_kaggle_asks_once_per_session(harness, monkeypatch, tmp_path):
    state, ws = harness
    from app import backend, kaggle
    key = tmp_path / "kaggle.json"
    key.write_text('{"username": "u", "key": "k"}', encoding="utf-8")
    monkeypatch.setattr(kaggle, "key_path", lambda: key)
    backend.save_prefs(onboarded=True, kaggle_offer="yes")
    asked = []
    monkeypatch.setattr(main.ui.menu, "choose", lambda console, q, opts, default=None: asked.append(q) or "no")
    Inputs.script = ["write a test", "write another", "/mode plan", "explain it", "exit"]
    main._chat()
    assert len(asked) == 1 and "Kaggle GPU" in asked[0]


def test_first_start_offers_kaggle_and_remembers_no(harness, monkeypatch):
    from app import backend
    backend._prefs_file().unlink()
    from app import kaggle
    monkeypatch.setattr(kaggle, "key_path", lambda: pathlib.Path("no-such-key.json"))
    monkeypatch.setattr(kaggle, "token_path", lambda: pathlib.Path("no-such-token"))
    for var in ("KAGGLE_API_TOKEN", "KAGGLE_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(main.sys.stdin, "isatty", lambda: True, raising=False)
    asked = []
    monkeypatch.setattr(main.ui.menu, "choose", lambda console, q, opts, default=None: asked.append(q) or "no")
    Inputs.script = ["exit"]
    main._chat()
    assert len(asked) == 1 and "free Kaggle GPU" in asked[0]
    assert backend.prefs() == {"onboarded": True, "kaggle_offer": "no"}
    asked.clear()
    Inputs.script = ["exit"]
    main._chat()
    assert asked == []  # never asked again


def test_ram_short_quietly_takes_the_smaller_laptop_model(harness, monkeypatch, capsys):
    state, ws = harness
    remote.set_remote(KAGGLE_URL, 262144, "kaggle")
    monkeypatch.setattr(fit, "check", lambda m, c, **k: fit.Fit(
        "remote" if remote.active() and not k.get("local") else ("ok" if m == "qwen3.5:4b" else "no"),
        m, c, 1.0, 1.0, 3.0, -2.0))

    def kaggle_dies():
        state["up"] = False
        return "go on"

    Inputs.script = [kaggle_dies, "exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())
    assert "→ laptop · qwen3.5:4b" in out and "RAM is short" in out
    assert state["llms"][-1][0] == "qwen3.5:4b"


def test_a_long_chat_is_compacted_before_moving_to_the_smaller_laptop_context(harness, monkeypatch, capsys):
    state, ws = harness
    config.save_context_choice("mimo-v2.6:9b", 131072)  # the laptop runs mimo at 128K (D-058)
    remote.set_remote(KAGGLE_URL, 262144, "kaggle")
    big = AIMessage(content="long answer", usage_metadata={"input_tokens": 200_000, "output_tokens": 50,
                                                           "total_tokens": 200_050})

    def fake_llm(model, temperature=0.2, *, base_url=None, num_ctx=None, **kw):
        state["llms"].append((model, base_url, num_ctx))
        m = Model(*([big] * 5))
        m.base_url, m.model = base_url, model
        return m

    monkeypatch.setattr(main, "get_local_llm", fake_llm)
    compacted = []
    monkeypatch.setattr(main, "_compact", lambda llm, msgs, *a, **k: compacted.append(k.get("reason")) or msgs[:1])

    def plan_mode_with_kaggle_up():
        return "/mode plan"

    Inputs.script = ["write a big feature", plan_mode_with_kaggle_up, "explain it", "exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())
    assert compacted[:1] == ["backend"] and "too long for 128K" in out
