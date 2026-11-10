"""Remote Ollama (I-23, D-060): run Mitra's model on a bigger GPU elsewhere, e.g. a Kaggle notebook, at full context.

The notebook (remote/kaggle/) starts Ollama behind a small token proxy and a Cloudflare quick tunnel, and prints
    mitra remote set https://<name>.trycloudflare.com/<token> --ctx 262144
The token is part of the URL path, so every client (ChatOllama, urllib calls, the night runner) just uses it as the
base URL. While a remote is set:
- every Ollama call goes there (`ollama_local_base_url` and OLLAMA_HOST), also in `/run` night children;
- the context is the remote's (`num_ctx`), unless mitra.toml sets one;
- the local memory check and `/free` are skipped (your laptop's RAM is not used);
- sessions are recorded with `remote = <name>`: energy is not measured there, and the dashboard can split it out.
`mitra remote off` goes back to the local Ollama.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

DEFAULT_CTX = 262_144


def _file() -> Path:
    from app import config
    return config._mitra_home() / "remote.json"


def active() -> dict | None:
    """The remote in use, or None. {"url", "name", "num_ctx", "set"}."""
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("url") else None


def clean_url(url: str) -> str:
    url = url.strip().rstrip("/")
    for tail in ("/api", "/v1"):
        url = url.removesuffix(tail)
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def shown(url: str) -> str:
    """The URL without its token, for screens and records."""
    parts = url.split("/")
    return "/".join(parts[:3]) + ("/…" if len(parts) > 3 else "")


def probe(url: str, timeout: float = 20.0) -> tuple[list[dict], str]:
    """(models on the remote, error). Uses /api/tags; the token is in the URL."""
    try:
        with urllib.request.urlopen(url + "/api/tags", timeout=timeout) as r:
            return list(json.loads(r.read().decode("utf-8") or "{}").get("models") or []), ""
    except Exception as exc:  # noqa: BLE001 - shown to the user as is
        return [], f"{type(exc).__name__}: {exc}"


def set_remote(url: str, num_ctx: int = DEFAULT_CTX, name: str = "kaggle") -> dict:
    data = {"url": clean_url(url), "name": name, "num_ctx": int(num_ctx), "set": time.time()}
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


def clear() -> bool:
    try:
        _file().unlink()
        return True
    except OSError:
        return False


def apply(cfg: dict) -> dict:
    """Point this process (and the processes it starts) at the remote; called at the end of config.load."""
    r = active()
    if not r:
        return cfg
    if "_local" not in cfg:  # what to go back to when the remote stops (unapply)
        cfg["_local"] = {"ollama_local_base_url": cfg.get("ollama_local_base_url"), "num_ctx": cfg.get("num_ctx"),
                         "OLLAMA_HOST": os.environ.get("OLLAMA_HOST")}
    cfg["ollama_local_base_url"] = r["url"]
    os.environ["OLLAMA_HOST"] = r["url"]  # config._ollama_base_url, and inherited by /run night children
    if not cfg.get("num_ctx"):
        cfg["num_ctx"] = int(r.get("num_ctx") or DEFAULT_CTX)
    cfg["remote"] = r.get("name") or "remote"
    return cfg


def unapply(cfg: dict) -> dict:
    """Back to this machine in a running Mitra (`/kaggle stop`): the settings `apply` replaced."""
    local = cfg.pop("_local", None)
    cfg.pop("remote", None)
    if local is None:
        return cfg
    cfg["ollama_local_base_url"] = local.get("ollama_local_base_url") or "http://localhost:11434"
    cfg["num_ctx"] = local.get("num_ctx") or 0
    if local.get("OLLAMA_HOST"):
        os.environ["OLLAMA_HOST"] = local["OLLAMA_HOST"]
    else:
        os.environ.pop("OLLAMA_HOST", None)
    return cfg


def check_alive(cfg: dict, echo=print, timeout: float = 15.0) -> bool:
    """At start: a remote that does not answer is not used (E-067: a Kaggle run that stopped by itself left Mitra
    asking a dead address, which then said "no compatible local Ollama models"). A dead Kaggle address is forgotten
    (each session gets a new one); another remote stays set but this run uses this machine. True = remote in use."""
    if not cfg.get("remote"):
        return False
    r = active()
    if not r:
        unapply(cfg)
        return False
    _, err = probe(r["url"], timeout=timeout)
    if not err:
        return True
    name = r.get("name") or "remote"
    unapply(cfg)
    cfg["_remote_died"] = name  # the chat writes the "Kaggle ended" report on the last session (D-062 B3)
    if name == "kaggle":
        clear()
        echo("☁ the Kaggle GPU is not answering: its run has ended (30 min unused, its time limit, or stopped on "
             "Kaggle). Using this machine's Ollama. `mitra kaggle start` starts a new one.")
    else:
        echo(f"☁ {name} ({shown(r['url'])}) is not answering: using this machine's Ollama for now. "
             "`mitra remote off` forgets it.")
    return False


def tag_rows(models: list[dict]) -> list[tuple[str, str, str]]:
    """/api/tags models as `ollama list` rows: (name, size value, size unit)."""
    out = []
    for m in models:
        size = float(m.get("size") or 0) / 1e9
        out.append((str(m.get("name") or m.get("model") or ""), f"{size:.1f}", "GB"))
    return [row for row in out if row[0]]
