# Setup in detail

The short version is in the [README](../../README.md): clone, then run `setup.ps1` (Windows) or `setup.sh` (macOS /
Linux). This page says what that does, how to do it by hand, and what to do when something goes wrong.

## What you need
- **git** (to clone): [git-scm.com](https://git-scm.com/downloads)
- **16 GB RAM**. An NVIDIA GPU with 8 GB or more helps; without one, use the free Kaggle GPU.
- Windows 10/11, macOS or Linux.

## What the setup does
`setup.ps1` / `setup.sh` installs **uv** (a Python tool manager, if you do not have it), installs **CodeMitra** with its
own Python (no clash with your projects), adds the `codemitra` command to your PATH, and then runs `codemitra setup`.
That one is a guided run; each step checks first and only acts when something is missing:

| Step | What happens | Asks you |
|---|---|---|
| 1. Ollama | Installs it (Windows: winget, macOS: Homebrew, Linux: Ollama's official script; otherwise opens the download page), starts it, and on Windows turns on its memory saver (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`) | before installing |
| 2. Model | Reads your GPU and RAM and downloads the model that fits: **Qwen3.5 4B** (3.4 GB) for an 8 GB GPU or none, **Qwen3.5 9B** (6.6 GB) for 12 GB+ GPU, 32 GB RAM or a Mac with 24 GB+. A model you already chose is kept | before downloading |
| 3. Kaggle | Optional free GPU (recommended under 12 GB GPU): opens kaggle.com, tells you what to click, takes the token, checks your hours and phone verification | yes / no, then the token |
| 4. About you | Your first name for mails (in `~/.codemitra/me.md`, which you can edit any time: tone, signature, stack) | your name |
| 5. Sharing | Optional: your name in the shared logs repo, and whether to ask at exit | yes / no |
| Summary | ✓ ready, ✗ needs you (with the fix), – skipped; then "Go to a project folder and run: codemitra" | |

Run `codemitra setup` again any time (for example after making your Kaggle account); it skips what is done.
Options: `--yes` takes every default without asking, `--model qwen3.5:latest` picks the model, `--kaggle yes|no` and
`--share yes|no` answer those steps.

## By hand (if you prefer, or the setup cannot)
1. **Ollama** from [ollama.com/download](https://ollama.com/download); start it (on Windows it runs in the tray).
   Optional, it halves the memory long chats need: set `OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q8_0` as
   environment variables, then restart Ollama.
2. **A model:** `ollama pull qwen3.5:4b` (8 GB GPU or none) or `ollama pull qwen3.5:latest` (12 GB+ GPU or 32 GB RAM).
3. **uv:** Windows `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`, macOS /
   Linux `curl -LsSf https://astral.sh/uv/install.sh | sh`.
4. **CodeMitra**, in the folder you cloned: `uv tool install -e . --python 3.12`, then `codemitra --version`.
5. Optional: `codemitra kaggle setup` ([Kaggle guide](KAGGLE.md)) and `codemitra share --setup` ([sharing](SHARING.md)).

## Update, remove
- **Update:** `cd codemitra && git pull`, then restart `codemitra` (the install follows the folder). Run
  `codemitra setup` again if the release notes say so.
- **Remove:** `uv tool uninstall codemitra`. Your sessions and settings are in `~/.codemitra/`; delete that folder too
  if you want them gone. Models: `ollama rm qwen3.5:4b`.

## Upgrading from Mitra
Mitra was renamed CodeMitra in v0.8.0; the command is now `codemitra`. In the folder you cloned it into:
```
uv tool uninstall mitra
git remote set-url origin https://github.com/prashanth-ds-ml/codemitra.git
git pull
powershell -ExecutionPolicy Bypass -File setup.ps1      # or: sh setup.sh
```
On the first run your `~/.mitra` moves to `~/.codemitra` (nothing is lost), and each project's `.mitra/` moves to
`.codemitra/` the first time you open it there.

## Troubleshooting
| Problem | Fix |
|---|---|
| `setup.ps1 cannot be loaded … running scripts is disabled` | Run it as shown: `powershell -ExecutionPolicy Bypass -File setup.ps1` |
| `codemitra: command not found` after setup | Open a **new** terminal (the PATH changed); or run `uv tool update-shell` once |
| Ollama "installed but not running" | Start the Ollama app (Windows: from the Start menu), or run `ollama serve` in another terminal, then `codemitra setup` again |
| The model download stopped | `ollama pull qwen3.5:4b` again: it resumes |
| The header shows ⚠ / ✗ memory | Not enough free RAM: type `/free` in CodeMitra (it lists the biggest programs and closes the ones you tick), `/context 64k`, or use Kaggle |
| Very slow answers | No GPU or a small one: use the free Kaggle GPU (`codemitra kaggle setup`, then `/kaggle start`) |
| Kaggle shows 0 GPU hours | Verify your phone: kaggle.com → Settings → Phone verification |
| `codemitra share --push` cannot push | You are not on the logs repo yet: send Prashanth your GitHub username, accept the invite, then `gh auth login` and `gh auth setup-git` |
| Windows Git Bash paths | Write `C:/Users/you/...` with `/`, not `\` |

Still stuck? A [bug report](https://github.com/prashanth-ds-ml/codemitra/issues/new?template=bug.yml) with what you
ran and what you saw (copy the terminal), or message me.
