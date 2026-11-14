"""Where the model runs: this laptop or a remote (Kaggle), and switching between them (D-062, docs/BACKENDS.md).

Pure decisions live here so they can be tested; the chat (app/main.py) applies them between turns:
- `Health`: a background check of the remote every 60 s (status calls only: never counts as Kaggle use) and the
  Kaggle hours left (every 10 min).                                                                        (B0)
- `status_text`: `☁ kaggle · qwen3.5 256K · 28.1 h left` / `💻 laptop · qwen3.5 64K`.                         (B1)
- `laptop_choice`: the laptop model + context that fits the free memory, quietly smaller when RAM is short. (B2)
- `route`: read work (plan mode, planner, reviewer) on the laptop, write work on the remote.               (B5)
- `prefs`: remembered answers (first-start Kaggle offer, "not this session").                              (B6)
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

LAPTOP, REMOTE = "laptop", "remote"
LAPTOP_MODES = {"plan", "read-only"}           # read-only work
LAPTOP_ROLES = {"planner", "reviewer"}         # thinking and reviewing: no edits
HEALTH_EVERY_S = 60
HOURS_EVERY_S = 600
LOW_HOURS = 1.0
FALLBACK_SMALL = "qwen3.5:4b"


# ── B5: read on the laptop, write on the remote ───────────────────────────────

def route(mode: str, role: str) -> str:
    """Which machine this kind of work should use when a remote is up. Switches happen between turns only."""
    if (mode or "").lower() in LAPTOP_MODES or (role or "").lower() in LAPTOP_ROLES:
        return LAPTOP
    return REMOTE


TALK_FIT = 0.8  # the conversation may fill this much of the laptop's context, the rest is the answer's room


def talk_on_laptop(kind: str, architecture: str, ctx_used: int, laptop_ctx: int) -> bool:
    """D-074: while the work runs on the remote, a phased turn's decide / talk call runs on the laptop, but only when
    the whole conversation fits the laptop's context (a chat grown on Kaggle's 256K is never cut to talk on 64K:
    that turn stays on the remote)."""
    return (kind == REMOTE and architecture == "phased" and laptop_ctx > 0
            and (ctx_used or 0) <= TALK_FIT * laptop_ctx)


def why(kind: str, mode: str, role: str) -> str:
    if kind == LAPTOP:
        return "plan mode: read work on the laptop" if (mode or "").lower() in LAPTOP_MODES else \
            f"{role} role: read work on the laptop"
    return "write work on the remote GPU"


# ── B2: a laptop model that fits ──────────────────────────────────────────────

def parse_choice(text: str) -> tuple[str, int]:
    """'mimo-v2.6:9b@128k' -> ('mimo-v2.6:9b', 131072); no '@' -> (name, 0) = the model's own setting."""
    name, _, size = text.strip().partition("@")
    size = size.strip().lower()
    n = int(size[:-1]) * 1024 if size.endswith("k") and size[:-1].isdigit() else int(size) if size.isdigit() else 0
    return name.strip(), n


def candidates(preferred: str, preferred_ctx: int, installed: set[str], configured=None) -> list[tuple[str, int]]:
    """Laptop models to try, best first: codemitra.toml `laptop_models`, else the preferred model at its laptop context,
    at 64K, then the 4B at 64K and 32K. Only installed models (an empty `installed` = unknown: keep all)."""
    if configured:
        out = [parse_choice(c) for c in configured]
        out = [(m, c or preferred_ctx) for m, c in out]
    else:
        out = [(preferred, preferred_ctx), (preferred, 65_536), (FALLBACK_SMALL, 65_536), (FALLBACK_SMALL, 32_768)]
    seen, keep = set(), []
    for m, c in out:
        if (m, c) in seen or not m or not c or (installed and m not in installed):
            continue
        seen.add((m, c))
        keep.append((m, c))
    return keep


def laptop_choice(preferred: str, preferred_ctx: int, installed: set[str], fits, configured=None) -> tuple[str, int, str]:
    """(model, context, note). `fits(model, ctx)` returns the memory verdict ("ok"/"tight"/"no"/"unknown").
    The first candidate that is ok or tight wins, quietly (the user's answer 3); note says when it is smaller."""
    cands = candidates(preferred, preferred_ctx, installed, configured) or [(preferred, preferred_ctx)]
    for i, (m, c) in enumerate(cands):
        verdict = fits(m, c)
        if verdict in ("ok", "tight", "unknown"):
            note = "" if i == 0 else f"RAM is short: {m} at {c // 1024}K instead of {preferred} at {preferred_ctx // 1024}K"
            return m, c, note
    m, c = cands[-1]
    return m, c, f"RAM is short even for {m} at {c // 1024}K: it may be slow (`/free` closes programs)"


# ── B0: health of the remote ──────────────────────────────────────────────────

