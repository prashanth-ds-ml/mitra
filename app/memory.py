"""Obsidian-compatible project memory for Mitra.

Files written to <workspace>/.mitra/
  activity.md  — timestamped log of every conversation turn (daily-note style)
  context.md   — running project state, injected into the system prompt
  plan.md      — current active plan (populated by the planner agent later)

All files are plain Markdown — open the .mitra/ folder as an Obsidian vault
to browse, search, and link between sessions.
"""

from __future__ import annotations

import json
import pathlib
import re
import sqlite3
import textwrap
from datetime import datetime


# ── Paths ─────────────────────────────────────────────────────────────────────

_DIR = ".mitra"
_ACTIVITY  = "activity.md"
_SESSION_LOG = "session_log.md"
_CONTEXT   = "context.md"
_PLAN      = "plan.md"
_BRAINSTORM = "brainstorm.md"
_UNDERSTAND = "understand.md"
_PRD = "prd.md"
_LAST_CHANGE = "last_change.json"
_SESSION = "session.json"
_TRACE = "execution_trace.jsonl"
_DECISIONS = "decisions.md"
_ERRORS = "errors.md"
_TASK_BOARD = "task_board.md"
_USER_PROFILE = "user_profile.yaml"
_MEMORY_DB = "memory.sqlite"


def _dir(workspace: str) -> pathlib.Path:
    d = pathlib.Path(workspace).resolve() / _DIR
    d.mkdir(exist_ok=True)
    return d


# ── Activity log ──────────────────────────────────────────────────────────────

def append_activity(workspace: str, user_msg: str, ai_summary: str) -> None:
    """Append one conversation turn to activity.md.

    Format (Obsidian daily-note style):
      ## YYYY-MM-DD
      ### HH:MM
      **You:** ...
      **Mitra:** ...
    """
    path = _dir(workspace) / _ACTIVITY
    now  = datetime.now()
    date_heading = f"## {now.strftime('%Y-%m-%d')}"
    time_heading  = f"### {now.strftime('%H:%M')}"

    # Trim long messages so the log stays readable
    user_short = _trim(user_msg, 300)
    ai_short   = _trim(ai_summary, 400)

    entry = (
        f"\n{time_heading}\n"
        f"**You:** {user_short}\n\n"
        f"**Mitra:** {ai_short}\n"
    )

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        # Only insert the date heading once per day
        if date_heading not in existing:
            entry = f"\n{date_heading}\n{entry}"
        path.write_text(existing + entry, encoding="utf-8")
    else:
        header = textwrap.dedent(f"""\
            ---
            title: Activity Log
            tags: [mitra, activity, log]
            ---

            # Mitra - Activity Log

            {date_heading}
        """)
        path.write_text(header + entry, encoding="utf-8")

    _append_session_log(workspace, date_heading, entry)
    append_execution_trace(
        workspace,
        "activity",
        {
            "user": user_short,
            "assistant": ai_short,
        },
    )


# ── Context file ──────────────────────────────────────────────────────────────

_CONTEXT_TEMPLATE = textwrap.dedent("""\
    ---
    title: Project Context
    tags: [mitra, context, memory]
    updated: {updated}
    ---

    # Project Context

    > Auto-maintained by Mitra. Edit freely - it is re-read at every startup.

    ## Last active
    {updated}

    ## Recent topics
    {topics}

    ## Notes
    <!-- Add anything you want Mitra to always remember about this project -->

""")


def load_context(workspace: str) -> str | None:
    """Return the contents of context.md, or None if it does not exist yet."""
    path = _dir(workspace) / _CONTEXT
    if path.exists():
        return _without_commands(path.read_text(encoding="utf-8"))
    return None


def context_notes(text: str | None) -> str | None:
    """Only what you wrote under '## Notes' in context.md (one Mitra, D-071): the auto-kept topic list is the
    first line of each request, which steered every answer back to old work. None when there is nothing."""
    m = re.search(r"^## Notes\s*$(.*?)(?=^## |\Z)", text or "", re.M | re.S)
    body = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S).strip() if m else ""
    return f"## Notes\n{body}" if body else None


_TOPIC_CMD = re.compile(r"^- `[^`]*` [/!]")


