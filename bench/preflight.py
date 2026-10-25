"""Preflight: refuse to start a benchmark run when the machine is not ready (L-001, L-002, L-008).

Checks: Ollama reachable, model pulled, no other model loaded, free RAM >= model size + headroom, and the
context the model really gets when an agent sends no num_ctx (loads the model once to read it from /api/ps).

    python bench/preflight.py --model qwen3.5:4b [--ollama http://127.0.0.1:11435] [--min-free-ram-gb N]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ollama_server import CONTEXT as BENCH_CONTEXT  # noqa: E402
from ollama_server import URL as BENCH_OLLAMA  # noqa: E402

HEADROOM_GB = 3.0  # Ollama maps the model file into RAM on Windows, plus runner buffers (L-008)


def _get_json(url: str, timeout: float = 5.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def _post_json(url: str, payload: dict, timeout: float = 300.0) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def gpu_status() -> dict | None:
    """Used / total GPU memory in MiB, or None when nvidia-smi is not available."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip().splitlines()[0]
    except (subprocess.SubprocessError, OSError, IndexError):
        return None
    name, used, total = (part.strip() for part in out.split(","))
    return {"name": name, "used_mib": int(used), "total_mib": int(total)}


def loaded_context(ollama: str, model: str) -> dict:
    """Load the model with no options (as most agents do) and report the context and GPU share it got."""
    _post_json(f"{ollama}/api/generate", {"model": model, "prompt": "", "stream": False})
    entry = next(
        (m for m in _get_json(f"{ollama}/api/ps").get("models", []) if model in (m.get("name"), m.get("model"))), {}
    )
    size, vram = entry.get("size") or 0, entry.get("size_vram") or 0
    return {"context_length": entry.get("context_length"), "gpu_share": round(vram / size, 3) if size else None}


def check(
    ollama: str, model: str, min_free_ram_gb: float | None = None, min_context: int | None = BENCH_CONTEXT
) -> tuple[dict, list[str]]:
    """Return (facts to record with the run, problems that block it)."""
    facts: dict = {"ollama": ollama, "model": model}
    problems: list[str] = []

    try:
        facts["ollama_version"] = _get_json(f"{ollama}/api/version").get("version")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        problems.append(f"Ollama not reachable at {ollama}: {exc} (start it: python bench/ollama_server.py)")
        return facts, problems

    tags = _get_json(f"{ollama}/api/tags").get("models", [])
    match = next((m for m in tags if m.get("name") == model or m.get("model") == model), None)
    if match is None:
        problems.append(f"model {model} is not pulled (ollama pull {model})")
    else:
        facts["model_digest"] = match.get("digest")
        facts["model_details"] = match.get("details")

    loaded = [m.get("name") for m in _get_json(f"{ollama}/api/ps").get("models", [])]
    facts["loaded_models"] = loaded
    if any(name != model for name in loaded):
        problems.append(f"other models are loaded and compete for memory: {loaded}")

    if min_free_ram_gb is None:  # a model already loaded holds its RAM already (E-009)
        model_gb = 0 if model in loaded else ((match or {}).get("size") or 0) / 2**30
        min_free_ram_gb = round(model_gb + HEADROOM_GB, 1)
    free_gb = psutil.virtual_memory().available / 2**30
    facts["free_ram_gb"] = round(free_gb, 1)
    facts["min_free_ram_gb"] = min_free_ram_gb
    if free_gb < min_free_ram_gb:
        problems.append(f"free RAM {free_gb:.1f} GB < {min_free_ram_gb} GB needed for {model}; close heavy apps first")

    facts["gpu"] = gpu_status()
    if min_context and not problems:
        try:
            facts["loaded"] = loaded_context(ollama, model)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            problems.append(f"could not load {model}: {exc}")
            return facts, problems
        got = facts["loaded"]["context_length"]
        if not got or got < min_context:
            problems.append(f"{model} loads with context {got} < {min_context}; use the bench server (bench/ollama_server.py)")
    return facts, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True)
    parser.add_argument("--ollama", default=BENCH_OLLAMA)
    parser.add_argument("--min-free-ram-gb", type=float)
    args = parser.parse_args(argv)
    facts, problems = check(args.ollama, args.model, args.min_free_ram_gb)
    print(json.dumps(facts, indent=2))
    for problem in problems:
        print(f"BLOCKED: {problem}")
    print("ready" if not problems else "not ready")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
