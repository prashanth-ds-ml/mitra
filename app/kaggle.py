"""`mitra kaggle start | stop | status` (D-061): use your Kaggle GPU hours from Mitra, without opening Kaggle.

start: checks your weekly GPU quota, uploads a PRIVATE notebook (remote/kaggle/, GPU T4 x2, internet on) with this
       session's random token in it, follows its live log (lines `MITRA|stage|key=value`), and when it says `ready`
       points Mitra at it (`app.remote`, every workspace). Typically 4-8 minutes (install, model download, load).
stop:  asks the notebook to shut down (POST /<token>/mitra/stop), so the Kaggle run ends and stops using hours;
       Mitra goes back to this machine. The notebook also stops by itself after `idle_min` unused minutes, and the
       run has a hard time limit (`max_hours`), so a forgotten session cannot eat the week.
status: the run's state, whether it answers, and Kaggle's own count of your GPU hours (used / total / reset).

Works for any Kaggle account: credentials from ~/.kaggle/kaggle.json (Kaggle → Settings → API → Create New Token) or
KAGGLE_USERNAME / KAGGLE_KEY. Needs the `kaggle` package (a Mitra dependency).
"""
from __future__ import annotations

import json
import re
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue

SLUG = "mitra-gpu-server"
ACCELERATOR = "NvidiaTeslaT4"   # Kaggle's "GPU T4 x2"
API_TIMEOUT_S = 60
STAGE_RE = re.compile(r"MITRA\|([a-z_]+)((?:\|[a-z_]+=[^|\r\n\"\\]*)*)")
STAGE_TEXT = {
    "started": "notebook started",
    "installing": "installing Ollama",
    "pulling": "downloading the model",
    "loading": "loading it at full context",
    "loaded": "model loaded",
    "tunnel": "opening the tunnel",
    "ready": "ready",
}


class KaggleError(Exception):
    """A problem the user can fix; the message says how."""


def _home() -> Path:
    from app import config
    return config._mitra_home()


def _state_file() -> Path:
    return _home() / "kaggle.json"


def load_state() -> dict:
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(data: dict) -> None:
    f = _state_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=1), encoding="utf-8")


def _timed(fn, *args, timeout: float = API_TIMEOUT_S, **kw):
    """Every Kaggle API call gets a timeout (CLAUDE.md non-negotiable)."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(fn, *args, **kw).result(timeout=timeout)
    except FutureTimeout as exc:
        raise KaggleError(f"Kaggle did not answer within {timeout:.0f} s; try again in a minute.") from exc
    finally:
        pool.shutdown(wait=False)


def client():
    """An authenticated KaggleApi, or KaggleError saying what to do."""
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as exc:  # missing, or one of its own packages missing (E-065: six)
        raise KaggleError(f"The `kaggle` package cannot load ({exc}). With Mitra closed, reinstall Mitra: "
                          "`uv tool install --reinstall -e <mitra folder>` (forward slashes in Git Bash).") from exc
    except (SystemExit, OSError) as exc:  # older kaggle versions authenticate on import
        raise KaggleError(_CREDS_HELP) from exc
    api = KaggleApi()
    try:
        _timed(api.authenticate)
    except (SystemExit, OSError, ValueError, KaggleError) as exc:
        raise KaggleError(_CREDS_HELP + f" ({exc})") from exc
    return api


_CREDS_HELP = ("No Kaggle API key found. On kaggle.com: your picture → Settings → API → Create New Token; save the "
               "downloaded kaggle.json as ~/.kaggle/kaggle.json (Windows: C:\\Users\\<you>\\.kaggle\\kaggle.json). "
               "Also verify your phone in Settings (notebooks need it for internet).")


def username(api) -> str:
    for getter in (lambda: api.get_config_value("username"), lambda: api.config_values.get("username")):
        try:
            name = getter()
            if name:
                return str(name)
        except Exception:
            continue
    raise KaggleError("Could not read your Kaggle username from the API key.")


def quota(api) -> dict:
    """Kaggle's own GPU numbers: {"used_h", "total_h", "left_h", "refresh"} (refresh = UTC datetime or None)."""
    from kagglesdk.kernels.types.kernels_api_service import ApiGetAcceleratorQuotaStatisticsRequest

    def ask():
        with api.build_kaggle_client() as k:
            return k.kernels.kernels_api_client.get_accelerator_quota_statistics(
                ApiGetAcceleratorQuotaStatisticsRequest())

    r = _timed(ask)
    g = r.gpu_quota
    used = g.time_used.total_seconds() / 3600 if g and g.time_used else 0.0
    total = g.total_time_allowed.total_seconds() / 3600 if g and g.total_time_allowed else 0.0
    refresh = r.quota_refresh_time
    if refresh is not None and refresh.tzinfo is None:
        refresh = refresh.replace(tzinfo=timezone.utc)
    return {"used_h": round(used, 2), "total_h": round(total, 2), "left_h": round(max(total - used, 0.0), 2),
            "refresh": refresh}