def _without_commands(text: str) -> str:
    """Topic lines that are slash or shell commands (`/logs`, `!dir`) are not topics: a model read `/logs` as a
    folder and guessed /logs/... paths seven times (2026-11-10, D-065 P0)."""
    kept = [line for line in text.splitlines() if not _TOPIC_CMD.match(line)]
    return "\n".join(kept) + ("\n" if text.endswith("\n") else "")


def update_context(workspace: str, new_topic: str) -> None:
    """Prepend `new_topic` to the Recent topics list in context.md.

    Creates the file with a starter template if it does not exist.
    """
    if (new_topic or "").strip().startswith(("/", "!")):  # commands are not topics (D-065 P0)
        return
    path  = _dir(workspace) / _CONTEXT
    now   = datetime.now().strftime("%Y-%m-%d %H:%M")
    topic = _trim(new_topic, 120)

    if path.exists():
        text = path.read_text(encoding="utf-8")

        # Update the 'updated' frontmatter field
        text = _replace_field(text, "updated", now)

        # Prepend new topic under "## Recent topics"
        marker = "## Recent topics"
        if marker in text:
            idx = text.index(marker) + len(marker)
            bullet = f"\n- `{now}` {topic}"
            # Keep only the last 20 topic lines to avoid unbounded growth
            lines = text[idx:].splitlines()
            topic_lines = [l for l in lines if l.startswith("- `")]
            topic_lines = topic_lines[:19]  # keep 19 existing + 1 new
            rest_lines  = [l for l in lines if not l.startswith("- `")]
            new_topics  = bullet + "\n" + "\n".join(topic_lines)
            text = text[:idx] + new_topics + "\n" + "\n".join(rest_lines)
        path.write_text(text, encoding="utf-8")
    else:
        content = _CONTEXT_TEMPLATE.format(
            updated=now,
            topics=f"- `{now}` {topic}",
        )
        path.write_text(content, encoding="utf-8")




# ── Plan file ─────────────────────────────────────────────────────────────────

_PLAN_TEMPLATE = textwrap.dedent("""\
    ---
    title: Active Plan
    tags: [mitra, plan]
    updated: {updated}
    ---

    # Active Plan

    > Managed by Mitra's planner. Ask Mitra to make or change the plan.

    ## Goal
    {goal}

    ## Steps
    {steps}

    ## Completed
    <!-- Mitra will check off steps here as work progresses -->

""")


def load_plan(workspace: str) -> str | None:
    """Return current plan.md contents, or None."""
    path = _dir(workspace) / _PLAN
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def load_brainstorm(workspace: str) -> str | None:
    """Return brainstorm.md contents, or None."""
    path = _dir(workspace) / _BRAINSTORM
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None






def load_recent_activity(workspace: str, limit: int = 5) -> list[dict[str, str]]:
    """Return the most recent conversation entries from activity.md."""
    path = _dir(workspace) / _ACTIVITY
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, str]] = []
    current_date = ""
    current: dict[str, str] | None = None

    for line in lines:
        if line.startswith("## "):
            current_date = line[3:].strip()
            continue
        if line.startswith("### "):
            if current:
                entries.append(current)
            current = {"date": current_date, "time": line[4:].strip(), "user": "", "assistant": ""}
            continue
        if current is None:
            continue
        if line.startswith("**You:** "):
            current["user"] = line[len("**You:** "):].strip()
        elif line.startswith("**Mitra:** "):
            current["assistant"] = line[len("**Mitra:** "):].strip()

    if current:
        entries.append(current)

    return entries[-limit:]


def write_plan(workspace: str, goal: str, steps: list[str]) -> pathlib.Path:
    """Write (or overwrite) plan.md with a new goal and step list."""
    path = _dir(workspace) / _PLAN
    now  = datetime.now().strftime("%Y-%m-%d %H:%M")
    steps_md = "\n".join(f"- [ ] {s}" for s in steps)
    content = _PLAN_TEMPLATE.format(updated=now, goal=goal, steps=steps_md)
    path.write_text(content, encoding="utf-8")
    return path






