"""CodeMitra skill discovery and prompt formatting."""
from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any


_MAX_DESCRIPTION_CHARS = 700


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: str
    args: dict[str, Any] = field(default_factory=dict)
    model_override: str | None = None
    pre_approved_tools: list[str] = field(default_factory=list)
    auto_invoke: bool = False
    invocation_mode: str = "prompt"


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
        if key in ("args", "pre_approved_tools"):
            try:
                values[key] = json.loads(value)
            except json.JSONDecodeError:
                values[key] = {}
        elif key == "auto_invoke":
            values[key] = value.lower() in ("true", "yes", "1")
        else:
            values[key] = value
    return values


def discover(workspace: str, entries=None) -> list[Skill]:
    """Discover skills from configured directories inside the workspace."""
    root = pathlib.Path(workspace).resolve()
    if entries is None:
        entries = ["skills", ".codemitra/skills"]
    if isinstance(entries, str):
        entries = [entries]

    skills: list[Skill] = []
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

        for skill_file in sorted(resolved.glob("*/SKILL.md")):
            try:
                skill_path = skill_file.resolve()
                skill_path.relative_to(root)
            except (OSError, ValueError):
                continue
            if skill_path in seen:
                continue
            try:
                text = skill_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = skill_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            frontmatter = _parse_frontmatter(text)
            name = frontmatter.get("name", skill_file.parent.name).strip()
            description = frontmatter.get("description", "").strip()
            if not name or not description:
                continue
            if len(description) > _MAX_DESCRIPTION_CHARS:
                description = description[:_MAX_DESCRIPTION_CHARS].rstrip() + "..."

            args = frontmatter.get("args", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            pre_approved = frontmatter.get("pre_approved_tools", [])
            if isinstance(pre_approved, str):
                try:
                    pre_approved = json.loads(pre_approved)
                except json.JSONDecodeError:
                    pre_approved = [t.strip() for t in pre_approved.split(",") if t.strip()]

            skills.append(
                Skill(
                    name=name,
                    description=description,
                    path=str(skill_path.relative_to(root)),
                    args=args,
                    model_override=frontmatter.get("model_override"),
                    pre_approved_tools=pre_approved,
                    auto_invoke=frontmatter.get("auto_invoke", False),
                    invocation_mode=frontmatter.get("invocation_mode", "prompt"),
                )
            )
            seen.add(skill_path)
    return skills


def find(skills: list[Skill], query: str) -> Skill | None:
    """Find a skill by exact name, folder name, or unambiguous partial text."""
    target = (query or "").strip().lower()
    if not target:
        return None

    for skill in skills:
        folder = pathlib.Path(skill.path).parent.name.lower()
        if target in {skill.name.lower(), folder}:
            return skill

    matches = [
        skill for skill in skills
        if target in skill.name.lower() or target in pathlib.Path(skill.path).parent.name.lower()
    ]
    return matches[0] if len(matches) == 1 else None


def read_body(workspace: str, skill: Skill) -> str | None:
    """Read a discovered skill body from inside the workspace."""
    root = pathlib.Path(workspace).resolve()
    target = root / skill.path
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


def format_prompt(skills: list[Skill]) -> str:
    """Return compact skill index text for the system prompt."""
    if not skills:
        return ""
    lines = [
        "## Available CodeMitra Skills",
        "",
        "Skills are reusable engineering playbooks stored in this workspace. When a user request clearly matches a skill description, read that skill's `SKILL.md` with the code reader before planning or editing, then follow its workflow. Keep using normal permission modes and approval rules.",
        "",
        "Executable skills (auto_invoke=true) will be invoked automatically when their trigger conditions match. Skills with pre_approved_tools can use those tools without additional approval prompts.",
        "",
    ]
    for skill in skills:
        meta = []
        if skill.auto_invoke:
            meta.append("auto-invoke")
        if skill.model_override:
            meta.append(f"model={skill.model_override}")
        if skill.pre_approved_tools:
            meta.append(f"pre-approved={','.join(skill.pre_approved_tools)}")
        if skill.args:
            meta.append(f"args={list(skill.args.keys())}")
        meta_str = f" [{', '.join(meta)}]" if meta else ""
        lines.append(f"- `{skill.name}` ({skill.path}): {skill.description}{meta_str}")
    return "\n".join(lines)
