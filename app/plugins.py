"""Workspace plugin loading for custom slash commands."""
from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
import pathlib
import traceback
from types import ModuleType
from typing import Callable


@dataclass(frozen=True)
class PluginCommand:
    name: str
    description: str
    handler: Callable[[str, "PluginContext"], str]
    plugin_name: str


@dataclass(frozen=True)
class PluginContext:
    workspace: str
    config: dict
    console: object | None = None


@dataclass
class PluginRegistry:
    commands: list[PluginCommand] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _resolve_dirs(workspace: str, entries=None) -> list[pathlib.Path]:
    root = pathlib.Path(workspace).resolve()
    if entries is None:
        entries = ["plugins", ".codemitra/plugins"]
    if isinstance(entries, str):
        entries = [entries]

    resolved_dirs: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for raw_entry in entries:
        entry = str(raw_entry).strip()
        if not entry:
            continue
        path = pathlib.Path(entry)
        target = path if path.is_absolute() else root / path
        try:
            resolved = target.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        if not resolved.is_dir() or resolved in seen:
            continue
        resolved_dirs.append(resolved)
        seen.add(resolved)
    return resolved_dirs


def _load_module(plugin_file: pathlib.Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"codemitra_plugin_{plugin_file.stem}_{abs(hash(str(plugin_file)))}",
        plugin_file,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load plugin module from {plugin_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_specs(module: ModuleType) -> list[dict]:
    if hasattr(module, "register"):
        registered = module.register()
    else:
        registered = getattr(module, "SLASH_COMMANDS", [])
    if isinstance(registered, dict):
        registered = [registered]
    if not isinstance(registered, list):
        raise TypeError("Plugin registration must return a list of command specs.")
    return registered


def _normalize_command_spec(spec: dict, plugin_name: str) -> PluginCommand:
    if not isinstance(spec, dict):
        raise TypeError("Each plugin command spec must be a dict.")
    raw_name = str(spec.get("name", "")).strip()
    if not raw_name.startswith("/"):
        raise ValueError("Plugin command names must start with '/'.")
    handler = spec.get("handler")
    if not callable(handler):
        raise TypeError("Plugin command handler must be callable.")
    description = str(spec.get("description", "")).strip() or "Custom plugin command"
    return PluginCommand(
        name=raw_name.lower(),
        description=description,
        handler=handler,
        plugin_name=plugin_name,
    )


def discover(workspace: str, entries=None) -> PluginRegistry:
    registry = PluginRegistry()
    seen_names: set[str] = set()

    for plugin_dir in _resolve_dirs(workspace, entries):
        for plugin_file in sorted(plugin_dir.glob("*.py")):
            if plugin_file.name.startswith("_"):
                continue
            try:
                module = _load_module(plugin_file)
                specs = _load_specs(module)
                for spec in specs:
                    command = _normalize_command_spec(spec, plugin_file.stem)
                    if command.name in seen_names:
                        registry.errors.append(
                            f"Skipped duplicate plugin command `{command.name}` from `{plugin_file.name}`."
                        )
                        continue
                    registry.commands.append(command)
                    seen_names.add(command.name)
            except Exception as exc:
                registry.errors.append(
                    f"Failed to load plugin `{plugin_file.name}`: {exc}"
                )
    return registry


def find_command(registry: PluginRegistry, name: str) -> PluginCommand | None:
    normalized = (name or "").strip().lower()
    for command in registry.commands:
        if command.name == normalized:
            return command
    return None


def execute(command: PluginCommand, raw: str, context: PluginContext) -> str:
    try:
        result = command.handler(raw, context)
    except Exception as exc:
        detail = traceback.format_exc(limit=3).strip().splitlines()[-1]
        return f"Plugin command `{command.name}` from `{command.plugin_name}` failed: {exc}\n\n{detail}"
    return str(result).strip() or f"Plugin command `{command.name}` completed with no output."


def build_registry_reply(registry: PluginRegistry) -> str:
    lines = ["## Workspace plugins", ""]
    if registry.commands:
        lines.append("### Loaded commands")
        for command in registry.commands:
            lines.append(f"- `{command.name}` — {command.description} (`{command.plugin_name}`)")
        lines.append("")
    else:
        lines.append("No plugin slash commands are loaded.")
        lines.append("")

    if registry.errors:
        lines.append("### Load issues")
        for error in registry.errors:
            lines.append(f"- {error}")
    else:
        lines.append("No plugin load issues detected.")
    return "\n".join(lines).strip()