def quota_line(q: dict, now: datetime | None = None) -> str:
    """e.g. 'Kaggle GPU: 1.0 h used of 30 · 29.0 h left · resets Sat 14 Nov 05:30' (reset in local time)."""
    when = ""
    if q.get("refresh"):
        local = q["refresh"].astimezone()
        when = f" · resets {local.strftime('%a %d %b %H:%M')}"
    return f"Kaggle GPU: {q['used_h']:.1f} h used of {q['total_h']:.0f} · {q['left_h']:.1f} h left{when}"


def run_status(api, ref: str) -> tuple[str, str]:
    """(QUEUED | RUNNING | COMPLETE | ERROR | CANCEL_... | UNKNOWN, failure message)."""
    try:
        r = _timed(api.kernels_status, ref)
    except KaggleError:
        raise
    except Exception as exc:  # noqa: BLE001 - e.g. never pushed yet
        return "UNKNOWN", f"{type(exc).__name__}: {exc}"
    status = getattr(getattr(r, "status", None), "name", None) or str(getattr(r, "status", "UNKNOWN"))
    return status.upper(), str(getattr(r, "failure_message", "") or "")


def parse_stages(text: str) -> list[tuple[str, dict]]:
    """Every `MITRA|stage|k=v` line in a piece of log (also inside JSON-escaped log blobs)."""
    out = []
    for m in STAGE_RE.finditer(text or ""):
        fields = {k: v.strip() for k, v in (part.split("=", 1) for part in m.group(2).split("|")[1:]
                                            if "=" in part)}
        out.append((m.group(1), fields))
    return out


