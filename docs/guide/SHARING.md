# Sharing sessions

CodeMitra learns from its mistakes. Your sessions show it mistakes it never makes for anyone else, so sharing them
is the most useful feedback you can give. Sharing is optional, and you choose every time.

## What a shared session holds (light and scrubbed)
- your messages and CodeMitra's answers
- which tools ran and whether they failed (a short error), test summaries (`1 failed, 4 passed`)
- the feedback labels (your next message's verdict, **+** / **-**, the session rating) and unverified claims
- the setup: CodeMitra version, model, context size, laptop or Kaggle

**Never in it:** file contents, tool outputs, the code CodeMitra wrote or edited, your notes (`me.md`), absolute
paths. Tokens and keys, emails, your user name and home folder are replaced (`[secret]`, `[email]`, `[user]`, `~`).
You see a preview before anything leaves your machine.

## Set up (once)
1. `codemitra share --setup` (or step 5 of `codemitra setup`): your name, and whether to ask when you exit.
2. **Access:** send Prashanth your GitHub username; you get an invite to the private logs repo
   (`prashanth-ds-ml/codemitra-logs`); accept it.
3. Let git use your GitHub login: install [GitHub CLI](https://cli.github.com), then `gh auth login` and
   `gh auth setup-git`.

## Share
- **Any time:** `codemitra share --push` shows a preview of your newest session not shared yet and pushes it after
  your yes. `--all` shares every new one; `--yes` skips the question.
- **At exit:** if you chose `ask` at setup, `exit` asks *"share this session? y"* (any other key skips). `always`
  shares without asking; `never` turns it off (`codemitra share --setup --at-exit never`).
- **Without GitHub:** `codemitra share` (no `--push`) writes the file to `~/.codemitra/share/out/<you>/`; send it to
  Prashanth any way you like.

A session is shared once; sharing again only sends the new ones.

## Who sees it
Everyone on the logs repo can read every folder in it (the friends who share and Prashanth). Share only what you are
fine with them seeing. You can delete your folder (`people/<you>/`) at any time.

## How it is used
The maintainer runs `codemitra share --pull`, which brings everyone's sessions into CodeMitra's records. CodeMitra's
own learning round reads them first: each turn that went wrong becomes a test case its next change must pass. A
frontier model is asked only when CodeMitra stops improving, and then only to guide it, never to change it directly
(decision D-082).
