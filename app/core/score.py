"""`codemitra score`: the measuring set (D-068 step 3, docs/BUILD_ORDER.md). The judge of every later change.

Six kinds of checks, all automatic, all from files in score/:
- sorting   how a request is sorted (intent.classify), no model                         score/sorting.toml
- writing   mails and summaries on the one-call path: facts, signature, length          score/writing.toml
- explain   questions about a project (the explainer): right file, key facts, no edits  score/explain.toml
- ideas     brainstorms and reviews: 3-5 options or 2+ points, real files, no wrong claim, no edits
- small     one clear change; hidden tests decide                                         score/tasks.toml
- medium    a feature; hidden tests decide

Every run appends one row to results/scores.jsonl (CodeMitra version, harness version, notes version, model, machine,
each case) and keeps each case's full record in ~/.codemitra/data/score-runs/<stamp>/ for the coach.
The model paths are the chat's own: ChatSession.reply / .explain / .turn, with your harness, thinking off.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage

from app.core import harness as H
from app.core import signals as SIG
from app.core.intent import classify, project_words

ROOT = Path(__file__).resolve().parents[2]
SET = ROOT / "score"
RESULTS = ROOT / "results" / "scores.jsonl"
CATEGORIES = ("sorting", "behaviour", "writing", "explain", "ideas", "real", "small", "medium")
QUICK = ("sorting", "behaviour", "writing", "explain", "ideas", "real")
HELD_OUT = ("real",)  # D-078 step 6: your real failures, scored but never learned from (`codemitra improve`)
ARCHITECTURES = ("router", "one", "phased")  # D-071: routed paths (D-068), one loop, or decide-then-act      # no coding tasks: a few minutes
SHELL_TIMEOUT_S = 120
GRADE_TIMEOUT_S = 120
# a case that gets no result in time fails and the run goes on (live 2026-11-11: a model stream hung for 12 min
# with nothing loaded in Ollama; an unattended score must never hang)
CASE_TIMEOUT_S = {"behaviour": 600, "writing": 300, "explain": 600, "ideas": 600, "small": 1800, "medium": 2700}


def _timed(fn, seconds: float, session=None):
    box: dict = {}

    def go() -> None:
        try:
            box["v"] = fn()
        except BaseException as exc:  # noqa: BLE001 - handed to the caller
            box["e"] = exc

    t = threading.Thread(target=go, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        if session is not None:
            session.cancelled = True  # it stops at its next model call or tool
        raise TimeoutError(f"timed out after {seconds:.0f} s (no answer from the model)")
    if "e" in box:
        raise box["e"]
    return box["v"]


_IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", ".codemitra", ".mitra")


@dataclass
class Case:
    id: str
    category: str
    passed: bool
    why: str = ""            # the first failed check, in plain words ("" = passed)
    seconds: float = 0.0
    steps: int = 0


def _toml(name: str) -> dict:
    return tomllib.loads((SET / name).read_text(encoding="utf-8"))


# ── the checks (pure: text in, the first failed check out; "" = passed) ──────────────────────────────────────────

def _words(text: str) -> int:
    return len(text.split())


def check_writing(case: dict, text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "empty answer"
    for fact in case.get("must", []):
        if fact.lower() not in t.lower():
            return f"missing: {fact}"
    for pat in case.get("must_not", []):
        if re.search(pat, t, re.M):
            return f"should not match: {pat}"
    sig = case.get("signature")
    if sig and not re.search(r"\s*\n\s*".join(re.escape(x) for x in sig) + r"\s*$", t):
        return "signature not exactly: " + " / ".join(sig)
    if _words(t) > case.get("max_words", 10_000):
        return f"too long: {_words(t)} words (max {case['max_words']})"
    return ""


_OPTION = re.compile(r"^\s{0,3}(#+\s*)?(\*\*)?(\d+)[.)]\s", re.M)


def count_options(text: str) -> int:
    """Top-level numbered items (1. / 2) / ### 3. / **4.**), counting each number once."""
    return len({m.group(3) for m in _OPTION.finditer(text or "")})


_NEGATED = re.compile(r"\b(doesn'?t|does not|don'?t|do not|isn'?t|is not|won'?t|will not|never|no|not|neither|nor|"
                      r"instead of|rather than)\b", re.I)


