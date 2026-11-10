"""D-068 step 1: everyday chat. Small talk, writing (mails, summaries, rewrites, translations) and general questions
take one call with no tools and thinking off; your notes (me.md, project notes) go with every turn; /copy."""
import json
import pathlib

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app import llm as llm_mod
from app import main
from app.core import chat as C
from app.core import harness as H
from app.core import roles
from app.core import signals as SIG
from app.core.intent import classify
from tests.test_backend_chat import Inputs, harness  # noqa: F401 - the driven chat fixture
from tests.test_chat_core import Model, fake_hooks


# ── sorting ──────────────────────────────────────────────────────────────────

def test_small_talk_writing_and_general_are_sorted_without_a_model():
    cases = {
        "hi": "chat", "hi mitra": "chat", "thanks a lot": "chat", "how are you": "chat", "good morning": "chat",
        "draft a mail to the team about the kaggle setup": "writing",
        "write an email to my manager asking for leave on friday": "writing",
        "write a reply to this message: can we meet at 5?": "writing",
        "summarise this:\nThe meeting covered the budget and the hiring plan.": "writing",
        "translate this to hindi: thank you for coming": "writing",
        "what is the difference between LoRA and QLoRA?": "general",
        "plan my day: gym, kaggle run, review PRs": "general",
        "how do I run a docker container?": "general",
        # still the project's: questions about it, code changes
        "explain the game logic": "question", "how does main.py start?": "question",
        "summarize the game module": "question", "write a function to parse the log": "small",
        "fix the failing test in test_game.py": "small", "add a reply endpoint to the api": "big",
        "where did we stop": "resume",
    }
    got = {t: classify(t) for t in cases}
    assert got == cases


def test_follow_ups_depend_on_the_last_request():
    assert classify("make it shorter", previous="writing") == "writing"
    assert classify("more formal please", previous="writing") == "writing"
    assert classify("make it shorter") == "small"                      # no mail before: a code change
    assert classify("ok", previous="small") == "small"                 # answers Mitra's question: keep working
    assert classify("yes go ahead", previous="question") == "small"
    assert classify("ok") == "chat" and classify("thanks", previous="small") == "chat"


def test_a_question_naming_a_project_file_is_about_the_project():
    assert classify("what does paddle do?") == "general"
    assert classify("what does paddle do?", project_words={"paddle", "ball"}) == "question"


# ── notes ────────────────────────────────────────────────────────────────────

def test_me_md_is_created_once_from_the_template(tmp_path):
    f = SIG.ensure_me()
    assert f == H.home() / "me.md" and "Mail signature:" in f.read_text(encoding="utf-8")
    f.write_text("Name: Prashanth", encoding="utf-8")
    assert SIG.ensure_me() is None and f.read_text(encoding="utf-8") == "Name: Prashanth"


def test_notes_text_drops_empty_template_fields_and_keeps_yours(tmp_path):
    SIG.ensure_me()
    empty = SIG.notes_text(tmp_path)
    assert "Name:" not in empty and "Stack:" not in empty and "<your name>" not in empty
    assert "Tone: concise" in empty
    (H.home() / "me.md").write_text("# About me\nName: Prashanth\nStack:\nMail signature:\n    Regards,\n"
                                    "    Prashanth\n", encoding="utf-8")
    (tmp_path / ".mitra").mkdir()
    (tmp_path / ".mitra" / "notes.md").write_text("Use uv, never pip.", encoding="utf-8")
    text = SIG.notes_text(tmp_path)
    assert "Name: Prashanth" in text and "Mail signature:\n    Regards,\n    Prashanth" in text
    assert "Stack:" not in text and text.index("me.md") < text.index("Use uv, never pip.")
    (tmp_path / ".mitra" / "notes.md").write_text("x" * 5000, encoding="utf-8")
    assert len(SIG.notes_text(tmp_path)) <= SIG.NOTES_MAX_CHARS


# ── the reply path ───────────────────────────────────────────────────────────

