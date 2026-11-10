"""Builds the Kaggle notebook (D-060, D-061) with proxy.py embedded as is (a test checks they match).

Two uses, one notebook:
- by hand (`mitra_kaggle_server.ipynb`, imported in the browser): prints the `mitra remote set ...` line, runs until you
  stop the session;
- by Mitra (`mitra kaggle start`): `build(auto={...})` puts Mitra's settings and token in the first cell, the notebook
  runs in the background, and Mitra reads its progress from the live log: lines `MITRA|<stage>|key=value|...`.
  It stops itself when Mitra says `mitra kaggle stop` (POST /<token>/mitra/stop) or after IDLE_MIN minutes unused.

    python remote/kaggle/build_notebook.py      (rewrites mitra_kaggle_server.ipynb)
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

INTRO = """# Mitra on a Kaggle GPU

Runs Ollama on this notebook's GPU so Mitra on your laptop can use a bigger GPU at full context (Mitra D-060).

**Easiest:** you do not need to open this at all: `mitra kaggle start` on your laptop uploads and runs it for you.

**By hand:** Settings (right panel) → *Accelerator* **GPU T4 x2** · *Internet* **On** (needs a verified phone).
Then **Run All** and keep this tab open. The tunnel cell prints one line to paste on your laptop:

    mitra remote set https://<name>.trycloudflare.com/<token> --ctx 262144

**When you are done:** stop the session (power button, top right) to save your weekly GPU hours, and on the laptop
run `mitra remote off`. A session ends by itself after 12 hours; the URL changes every session.

The token is new every session and is part of the URL: anyone without it gets 404. Your code and prompts pass through
this Kaggle machine and Cloudflare's tunnel."""

SETTINGS_MANUAL = """# Settings: the model and the context Mitra will use (mimo's maximum is 256K)
MODEL = "mimo-v2.6:9b"
CONTEXT = 262144
PORT = 8000
IDLE_MIN = 0  # by hand: run until you stop the session

import secrets
TOKEN = secrets.token_urlsafe(24)
"""

SETTINGS_AUTO = """# Settings from Mitra (`mitra kaggle start`): this private notebook holds this session's token
MODEL = {model!r}
CONTEXT = {ctx}
PORT = 8000
IDLE_MIN = {idle_min}  # stops itself when Mitra has not used it for this long (saves your GPU hours)
TOKEN = {token!r}
"""

SAY = """
def say(stage, **kw):
    # one line Mitra reads from the live log: MITRA|stage|key=value (no quotes, pipes or backslashes in values)
    clean = lambda v: str(v).replace("|", "/").replace('"', "'").replace("\\\\", "/").replace("\\n", " ")
    print("MITRA|" + stage + "".join(f"|{k}={clean(v)}" for k, v in kw.items()), flush=True)

say("started", model=MODEL, context=CONTEXT)
print("model", MODEL, "| context", CONTEXT)"""

INSTALL = """# Install Ollama (about 1 minute) and show the GPUs
say("installing")
!apt-get -qq update > /dev/null && apt-get -qq install -y zstd pciutils lshw > /dev/null
!curl -fsSL https://ollama.com/install.sh | sh
!nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv"""

START = """# Start Ollama: flash attention + q8_0 KV cache (half the context memory), one model kept loaded
import json, os, subprocess, time, urllib.request

def api(path, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request("http://127.0.0.1:11434" + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")

env = dict(os.environ, OLLAMA_HOST="127.0.0.1:11434", OLLAMA_CONTEXT_LENGTH=str(CONTEXT),
           OLLAMA_FLASH_ATTENTION="1", OLLAMA_KV_CACHE_TYPE="q8_0", OLLAMA_KEEP_ALIVE="-1",
           OLLAMA_NUM_PARALLEL="1", OLLAMA_MAX_LOADED_MODELS="1")
ollama_log = open("/kaggle/working/ollama.log", "w")
ollama = subprocess.Popen(["ollama", "serve"], env=env, stdout=ollama_log, stderr=subprocess.STDOUT)
for _ in range(60):
    try:
        print("Ollama", api("/api/version")["version"], "is up")
        break
    except Exception:
        time.sleep(1)
else:
    say("error", detail="Ollama did not start")
    raise SystemExit("Ollama did not start: see /kaggle/working/ollama.log")"""

PULL = """# Download the model (a few minutes) and load it once at the full context, so Mitra's first call is fast
say("pulling", model=MODEL)
!ollama pull {MODEL}
say("loading", model=MODEL, context=CONTEXT)
t0 = time.time()
api("/api/generate", {"model": MODEL, "prompt": "Say ok.", "stream": False,
                      "options": {"num_ctx": CONTEXT}, "keep_alive": -1}, timeout=1800)
for m in api("/api/ps").get("models", []):
    size, vram = m.get("size", 0), m.get("size_vram", 0)
    where = "fully on GPU" if vram >= size else f"{100 * vram / max(size, 1):.0f}% on GPU (the rest on CPU: slower)"
    print(f"{m['name']}: {size / 1e9:.1f} GB at {m.get('context_length')} context, {where}, "
          f"loaded in {time.time() - t0:.0f} s")
    say("loaded", model=m["name"], gb=round(size / 1e9, 1), context=m.get("context_length"), where=where,
        seconds=round(time.time() - t0))
!nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv"""