def claims(pattern: str, text: str) -> bool:
    """E-121: the answer makes the claim `pattern`, not its denial: "The game doesn't wrap around or bounce" is right
    and must not count as claiming that it wraps around. A match counts unless its sentence negates it before it."""
    for m in re.finditer(pattern, text or ""):
        start = max(text.rfind(c, 0, m.start()) for c in ".!?\n") + 1
        if not _NEGATED.search(text[start:m.start()]):
            return True
    return False


def check_explain(case: dict, text: str, root: Path, *, changed: list[str] | None = None) -> str:
    from app.core.chat import cited_files

    t = (text or "").strip()
    if not t:
        return "empty answer"
    if changed:
        return "changed files: " + ", ".join(changed[:3])
    cited = cited_files(t, root)
    if case.get("cite") and not set(case["cite"]) & set(cited):
        return "did not cite " + " or ".join(case["cite"]) + (f" (cited {', '.join(cited)})" if cited else "")
    for pat in case.get("facts", []):
        if not re.search(pat, t, re.I):
            return f"missing fact: {pat}"
    for pat in case.get("must_not", []):
        if claims(pat, t):
            return f"wrong claim: {pat}"
    if case.get("options"):
        lo, hi = case["options"]
        n = count_options(t)
        if not lo <= n <= hi:
            return f"{n} options (want {lo}-{hi})"
    if case.get("points") and count_options(t) + len(re.findall(r"^\s*[-*]\s", t, re.M)) < case["points"]:
        return f"fewer than {case['points']} points"
    return ""


# ── sorting: no model ───────────────────────────────────────────────────────────────────────────────────────────

def run_sorting(on_case: Callable[[Case], None] = lambda c: None) -> list[Case]:
    data = _toml("sorting.toml")
    words = set(data.get("project_words", []))
    out = []
    for i, c in enumerate(data["cases"], 1):
        got = classify(c["text"], previous=c.get("previous", ""), project_words=words)
        case = Case(f"S{i:02d}", "sorting", got == c["want"],
                    "" if got == c["want"] else f"{c['text'][:50]!r}: {got}, want {c['want']}")
        on_case(case)
        out.append(case)
    return out


# ── the model runs ──────────────────────────────────────────────────────────────────────────────────────────────

def _stream(chunks, step: int = 1, cancelled: Callable[[], bool] = lambda: False):
    """Consume a model stream. A cancelled case closes the stream, so Ollama aborts the request instead of
    generating on while the next cases queue behind it (E-099: one ran 36 minutes)."""
    t0, first, msg, think = time.monotonic(), None, None, 0
    for c in chunks:
        if cancelled():
            close = getattr(chunks, "close", None)
            if callable(close):
                close()
            return SimpleNamespace(message=msg, text=(msg.content if msg else "") or "", stopped=True, printed=True,
                                   first_s=first, seconds=time.monotonic() - t0, thinking="x" * think)
        msg = c if msg is None else msg + c
        if (getattr(c, "additional_kwargs", {}) or {}).get("reasoning_content"):
            think += 1
        if first is None and (c.content or getattr(c, "tool_call_chunks", None)):
            first = time.monotonic() - t0
    return SimpleNamespace(message=msg, text=(msg.content if msg else "") or "", stopped=False, printed=True,
                           first_s=first, seconds=time.monotonic() - t0, thinking="x" * think)