def mark_step_done(workspace: str, step_index: int) -> None:
    """Tick off step number `step_index` (0-based) in plan.md."""
    path = _dir(workspace) / _PLAN
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    step_lines = [i for i, l in enumerate(lines) if l.startswith("- [ ]") or l.startswith("- [x]")]
    if 0 <= step_index < len(step_lines):
        i = step_lines[step_index]
        lines[i] = lines[i].replace("- [ ]", "- [x]", 1)
    path.write_text("\n".join(lines), encoding="utf-8")


def record_last_change_set(workspace: str, change_set: dict) -> None:
    """Persist the latest undoable change set for this workspace."""
    path = _dir(workspace) / _LAST_CHANGE
    payload = {
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        **change_set,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    append_execution_trace(workspace, "change_set", payload)




def load_last_change_set(workspace: str) -> dict | None:
    """Load the latest persisted change set, if any."""
    path = _dir(workspace) / _LAST_CHANGE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def clear_last_change_set(workspace: str) -> None:
    """Remove the persisted change set after a successful undo."""
    path = _dir(workspace) / _LAST_CHANGE
    if path.exists():
        path.unlink()


def load_session_metadata(workspace: str) -> dict | None:
    """Load persisted session metadata for this workspace."""
    path = _dir(workspace) / _SESSION
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_session_metadata(workspace: str, metadata: dict) -> pathlib.Path:
    """Persist session metadata for this workspace."""
    path = _dir(workspace) / _SESSION
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        **metadata,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_memory_db_event(workspace, "session_metadata", payload)
    return path


def append_execution_trace(workspace: str, event_type: str, payload: dict) -> pathlib.Path:
    """Append one JSONL trace event to execution_trace.jsonl."""
    path = _dir(workspace) / _TRACE
    event = {
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "event_type": event_type,
        "payload": payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True) + "\n")
    _write_memory_db_event(workspace, event_type, payload)
    return path




def append_error(workspace: str, summary: str, detail: str) -> pathlib.Path:
    """Append an error record to errors.md and execution_trace.jsonl."""
    path = _dir(workspace) / _ERRORS
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n## {stamp}\n\n"
        f"**Summary:** {summary.strip()}\n\n"
        f"```text\n{detail.strip()}\n```\n"
    )
    existing = path.read_text(encoding="utf-8") if path.exists() else _ERRORS_TEMPLATE
    path.write_text(existing + entry, encoding="utf-8")
    append_execution_trace(workspace, "error", {"summary": summary.strip(), "detail": detail.strip()})
    return path