PROXY_HEAD = "%%writefile /kaggle/working/proxy.py\n"

TUNNEL = """# Start the token proxy and a Cloudflare quick tunnel (no account needed), then print the line for your laptop
import re, sys, threading
say("tunnel")
proxy = subprocess.Popen([sys.executable, "/kaggle/working/proxy.py", TOKEN, str(PORT), "127.0.0.1:11434",
                          "/kaggle/working"],
                         stdout=open("/kaggle/working/proxy.log", "w"), stderr=subprocess.STDOUT)
!wget -q -O /kaggle/working/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
!chmod +x /kaggle/working/cloudflared
tunnel = subprocess.Popen(["/kaggle/working/cloudflared", "tunnel", "--url", f"http://127.0.0.1:{PORT}",
                           "--no-autoupdate"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
public = None
tunnel_log = open("/kaggle/working/tunnel.log", "w")
t_end = time.time() + 90
while time.time() < t_end and public is None:
    line = tunnel.stdout.readline()
    tunnel_log.write(line)
    found = re.search(r"https://[a-z0-9-]+\\.trycloudflare\\.com", line)
    if found:
        public = found.group(0)
if not public:
    say("error", detail="no tunnel URL")
    raise SystemExit("No tunnel URL: see /kaggle/working/tunnel.log")
threading.Thread(target=lambda: [tunnel_log.write(l) for l in tunnel.stdout], daemon=True).start()
URL = f"{public}/{TOKEN}"
for _ in range(30):  # a new tunnel name takes a few seconds to resolve
    try:
        with urllib.request.urlopen(URL + "/api/tags", timeout=15) as r:
            names = [m["name"] for m in json.loads(r.read().decode()).get("models", [])]
        print("✓ the tunnel works · models:", ", ".join(names))
        break
    except Exception:
        time.sleep(3)
else:
    print("⚠ the tunnel did not answer yet; try the line below anyway in a minute")
say("ready", url=public, model=MODEL, context=CONTEXT)  # the token is not printed: Mitra already has it
print()
print("On your laptop, run:")
print()
print(f"    mitra remote set {URL} --ctx {CONTEXT}")
print()
print("then start Mitra. Keep this tab open.")"""

WATCH = """# Keep the session alive and show its state every 5 minutes. Stops when Mitra says `mitra kaggle stop`, or after
# IDLE_MIN minutes without a model request (0 = never), and then shuts everything down: the Kaggle run ends.
started = last_seen = time.time()
reason, next_report = "", 0.0
while not reason:
    if os.path.exists("/kaggle/working/stop"):
        reason = "mitra kaggle stop"
    elif os.path.exists("/kaggle/working/last_request"):
        last_seen = max(last_seen, os.path.getmtime("/kaggle/working/last_request"))
    if not reason and IDLE_MIN and time.time() - last_seen > IDLE_MIN * 60:
        reason = f"idle {IDLE_MIN} min"
    if not reason and (ollama.poll() is not None or tunnel.poll() is not None):
        reason = "ollama or the tunnel stopped"
    if time.time() >= next_report:
        try:
            ps = api("/api/ps").get("models", [])
            loaded = ", ".join(f"{m['name']} {m.get('size_vram', 0) / 1e9:.1f} GB on GPU" for m in ps) or "none loaded"
        except Exception as exc:
            loaded = f"Ollama not answering: {exc}"
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=30).stdout.strip().replace("\\n", " | ")
        idle = int((time.time() - last_seen) / 60)
        print(time.strftime("%H:%M"), "·", loaded, "· GPU", gpu, f"· idle {idle} min", flush=True)
        say("alive", idle_min=idle, up_min=int((time.time() - started) / 60))
        next_report = time.time() + 300
    time.sleep(15)
say("stopping", reason=reason, up_min=int((time.time() - started) / 60))
for p in (tunnel, proxy, ollama):
    p.terminate()
print("stopped:", reason)"""


def _code(src: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
            "source": src.splitlines(keepends=True)}


def build(auto: dict | None = None) -> dict:
    """The notebook. `auto` = {"model", "ctx", "token", "idle_min"} when Mitra starts it (`mitra kaggle start`)."""
    proxy = (HERE / "proxy.py").read_text(encoding="utf-8")
    settings = (SETTINGS_AUTO.format(model=auto["model"], ctx=int(auto["ctx"]), token=auto["token"],
                                     idle_min=int(auto.get("idle_min", 30)))
                if auto else SETTINGS_MANUAL) + SAY
    cells = [{"cell_type": "markdown", "metadata": {}, "source": INTRO.splitlines(keepends=True)},
             _code(settings), _code(INSTALL), _code(START), _code(PULL), _code(PROXY_HEAD + proxy), _code(TUNNEL),
             _code(WATCH)]
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                                        "name": "python3"},
                                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5}


if __name__ == "__main__":
    out = HERE / "mitra_kaggle_server.ipynb"
    out.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", out)