def _run_shell(ws: Path) -> Callable[[str], tuple[str, bool]]:
    def run(cmd: str) -> tuple[str, bool]:
        try:
            p = subprocess.run(cmd, shell=True, cwd=ws, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=SHELL_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return f"timed out after {SHELL_TIMEOUT_S}s", False
        return ((p.stdout or "") + (p.stderr or ""))[-4000:] or f"exit {p.returncode}", p.returncode == 0
    return run


@dataclass
class Runner:
    """The model and harness a run uses, and where each case's record goes."""
    llm: object
    harness: H.Harness
    num_ctx: int
    records: Path
    backend: str = "laptop"
    max_steps: int = 0                  # coding: 0 = the harness's chat_max_steps
    arch: str = "router"                # D-071: "router" (D-068 paths) or "one" (one conversational loop)
    threads_root: Path | None = None    # one CodeMitra's conversation memory for a case (a temp folder, seeded)

    def session(self, ws: Path, case_id: str):
        from app.core import chat as C

        box: dict = {}
        hooks = C.Hooks(stream=lambda chunks, step=1: _stream(chunks, step, lambda: box["s"].cancelled),
                        show=lambda *a: None, confirm=lambda *a: True, run_shell=_run_shell(ws),
                        web_search=lambda q: "web search is off in scoring", fetch_url=lambda u: "fetch is off in scoring",
                        mcp_find=lambda q: "no MCP in scoring", mcp_call=lambda *a: "no MCP in scoring")
        s = C.ChatSession(workspace=ws, llm=self.llm, hooks=hooks, num_ctx=self.num_ctx, harness=self.harness,
                          traces=False)
        self.records.mkdir(parents=True, exist_ok=True)
        s.rec.path = self.records / f"{case_id}.jsonl"   # inside the store: kept for the coach, never mirrored
        s.backend_kind, s.thinking = self.backend, False
        box["s"] = s
        return s

    def system(self, notes: str = "", ws: Path | None = None) -> SystemMessage:
        from app.core import chat as C
        prompt = {"one": C.ONE_PROMPT, "phased": C.PHASED_PROMPT}.get(self.arch, C.CHAT_PROMPT)
        base = H.apply_prompt(prompt, self.harness)
        if self.arch in ("one", "phased") and ws is not None:  # what is in the folder, as the chat gives it
            outline = C.project_outline(ws)
            base += ("\n\n" + outline) if outline else ""
        if self.arch in ("one", "phased") and self.threads_root is not None:
            from app.core import threads
            index = threads.index_text(self.threads_root)
            base += ("\n\n" + index) if index else ""
        return SystemMessage(content=base + ("\n\n" + notes if notes else ""))

    def respond(self, s, messages: list, ws: Path, previous: str = ""):
        """One message through the chat's own entry, as the chosen architecture handles it. Returns (result, path).
        router: sorted by intent rules, then the one-call reply, the explainer or the working loop (D-068);
        one: the single conversational loop decides itself (D-071)."""
        if self.arch in ("one", "phased"):
            from app.core import threads
            root = self.threads_root if self.threads_root is not None else Path(tempfile.gettempdir()) / "no-threads"
            notes = threads.relevant_text(str(messages[-1].content), root)
            if self.arch == "phased":
                return s.phased(messages, notes=notes), "phased"
            return s.converse(messages, notes=notes), "one"
        from app.core.intent import EVERYDAY
        text = str(messages[-1].content)
        kind = classify(text, previous=previous, project_words=project_words(ws))
        if kind in EVERYDAY:
            return s.reply(messages, kind, self.llm), "reply"
        if kind == "question":
            return s.explain(messages), "explain"
        return s.turn(messages, max_steps=self.max_steps or None), "loop"


def _digest(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha1(p.read_bytes()).hexdigest() for p in root.rglob("*")
            if p.is_file() and ".codemitra" not in p.parts and "__pycache__" not in p.parts}


def _changed(before: dict, after: dict) -> list[str]:
    return sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))


def run_writing(r: Runner, on_case: Callable[[Case], None] = lambda c: None, only: set | None = None) -> list[Case]:
    data, out = _toml("writing.toml"), []
    for c in data["case"]:
        if only and c["id"] not in only:
            continue
        with tempfile.TemporaryDirectory(prefix="codemitra-score-", ignore_cleanup_errors=True) as tmp:
            s = r.session(Path(tmp), c["id"])
            messages = [r.system(data["notes"]), HumanMessage(content=c["request"])]
            t0 = time.monotonic()
            try:
                res, _path = _timed(lambda: r.respond(s, messages, Path(tmp)), CASE_TIMEOUT_S["writing"], s)
                steps = res.steps
                why = check_writing(c, res.text)
            except Exception as exc:  # noqa: BLE001 - a crash or a hang is a failed case, never a pass
                steps, why = 0, f"{type(exc).__name__}: {str(exc)[:150]}"
        case = Case(c["id"], "writing", not why, why, round(time.monotonic() - t0, 1), steps)
        on_case(case)
        out.append(case)
    return out