@dataclass
class HealthState:
    state: str = "none"              # none | up | down | starting
    name: str = ""                   # e.g. "kaggle"
    hours_left: float | None = None
    hours_total: float | None = None
    last_ok: float = 0.0
    error: str = ""
    stage: str = ""                  # while a background Kaggle start runs: "loading the model", ...
    checked: float = 0.0


class Health:
    """Checks the remote in a background thread. `probe(url) -> (models, error)`, `quota() -> dict | None`."""

    def __init__(self, *, probe=None, quota=None, active=None, interval: float = HEALTH_EVERY_S,
                 hours_every: float = HOURS_EVERY_S, clock=time.time):
        from app import remote
        self._probe = probe or (lambda url: remote.probe(url, timeout=15))
        self._quota = quota
        self._active = active or remote.active
        self.interval, self.hours_every, self.clock = interval, hours_every, clock
        self.s = HealthState()
        self._hours_at = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def check(self) -> HealthState:
        r = self._active()
        with self._lock:
            if not r:
                if self.s.state != "starting":
                    self.s.state, self.s.name, self.s.error = "none", "", ""
                return self.s
            self.s.name = str(r.get("name") or "remote")
        _, err = self._probe(r["url"])
        now = self.clock()
        with self._lock:
            self.s.checked = now
            if err:
                self.s.state, self.s.error = "down", err
            else:
                self.s.state, self.s.error, self.s.last_ok, self.s.stage = "up", "", now, ""
        if not err and self._quota and self.s.name == "kaggle" and now - self._hours_at >= self.hours_every:
            try:
                q = self._quota()
                if q:
                    with self._lock:
                        self.s.hours_left, self.s.hours_total = q.get("left_h"), q.get("total_h")
                self._hours_at = now
            except Exception:  # noqa: BLE001 - hours are a nice-to-have
                pass
        return self.s

    def starting(self, stage: str) -> None:
        with self._lock:
            self.s.state, self.s.stage, self.s.name = "starting", stage, "kaggle"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def loop():
            while True:
                try:
                    self.check()
                except Exception:  # noqa: BLE001 - a health check must never break the chat
                    pass
                if self._stop.wait(self.interval):
                    break

        self._thread = threading.Thread(target=loop, daemon=True, name="codemitra-health")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


# ── B1: the status text ───────────────────────────────────────────────────────

def status_text(kind: str, model: str, num_ctx: int, h: HealthState) -> tuple[str, str]:
    """(text, level) for the status line; level: ok | warn | err | info."""
    short = model.split(":")[0]
    ctx = f"{num_ctx // 1024}K" if num_ctx else ""
    if kind == REMOTE:
        if h.state == "down":
            return f"☁ {h.name or 'remote'} not answering · {short} {ctx}", "err"
        hours = ""
        level = "ok"
        if h.hours_left is not None:
            hours = f" · {h.hours_left:.1f} h left"
            if h.hours_left < LOW_HOURS:
                level = "warn"
        return f"☁ {h.name or 'remote'} · {short} {ctx}{hours}", level
    extra = ""
    if h.state == "starting":
        extra = f" · ☁ starting: {h.stage}" if h.stage else " · ☁ starting"
    elif h.state == "up":
        extra = f" · ☁ {h.name} ready"
    return f"💻 laptop · {short} {ctx}{extra}", "info" if extra else "ok"


# ── B6: remembered answers ────────────────────────────────────────────────────

def _prefs_file() -> Path:
    from app import config
    return config._mitra_home() / "backend.json"


def prefs() -> dict:
    try:
        data = json.loads(_prefs_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_prefs(**kw) -> dict:
    data = {**prefs(), **kw}
    f = _prefs_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


@dataclass
class Session:
    """Per chat session: where we are now, and what the user said for this session only."""
    kind: str = LAPTOP
    no_kaggle_this_session: bool = False
    asked_start: bool = False
    notes: list = field(default_factory=list)


# ── D-064: does the user want Kaggle, and when ───────────────────────────────

USE_VALUES = ("now", "when-needed", "never")
USE_TEXT = {"now": "starts in the background when CodeMitra starts",
            "when-needed": "starts in the background on your first write work",
            "never": "not used: this machine only"}


def kaggle_use() -> str | None:
    """The user's answer: now | when-needed | never, or None = not asked yet (or 'later')."""
    p = prefs()
    use = p.get("kaggle_use")
    if use in USE_VALUES:
        return use
    if p.get("kaggle_offer") == "no":  # an explicit "No" given in v0.2.0
        return "never"
    return None  # v0.2.0 also saved a silent "yes" for anyone with a key: ask them properly now


def asked_later_today(today: str | None = None) -> bool:
    """'Later' asks again at the next start, at most once a day."""
    return prefs().get("later_day") == (today or time.strftime("%Y-%m-%d"))
