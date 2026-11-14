"""Conversation memory as threads (D-071, BUILD_ORDER step 3b).

Root cause R4 (2026-11-11): CodeMitra kept only the first line of each request, so "do you remember our discussion?"
got a list of titles and ideas were filed under the wrong project. A thread keeps what was said, decided and left
open in one discussion, written by the model from the chat records when a session ends (or at the next start if
CodeMitra was closed without `exit`).

Store: ~/.codemitra/threads/<slug>.md, one file per thread, global (an idea is not tied to a folder; `project` says
where it came up). Loaded per turn: a short index of recent threads, and the full text of the threads your message
is about (shared words with the title and the summary).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from app.core import harness as H

INDEX_MAX = 10
RELEVANT_MAX_CHARS = 1600
CONVO_MAX_CHARS = 7000
_STOP = set("""a an the and or but if then so to of in on at for with from by about into over is are was were be been
being it its this that these those i you we he she they me my our your their what which who how why when where can
could would should will shall do does did done have has had not no yes ok okay lets let's just like want need think
mitra codemitra please also more some any very really get got make made go going""".split())

SUMMARIZE_PROMPT = """You keep the memory of conversations between a user and their assistant, CodeMitra, as threads.
A thread is one discussion worth remembering later: an idea, a plan, a decision, a preference, an open question.
Not a thread: greetings, small talk, a finished small task, a mail that was drafted and sent.

Existing threads (update one when the conversation continues it, by using its slug):
{existing}

The new conversation (project folder: {project}):
{conversation}

Reply with only a JSON array, one object per thread that this conversation started or continued:
[{{"slug": "short-kebab-case", "title": "a few words", "project": "{project} or - if it is not about this folder",
"said": "2-4 short sentences: what was discussed", "decided": "what was decided, or -",
"open": "what is still open, or -"}}]
Write [] if nothing is worth remembering. Use the user's own words and facts; do not invent."""


def threads_dir() -> Path:
    return H.home() / "threads"


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9\-]{2,}", (text or "").lower()) if w not in _STOP}


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:48] or "thread"


def load(root: Path | None = None) -> list[dict]:
    """Every thread: {slug, title, project, updated, said, decided, open}, newest first."""
    root = root or threads_dir()
    out = []
    for f in root.glob("*.md"):
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = dict(re.findall(r"^(title|project|updated): (.*)$", text, re.M))
        body = dict(re.findall(r"^(Said|Decided|Open): (.*)$", text, re.M))
        out.append({"slug": f.stem, "title": meta.get("title", f.stem), "project": meta.get("project", "-"),
                    "updated": meta.get("updated", ""), "said": body.get("Said", ""),
                    "decided": body.get("Decided", "-"), "open": body.get("Open", "-")})
    return sorted(out, key=lambda t: t["updated"], reverse=True)


def save(thread: dict, root: Path | None = None) -> Path:
    root = root or threads_dir()
    root.mkdir(parents=True, exist_ok=True)
    slug = _slug(thread.get("slug") or thread.get("title", ""))
    f = root / f"{slug}.md"
    f.write_text(f"---\ntitle: {str(thread.get('title') or slug).strip()}\n"
                 f"project: {str(thread.get('project') or '-').strip()}\n"
                 f"updated: {time.strftime('%Y-%m-%d %H:%M')}\n---\n"
                 f"Said: {_one_line(thread.get('said'))}\nDecided: {_one_line(thread.get('decided')) or '-'}\n"
                 f"Open: {_one_line(thread.get('open')) or '-'}\n", encoding="utf-8")
    return f


def _one_line(text) -> str:
    return " ".join(str(text or "").split())[:900]


def index_text(root: Path | None = None, limit: int = INDEX_MAX) -> str:
    """'## Our earlier conversations' with one line per recent thread; '' when there are none."""
    ts = load(root)[:limit]
    if not ts:
        return ""
    lines = [f"- {t['title']} ({t['project']}, {t['updated'][:10]}): {t['said'][:110]}" for t in ts]
    return ("## Our earlier conversations (threads; the full one comes with a message about it)\n"
            + "\n".join(lines))