def run_explain(r: Runner, on_case: Callable[[Case], None] = lambda c: None, categories=("explain", "ideas"),
                only: set | None = None) -> list[Case]:
    data, out = _toml("explain.toml"), []
    project = SET / "projects" / data["project"]
    for c in data["case"]:
        if c["category"] not in categories or (only and c["id"] not in only):
            continue
        with tempfile.TemporaryDirectory(prefix="codemitra-score-", ignore_cleanup_errors=True) as tmp:
            ws = Path(tmp) / data["project"]
            shutil.copytree(project, ws, ignore=_IGNORE)
            before = _digest(ws)
            s = r.session(ws, c["id"])
            messages = [r.system(ws=ws), HumanMessage(content=c["question"])]
            t0 = time.monotonic()
            try:
                res, _path = _timed(lambda: r.respond(s, messages, ws), CASE_TIMEOUT_S[c["category"]], s)
                steps = res.steps
                why = check_explain(c, res.text, ws, changed=_changed(before, _digest(ws)))
            except Exception as exc:  # noqa: BLE001 - a crash or a hang is a failed case, never a pass
                steps, why = 0, f"{type(exc).__name__}: {str(exc)[:150]}"
        case = Case(c["id"], c["category"], not why, why, round(time.monotonic() - t0, 1), steps)
        on_case(case)
        out.append(case)
    return out


# ── behaviour: how it holds a conversation (D-071) ─────────────────────────────────────────────────────────────

_HEADING = re.compile(r"^\s{0,3}(#{1,4} \S|\*\*[^*\n]{2,60}\*\*:?\s*$)", re.M)


def headings(text: str) -> int:
    """Report-style headings: '## What we have', a bold line on its own ('**What's risky:**')."""
    return len(_HEADING.findall(text or ""))


def asks_back(text: str) -> bool:
    """Ends by asking the user something (a question in its last two sentences)."""
    tail = re.split(r"(?<=[.!?])\s+", (text or "").strip())[-2:]
    return any(t.rstrip().endswith("?") for t in tail)


def check_behaviour(case: dict, text: str, root: Path, *, tools: list[str], changed: list[str],
                    check_error: str = "") -> str:
    t = (text or "").strip()
    if not t:
        return "empty answer"
    for pat in case.get("must_not", []):
        if re.search(pat, t):
            return f"should not match: {pat}"
    for pat in case.get("facts", []):
        if not re.search(pat, t, re.I):
            return f"missing fact: {pat}"
    expect = case["expect"]
    if expect == "talk":
        if tools:
            return f"used tools to talk: {', '.join(tools[:4])}"
        if changed:
            return "changed files: " + ", ".join(changed[:3])
        # D-076: headings are allowed now (the user wants every answer formatted); length still decides "report"
        if len(t.split()) > case.get("max_words", 150):
            return f"too long for a conversation: {len(t.split())} words (max {case.get('max_words', 150)})"
        if case.get("ask_back") and not asks_back(t):
            return "did not ask back (you were deciding)"
    elif expect == "look":
        if not [x for x in tools if x in ("read_file", "search", "list_files")]:
            return "answered about the code without reading it"
        if changed:
            return "changed files: " + ", ".join(changed[:3])
        why = check_explain({"cite": case.get("cite", [])}, t, root)
        if why:
            return why
    elif expect == "lookup":  # E-102: find / pull information = the web, never memory
        if not [x for x in tools if x in ("web_search", "fetch_url")]:
            return "answered from memory without looking it up"
        if changed:
            return "changed files: " + ", ".join(changed[:3])
    elif expect == "change":
        if not changed:
            return "changed nothing"
        if check_error:
            return "the change does not work: " + check_error
    return ""


