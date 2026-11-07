"""Can this machine run the chosen model at its context, and what to close if not (D-040).

Pure logic: callers pass in what they measured (free RAM, free VRAM, Ollama's /api/ps, running processes), so every
case is testable without a real machine. `check()` gathers those facts live.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field

GIB = 1024 ** 3
COMFORT_GB = 3.0     # RAM left after loading: Mitra, the terminal, tests and builds need room (L-008)
MIN_PROGRAM_GB = 0.3  # smaller programs are not worth closing

# Loaded size and GPU part measured on this machine (8 GB GPU, flash attention + q8_0 KV, EVALS 2026-11-07, D-039).
MEASURED: dict[tuple[str, int], tuple[float, float]] = {
    ("qwen3.5:4b", 131_072): (6.7, 5.8),
    ("qwen3.5:4b", 262_144): (10.0, 5.2),
    ("qwen3.5:latest", 262_144): (12.0, 5.2),
    ("qwen3.5:9b", 262_144): (12.0, 5.2),
    ("qwen3.5:latest", 131_072): (9.5, 5.5),
    ("qwen3.5:9b", 131_072): (9.5, 5.5),
}

# Never suggest closing these: Windows itself, the AV, the desktop, Ollama (it is the model), Mitra's own terminal.
_NEVER = {
    "system", "system idle process", "idle", "registry", "memory compression", "secure system", "smss.exe",
    "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe", "dwm.exe",
    "explorer.exe", "msmpeng.exe", "searchhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
    "fontdrvhost.exe", "sihost.exe", "ctfmon.exe", "audiodg.exe", "conhost.exe", "openconsole.exe",
    "windowsterminal.exe", "ollama.exe", "ollama", "ollama app.exe", "llama-server.exe", "llama-server",
    "systemd", "init", "kthreadd", "xorg", "gnome-shell",
}


@dataclass
class Program:
    name: str
    gb: float
    count: int = 1
    hint: str = ""  # e.g. "langgraph dev" for a python process


@dataclass
class Fit:
    verdict: str                  # "ok" | "tight" | "no" | "unknown"
    model: str
    context: int
    need_ram_gb: float | None     # RAM this model takes once loaded (0 when already loaded as asked)
    need_gpu_gb: float | None
    free_ram_gb: float | None     # free now, plus what Ollama frees by unloading other models
    left_gb: float | None         # free_ram_gb - need_ram_gb
    source: str = ""              # "loaded" | "measured" | "estimate"
    unload: list[str] = field(default_factory=list)   # other models Ollama will unload
    close: list[Program] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)


def _norm(name: str) -> str:
    name = (name or "").strip()
    return name if ":" in name else f"{name}:latest"


def estimate(model: str, context: int, *, file_gb: float | None, free_vram_gb: float | None) -> tuple[float, float, str] | None:
    """(total GB, GPU GB, source) for `model` at `context`."""
    hit = MEASURED.get((_norm(model), context))
    if hit:
        return hit[0], hit[1], "measured"
    if not file_gb:
        return None
    # KV cache (q8_0) grows with context; ~0.6x the weights per 128K matches the measured qwen3.5 rows within ~20%.
    total = file_gb * (1 + 0.6 * context / 131_072)
    gpu = min(total, max(0.0, (free_vram_gb or 0.0) * 0.7))  # Ollama keeps whole layers + buffers off the last GB
    return round(total, 1), round(gpu, 1), "estimate"


def assess(model: str, context: int, *, free_ram_gb: float | None, free_vram_gb: float | None,
           file_gb: float | None, loaded: list[dict], programs: list[Program],
           alternatives: list[str] | None = None) -> Fit:
    """Decide ok / tight / no. `loaded` is Ollama's /api/ps models list (name, size, size_vram, context_length)."""
    unload, reclaim = [], 0.0
    mine = None
    for m in loaded:
        if _norm(m.get("name", "")) == _norm(model) and int(m.get("context_length") or 0) >= context:
            mine = m
        else:
            same = _norm(m.get("name", "")) == _norm(model)
            unload.append(m.get("name", "?") + (" (reloads with the bigger context)" if same else ""))
            reclaim += max(0, int(m.get("size") or 0) - int(m.get("size_vram") or 0)) / GIB
            free_vram_gb = (free_vram_gb or 0.0) + int(m.get("size_vram") or 0) / GIB
    if mine is not None:
        need_ram, need_gpu, source = 0.0, int(mine.get("size_vram") or 0) / GIB, "loaded"
    else:
        est = estimate(model, context, file_gb=file_gb, free_vram_gb=free_vram_gb)
        if est is None:
            return Fit("unknown", model, context, None, None, free_ram_gb, None, unload=unload)
        total, need_gpu, source = est
        need_ram = max(0.0, total - need_gpu)
    if free_ram_gb is None:
        return Fit("unknown", model, context, need_ram, need_gpu, None, None, source, unload)
    free = free_ram_gb + reclaim
    left = free - need_ram
    verdict = "ok" if left >= COMFORT_GB else "tight" if left >= 0 else "no"
    fit = Fit(verdict, model, context, round(need_ram, 1), round(need_gpu, 1), round(free, 1), round(left, 1),
              source, unload)
    if verdict != "ok":
        short = COMFORT_GB - left
        fit.close = pick_to_close(programs, short)
        fit.alternatives = list(alternatives or [])
    return fit


def pick_to_close(programs: list[Program], short_gb: float) -> list[Program]:
    """Biggest programs first, until they cover the shortfall (at most 5)."""
    out, freed = [], 0.0
    for p in sorted(programs, key=lambda p: p.gb, reverse=True):
        if p.gb < MIN_PROGRAM_GB or len(out) >= 5:
            break
        out.append(p)
        freed += p.gb
        if freed >= short_gb and len(out) >= 2:
            break
    return out


