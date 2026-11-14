"""Checks for /doctor that ask Ollama what it is actually running."""

from __future__ import annotations

import json
import urllib.request

_TIMEOUT_S = 5


def _http_get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _gib(n: int) -> str:
    return f"{n / (1024 ** 3):.1f} GiB"


def _same_model(a: str, b: str) -> bool:
    # Ollama adds ":latest" when no tag is given; treat "x" and "x:latest" as one.
    def norm(name: str) -> str:
        name = (name or "").strip()
        return name if ":" in name else f"{name}:latest"
    return norm(a) == norm(b)


def ollama_report(model: str, num_ctx: int, base_url: str = "http://127.0.0.1:11434", get=None) -> str:
    """Markdown report: Ollama reachable, loaded models, and whether `model` runs with `num_ctx`.

    `get(url) -> dict` is injectable for tests; the default uses urllib with a 5 s timeout.
    """
    get = get or _http_get_json
    url = base_url.rstrip("/") + "/api/ps"
    try:
        data = get(url) or {}
    except Exception as exc:  # any failure here means "not reachable" to the user
        return (
            f"- **Ollama:** not reachable at `{base_url}` ({type(exc).__name__}: {exc})\n"
            "- Start it with `ollama serve`, or check `ollama_local_base_url` in codemitra.toml."
        )

    lines = [f"- **Ollama:** reachable at `{base_url}`"]
    loaded = data.get("models") or []
    if not loaded:
        lines.append("- **Loaded models:** none")
    else:
        lines.append("- **Loaded models:**")
        for m in loaded:
            name = m.get("name") or m.get("model") or "?"
            size = int(m.get("size") or 0)
            vram = int(m.get("size_vram") or 0)
            gpu = f"{round(100 * vram / size)}% on GPU" if size else "GPU share unknown"
            ctx = m.get("context_length")
            ctx_text = f", context {int(ctx):,}" if ctx else ""
            lines.append(f"  - `{name}`: {_gib(size)}, {gpu}{ctx_text}")

    mine = next((m for m in loaded if _same_model(m.get("name") or m.get("model") or "", model)), None)
    if mine is None:
        lines.append(f"- **`{model}`:** not loaded (Ollama loads it on the first message)")
        return "\n".join(lines)

    lines.append(f"- **`{model}`:** loaded")
    ctx = mine.get("context_length")
    if not ctx:
        lines.append("- **Context:** this Ollama version does not report it; cannot check")
    elif int(ctx) < num_ctx:
        lines.append(
            f"- **Warning:** Ollama is running it with a smaller context than CodeMitra asked for "
            f"({int(ctx):,} < {num_ctx:,}). Long chats will be cut silently; "
            "set `OLLAMA_CONTEXT_LENGTH` or reload the model."
        )
    elif int(ctx) == num_ctx:
        lines.append(f"- **Context:** {int(ctx):,}, as CodeMitra asked")
    else:
        lines.append(f"- **Context:** {int(ctx):,} (CodeMitra asked for {num_ctx:,}; larger is fine)")
    return "\n".join(lines)
