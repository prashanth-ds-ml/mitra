"""Tests for app/ui: Phosphor theme, tool lines, live streaming, status line (D-031)."""
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessageChunk
from rich.console import Console

from app import ui
from app.ui.stream import ThinkSplitter, split_blocks


def make_console(width: int = 100) -> Console:
    return ui.apply(Console(record=True, width=width, force_terminal=False, color_system=None))


def printed(console: Console) -> str:
    return console.export_text()


class FakeClock:
    def __init__(self, step: float = 1.0):
        self.t, self.step = 0.0, step

    def __call__(self):
        self.t += self.step
        return self.t


# ── tool lines ──────────────────────────────────────────────────────────────

def test_tool_line_has_marker_action_target_counts_and_detail():
    c = make_console()
    c.print(ui.tool_line("Edit", "snake/game.py", added=9, removed=2, detail="saved"))
    out = printed(c)
    assert "● Edit snake/game.py  +9 −2" in out
    assert "⎿  saved" in out


def test_step_line_summarises_reads_searches_and_errors():
    c = make_console()
    c.print(ui.step_line("read_file", {"path": "a.py"}, "1\n2\n3", True))
    c.print(ui.step_line("search_text", {"pattern": "score"}, "a.py:1\nb.py:4", True))
    c.print(ui.step_line("edit_file", {"path": "b.py"}, "✗ Permission denied: outside the workspace\nmore", False))
    out = printed(c)
    assert "● Read a.py" in out and "⎿  3 lines" in out
    assert '● Search "score"' in out and "2 matches" in out
    assert "● Edit b.py" in out and "Permission denied: outside the workspace" in out and "more" not in out


def test_shell_done_reports_each_outcome():
    ok = SimpleNamespace(exit_code=0, output_lines=["a", "b"], denied=False, timed_out=False)
    bad = SimpleNamespace(exit_code=2, output_lines=[], denied=False, timed_out=False)
    late = SimpleNamespace(exit_code=-1, output_lines=[], denied=False, timed_out=True)
    texts = [ui.shell_done(r).plain for r in (ok, bad, late)]
    assert "done · 2 lines of output" in texts[0]
    assert "failed · exit 2" in texts[1]
    assert "timed out" in texts[2]


def test_turn_footer_and_token_format():
    assert ui.format_tokens(950) == "950"
    assert ui.format_tokens(3200) == "3.2K"
    assert ui.turn_footer(23.4, 3200, 900).plain == "  23s · ↑ 3.2K ↓ 900 tokens"


# ── <think> splitting ───────────────────────────────────────────────────────

def test_think_splitter_handles_tags_cut_across_chunks():
    sp = ThinkSplitter()
    parts = []
    for piece in ["<thi", "nk>plan it</th", "ink>Hello", " world"]:
        parts += sp.feed(piece)
    parts += sp.flush()
    think = "".join(t for k, t in parts if k == "think")
    say = "".join(t for k, t in parts if k == "say")
    assert think == "plan it"
    assert say == "Hello world"


def test_split_blocks_keeps_code_fences_whole():
    text = "Intro line\n\n```python\nx = 1\n\ny = 2\n```\n\nStill writing"
    done, current = split_blocks(text)
    assert done == ["Intro line", "```python\nx = 1\n\ny = 2\n```"]
    assert current == "Still writing"


# ── streaming ───────────────────────────────────────────────────────────────

def chunks(*pieces, reasoning=()):
    for r in reasoning:
        yield AIMessageChunk(content="", additional_kwargs={"reasoning_content": r})
    for p in pieces:
        yield AIMessageChunk(content=p)


def test_stream_prints_answer_as_markdown_and_one_thinking_line():
    c = make_console()
    res = ui.stream_reply(c, chunks("<think>look at", " the code</think>", "Done. ", "Score added.\n\n- one\n- two"),
                          clock=FakeClock())
    out = printed(c)
    assert "✻ Thought for" in out and "(/think on to show)" in out
    assert "look at the code" not in out           # reasoning hidden by default
    assert "Done. Score added." in out and "• one" in out
    assert res.text.startswith("Done. Score added.") and res.thinking == "look at the code"
    assert res.printed and res.message is not None


def test_stream_shows_reasoning_when_asked_and_reads_reasoning_content():
    c = make_console()
    res = ui.stream_reply(c, chunks("Answer", reasoning=["step one ", "step two"]), show_reasoning=True,
                          clock=FakeClock())
    out = printed(c)
    assert "step one step two" in out
    assert "/think on" not in out
    assert res.thinking_tokens == 2 and res.text == "Answer"


def test_stream_with_only_a_tool_call_prints_no_answer():
    c = make_console()
    tool_chunk = AIMessageChunk(content="", tool_call_chunks=[
        {"name": "read_codebase", "args": '{"request": "x"}', "id": "1", "index": 0}])
    res = ui.stream_reply(c, iter([tool_chunk]), clock=FakeClock())
    assert not res.printed and res.text == ""
    assert res.message.tool_calls[0]["name"] == "read_codebase"
    assert "Thought for" not in printed(c)


# ── status line ─────────────────────────────────────────────────────────────

def test_status_line_shows_model_mode_context_tokens_folder_branch():
    parts = ui.status_line(model="qwen3.5:9b", mode="approve", total_tokens=4100, context_limit=41000,
                           cwd=r"C:\dev\snake_game", branch="main", background_tasks=1)
    text = "".join(t for _, t in parts)
    assert text == "  qwen3.5:9b · approve · ctx 10% · 4.1K tokens · snake_game (main) · 1 running"
    assert ("class:status.accent", "approve") in parts


def test_status_line_warns_near_the_limit():
    parts = ui.status_line(model="m", mode="auto", total_tokens=90, context_limit=100, cwd=".", branch="")
    assert ("class:status.warn", "ctx 90%") in parts
    assert any("/compact" in t for _, t in parts)


def test_git_branch_outside_a_repo_is_empty(tmp_path):
    assert ui.git_branch(str(tmp_path)) == ""


def test_theme_is_phosphor():
    assert ui.PHOSPHOR["accent"] == "#5cff7a"
    assert ui.PHOSPHOR["bg"] == "#050a06"
    style = ui.prompt_style()
    assert "prompt" in dict(style.style_rules)


# ── startup screen ──────────────────────────────────────────────────────────

def test_header_shows_model_context_placement_folder_and_mcp():
    c = make_console(width=100)
    c.print(ui.header.header(model="qwen3.5:4b", folder="snake_game", context=65536, placement="gpu",
                             mcp_servers=["git", "github"]))
    out = printed(c)
    assert "✻ Mitra" in out
    assert "qwen3.5:4b  (64K context, on GPU)" in out
    assert "snake_game" in out and "● git  ● github" in out


def test_model_table_numbers_models_with_size_and_placement():
    from types import SimpleNamespace as NS
    c = make_console()
    c.print(ui.header.model_table([NS(name="qwen3.5:4b", size_text="3.4 GB", placement="gpu"),
                                   NS(name="gemma4:e4b", size_text="9.6 GB", placement="split")]))
    lines = [ln.rstrip() for ln in printed(c).splitlines() if ln.strip()]
    assert lines[0].split() == ["1", "qwen3.5:4b", "3.4", "GB", "GPU"]
    assert lines[1].split() == ["2", "gemma4:e4b", "9.6", "GB", "GPU+CPU"]


def test_startup_title_replaces_the_big_banner(monkeypatch):
    import app.main as main
    c = make_console()
    monkeypatch.setattr(main, "console", c)
    main.show_banner()
    out = printed(c)
    assert "✻ Mitra" in out and "▓" not in out