def _hint(cmdline: list[str]) -> str:
    """Short label for interpreters: 'langgraph dev', 'streamlit run app.py', 'script.py'."""
    words = [os.path.basename(str(w)) for w in cmdline[1:] if not str(w).startswith("-")]
    words = [w.removesuffix(".exe") for w in words if w.lower() not in ("python", "python.exe", "-m", "node")]
    return " ".join(words[:2])


def group_programs(procs, *, skip_pids: set[int] = frozenset()) -> list[Program]:
    """Group processes by name (Chrome's 30 processes are one program, L-008). `procs` yields
    (pid, name, rss_bytes, cmdline). Interpreters (python, node) are split by what they run."""
    groups: dict[str, Program] = {}
    for pid, name, rss, cmdline in procs:
        low = (name or "").lower()
        if pid in skip_pids or not low or low in _NEVER or not rss:
            continue
        key, hint = low, ""
        if low.removesuffix(".exe") in ("python", "pythonw", "python3", "node", "java", "javaw"):
            hint = _hint(cmdline or [])
            key = f"{low}|{hint}"
        g = groups.setdefault(key, Program(name.removesuffix(".exe"), 0.0, 0, hint))
        g.gb += rss / GIB
        g.count += 1
    progs = list(groups.values())
    for p in progs:
        p.gb = round(p.gb, 1)
    return sorted(progs, key=lambda p: p.gb, reverse=True)


# ── live facts ────────────────────────────────────────────────────────────────

def _ollama_ps(base_url: str) -> list[dict]:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/ps", timeout=5) as r:
            return json.loads(r.read().decode("utf-8") or "{}").get("models", []) or []
    except (OSError, ValueError):
        return []


def _own_pids() -> set[int]:
    """Mitra and the terminal it runs in (closing those closes Mitra)."""
    try:
        import psutil
        me = psutil.Process()
        return {me.pid} | {p.pid for p in me.parents()}
    except Exception:
        return {os.getpid()}


def live_programs() -> list[Program]:
    try:
        import psutil
    except ImportError:
        return []

    def rows():
        for p in psutil.process_iter(["pid", "name", "memory_info", "cmdline"]):
            try:
                info = p.info
                rss = getattr(info.get("memory_info"), "rss", 0) or 0
                yield info.get("pid") or 0, info.get("name") or "", rss, info.get("cmdline") or []
            except Exception:
                continue

    return group_programs(rows(), skip_pids=_own_pids())


def check(model: str, context: int, *, base_url: str = "http://127.0.0.1:11434") -> Fit:
    """Gather the live facts and assess. Process listing runs only when the fit is not comfortable."""
    from app import config

    gpu = config.get_gpu_memory_info()
    inv = {m.name: m for m in config.get_local_model_inventory()}
    info = inv.get(model) or inv.get(_norm(model))
    small = [n for n in ("qwen3.5:4b",) if n in inv and _norm(n) != _norm(model)]
    alternatives = [f"/model use {n}" for n in small]
    if context > 131_072:
        alternatives.append("/context 128k (half the context)")
    fit = assess(model, context, free_ram_gb=config.get_available_system_memory_gib(),
                 free_vram_gb=gpu.free_gib if gpu else None,
                 file_gb=getattr(info, "size_gib", None), loaded=_ollama_ps(base_url), programs=[],
                 alternatives=alternatives)
    if fit.verdict in ("tight", "no"):
        fit.close = pick_to_close(live_programs(), COMFORT_GB - (fit.left_gb or 0.0))
    return fit


# ── text ──────────────────────────────────────────────────────────────────────

_MARK = {"ok": "✓", "tight": "⚠", "no": "✗", "unknown": "?"}
_WORD = {"ok": "comfortable", "tight": "tight: may be slow, or fail on long chats",
         "no": "not enough free RAM: loading will likely fail or swap", "unknown": "could not check memory"}


def summary(fit: Fit) -> str:
    """One line, e.g. '✓ needs ~6.8 GB RAM + 5.2 GB GPU · 9.4 GB free · comfortable'."""
    parts = []
    if fit.source == "loaded":
        parts.append("already loaded")
    elif fit.need_ram_gb is not None:
        approx = "~" if fit.source == "estimate" else ""
        parts.append(f"needs {approx}{fit.need_ram_gb:.1f} GB RAM + {fit.need_gpu_gb:.1f} GB GPU")
    if fit.free_ram_gb is not None:
        parts.append(f"{fit.free_ram_gb:.1f} GB RAM free")
    parts.append(_WORD[fit.verdict])
    return f"{_MARK[fit.verdict]} " + " · ".join(parts)


def advice(fit: Fit) -> list[str]:
    """Extra lines when not comfortable: what Ollama unloads, what to close, smaller options."""
    lines = []
    if fit.unload:
        lines.append("Ollama will unload " + ", ".join(fit.unload) + " (counted as free)")
    if fit.close:
        names = [f"{p.name}{' (' + p.hint + ')' if p.hint else ''} {p.gb:.1f} GB" for p in fit.close]
        lines.append("Close to free RAM: " + " · ".join(names))
    if fit.alternatives:
        lines.append("Or: " + " · ".join(fit.alternatives) + " — both work right away")
    return lines


def markdown(fit: Fit) -> str:
    """For /doctor."""
    out = [f"- **Fit:** {summary(fit)}", f"- **Model:** {fit.model} at {fit.context:,} context"
           + (f" ({fit.source})" if fit.source else "")]
    if fit.left_gb is not None:
        out.append(f"- **RAM left after loading:** {fit.left_gb:.1f} GB (comfortable at {COMFORT_GB:.0f} GB or more)")
    out += [f"- {line}" for line in advice(fit)]
    return "\n".join(out)
