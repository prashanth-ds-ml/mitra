"""D-071 conversation memory as threads: what was said, decided and left open, written by the model from the chat
records at exit (or the next start), loaded per turn when your message is about it."""
import json

from langchain_core.messages import AIMessage

from app.core import threads as T

WEB = {"slug": "feedback-web-app", "title": "Web app that collects ratings to fine-tune a model", "project": "-",
       "said": "People chat in Roman Telugu and rate answers 1-5; ratings become fine-tuning data.",
       "decided": "FastAPI + SQLite.", "open": "Who rates first."}


def test_save_load_and_index(tmp_path):
    T.save(WEB, tmp_path)
    T.save({"title": "Brick breaker plan", "project": "mitra-try", "said": "Rewrite the stale plan."}, tmp_path)
    got = {t["slug"]: t for t in T.load(tmp_path)}
    assert got["feedback-web-app"]["decided"] == "FastAPI + SQLite." and got["brick-breaker-plan"]["open"] == "-"
    index = T.index_text(tmp_path)
    assert index.startswith("## Our earlier conversations") and "Web app that collects ratings" in index
    assert T.index_text(tmp_path / "none") == ""


def test_relevant_threads_follow_the_message(tmp_path):
    T.save(WEB, tmp_path)
    T.save({"title": "Brick breaker plan", "project": "mitra-try", "said": "Rewrite the stale plan."}, tmp_path)
    text = T.relevant_text("lets continue the web app idea from yesterday", tmp_path)
    assert "## Thread: Web app that collects ratings" in text and "Brick breaker" not in text
    assert T.relevant_text("hi", tmp_path) == "" and T.relevant_text("what about lunch", tmp_path) == ""


def _record(path, turns):
    rows = []
    for n, (user, answer) in enumerate(turns, 1):
        rows += [{"t": n * 10, "kind": "turn_start", "turn": n, "user": user},
                 {"t": n * 10 + 1, "kind": "turn_end", "turn": n, "text": answer}]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_pending_turns_skip_commands_and_empty_answers(tmp_path):
    rec = tmp_path / "chat.jsonl"
    _record(rec, [("hi", "Hi!"), ("/help", "x"), ("build it", ""), ("web app with ratings?", "Yes: rate 1-5.")])
    assert [t["user"] for t in T.pending_turns(rec, tmp_path / "th")] == ["hi", "web app with ratings?"]


def test_summarize_writes_threads_once_from_the_models_json(tmp_path):
    rec, root = tmp_path / "chat.jsonl", tmp_path / "th"
    _record(rec, [("lets build a web app where users rate answers to fine tune", "Good idea: store ratings.")])
    reply = 'Here you go:\n[{"slug": "feedback-web-app", "title": "Ratings web app", "project": "-", ' \
            '"said": "Users rate answers; ratings fine-tune the model.", "decided": "-", "open": "Who rates"}]'

    class LLM:
        calls = 0

        def invoke(self, messages):
            LLM.calls += 1
            assert "lets build a web app" in messages[0].content
            return AIMessage(content=reply)

    assert T.summarize(LLM(), rec, "mitra-try", root) == ["Ratings web app"]
    assert T.load(root)[0]["said"].startswith("Users rate answers")
    assert T.summarize(LLM(), rec, "mitra-try", root) == [] and LLM.calls == 1   # nothing new: no model call


def test_bad_model_output_writes_nothing(tmp_path):
    assert T.parse_threads("sure, here are the threads") == [] and T.parse_threads("[{not json}]") == []
    assert T.parse_threads('[{"title": "x"}]') == []                              # no summary: not a thread


def test_the_score_seeds_a_thread_and_one_codemitra_gets_it(tmp_path):
    from app.core import chat as C
    from app.core import score as S
    from app.core import store
    from tests.test_chat_core import Model

    seen = []

    class Watch(Model):
        def stream(self, messages):
            seen.append(" ".join(str(m.content) for m in messages))
            return super().stream(messages)

    ref = ("Sure. Where we left it: people chat in Roman Telugu, rate each answer, and the ratings become "
           "fine-tuning data. Want to start with the ratings table?")
    r = S.Runner(llm=Watch(AIMessage(content=ref)), harness=C.H.Harness(), num_ctx=8192,
                 records=store.root() / "score-runs" / "th", arch="one")
    out = S.run_behaviour(r, only={"B10_remembers"})
    assert [(c.id, c.passed) for c in out] == [("B10_remembers", True)]
    assert "## Thread: Web app that collects ratings" in seen[0] and "Our earlier conversations" in seen[0]


def test_a_matched_thread_is_marked_as_its_own_topic_not_the_folders_project(tmp_path):
    """E-101 (B10): continuing the web-app thread inside the snake folder, a 9B mixed in the snake game."""
    T.save(WEB, tmp_path)
    text = T.relevant_text("lets continue the web app idea from yesterday", tmp_path)
    assert text.startswith("[Earlier conversation(s) this message is about.") and "not about the files" in text
    assert T.relevant_text("hi", tmp_path) == ""                              # no header without a thread
