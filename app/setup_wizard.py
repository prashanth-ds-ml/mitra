"""`codemitra setup` (D-083): everything a new user needs after `git clone`, in one guided run that can be repeated.

Each step checks first and only acts when something is missing, so running it again is safe:
  1. Ollama        installed (asks, then winget / brew / the official script), running, two memory-saving settings
  2. Model         the one that fits this machine (GPU memory, RAM), downloaded
  3. Kaggle        optional free GPU: opens the page, says what to click, takes the token, checks hours + phone
  4. About you     your name for mails (~/.codemitra/me.md)
  5. Sharing       optional: your name in the shared logs repo, ask at exit
  6. Summary       what is ready, and the one command to start

What no script can do for you (Kaggle's rules): create the Kaggle account and verify your phone on kaggle.com.
The wizard opens the right page and waits.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass, field
from typing import Callable

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_DOWNLOAD = "https://ollama.com/download"
KAGGLE_SIGNUP = "https://www.kaggle.com/account/login?phase=startRegisterTab"
KAGGLE_SETTINGS = "https://www.kaggle.com/settings"
OLLAMA_SETTINGS = {"OLLAMA_FLASH_ATTENTION": "1", "OLLAMA_KV_CACHE_TYPE": "q8_0"}
SMALL, LARGE = "qwen3.5:4b", "qwen3.5:latest"   # 3.4 GB and 6.6 GB downloads
PULL_TIMEOUT_S = 3 * 3600
CMD_TIMEOUT_S = 900


@dataclass
class Machine:
    os: str                      # windows | mac | linux
    ram_gb: float | None
    vram_gb: float | None        # the biggest NVIDIA GPU; None = none found (or not NVIDIA)
    gpu: str = ""


@dataclass
class Result:
    step: str
    ok: bool | None              # True ready, False needs you, None skipped
    note: str


@dataclass
class IO:
    """Everything the wizard does to the outside, so tests run it with fakes."""
    say: Callable[[str], None] = print
    ask: Callable[[str, str], str] = lambda q, default="": input(f"{q} [{default}] ").strip() or default
    run: Callable[..., tuple[int, str]] = None  # (args, timeout, stream) -> (code, output)
    which: Callable[[str], str | None] = shutil.which
    open_url: Callable[[str], None] = lambda url: webbrowser.open(url)
    ollama_up: Callable[[], bool] = None
    sleep: Callable[[float], None] = time.sleep
    results: list = field(default_factory=list)

    def __post_init__(self):
        self.run = self.run or _run
        self.ollama_up = self.ollama_up or _ollama_up


def _run(args: list[str], timeout: float = CMD_TIMEOUT_S, stream: bool = False) -> tuple[int, str]:
    try:
        if stream:  # a download: show its progress as it goes
            p = subprocess.run(args, timeout=timeout)
            return p.returncode, ""
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def _ollama_up() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def yes(io: IO, question: str, default: bool = True, auto: bool = False) -> bool:
    if auto:  # --yes: the default, no question
        return default
    ans = io.ask(f"{question} ({'Y/n' if default else 'y/N'})", "y" if default else "n").lower()
    return ans.startswith("y")


# ── 0. the machine ───────────────────────────────────────────────────────────────────────────────────────────────
def machine(run=_run) -> Machine:
    osname = {"Windows": "windows", "Darwin": "mac"}.get(platform.system(), "linux")
    try:
        import psutil
        ram = round(psutil.virtual_memory().total / 2**30, 1)
    except Exception:
        ram = None
    vram, gpu = None, ""
    code, out = run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], 20)
    if code == 0 and out:
        best = None
        for line in out.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 2 and parts[1].replace(".", "").isdigit():
                gb = round(float(parts[1]) / 1024, 1)
                if best is None or gb > best[1]:
                    best = (parts[0], gb)
        if best:
            gpu, vram = best
    if osname == "mac" and platform.machine() == "arm64":
        vram, gpu = ram, "Apple silicon (shared memory)"
    return Machine(osname, ram, vram, gpu)


def pick_model(m: Machine) -> tuple[str, str]:
    """(model, why). The README table: 12 GB+ GPU (or 32 GB RAM, or a Mac with 24 GB+) → 9B, else 4B."""
    if (m.vram_gb or 0) >= 12 or (m.ram_gb or 0) >= 32 or (m.os == "mac" and (m.ram_gb or 0) >= 24):
        return LARGE, "this machine has room for the 9B model (better answers)"
    if (m.vram_gb or 0) >= 6:
        return SMALL, f"{m.vram_gb:g} GB GPU: the 4B model fits on it (the 9B would be slow here; use Kaggle for it)"
    return SMALL, "no big GPU found: the 4B model works but slowly here; a free Kaggle GPU is recommended (step 3)"


# ── 1. Ollama ────────────────────────────────────────────────────────────────────────────────────────────────────
def step_ollama(io: IO, m: Machine, auto: bool) -> Result:
    if not io.which("ollama"):
        io.say("Ollama runs the AI model on your machine. It is not installed yet.")
        if not yes(io, "Install Ollama now?", auto=auto):
            return Result("Ollama", False, f"not installed: get it from {OLLAMA_DOWNLOAD}, then run `codemitra setup` again")
        if m.os == "windows" and io.which("winget"):
            code, out = io.run(["winget", "install", "--id", "Ollama.Ollama", "-e", "--silent",
                                "--accept-source-agreements", "--accept-package-agreements"], CMD_TIMEOUT_S)
        elif m.os == "mac" and io.which("brew"):
            code, out = io.run(["brew", "install", "ollama"], CMD_TIMEOUT_S)
        elif m.os == "linux":
            io.say("Installing with Ollama's official script (it may ask for your password).")
            code, out = io.run(["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"], CMD_TIMEOUT_S, True)
        else:
            code, out = 1, "no package manager"
        if code != 0 or not (io.which("ollama") or _known_ollama_path(m)):
            io.open_url(OLLAMA_DOWNLOAD)
            return Result("Ollama", False, f"could not install it here ({out[:120]}); the download page is open: "
                                           "install it, then run `codemitra setup` again")
        io.say("✓ Ollama installed")
    if m.os == "windows":
        missing = {k: v for k, v in OLLAMA_SETTINGS.items() if os.environ.get(k) != v}
        if missing and yes(io, "Turn on Ollama's memory saver (halves the memory long chats need)?", auto=auto):
            for k, v in missing.items():
                io.run(["setx", k, v], 30)
                os.environ[k] = v
            io.say("✓ memory saver on (Ollama picks it up when it restarts)")
    elif any(os.environ.get(k) != v for k, v in OLLAMA_SETTINGS.items()):
        io.say("Tip: Ollama uses half the memory for long chats with " +
               " and ".join(f"{k}={v}" for k, v in OLLAMA_SETTINGS.items()) + " in its environment.")
    if not io.ollama_up():
        exe = io.which("ollama") or _known_ollama_path(m) or "ollama"
        _start_ollama(exe)
        for _ in range(20):
            if io.ollama_up():
                break
            io.sleep(1.5)
    if not io.ollama_up():
        return Result("Ollama", False, "installed but not running: start the Ollama app (or `ollama serve`), then run "
                                       "`codemitra setup` again")
    return Result("Ollama", True, "installed and running")


def _known_ollama_path(m: Machine) -> str | None:
    if m.os == "windows":
        p = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
        return p if os.path.isfile(p) else None
    return None


def _start_ollama(exe: str) -> None:
    try:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags if os.name == "nt" else 0, start_new_session=os.name != "nt")
    except OSError:
        pass


# ── 2. the model ─────────────────────────────────────────────────────────────────────────────────────────────────
def installed_models(io: IO) -> set[str]:
    code, out = io.run(["ollama", "list"], 60)
    if code != 0:
        return set()
    names = {line.split()[0] for line in out.splitlines()[1:] if line.strip()}
    return names | {n.replace(":latest", "") for n in names}


def step_model(io: IO, m: Machine, auto: bool, chosen: str = "") -> Result:
    from app import config
    have = installed_models(io)
    current = config.load_last_model()
    if chosen:
        model, why = chosen, "your choice"
    elif current and (current in have or current.replace(":latest", "") in have):
        return Result("Model", True, f"{current} ready (your current model; `--model` changes it)")
    else:
        model, why = pick_model(m)
    if model in have or model.replace(":latest", "") in have:
        config.save_last_model(model)
        return Result("Model", True, f"{model} ready ({why})")
    size = "6.6 GB" if model == LARGE else "3.4 GB"
    io.say(f"Model: {model} ({size} download) · {why}.")
    if not yes(io, f"Download {model} now?", auto=auto):
        return Result("Model", False, f"not downloaded: run `ollama pull {model}` when you are ready")
    code, _ = io.run(["ollama", "pull", model], PULL_TIMEOUT_S, True)
    if code != 0:
        return Result("Model", False, f"the download stopped: run `ollama pull {model}` again (it resumes)")
    config.save_last_model(model)
    return Result("Model", True, f"{model} downloaded ({why})")


# ── 3. Kaggle ────────────────────────────────────────────────────────────────────────────────────────────────────
def step_kaggle(io: IO, m: Machine, auto: bool, want: bool | None = None) -> Result:
    from app import backend
    from app import kaggle as K
    small = (m.vram_gb or 0) < 12
    if want is None:
        io.say("Kaggle gives every account ~30 free GPU hours a week. CodeMitra can run its model there (bigger model, "
               "3-4x faster) without you opening Kaggle." + (" Recommended for this machine." if small else ""))
        want = yes(io, "Set up the free Kaggle GPU?", default=small, auto=auto)
    decided = backend.kaggle_use() is not None  # never overwrite a choice you made before
    if not want:
        if not decided:
            backend.save_prefs(kaggle_use="never", onboarded=True)
        return Result("Kaggle", None, "skipped (later: `codemitra kaggle setup`)")
    if K.key_path().exists() or K.token_path().exists():
        if K.setup("", echo=lambda t: io.say("  " + t)):
            if not decided:
                backend.save_prefs(kaggle_use="when-needed", onboarded=True)
            return Result("Kaggle", True, "signed in; it starts by itself when you need it (`codemitra kaggle start`)")
    io.say("Kaggle needs two things only you can do on its website (2 minutes):\n"
           "  1. a free account (skip if you have one): sign up with Google or email\n"
           "  2. your phone verified: Settings → Phone verification (Kaggle needs it for GPUs)\n"
           "Then the key for CodeMitra: Settings → API → Generate New Token → copy it.")
    if auto:
        return Result("Kaggle", False, "needs you once: `codemitra kaggle setup` (or run `codemitra setup` without --yes)")
    if yes(io, "Open Kaggle in your browser now?"):
        io.open_url(KAGGLE_SETTINGS)
    for _ in range(3):
        token = io.ask("Paste the token here (or press Enter if your browser downloaded kaggle.json; 'skip' to stop)",
                       "").strip()
        if token.lower() == "skip":
            break
        if K.setup(token, echo=lambda t: io.say("  " + t)):
            if not decided:
                backend.save_prefs(kaggle_use="when-needed", onboarded=True)
            return Result("Kaggle", True, "signed in; it starts by itself when you need it (`codemitra kaggle start`)")
    return Result("Kaggle", False, "not set up yet: `codemitra kaggle setup <token>` any time")


# ── 4. about you, 5. sharing ─────────────────────────────────────────────────────────────────────────────────────
def step_me(io: IO, auto: bool) -> Result:
    from app.core import harness as H
    from app.core import signals as SIG
    SIG.ensure_me()
    me = H.home() / "me.md"
    text = me.read_text(encoding="utf-8") if me.exists() else ""
    current = next((ln.split(":", 1)[1].strip() for ln in text.splitlines() if ln.strip().startswith("Name:")), "")
    if current:
        return Result("About you", True, f"{me}")
    name = "" if auto else io.ask("Your first name (CodeMitra signs mails you draft with it; Enter skips)", "")
    if name:
        lines = [(f"Name: {name}" if ln.strip().startswith("Name:") else ln.replace("<your name>", name))
                 for ln in text.splitlines()]
        if not any(ln.startswith("Name:") for ln in lines):
            lines.append(f"Name: {name}")
        me.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Result("About you", True, f"{me} (edit it any time: tone, mail signature, your stack)")


def step_share(io: IO, auto: bool, want: bool | None = None) -> Result:
    from app.core import share as SH
    cur = SH.settings()
    if cur.get("name"):
        return Result("Sharing", True, f"as people/{SH.friend_name()}/ in {cur.get('repo', SH.DEFAULT_REPO)}")
    if want is None:
        io.say("Sharing your sessions (light and scrubbed: no file contents, tokens or paths, a preview every time) "
               "helps CodeMitra learn from everyone. It needs a GitHub account added to the private logs repo.")
        want = yes(io, "Set up sharing?", default=not auto, auto=auto)
    if not want:
        return Result("Sharing", None, "skipped (later: `codemitra share --setup`)")
    name = io.ask("Your name for the logs repo", SH.friend_name())
    mode = io.ask("Ask to share each session when you exit? ask / always / never", "ask")
    SH.save_settings(name=name, repo=cur.get("repo") or SH.DEFAULT_REPO, at_exit=mode if mode in SH.AT_EXIT else "ask")
    ok, _ = SH.check_access(SH.settings()["repo"])
    if ok:
        return Result("Sharing", True, f"as people/{SH.friend_name()}/ · at exit: {SH.settings()['at_exit']}")
    gh = "`gh auth login` then `gh auth setup-git`" if io.which("gh") else "install GitHub CLI (cli.github.com), then " \
         "`gh auth login` and `gh auth setup-git`"
    return Result("Sharing", False, f"set up; send Prashanth your GitHub username to be added, accept the invite, "
                                    f"then {gh}")


# ── the whole run ────────────────────────────────────────────────────────────────────────────────────────────────
def run(io: IO | None = None, *, auto: bool = False, model: str = "", kaggle: bool | None = None,
        share: bool | None = None) -> list[Result]:
    io = io or IO()
    m = machine(io.run)
    mem = f"{m.ram_gb:g} GB RAM" if m.ram_gb else "RAM unknown"
    io.say(f"This machine: {m.os}, {mem}, " + (f"{m.gpu} {m.vram_gb:g} GB" if m.vram_gb else "no NVIDIA GPU found"))
    results = [step_ollama(io, m, auto)]
    if results[0].ok:
        results.append(step_model(io, m, auto, model))
    else:
        results.append(Result("Model", False, "needs Ollama first"))
    results.append(step_kaggle(io, m, auto, kaggle))
    results.append(step_me(io, auto))
    results.append(step_share(io, auto, share))
    return results


def summary(results: list[Result]) -> str:
    mark = {True: "✓", False: "✗", None: "–"}
    lines = [f"  {mark[r.ok]} {r.step:10s} {r.note}" for r in results]
    ready = all(r.ok is not False for r in results if r.step in ("Ollama", "Model")) or any(
        r.step == "Kaggle" and r.ok for r in results)
    lines.append("")
    lines.append("Ready. Go to a project folder and run:  codemitra" if ready else
                 "Not ready yet: fix the ✗ lines above, then run `codemitra setup` again (it skips what is done).")
    return "\n".join(lines)