def _run_check(code: str, ws: Path) -> str:
    try:
        p = subprocess.run([sys.executable, "-c", code], cwd=ws, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
    except subprocess.TimeoutExpired:
        return "check timed out"
    return "" if p.returncode == 0 else _last_line(p.stderr or p.stdout)


def _tools_used(s) -> list[str]:
    try:
        rows = [json.loads(x) for x in s.rec.path.read_text(encoding="utf-8").splitlines() if x.strip()]
    except OSError:
        return []
    return [str(r.get("name")) for r in rows if r.get("kind") == "tool" and r.get("turn") == s.turn_no]


def run_behaviour(r: Runner, on_case: Callable[[Case], None] = lambda c: None, only: set | None = None,
                  data: dict | None = None, category: str = "behaviour") -> list[Case]:
    from langchain_core.messages import AIMessage

    data, out = data or _toml("behaviour.toml"), []
    project = SET / "projects" / data.get("project", "snake")
    for c in data["case"]:
        if only and c["id"] not in only:
            continue
        with tempfile.TemporaryDirectory(prefix="codemitra-score-", ignore_cleanup_errors=True) as tmp:
            ws = Path(tmp) / data["project"]
            shutil.copytree(project, ws, ignore=_IGNORE)
            before = _digest(ws)
            s = r.session(ws, c["id"])
            r.threads_root = Path(tmp) / "threads"   # empty unless the case seeds earlier conversations
            from app.core import threads
            for t in c.get("threads", []):
                threads.save(t, r.threads_root)
            messages, previous = [r.system(ws=ws)], ""
            for you, mitra in c.get("history", []):
                messages += [HumanMessage(content=you), AIMessage(content=mitra)]
                previous = classify(you, previous=previous, project_words=project_words(ws))
            messages.append(HumanMessage(content=c["text"]))
            t0 = time.monotonic()
            try:
                res, path = _timed(lambda: r.respond(s, messages, ws, previous=previous),
                                   CASE_TIMEOUT_S["behaviour"], s)
                steps, changed = res.steps, _changed(before, _digest(ws))
                err = _run_check(c["check"], ws) if c.get("check") else ""
                why = check_behaviour(c, res.text, ws, tools=_tools_used(s), changed=changed, check_error=err)
            except Exception as exc:  # noqa: BLE001 - a crash or a hang is a failed case, never a pass
                steps, why = 0, f"{type(exc).__name__}: {str(exc)[:150]}"
        case = Case(c["id"], category, not why, why, round(time.monotonic() - t0, 1), steps)
        on_case(case)
        out.append(case)
    return out


def real_cases() -> dict | None:
    """D-078 step 6: ~/.codemitra/score/real.toml, the cases you kept from your /bad turns (private, held out)."""
    from app.core import cases as cases_mod
    try:
        data = tomllib.loads(cases_mod.real_path().read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    return data if data.get("case") else None


def run_real(r: Runner, on_case: Callable[[Case], None] = lambda c: None, only: set | None = None) -> list[Case]:
    data = real_cases()
    return run_behaviour(r, on_case, only, data=data, category="real") if data else []


def _validate_behaviour() -> list[str]:
    problems = []
    data = _toml("behaviour.toml")
    project = SET / "projects" / data["project"]
    for c in data["case"]:
        reads = {"look": ["read_file"], "lookup": ["web_search"]}.get(c["expect"], [])
        changed: list[str] = []
        err = ""
        if c["expect"] == "change":
            with tempfile.TemporaryDirectory(prefix="codemitra-validate-", ignore_cleanup_errors=True) as tmp:
                ws = Path(tmp) / "p"
                shutil.copytree(project, ws, ignore=_IGNORE)
                if _run_check(c["check"], ws) == "":
                    problems.append(f"behaviour {c['id']}: the check passes before any change")
                f = ws / c["solution"]["file"]
                text = f.read_text(encoding="utf-8")
                if c["solution"]["old"] not in text:
                    problems.append(f"behaviour {c['id']}: the solution's old text is not in the file")
                f.write_text(text.replace(c["solution"]["old"], c["solution"]["new"]), encoding="utf-8")
                err, changed = _run_check(c["check"], ws), [c["solution"]["file"]]
        why = check_behaviour(c, c["reference"], project, tools=reads, changed=changed, check_error=err)
        if why:
            problems.append(f"behaviour {c['id']}: reference fails: {why}")
    return problems


# ── coding tasks: the bench's payments app, or a task folder here ───────────────────────────────────────────────

def _bench():
    if str(ROOT / "bench") not in sys.path:  # called per task: insert once, not once per call
        sys.path.insert(0, str(ROOT / "bench"))
    import bench  # noqa: PLC0415 - bench/ is a script folder, not a package
    return bench


@dataclass
class Task:
    id: str
    size: str
    prompt: str
    title: str
    bench_task: object = None
    dir: Path | None = None

    def prepare(self, dest: Path) -> None:
        if self.bench_task is not None:
            _bench().prepare(self.bench_task, dest)
            return
        shutil.copytree(self.dir / "start", dest, ignore=_IGNORE)
        (dest / "tests").mkdir(exist_ok=True)
        for t in sorted((self.dir / "visible").glob("test_*.py")):
            shutil.copy2(t, dest / "tests" / t.name)

    def grade(self, ws: Path) -> tuple[bool, str]:
        """(passed, why). Visible tests unchanged, visible + hidden tests pass, in a separate copy."""
        if self.bench_task is not None:
            g = _bench().grade(self.bench_task, ws)
            why = ("changed the tests: " + ", ".join(g.tampered)) if g.tampered else (
                g.infra_error or _last_line(g.output_tail))
            return g.passed, "" if g.passed else why
        tampered = [t.name for t in (self.dir / "visible").glob("test_*.py")
                    if not (ws / "tests" / t.name).is_file()
                    or (ws / "tests" / t.name).read_bytes() != t.read_bytes()]
        if tampered:  # fails whatever the tests say: no need to run them
            return False, "changed the tests: " + ", ".join(tampered)
        with tempfile.TemporaryDirectory(prefix=f"codemitra-grade-{self.id}-") as tmp:
            copy = Path(tmp) / "ws"
            shutil.copytree(ws, copy, ignore=_IGNORE)
            (copy / "tests").mkdir(exist_ok=True)
            for t in sorted((self.dir / "hidden").glob("test_*.py")):
                shutil.copy2(t, copy / "tests" / t.name)
            try:
                p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
                                   cwd=copy, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=GRADE_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                return False, f"grading timed out after {GRADE_TIMEOUT_S}s"
        return p.returncode == 0, "" if p.returncode == 0 else _last_line(p.stdout + p.stderr)


def _last_line(text: str) -> str:
    lines = [x for x in (text or "").strip().splitlines() if x.strip()]
    return lines[-1][:200] if lines else "tests failed"


def load_tasks(sizes=("small", "medium"), only: set | None = None) -> list[Task]:
    out = []
    for e in _toml("tasks.toml")["tasks"]:
        if e["size"] not in sizes or (only and e["id"] not in only):
            continue
        if e.get("bench"):
            bt = next(t for t in _bench().load_tasks() if t.id == e["bench"])
            out.append(Task(e["id"], e["size"], bt.prompt.strip(), bt.title, bench_task=bt))
        else:
            d = SET / e["dir"]
            meta = tomllib.loads((d / "task.toml").read_text(encoding="utf-8"))
            out.append(Task(e["id"], e["size"], meta["prompt"].strip(), meta["title"], dir=d))
    return out


def run_coding(r: Runner, tasks: list[Task], on_case: Callable[[Case], None] = lambda c: None) -> list[Case]:
    out = []
    for task in tasks:
        with tempfile.TemporaryDirectory(prefix=f"codemitra-score-{task.id}-", ignore_cleanup_errors=True) as tmp:
            ws = Path(tmp) / "ws"
            task.prepare(ws)
            s = r.session(ws, task.id)
            s.request_kind, s.path = classify(task.prompt, project_words=project_words(ws)), "loop"
            messages = [r.system(ws=ws), HumanMessage(content=task.prompt)]
            t0 = time.monotonic()
            try:
                res, _path = _timed(lambda: r.respond(s, messages, ws), CASE_TIMEOUT_S[task.size], s)
                steps = res.steps
                passed, why = task.grade(ws)
            except Exception as exc:  # noqa: BLE001 - a crash is a failed case, recorded, never a pass
                steps, passed, why = 0, False, ("" if isinstance(exc, TimeoutError) else "crashed: ") + f"{type(exc).__name__}: {str(exc)[:150]}"
        case = Case(task.id, task.size, passed, why, round(time.monotonic() - t0, 1), steps)
        on_case(case)
        out.append(case)
    return out


# ── validation: every reference passes its checks, every start state fails ─────────────────────────────────────

def validate() -> list[str]:
    problems = _validate_behaviour()
    s = _toml("sorting.toml")
    if len(s["cases"]) < 30:
        problems.append("sorting: fewer than 30 cases")
    w = _toml("writing.toml")
    for c in w["case"]:
        why = check_writing(c, c["reference"])
        if why:
            problems.append(f"writing {c['id']}: reference fails: {why}")
        if classify(c["request"]) != "writing":
            problems.append(f"writing {c['id']}: the request is not sorted as writing")
    e = _toml("explain.toml")
    project = SET / "projects" / e["project"]
    for c in e["case"]:
        why = check_explain(c, c["reference"], project)
        if why:
            problems.append(f"{c['category']} {c['id']}: reference fails: {why}")
        if classify(c["question"], project_words=project_words(project)) != "question":
            problems.append(f"{c['category']} {c['id']}: the question is not sorted as a question")
        for f in c.get("cite", []):
            if not (project / f).is_file():
                problems.append(f"{c['id']}: cites {f}, which is not in the project")
    for task in load_tasks():
        with tempfile.TemporaryDirectory(prefix=f"codemitra-validate-{task.id}-") as tmp:
            start = Path(tmp) / "start"
            task.prepare(start)
            if task.grade(start)[0]:
                problems.append(f"task {task.id}: the start state already passes")
            if task.bench_task is not None:
                problems += [f"task {task.id}: {p}" for p in _bench().validate(task.bench_task)]
            else:
                solved = Path(tmp) / "solved"
                task.prepare(solved)
                shutil.copytree(task.dir / "solution", solved, dirs_exist_ok=True)
                ok, why = task.grade(solved)
                if not ok:
                    problems.append(f"task {task.id}: the reference solution fails: {why}")
    return problems


# ── a whole run ─────────────────────────────────────────────────────────────────────────────────────────────────

def mitra_version() -> str:
    try:
        return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError, ValueError):
        return "?"


def run(categories=CATEGORIES, *, runner: Runner | None = None, model: str = "", cwd: Path | None = None,
        only: set | None = None, on_case: Callable[[Case], None] = lambda c: None,
        results: Path | None = None) -> dict:
    """Run the chosen categories, append one row to results/scores.jsonl, return it."""
    t0, cases = time.monotonic(), []
    if "sorting" in categories:
        for c in run_sorting():  # only the cases asked for are shown and scored
            if not only or c.id in only:
                on_case(c)
                cases.append(c)
    needs_model = [c for c in categories if c != "sorting"]
    if needs_model and runner is None:
        raise ValueError("a model is needed for: " + ", ".join(needs_model))
    if "behaviour" in categories:
        cases += run_behaviour(runner, on_case, only)
    if "writing" in categories:
        cases += run_writing(runner, on_case, only)
    if "real" in categories:
        cases += run_real(runner, on_case, only)
    if {"explain", "ideas"} & set(categories):
        cases += run_explain(runner, on_case, tuple(c for c in ("explain", "ideas") if c in categories), only)
    sizes = tuple(s for s in ("small", "medium") if s in categories)
    if sizes:
        cases += run_coding(runner, load_tasks(sizes, only), on_case)
    row = {"t": time.time(), "date": time.strftime("%Y-%m-%d %H:%M"), "mitra_version": mitra_version(),
           "harness_version": runner.harness.version if runner else H.load().version,
           "notes_version": SIG.notes_version(cwd or Path.cwd()), "model": model, "arch": runner.arch if runner else "",
           "backend": runner.backend if runner else "", "num_ctx": runner.num_ctx if runner else 0,
           "categories": list(categories), "only": sorted(only) if only else None,
           "score": totals(cases), "seconds": round(time.monotonic() - t0, 1),
           "records": str(runner.records) if runner else "", "cases": [asdict(c) for c in cases]}
    results = results or RESULTS
    results.parent.mkdir(parents=True, exist_ok=True)
    with results.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def totals(cases: list[Case]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for c in cases:
        t = out.setdefault(c.category, [0, 0])
        t[0] += int(c.passed)
        t[1] += 1
    return {k: out[k] for k in CATEGORIES if k in out}


def summary(score: dict) -> str:
    """'sorting 40/40 · writing 2/3 · ... · small 4/7'"""
    return " · ".join(f"{k} {p}/{n}" for k, (p, n) in score.items())


def history(results: Path | None = None, last: int = 10) -> list[dict]:
    results = results or RESULTS
    try:
        rows = [json.loads(x) for x in results.read_text(encoding="utf-8").splitlines() if x.strip()]
    except OSError:
        return []
    return rows[-last:]
