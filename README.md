# Mitra

**A coding assistant in your terminal that runs on local models.** You chat with it in your project folder; it reads
your code, edits files (asking first), runs your tests and fixes what fails, using a small model on your own GPU
through [Ollama](https://ollama.com). No API key, no subscription, your code stays on your machine. If your laptop is
too small, it can borrow a free Kaggle GPU for a few hours.

> **Preview (v0.1.0).** It works for everyday tasks on 4-9B models, and it is still rough. I am asking colleagues to
> try it on their own projects and tell me what breaks: see [Feedback](#feedback).

## Quick start (about 15 minutes)

**You need:** Windows 10/11, macOS or Linux · 16 GB RAM (8 GB GPU recommended; no GPU works via Kaggle) · git.

1. **Install Ollama** from [ollama.com/download](https://ollama.com/download) and start it (on Windows it runs in the
   tray). Optional but recommended, it halves the memory long chats need: set these two environment variables and
   restart Ollama:
   ```
   OLLAMA_FLASH_ATTENTION=1
   OLLAMA_KV_CACHE_TYPE=q8_0
   ```
2. **Get a model** that fits your machine:

   | Your machine | Model | Command |
   |---|---|---|
   | 8 GB GPU, or no GPU (slow) | Qwen3.5 4B (3.4 GB) | `ollama pull qwen3.5:4b` |
   | 12 GB+ GPU, or 32 GB RAM | MiMo v2.6 9B or Qwen3.5 9B (6.6 GB) | `ollama pull mimo-v2.6:9b` |
   | Small laptop | use a free Kaggle GPU instead | see [Kaggle](#no-big-gpu-use-a-free-kaggle-gpu) |

3. **Install uv** (Python tool manager), if you do not have it:
   - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
4. **Install Mitra:**
   ```
   git clone https://github.com/prashanth-ds-ml/mitra.git
   cd mitra
   uv tool install -e . --python 3.12
   ```
   This adds a `mitra` command with its own Python (no clash with your projects). `mitra --version` checks it.
   On Windows Git Bash, write paths with `/` (`C:/Users/you/...`), not `\`.
5. **Use it:** go to one of your projects and run `mitra`:
   ```
   cd ~/my-project
   mitra
   ```
   The header shows the model and a memory check. **✓** = fine. **⚠ / ✗** = not enough free memory: type `/free`
   (Mitra lists your biggest programs and closes the ones you tick), or `/context 64k` for a smaller context, or
   `/model use qwen3.5:4b`.

**Update later:** `cd mitra && git pull` (the install follows the folder; restart `mitra`). **Remove:**
`uv tool uninstall mitra`.

## Using it

Just type what you want, e.g. *"what does this project do?"*, *"add a --verbose flag to cli.py and a test for it"*,
*"the tests in tests/test_api.py fail, fix them"*. Mitra asks before every file change and command (shift+tab
switches between asking, auto-edit and plan-only).

| Command | What it does |
|---|---|
| `/help` | All commands and keys |
| `/model use <name>` · `/context 64k\|128k\|auto` | Switch model or context size, live |
| `/free` | Close programs to make RAM room for the model |
| `/plan template` · `/plan check` · `/run plan.md 4` | Write a task plan, check it, let Mitra build it unattended (up to 4 h) |
| `/undo` | Undo Mitra's last changes |
| `/good` · `/bad <why>` | Tell Mitra how the last answer was (it learns from these) |
| `/kaggle start\|stop\|status` | Run on a free Kaggle GPU (below) |
| `! <command>` | Run a shell command yourself |
| `mitra dashboard` | A local page with your sessions, what worked, what failed |

Keys: **enter** sends, **shift+enter** new line, **esc** stops the model, **ctrl+c** twice quits.

## No big GPU? Use a free Kaggle GPU

Kaggle gives every verified account about **30 GPU hours a week** (2x T4, 16 GB each). Mitra can run its model there
at full 256K context, about 3-4x faster than an 8 GB laptop, without you opening Kaggle:

1. **Once (2 minutes):** sign in on [kaggle.com](https://www.kaggle.com) (a free account) → your picture →
   **Settings**:
   - **Phone verification**: verify (Kaggle needs it for GPUs and internet in notebooks).
   - **API → Generate New Token**: copy the token it shows.

   Then run `mitra kaggle setup <the token>`. Mitra saves it where Kaggle looks, signs in and shows your hours.
   (If your browser downloaded a `kaggle.json` instead, just run `mitra kaggle setup`: it finds it in Downloads.)
2. **Every time:** `mitra kaggle start` uploads a private notebook to your account, waits until the model is loaded
   (4-8 minutes, it shows each step), and then every `mitra` window uses it. Inside Mitra: `/kaggle start`.
3. **When done:** `mitra kaggle stop` (or `/kaggle stop`). It also stops by itself after 30 minutes unused.
   `mitra kaggle status` shows your hours left this week.

The first time you start Mitra it offers to set this up for you (*Yes, guide me* opens the Kaggle settings page and
takes the pasted token).

**How Mitra switches** (you do not have to think about it):
- The status line always shows where the model runs: `☁ kaggle · mimo 256K · 28.1 h left` or `💻 laptop · …`.
- **Read work** (plan mode, the planner and reviewer roles) runs on the laptop; **write work** (edits, tests,
  `/run` nights) runs on Kaggle when it is up. Mitra switches between turns, never in the middle of one, and compacts
  a long chat first if the laptop's context is smaller.
- Write work with Kaggle not running: Mitra asks once per session whether to start it in the background; you keep
  working on the laptop meanwhile and it moves over when ready.
- **Kaggle ends** (30 minutes unused, the 12 h limit, your hours run out, the tunnel drops): Mitra switches to the
  laptop model (a smaller one if RAM is short), writes a report of what was done (`.mitra/reports/kaggle-ended-….md`:
  your requests, changed files, last tests, a short summary) and stops, so you decide how to go on. A message you had
  just typed goes back to the input box.

Your code and prompts then pass through the Kaggle machine and Cloudflare's tunnel (protected by a random token):
use it for code you may share, not secrets. Kaggle's terms do not mention tunnels; Mitra keeps it to one private
notebook, used by you and stopped when idle, but it is your account and your call. Details:
[remote/kaggle/README.md](remote/kaggle/README.md).

## What stays on your machine

Everything Mitra records stays in `~/.mitra/` on your computer (sessions, traces for the dashboard, settings). Nothing
is uploaded, except: web searches you ask for, MCP servers you use (git, GitHub, docs lookups; `/mcp` lists them), and
your prompts and code when you use Kaggle.

## Feedback

This preview exists to collect feedback. Please try it for a few real tasks on your own projects, then
**[open a feedback issue](https://github.com/prashanth-ds-ml/mitra/issues/new?template=feedback.yml)** (2 minutes; or
just message me). Things worth trying:

1. Ask about a project you know: *"explain how X works"*. Was it right?
2. A small change with a test: *"add Y and a test for it"*. Did the test pass? How many tries?
3. A bug you know: *"fix Z"*.
4. `/plan template`, fill it in (or ask Mitra to), `/run plan.md 1`.
5. If your laptop struggles: `mitra kaggle start`.

Something broke? A [bug report](https://github.com/prashanth-ds-ml/mitra/issues/new?template=bug.yml) with what you
typed and what you saw (copy the terminal) helps most. `/good` and `/bad <why>` in the chat help too.

## Why

Coding agents like Claude Code, Codex and OpenCode can talk to local models, but they are built for frontier models:
many tools, strict tool-call formats and a large fixed prompt (measured: 2.7K-12.2K tokens before reading any code;
[EVALS.md](docs/EVALS.md)). On a 4-9B model they often break. Mitra is built the other way round: a small prompt, few
tools, tolerant parsing, and every change checked by your tests. The question it is trying to answer, in public:

> On an 8 GB consumer GPU, how much everyday coding work can a small model do when the agent is built for it?

Progress and decisions: [docs/STATUS.md](docs/STATUS.md) · [docs/PLAN.md](docs/PLAN.md) ·
[docs/DECISIONS.md](docs/DECISIONS.md) · [CHANGELOG.md](CHANGELOG.md)

## Credits

Starts from [local-codex](https://github.com/prashanth-ds-ml/local-codex). Ideas from deepseek-harness, Google
Research Harness², Uber's Debug Assist write-up, LangChain Deep Agents and langgraph-bigtool (details in
[docs/SCOPE.md](docs/SCOPE.md)).

## Licence

MIT
