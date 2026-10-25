"""Bench-owned Ollama server: same models on disk, separate port, fixed settings for every agent (D-016).

The user's own Ollama on 11434 is left alone. This one listens on 11435 with a 64K default context (Ollama's
documented minimum for Claude Code, Codex and OpenCode; its 4K default truncates silently, L-001), one model
loaded at a time (L-008) and one request at a time (parallel slots multiply the KV cache).

    python bench/ollama_server.py            # runs in the foreground; log in results/ollama-bench.log
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PORT = 11435
URL = f"http://127.0.0.1:{PORT}"
CONTEXT = 65536
SETTINGS = {
    "OLLAMA_HOST": f"127.0.0.1:{PORT}",
    "OLLAMA_CONTEXT_LENGTH": str(CONTEXT),
    "OLLAMA_MAX_LOADED_MODELS": "1",
    "OLLAMA_NUM_PARALLEL": "1",
    "OLLAMA_KEEP_ALIVE": "10m",
}
LOG = Path(__file__).resolve().parents[1] / "results" / "ollama-bench.log"


def server_env(base: dict[str, str]) -> dict[str, str]:
    return {**base, **SETTINGS}


def main() -> int:
    exe = shutil.which("ollama")
    if not exe:
        print("ollama not found on PATH")
        return 1
    LOG.parent.mkdir(parents=True, exist_ok=True)
    print(f"bench Ollama on {URL}, settings {SETTINGS}, log {LOG}", flush=True)
    with LOG.open("a", encoding="utf-8") as log:
        return subprocess.call([exe, "serve"], env=server_env(dict(os.environ)), stdout=log, stderr=log)


if __name__ == "__main__":
    sys.exit(main())
