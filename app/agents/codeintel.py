"""Code Intelligence Agent — symbol-focused definitions and references using LSP."""
from __future__ import annotations

from dataclasses import dataclass
import pathlib

from rich.markdown import Markdown
from rich.panel import Panel

from app.agents import diagnostics as diagnostics_agent
from app.agents import reader as reader_agent


@dataclass
class CodeIntelResponse:
    symbol: str
    summary: str


def _run_lsp_symbol_lookup(workspace: str, symbol: str) -> tuple[list[dict], list[dict], str | None]:
    root = pathlib.Path(workspace).resolve()
    files = diagnostics_agent._resolve_target_files(workspace, "")
    if not files:
        return [], [], None

    by_language: dict[str, list[pathlib.Path]] = {}
    for path in files:
        by_language.setdefault(diagnostics_agent._LANGUAGE_BY_SUFFIX[path.suffix.lower()], []).append(path)

    all_definitions: list[dict] = []
    all_references: list[dict] = []
    server_names: list[str] = []

    for language, language_files in by_language.items():
        defs, refs, server_name = diagnostics_agent._collect_symbol_info(root, language, language_files, symbol)
        if server_name is None:
            continue
        server_names.append(server_name)
        all_definitions.extend(defs)
        all_references.extend(refs)

    return all_definitions, all_references, server_names[0] if server_names else None


def run(workspace: str, symbol: str) -> CodeIntelResponse:
    reader_agent.configure(workspace=workspace)

    lsp_definitions, lsp_references, server_name = _run_lsp_symbol_lookup(workspace, symbol)

    definition = reader_agent.find_definition.invoke({"name": symbol, "path": workspace})
    usages = reader_agent.grep_symbol.invoke({"symbol": symbol, "path": workspace})

    lines = [f"## Symbol: `{symbol}`", ""]

    if lsp_definitions:
        lines.append("### Definitions (LSP)")
        if server_name:
            lines.append(f"*Server: {server_name}*")
        lines.append("")
        for loc in lsp_definitions[:10]:
            lines.append(f"- `{diagnostics_agent._lsp_location_to_str(pathlib.Path(workspace).resolve(), loc)}`")
        if len(lsp_definitions) > 10:
            lines.append(f"- ... and {len(lsp_definitions) - 10} more")
        lines.append("")

    lines.append("### Definitions (grep fallback)")
    lines.append(definition if isinstance(definition, str) else str(definition))
    lines.append("")

    if lsp_references:
        lines.append("### References (LSP)")
        if server_name:
            lines.append(f"*Server: {server_name}*")
        lines.append("")
        for loc in lsp_references[:20]:
            lines.append(f"- `{diagnostics_agent._lsp_location_to_str(pathlib.Path(workspace).resolve(), loc)}`")
        if len(lsp_references) > 20:
            lines.append(f"- ... and {len(lsp_references) - 20} more")
        lines.append("")

    lines.append("### Usages (grep fallback)")
    lines.append(usages if isinstance(usages, str) else str(usages))

    return CodeIntelResponse(symbol=symbol, summary="\n".join(lines))


def render(response: CodeIntelResponse) -> Panel:
    return Panel(
        Markdown(response.summary),
        title="[bold cyan]Code Intelligence[/bold cyan]",
        border_style="cyan",
    )