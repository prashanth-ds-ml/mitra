# CodeMitra on a Kaggle GPU (D-060)

Kaggle gives about 30 GPU hours a week (2x T4 16 GB, or a P100), up to 12 hours per session. This notebook runs Ollama
there so CodeMitra on your laptop uses that GPU at full context: mimo-v2.6:9b at its 256K maximum fits on the T4s, where
the laptop's 8 GB GPU needs RAM and 128K.

**Easiest: you do not need this notebook by hand.** `codemitra kaggle setup` (once) and `codemitra kaggle start` do
everything below from CodeMitra (see the main README). This page is the manual way and how it works.

## Once
1. Kaggle → your profile → Settings: verify your phone (needed for internet in notebooks) and note your GPU quota.
2. Kaggle → Create → New Notebook → File → Import Notebook → `codemitra_kaggle_server.ipynb` from this folder.

## Every session
1. In the notebook: Settings → Accelerator **GPU T4 x2**, Internet **On**. Change `MODEL` / `CONTEXT` in the first
   cell if you want another model.
2. **Run All**, keep the tab open. After 3-6 minutes it prints:

       codemitra remote set https://<name>.trycloudflare.com/<token> --ctx 262144

3. On the laptop: paste that line, then start `codemitra` (header: `remote GPU`, the memory line: `☁ runs on kaggle`).
   `/run` nights use it too.
4. Done: `codemitra remote off` on the laptop, and stop the Kaggle session to keep your hours.

`codemitra remote` shows whether the remote answers. The URL changes every session: set it again each time.

## How it works
Ollama listens on 127.0.0.1 only. `proxy.py` (standard library) answers only paths starting with the session's random
token and streams Ollama's replies through. A Cloudflare quick tunnel (no account) gives it a public https URL.
CodeMitra keeps the token in `~/.codemitra/remote.json` and uses the URL as its Ollama address everywhere.

## Things to know
- Your code and prompts pass through the Kaggle machine and Cloudflare. Use it for your own projects, not secrets.
- Energy on Kaggle is not measured: sessions are recorded with `remote = kaggle`, so results can be split.
- Kaggle's terms do not mention tunnels explicitly; Kaggle can end access for misuse. Your account, your call.
- `build_notebook.py` regenerates the notebook (a test checks the embedded proxy matches `proxy.py`).
