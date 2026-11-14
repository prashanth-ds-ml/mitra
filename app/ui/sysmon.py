"""This machine, for the status line: CPU %, free RAM, GPU memory / load / temperature (user, 2026-11-11).

A daemon thread samples every 2 s, so drawing the status line (every 0.5 s and on every key) never waits on
nvidia-smi. Anything missing (no NVIDIA GPU, psutil fails) is simply left out.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, replace

INTERVAL_S = 2.0
GPU_QUERY = ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"]


@dataclass(frozen=True)
class Sample:
    cpu_pct: float | None = None
    ram_free_gb: float | None = None
    gpu_used_gb: float | None = None
    gpu_total_gb: float | None = None
    gpu_pct: float | None = None
    gpu_temp_c: float | None = None


def parse_gpu(text: str) -> tuple[float, float, float, float] | None:
    """'409, 8151, 11, 60' (MiB, MiB, %, °C) -> (used GB, total GB, load %, temp). First GPU only."""
    try:
        used, total, load, temp = (float(x.strip()) for x in (text or "").strip().splitlines()[0].split(","))
    except (ValueError, IndexError):
        return None
    return used / 1024, total / 1024, load, temp


def sample() -> Sample:
    cpu = ram = None
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().available / 1024 ** 3
    except Exception:  # noqa: BLE001 - a missing number, never a broken status line
        pass
    gpu = None
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(GPU_QUERY, capture_output=True, text=True, timeout=2,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            gpu = parse_gpu(out.stdout) if out.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            gpu = None
    return Sample(cpu, ram, *(gpu or (None, None, None, None)))


class Monitor:
    def __init__(self, interval_s: float = INTERVAL_S, sampler=sample):
        self.interval_s, self._sampler = interval_s, sampler
        self.last = Sample()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> "Monitor":
        if self._thread is None:
            # psutil's first CPU reading is always 0: leave CPU out until the first real one, 2 s later
            self.last = replace(self._sampler(), cpu_pct=None)
            self._thread = threading.Thread(target=self._run, name="codemitra-sysmon", daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            try:
                self.last = self._sampler()
            except Exception:  # noqa: BLE001
                pass


_monitor: Monitor | None = None


def current() -> Sample:
    """The latest sample; starts the sampler on first use."""
    global _monitor
    if _monitor is None:
        _monitor = Monitor().start()
    return _monitor.last


def segments(s: Sample, *, speed: float | None = None, slow: bool = False, ram_warn_gb: float = 2.0,
             compact: bool = False) -> list[tuple[str, str]]:
    """The right-hand block: '24 tok/s · CPU 18% · RAM 3.7G free · GPU 5.2/8G 41% 63°C' (compact: shorter).
    Orange: a slow answer (the model spilled to the CPU), free RAM below what is needed, a hot GPU."""
    out: list[tuple[str, str]] = []

    def add(text: str, warn: bool = False) -> None:
        if out:
            out.append(("class:status", " · "))
        out.append(("class:status.warn" if warn else "class:status", text))

    if speed:
        add(f"{speed:.0f} tok/s", slow)
    if s.cpu_pct is not None:
        add(f"CPU {s.cpu_pct:.0f}%")
    if s.ram_free_gb is not None:
        add(f"RAM {s.ram_free_gb:.1f}G" + ("" if compact else " free"), s.ram_free_gb < ram_warn_gb)
    if s.gpu_used_gb is not None:
        hot = (s.gpu_temp_c or 0) >= 85
        if compact:
            add(f"GPU {s.gpu_pct:.0f}%", hot)
        else:
            add(f"GPU {s.gpu_used_gb:.1f}/{s.gpu_total_gb:.0f}G {s.gpu_pct:.0f}% {s.gpu_temp_c:.0f}°C", hot)
    return out


def working_footer(seconds: float, sample: Sample, *, speed: float | None = None, slow: bool = False,
                   ram_warn_gb: float = 2.0, writing: bool = True):
    """The line under the live part while CodeMitra works (user, 2026-11-11: the status line vanished during a turn):
    '  working 12s · 24 tok/s · CPU 35% · RAM 4.1G free · GPU 5.2/8G 92% 74°C   esc to stop'. Rich Text."""
    from rich.text import Text

    t = Text(f"  working {seconds:.0f}s", style="m.faint")
    parts = segments(sample, speed=speed, slow=slow, ram_warn_gb=ram_warn_gb)
    if parts:
        t.append(" · ", style="m.faint")
    for style, piece in parts:  # segments() already holds the " · " separators
        t.append(piece, style="m.err" if style == "class:status.warn" else "m.faint")
    if writing:  # while thinking, the spinner above already says esc to stop
        t.append("   esc to stop", style="m.faint")
    return t
