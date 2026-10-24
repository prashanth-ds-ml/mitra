"""Preflight: refuse to start a benchmark run when the machine is not ready (L-002, L-008).

    python bench/preflight.py --model qwen3.5:4b [--ollama http://127.0.0.1:11434] [--min-free-ram-gb 11]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

import psutil

DEFAULT_MIN_FREE_RAM_GB = 11.0  # Ollama maps ~8 GB of RAM on Windows (L-008)


def _get_json(url: str, timeout: float = 5.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
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


def check(ollama: str, model: str, min_free_ram_gb: float = DEFAULT_MIN_FREE_RAM_GB) -> tuple[dict, list[str]]:
    """Return (facts to record with the run, problems that block it)."""
    facts: dict = {"ollama": ollama, "model": model}
    problems: list[str] = []

    try:
        facts["ollama_version"] = _get_json(f"{ollama}/api/version").get("version")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        problems.append(f"Ollama not reachable at {ollama}: {exc}")
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

    free_gb = psutil.virtual_memory().available / 2**30
    facts["free_ram_gb"] = round(free_gb, 1)
    if free_gb < min_free_ram_gb:
        problems.append(f"free RAM {free_gb:.1f} GB < {min_free_ram_gb} GB; close heavy apps first")

    facts["gpu"] = gpu_status()
    return facts, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True)
    parser.add_argument("--ollama", default="http://127.0.0.1:11434")
    parser.add_argument("--min-free-ram-gb", type=float, default=DEFAULT_MIN_FREE_RAM_GB)
    args = parser.parse_args(argv)
    facts, problems = check(args.ollama, args.model, args.min_free_ram_gb)
    print(json.dumps(facts, indent=2))
    for problem in problems:
        print(f"BLOCKED: {problem}")
    print("ready" if not problems else "not ready")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
