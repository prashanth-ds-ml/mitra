"""Project playbook discovery and formatting."""
from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any


_DEFAULT_PLAYBOOK_DIRS = [
    "playbooks",
    ".codemitra/playbooks",
]
_MAX_DESCRIPTION_CHARS = 700


@dataclass(frozen=True)
class Playbook:
    name: str
    description: str
    path: str
    starter_steps: tuple[str, ...] = field(default_factory=tuple)
    target_stack: str = ""


def _parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    match = re.match(r"^---\s*\n(.*?)\n---\s*", text, flags=re.DOTALL)
    if not match:
        return {}

    values: dict[str, Any] = {}
    for raw_line in match.group(1).splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key == "starter_steps":
            try:
                values[key] = json.loads(value)
            except json.JSONDecodeError:
                values[key] = [part.strip() for part in value.split(",") if part.strip()]
        else:
            values[key] = value
    return values


def discover(workspace: str, entries=None) -> list[Playbook]:
    """Discover markdown playbooks from configured directories inside the workspace."""
    root = pathlib.Path(workspace).resolve()
    if entries is None:
        entries = list(_DEFAULT_PLAYBOOK_DIRS)
    if isinstance(entries, str):
        entries = [entries]

    playbooks: list[Playbook] = []
    seen: set[pathlib.Path] = set()
    for raw_entry in entries:
        entry = str(raw_entry).strip()
        if not entry:
            continue
        base = pathlib.Path(entry)
        target = base if base.is_absolute() else root / base
        try:
            resolved = target.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        if not resolved.is_dir():
            continue

        for playbook_file in sorted(resolved.glob("*/PLAYBOOK.md")):
            try:
                playbook_path = playbook_file.resolve()
                playbook_path.relative_to(root)
            except (OSError, ValueError):
                continue
            if playbook_path in seen:
                continue
            try:
                text = playbook_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = playbook_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            frontmatter = _parse_frontmatter(text)
            name = frontmatter.get("name", playbook_file.parent.name).strip()
            description = frontmatter.get("description", "").strip()
            if not name or not description:
                continue
            if len(description) > _MAX_DESCRIPTION_CHARS:
                description = description[:_MAX_DESCRIPTION_CHARS].rstrip() + "..."

            starter_steps = frontmatter.get("starter_steps", [])
            if isinstance(starter_steps, str):
                try:
                    starter_steps = json.loads(starter_steps)
                except json.JSONDecodeError:
                    starter_steps = [step.strip() for step in starter_steps.split("\n") if step.strip()]
            if not isinstance(starter_steps, list):
                starter_steps = []

            playbooks.append(
                Playbook(
                    name=name,
                    description=description,
                    path=str(playbook_path.relative_to(root)),
                    starter_steps=tuple(str(step).strip() for step in starter_steps if str(step).strip()),
                    target_stack=str(frontmatter.get("target_stack", "")).strip(),
                )
            )
            seen.add(playbook_path)
    return playbooks


def find(playbooks: list[Playbook], query: str) -> Playbook | None:
    """Find a playbook by exact name, folder name, or unambiguous partial text."""
    target = (query or "").strip().lower()
    if not target:
        return None

    for playbook in playbooks:
        folder = pathlib.Path(playbook.path).parent.name.lower()
        if target in {playbook.name.lower(), folder}:
            return playbook

    matches = [
        playbook
        for playbook in playbooks
        if target in playbook.name.lower() or target in pathlib.Path(playbook.path).parent.name.lower()
    ]
    return matches[0] if len(matches) == 1 else None


def read_body(workspace: str, playbook: Playbook) -> str | None:
    """Read a discovered playbook body from inside the workspace."""
    root = pathlib.Path(workspace).resolve()
    target = root / playbook.path
    try:
        resolved = target.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    if not resolved.is_file():
        return None
    try:
        return resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return resolved.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def format_prompt(playbooks: list[Playbook]) -> str:
    """Return compact playbook index text for the system prompt or operator output."""
    if not playbooks:
        return ""
    lines = [
        "## Available Project Playbooks",
        "",
        "Project playbooks are constrained starting points for common app types. Use `/start --playbook <name>` to seed a plan from one of these patterns.",
        "",
    ]
    for playbook in playbooks:
        meta = []
        if playbook.target_stack:
            meta.append(playbook.target_stack)
        if playbook.starter_steps:
            meta.append(f"{len(playbook.starter_steps)} starter steps")
        meta_str = f" [{', '.join(meta)}]" if meta else ""
        lines.append(f"- `{playbook.name}` ({playbook.path}): {playbook.description}{meta_str}")
    return "\n".join(lines)


def build_context(playbook: Playbook, *, body: str | None = None) -> str:
    """Return the prompt context that describes a selected playbook."""
    parts = [
        f"Project playbook: {playbook.name}",
        f"Description: {playbook.description}",
    ]
    if playbook.target_stack:
        parts.append(f"Target stack: {playbook.target_stack}")
    if playbook.starter_steps:
        parts.append("Starter steps:\n" + "\n".join(f"- {step}" for step in playbook.starter_steps))
    if body:
        parts.append("Playbook body:\n" + body.strip())
    return "\n\n".join(parts)