def relevant_text(message: str, root: Path | None = None, max_chars: int = RELEVANT_MAX_CHARS) -> str:
    """The threads this message is about (shared words with title and summary, at least 2 or a title word)."""
    words = _words(message)
    if not words:
        return ""
    scored = []
    for t in load(root):
        title_w = _words(t["title"] + " " + t["slug"].replace("-", " "))
        hits = len(words & (title_w | _words(t["said"] + " " + t["decided"] + " " + t["open"])))
        if hits >= 2 or words & title_w:
            scored.append((hits + 2 * len(words & title_w), t))
    out, used = [], 0
    for _, t in sorted(scored, key=lambda x: -x[0]):
        block = (f"## Thread: {t['title']} ({t['project']}, {t['updated'][:10]})\nSaid: {t['said']}\n"
                 f"Decided: {t['decided']}\nOpen: {t['open']}")
        if used + len(block) > max_chars:
            break
        out.append(block)
        used += len(block)
    if not out:
        return ""
    # E-101 (B10): with the folder's files in the prompt, a 9B mixed the folder's project into a continued thread
    return ("[Earlier conversation(s) this message is about. If the user continues one, talk about that topic only; "
            "it is not about the files in this folder unless its project says so.]\n\n" + "\n\n".join(out))


# ── writing threads from the chat records ───────────────────────────────────────────────────────────────────

def _state_file(root: Path) -> Path:
    return root / ".state.json"


def pending_turns(record: Path, root: Path | None = None) -> list[dict]:
    """Turns in this record not summarized yet: {t, user, answer} (commands and empty answers left out)."""
    root = root or threads_dir()
    try:
        done = json.loads(_state_file(root).read_text(encoding="utf-8")).get(str(record), 0)
    except (OSError, ValueError):
        done = 0
    try:
        rows = [json.loads(x) for x in Path(record).read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        return []
    out, cur = [], None
    for r in rows:
        if r.get("kind") == "turn_start":
            cur = r
        elif r.get("kind") == "turn_end" and cur is not None:
            user, answer = str(cur.get("user") or ""), str(r.get("text") or "")
            if r.get("t", 0) > done and answer.strip() and not user.strip().startswith(("/", "!")):
                out.append({"t": r.get("t", 0), "user": user, "answer": answer})
            cur = None
    return out


def _mark_done(record: Path, t: float, root: Path) -> None:
    f = _state_file(root)
    try:
        state = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    state[str(record)] = max(float(state.get(str(record), 0)), t)
    root.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(state, indent=1), encoding="utf-8")


def parse_threads(text: str) -> list[dict]:
    """The model's JSON array (first [...] in the reply); [] if it is not there or not valid."""
    m = re.search(r"\[.*\]", text or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return []
    return [d for d in data if isinstance(d, dict) and (d.get("title") or d.get("slug")) and d.get("said")]


def summarize(llm, record: Path, project: str, root: Path | None = None) -> list[str]:
    """Turn the record's new turns into threads (one model call). Returns the titles written."""
    root = root or threads_dir()
    turns = pending_turns(record, root)
    if not turns:
        return []
    convo = "\n".join(f"User: {t['user'][:800]}\nCodeMitra: {t['answer'][:900]}" for t in turns)[-CONVO_MAX_CHARS:]
    near = [t for t in load(root) if _words(t["title"] + " " + t["said"]) & _words(convo)][:6]
    existing = "\n".join(f"- {t['slug']}: {t['title']} ({t['project']}): said: {t['said'][:200]} | decided: "
                         f"{t['decided'][:120]} | open: {t['open'][:120]}" for t in near) or "(none)"
    from langchain_core.messages import HumanMessage
    reply = llm.invoke([HumanMessage(content=SUMMARIZE_PROMPT.format(existing=existing, project=project,
                                                                     conversation=convo))])
    written = []
    for t in parse_threads(str(getattr(reply, "content", "") or "")):
        save(t, root)
        written.append(str(t.get("title") or t.get("slug")))
    _mark_done(record, max(x["t"] for x in turns), root)
    return written
