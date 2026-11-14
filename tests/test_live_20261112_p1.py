"""1d: the user's live session on the Phase 1 code (2026-11-12, 5 /bad): E-116 "tell me about you in detail" searched
the project's files; E-117 "about the model qwen3.5" searched the project's files; E-118 "deep dive on the model once
again" got "Would you like me to search?"; E-119 a WhatsApp draft got a Subject line and **bold**."""
from langchain_core.messages import AIMessage, HumanMessage

from app.core import chat as C
from tests.test_chat_core import fake_hooks, tc
from tests.test_phased import _msgs
from tests.test_trust_d077 import Spy


def test_questions_about_mitra_and_outside_tech_are_not_answered_from_the_files():
    for prompt in (C.PHASED_PROMPT, C.ONE_PROMPT):
        assert C.SELF_AND_TECH in prompt
    assert "answer yourself from \"About you\"" in C.SELF_AND_TECH
    assert "qwen3.5" in C.SELF_AND_TECH and "look_up, or answer from" in C.SELF_AND_TECH


def test_a_whatsapp_draft_has_no_subject_and_whatsapp_bold():
    assert "no Subject line and no Markdown" in C.SELF_AND_TECH and "*one star*" in C.SELF_AND_TECH


def _decide_note(tmp_path, said):
    m = Spy(AIMessage(content="ok"))
    C.ChatSession(workspace=tmp_path, llm=m, hooks=fake_hooks()[0]).phased(_msgs(said))
    return " ".join(x.content for x in m.seen[0] if isinstance(x, HumanMessage) and x.content.startswith("[CodeMitra"))


def test_a_deep_dive_or_search_request_is_told_to_search_now(tmp_path):
    for said in ("can you do a deep dive on the model once again", "search the web for qwen3.5",
                 "do a deep dive in web and tell me"):
        assert "do not ask whether to search" in _decide_note(tmp_path, said), said
    assert "do not ask whether to search" not in _decide_note(tmp_path, "hello mitra how are you doing")


def test_a_denied_wrong_claim_is_not_a_wrong_claim():
    """E-121 (quick score 2026-11-12 20:08, X4_wall): "The game doesn't wrap around or bounce, it simply stops" was
    failed as the wrong claim "wraps around"."""
    from app.core import score as S
    pat = r"(?i)wraps? around|bounces?|teleport"
    assert not S.claims(pat, "- The game doesn't wrap around or bounce, it simply stops when the snake hits a wall")
    assert not S.claims(pat, "It never teleports. The game ends.")
    assert S.claims(pat, "When it hits the wall, the snake wraps around to the other side.")
    assert S.claims(pat, "It does not stop. It bounces back.")                 # the denial is in another sentence