def test_reply_is_one_call_with_no_tools_and_the_history_stays_clean(tmp_path):
    session_llm, reply_llm = Model(), Model(AIMessage(content="Subject: Kaggle\n\nHi team, ...\n\nRegards,\nP"))
    s = C.ChatSession(workspace=tmp_path, llm=session_llm, hooks=fake_hooks()[0])
    messages = [SystemMessage(content="sys"), HumanMessage(content="draft a mail to the team about kaggle")]
    res = s.reply(messages, "writing", reply_llm, notes="## About the user (me.md)\nName: P")
    assert res.text.startswith("Subject: Kaggle") and res.steps == 1
    assert reply_llm.calls == 1 and reply_llm.tool_names is None and session_llm.calls == 0  # never bound tools
    assert [type(m).__name__ for m in messages] == ["SystemMessage", "HumanMessage", "AIMessage"]
    assert s.llm is session_llm and s.allowed_tools is None and s.path == "loop"             # restored
    start = [json.loads(x) for x in s.rec.path.read_text(encoding="utf-8").splitlines()
             if '"turn_start"' in x][0]
    assert start["path"] == "reply" and start["request_kind"] == "writing" and start["thinking"] is False


def test_thinking_is_off_by_default_except_planner_and_debugger():
    on = {r for r, v in roles.THINKING.items() if v == "on"}
    assert on == {"planner", "debugger"} and roles.THINKING["chat"] == "off"


# ── end to end: the real chat loop ───────────────────────────────────────────

def test_everyday_chat_end_to_end(harness, monkeypatch, capsys):  # noqa: F811
    state, ws = harness
    H.home().mkdir(parents=True, exist_ok=True)
    (H.home() / "me.md").write_text("Name: Prashanth\nMail signature:\n    Regards,\n    Prashanth\n",
                                    encoding="utf-8")
    made, prompts = [], []
    orig = main.get_local_llm

    def tracking(*a, **k):
        m = orig(*a, **k)
        m.reasoning = k.get("reasoning")
        plain = m.stream

        def stream(messages):
            prompts.append((m, list(messages)))
            return plain(messages)

        m.stream = stream
        made.append(m)
        return m

    monkeypatch.setattr(main, "get_local_llm", tracking)
    monkeypatch.setattr(llm_mod, "model_supports_thinking", lambda model: True)
    copied = []
    from app.ui import clipboard
    monkeypatch.setattr(clipboard, "copy", lambda text: copied.append(text) or True)
    Inputs.script = ["hi", "draft a mail to the team about the kaggle setup", "/copy", "make it shorter",
                     "fix the failing test in test_x.py", "exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())
    rows = [json.loads(x) for f in (ws / ".mitra" / "runs").glob("chat-*.jsonl")
            for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    starts = [r for r in rows if r["kind"] == "turn_start"]
    assert [(r["path"], r["request_kind"]) for r in starts] == [
        ("reply", "chat"), ("reply", "writing"), ("reply", "writing"), ("loop", "small")]
    assert all(r["thinking"] is False for r in starts)
    # each reply was one call without tools, with thinking off, and carried your notes and signature
    reply_calls = [(m, msgs) for m, msgs in prompts if m.tool_names is None]
    assert len(reply_calls) == 3 and all(m.reasoning is False for m, _ in reply_calls)
    mail_prompt = " ".join(str(x.content) for x in reply_calls[1][1])
    assert "Regards," in mail_prompt and "signature" in mail_prompt and "Do not call tools" in mail_prompt
    # the code request still went to the loop with tools
    assert any(m.tool_names for m, _ in prompts)
    # /copy copied the mail and was recorded
    assert copied == ["answer 0"] and "copied the last answer" in out
    assert [r["signal"] for r in rows if r["kind"] == "signal"] == ["copy"]


def test_clipboard_sends_utf16_without_a_byte_order_mark(monkeypatch):
    """Live 2026-11-10: "utf-16" put an invisible U+FEFF at the start of the pasted mail."""
    import sys
    import subprocess
    from app.ui import clipboard
    sent = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "run", lambda cmd, input, check, timeout: sent.append((cmd, input)))
    assert clipboard.copy("Regards, ✓")
    assert sent == [(["clip"], "Regards, ✓".encode("utf-16-le"))] and not sent[0][1].startswith(b"\xff\xfe")