def notebook_folder(model: str, ctx: int, token: str, idle_min: int, user: str) -> Path:
    """Write the notebook + kernel-metadata.json Kaggle's push needs; returns the folder."""
    import importlib.util
    root = Path(__file__).resolve().parents[1] / "remote" / "kaggle"
    spec = importlib.util.spec_from_file_location("mitra_kaggle_nb", root / "build_notebook.py")
    nb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nb)
    folder = _home() / "kaggle-push"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{SLUG}.ipynb").write_text(
        json.dumps(nb.build({"model": model, "ctx": ctx, "token": token, "idle_min": idle_min}), indent=1),
        encoding="utf-8")
    meta = {"id": f"{user}/{SLUG}", "title": SLUG, "code_file": f"{SLUG}.ipynb", "language": "python",
            "kernel_type": "notebook", "is_private": True, "enable_gpu": True, "enable_internet": True,
            "dataset_sources": [], "competition_sources": [], "kernel_sources": [], "model_sources": []}
    (folder / "kernel-metadata.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return folder


def _log_lines(api, ref: str, q: Queue, stop: threading.Event) -> None:
    """Background thread: the live log, chunk by chunk, into `q` (None at the end)."""
    try:
        for event in api.kernels_logs_stream(ref):
            if stop.is_set():
                break
            q.put(str(event.get("data", "")) if isinstance(event, dict) else str(event))
    except Exception as exc:  # noqa: BLE001 - the caller polls the status as well
        q.put(f"__error__ {type(exc).__name__}: {exc}")
    q.put(None)


def start(model: str, ctx: int = 262_144, *, idle_min: int = 30, max_hours: float = 11.5, wait_min: float = 20,
          echo=print, api=None, sleep=time.sleep) -> dict:
    """Upload and run the notebook, follow it until ready, point Mitra at it. Returns the remote settings."""
    from app import remote
    api = api or client()
    user = username(api)
    ref = f"{user}/{SLUG}"
    state = load_state()
    if state.get("ref") == ref and state.get("token"):
        status, _ = run_status(api, ref)
        if status in ("QUEUED", "RUNNING"):
            r = remote.active()
            if r and r.get("name") == "kaggle":
                echo("☁ already running: Mitra uses it (`mitra kaggle stop` ends it).")
                return r
            echo(f"⏳ a run is already {status.lower()}: following it")
            return _follow(api, ref, state, ctx, wait_min, echo, sleep)
    q = quota(api)
    echo("  " + quota_line(q))
    if q["total_h"] and q["left_h"] < 0.25:
        raise KaggleError("Less than 15 minutes of GPU time left this week: " + quota_line(q))
    hours = min(max_hours, max(q["left_h"], 0.25) if q["total_h"] else max_hours)
    token = secrets.token_urlsafe(24)
    folder = notebook_folder(model, ctx, token, idle_min, user)
    echo(f"  uploading a private notebook ({ACCELERATOR}, {model} at {ctx // 1024}K, stops after {idle_min} min "
         f"unused or {hours:.1f} h) …")
    # kernels_push's own `timeout` is the run's time limit (seconds); ours (120 s) is for the upload call
    resp = _timed(lambda: api.kernels_push(str(folder), timeout=str(int(hours * 3600)), acc=ACCELERATOR),
                  timeout=120)
    err = str(getattr(resp, "error", "") or "")
    if err:
        raise KaggleError(f"Kaggle refused the notebook: {err}")
    state = {"ref": ref, "token": token, "model": model, "ctx": ctx, "pushed": time.time(),
             "url": str(getattr(resp, "url", "") or f"https://www.kaggle.com/code/{ref}"), "idle_min": idle_min}
    save_state(state)
    return _follow(api, ref, state, ctx, wait_min, echo, sleep)


def _follow(api, ref: str, state: dict, ctx: int, wait_min: float, echo, sleep) -> dict:
    from app import remote
    deadline = time.time() + wait_min * 60
    seen: set[str] = set()
    while time.time() < deadline:
        status, failure = run_status(api, ref)
        if status in ("ERROR", "CANCEL_REQUESTED", "CANCEL_ACKNOWLEDGED", "COMPLETE"):
            raise KaggleError(f"The Kaggle run ended ({status.lower()}{': ' + failure if failure else ''}). "
                              f"Its log: {state.get('url')}")
        if status != "RUNNING":
            if "queued" not in seen:
                echo("  ⏳ queued on Kaggle …")
                seen.add("queued")
            sleep(10)
            continue
        q: Queue = Queue()
        stop = threading.Event()
        threading.Thread(target=_log_lines, args=(api, ref, q, stop), daemon=True).start()
        buffer = ""
        while time.time() < deadline:
            try:
                chunk = q.get(timeout=15)
            except Empty:
                continue
            if chunk is None or chunk.startswith("__error__"):
                break
            buffer = (buffer + chunk)[-20000:]
            for stage, fields in parse_stages(buffer):
                key = stage + json.dumps(fields, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                if stage == "error":
                    stop.set()
                    raise KaggleError(f"The notebook failed: {fields.get('detail', '?')}. Log: {state.get('url')}")
                if stage == "loaded":
                    echo(f"  ✓ {fields.get('model')} {fields.get('gb')} GB at {fields.get('context')} context, "
                         f"{fields.get('where')}")
                elif stage == "ready" and fields.get("url"):
                    stop.set()
                    url = fields["url"].rstrip("/") + "/" + state["token"]
                    models, problem = remote.probe(url, timeout=30)
                    for _ in range(6):
                        if not problem:
                            break
                        sleep(5)
                        models, problem = remote.probe(url, timeout=30)
                    if problem:
                        raise KaggleError(f"The notebook is ready but its address does not answer: {problem}")
                    data = remote.set_remote(url, ctx, "kaggle")
                    state.update(started=time.time(), public=fields["url"])
                    save_state(state)
                    echo(f"  ☁ ready: every Mitra window now uses Kaggle ({state.get('model')} at {ctx // 1024}K)")
                    return data
                elif stage in STAGE_TEXT:
                    echo(f"  · {STAGE_TEXT[stage]}")
        stop.set()
        sleep(5)
    raise KaggleError(f"Not ready after {wait_min:.0f} minutes. `mitra kaggle status` shows it; the log: "
                      f"{state.get('url')}")


def stop(*, echo=print, api=None, sleep=time.sleep, wait_s: float = 90) -> None:
    """Ask the notebook to shut down; Mitra goes back to this machine; show the hours."""
    import urllib.request

    from app import remote
    state = load_state()
    r = remote.active()
    url = r["url"] if r and r.get("name") == "kaggle" else (
        (state.get("public", "").rstrip("/") + "/" + state["token"]) if state.get("public") and state.get("token")
        else "")
    asked = False
    if url:
        try:
            req = urllib.request.Request(url + "/mitra/stop", data=b"{}", method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30):
                asked = True
        except Exception as exc:  # noqa: BLE001
            echo(f"  ⚠ the notebook did not answer ({type(exc).__name__}); it stops by itself after "
                 f"{state.get('idle_min', 30)} min unused")
    if remote.active() and remote.active().get("name") == "kaggle":
        remote.clear()
    echo("  ✓ Mitra is back on this machine's Ollama")
    if asked:
        echo("  asked the Kaggle notebook to stop …")
    try:
        api = api or client()
        if state.get("ref") and asked:
            end = time.time() + wait_s
            while time.time() < end:
                status, _ = run_status(api, state["ref"])
                if status not in ("QUEUED", "RUNNING"):
                    echo(f"  ✓ the Kaggle run ended ({status.lower()}): no more GPU hours used")
                    break
                sleep(5)
            else:
                echo(f"  ⏳ still shutting down; check with `mitra kaggle status` ({state.get('url')})")
        echo("  " + quota_line(quota(api)))
    except KaggleError as exc:
        echo(f"  ({exc})")
    state.update(stopped=time.time())
    save_state(state)


def status(*, echo=print, api=None) -> None:
    from app import remote
    state = load_state()
    r = remote.active()
    try:
        api = api or client()
        if state.get("ref"):
            run, failure = run_status(api, state["ref"])
            echo(f"Kaggle run: {run.lower()}{' · ' + failure if failure else ''} · {state.get('model', '?')} at "
                 f"{int(state.get('ctx') or 0) // 1024}K · {state.get('url', '')}")
        else:
            echo("Kaggle run: none started from Mitra yet (`mitra kaggle start`)")
        echo(quota_line(quota(api)))
    except KaggleError as exc:
        echo(f"Kaggle: {exc}")
    if r:
        models, err = remote.probe(r["url"], timeout=15)
        echo(f"Mitra uses: ☁ {r.get('name')} · {remote.shown(r['url'])} · " +
             (f"✗ not answering ({err})" if err else "✓ answering"))
    else:
        echo("Mitra uses: this machine's Ollama")