def ensure_session_metadata(workspace: str, *, default_name: str | None = None) -> dict:
    """Ensure a session metadata file exists and return its content."""
    existing = load_session_metadata(workspace)
    if existing:
        return existing

    root = pathlib.Path(workspace).resolve()
    metadata = {
        "name": default_name or root.name,
        "workspace": str(root),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_session_metadata(workspace, metadata)
    return load_session_metadata(workspace) or metadata


def is_shell_command_trusted(workspace: str, cwd: str, command_name: str) -> bool:
    """Return True when a shell command is trusted for a specific directory."""
    metadata = ensure_session_metadata(workspace)
    trusted = metadata.get("shell_trust", {})
    commands = trusted.get(str(pathlib.Path(cwd).resolve()), [])
    return command_name in commands


def trust_shell_command(workspace: str, cwd: str, command_name: str) -> dict:
    """Persist trust for a shell command within a specific directory."""
    metadata = ensure_session_metadata(workspace)
    trusted = dict(metadata.get("shell_trust", {}))
    scope = str(pathlib.Path(cwd).resolve())
    commands = list(trusted.get(scope, []))
    if command_name not in commands:
        commands.append(command_name)
    trusted[scope] = sorted(commands)
    metadata["shell_trust"] = trusted
    save_session_metadata(workspace, metadata)
    return load_session_metadata(workspace) or metadata


# ── Init ──────────────────────────────────────────────────────────────────────

_ACTIVITY_TEMPLATE = textwrap.dedent("""\
    ---
    title: Activity Log
    tags: [mitra, activity, log]
    ---

    # Mitra - Activity Log

    > One entry per conversation turn. Open this folder as an Obsidian vault.

""")

_SESSION_LOG_TEMPLATE = textwrap.dedent("""\
    ---
    title: Session Log
    tags: [mitra, session, log]
    ---

    # Mitra - Session Log

    > Mirror of high-level session activity for traceability.

""")

_DECISIONS_TEMPLATE = textwrap.dedent("""\
    ---
    title: Decision Journal
    tags: [mitra, decisions]
    ---

    # Decision Journal

    > Important implementation and operator decisions recorded by Mitra.

""")

_ERRORS_TEMPLATE = textwrap.dedent("""\
    ---
    title: Error Log
    tags: [mitra, errors]
    ---

    # Error Log

    > Structured error records captured during execution.

""")

_TASK_BOARD_TEMPLATE = textwrap.dedent("""\
    ---
    title: Task Board
    tags: [mitra, tasks]
    updated: {updated}
    ---

    # Task Board

    {tasks}
""")

_USER_PROFILE_TEMPLATE = textwrap.dedent("""\
    name: ""
    preferences:
      response_style: concise
      planning_mode: explicit
    notes: []
""")

_OBSIDIAN_README = textwrap.dedent("""\
    # .mitra vault

    This folder is managed by **Mitra** and doubles as an [Obsidian](https://obsidian.md) vault.

    | File | Purpose |
    |---|---|
    | `activity.md` | Timestamped log of every conversation turn |
    | `session_log.md` | Session-oriented mirror log for traceability |
    | `context.md`  | Running project state — injected into every session |
    | `plan.md`     | Active task plan with checkboxes |
    | `brainstorm.md` | Saved brainstorming and ideation notes |
    | `execution_trace.jsonl` | Append-only structured trace events |
    | `decisions.md` | Human-readable decision journal |
    | `errors.md` | Structured execution error log |
    | `task_board.md` | Simple tracked task checklist |
    | `user_profile.yaml` | Local operator preferences and notes |
    | `memory.sqlite` | Local structured event store |

    Open this folder in Obsidian for graph view, search, and daily-note navigation.
""")


def init_memory(workspace: str) -> list[str]:
    """Create the .mitra/ vault skeleton during `mitra init`.

    Returns a list of file paths that were created (skips existing files).
    """
    d = _dir(workspace)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    project_name = pathlib.Path(workspace).resolve().name
    created: list[str] = []

    # activity.md
    activity_path = d / _ACTIVITY
    if not activity_path.exists():
        activity_path.write_text(_ACTIVITY_TEMPLATE, encoding="utf-8")
        created.append(str(activity_path.relative_to(pathlib.Path(workspace).resolve())))

    session_log_path = d / _SESSION_LOG
    if not session_log_path.exists():
        session_log_path.write_text(_SESSION_LOG_TEMPLATE, encoding="utf-8")
        created.append(str(session_log_path.relative_to(pathlib.Path(workspace).resolve())))

    # context.md — pre-fill with project name as first note
    context_path = d / _CONTEXT
    if not context_path.exists():
        content = _CONTEXT_TEMPLATE.format(
            updated=now,
            topics=f"- `{now}` Project initialised",
        )
        # Inject project name into Notes section
        content = content.replace(
            "<!-- Add anything you want Mitra to always remember about this project -->",
            f"<!-- Add anything you want Mitra to always remember about this project -->\n"
            f"- Project: **{project_name}**",
        )
        context_path.write_text(content, encoding="utf-8")
        created.append(str(context_path.relative_to(pathlib.Path(workspace).resolve())))

    # plan.md — empty starter
    plan_path = d / _PLAN
    if not plan_path.exists():
        content = _PLAN_TEMPLATE.format(
            updated=now,
            goal="_No active goal. Ask Mitra to make a plan._",
            steps="- [ ] Define project goal",
        )
        plan_path.write_text(content, encoding="utf-8")
        created.append(str(plan_path.relative_to(pathlib.Path(workspace).resolve())))

    understand_path = d / _UNDERSTAND
    if not understand_path.exists():
        understand_path.write_text(
            textwrap.dedent("""\
                ---
                title: Understand Notes
                tags: [mitra, understand, notes]
                ---

                # Understand Notes

                > Mitra keeps the questions and answers about the idea here.
            """),
            encoding="utf-8",
        )
        created.append(str(understand_path.relative_to(pathlib.Path(workspace).resolve())))

    prd_path = d / _PRD
    if not prd_path.exists():
        prd_path.write_text(
            textwrap.dedent("""\
                ---
                title: Product Requirements Document
                tags: [mitra, prd, requirements]
                ---

                # Product Requirements Document

                > Mitra keeps the project PRD here.
            """),
            encoding="utf-8",
        )
        created.append(str(prd_path.relative_to(pathlib.Path(workspace).resolve())))

    brainstorm_path = d / _BRAINSTORM
    if not brainstorm_path.exists():
        brainstorm_path.write_text(
            textwrap.dedent("""\
                ---
                title: Brainstorm Notes
                tags: [mitra, brainstorm, notes]
                ---

                # Brainstorm Notes

                > Mitra keeps idea exploration here.
            """),
            encoding="utf-8",
        )
        created.append(str(brainstorm_path.relative_to(pathlib.Path(workspace).resolve())))

    decisions_path = d / _DECISIONS
    if not decisions_path.exists():
        decisions_path.write_text(_DECISIONS_TEMPLATE, encoding="utf-8")
        created.append(str(decisions_path.relative_to(pathlib.Path(workspace).resolve())))

    errors_path = d / _ERRORS
    if not errors_path.exists():
        errors_path.write_text(_ERRORS_TEMPLATE, encoding="utf-8")
        created.append(str(errors_path.relative_to(pathlib.Path(workspace).resolve())))

    task_board_path = d / _TASK_BOARD
    if not task_board_path.exists():
        task_board_path.write_text(
            _TASK_BOARD_TEMPLATE.format(updated=now, tasks="- [ ] No active tracked tasks"),
            encoding="utf-8",
        )
        created.append(str(task_board_path.relative_to(pathlib.Path(workspace).resolve())))

    user_profile_path = d / _USER_PROFILE
    if not user_profile_path.exists():
        user_profile_path.write_text(_USER_PROFILE_TEMPLATE, encoding="utf-8")
        created.append(str(user_profile_path.relative_to(pathlib.Path(workspace).resolve())))

    trace_path = d / _TRACE
    if not trace_path.exists():
        trace_path.write_text("", encoding="utf-8")
        created.append(str(trace_path.relative_to(pathlib.Path(workspace).resolve())))

    db_path = d / _MEMORY_DB
    if not db_path.exists():
        _ensure_memory_db(workspace)
        created.append(str(db_path.relative_to(pathlib.Path(workspace).resolve())))
    else:
        _ensure_memory_db(workspace)

    # README.md — Obsidian vault description
    readme_path = d / "README.md"
    if not readme_path.exists():
        readme_path.write_text(_OBSIDIAN_README, encoding="utf-8")
        created.append(str(readme_path.relative_to(pathlib.Path(workspace).resolve())))

    return created


# ── Helpers ───────────────────────────────────────────────────────────────────

def _trim(text: str, max_chars: int) -> str:
    text = text.strip().replace("\n", " ")
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "…"
    return text


def _replace_field(text: str, field: str, value: str) -> str:
    """Replace `field: <old>` in YAML frontmatter."""
    import re
    return re.sub(rf"^{field}:.*$", f"{field}: {value}", text, flags=re.MULTILINE)


def _append_session_log(workspace: str, date_heading: str, entry: str) -> None:
    path = _dir(workspace) / _SESSION_LOG
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if date_heading not in existing:
            entry = f"\n{date_heading}\n{entry}"
        path.write_text(existing + entry, encoding="utf-8")
    else:
        path.write_text(_SESSION_LOG_TEMPLATE + f"\n{date_heading}\n{entry}", encoding="utf-8")


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _ensure_memory_db(workspace: str) -> pathlib.Path:
    path = _dir(workspace) / _MEMORY_DB
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _write_memory_db_event(workspace: str, event_type: str, payload: dict) -> None:
    path = _ensure_memory_db(workspace)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO events (recorded_at, event_type, payload_json) VALUES (?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), event_type, json.dumps(payload, ensure_ascii=True)),
        )
        conn.commit()
    finally:
        conn.close()
