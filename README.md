# CodeMitra

**A coding assistant in your terminal that runs on small local models.** You chat with it in your project folder; it
reads your code, changes files (asking first), runs your tests and fixes what fails. It runs on your own GPU through
[Ollama](https://ollama.com), or on a free Kaggle GPU when your laptop is too small. No API key, no subscription.

> **Preview (v0.8.1)**, for friends: it works for everyday tasks on 4-9B models, and it is still rough. Please try it
> and tell me what breaks. (Until v0.7 it was called Mitra: see [Upgrading from Mitra](docs/guide/SETUP.md#upgrading-from-mitra).)

## Set up (one command, ~15 minutes)

You need **git** and **16 GB RAM** (an 8 GB GPU helps; without one, the free Kaggle GPU does the work).

**Windows** (PowerShell):
```
git clone https://github.com/prashanth-ds-ml/codemitra.git
cd codemitra
powershell -ExecutionPolicy Bypass -File setup.ps1
```

**macOS / Linux**:
```
git clone https://github.com/prashanth-ds-ml/codemitra.git
cd codemitra
sh setup.sh
```

The setup installs what is missing and asks before each step: uv (Python tools), CodeMitra itself, Ollama, the model
that fits your machine, the free Kaggle GPU, your name for mails, and sharing. Run it again any time: it only does
what is still missing.

**Kaggle needs two things only you can do** on its website (2 minutes, the setup opens the page): make a free
account, and verify your phone (Kaggle requires it for GPUs). The setup then takes the token and does the rest.

## Use it

```
cd ~/my-project
codemitra
```
Then just type, for example:
- *"what does this project do?"*
- *"add a --verbose flag to cli.py, with a test"*
- *"the tests in tests/test_api.py fail, fix them"*
- *"draft a mail to my team saying the release moves to Friday"*

CodeMitra asks before every file change (**shift+tab** switches to auto-edit). **esc** stops it, **ctrl+c** twice
quits. After an answer, press **+** or **-** to say how it went. Everything: [docs/guide/USING.md](docs/guide/USING.md).

## Feedback

Your next message already tells CodeMitra how the last answer went ("why don't you…", a pasted error = wrong;
"thanks", "works" = right), so feedback costs you nothing. To help more:
- **Share your sessions** so CodeMitra learns from your mistakes too: `codemitra share --push` (light and scrubbed,
  with a preview first; [docs/guide/SHARING.md](docs/guide/SHARING.md)).
- **Tell me** in a [feedback issue](https://github.com/prashanth-ds-ml/codemitra/issues/new?template=feedback.yml)
  (2 minutes) or a [bug report](https://github.com/prashanth-ds-ml/codemitra/issues/new?template=bug.yml).

## Guides
| | |
|---|---|
| [Setup in detail](docs/guide/SETUP.md) | what the setup does, doing it by hand, updating, removing, troubleshooting |
| [Using CodeMitra](docs/guide/USING.md) | how it handles a request, commands, keys, modes, what stays on your machine |
| [The free Kaggle GPU](docs/guide/KAGGLE.md) | account, token, hours, how it switches, privacy |
| [Sharing sessions](docs/guide/SHARING.md) | what is shared and what never is, access, the exit question |

## Why

Coding agents like Claude Code, Codex and OpenCode can talk to local models, but they are built for frontier models:
many tools, strict tool-call formats and a large fixed prompt (2.7K-12.2K tokens before reading any code;
[measured](docs/EVALS.md)). On a 4-9B model they often break. CodeMitra is built the other way round: a small prompt,
few tools, tolerant parsing, every change checked by your tests, and it learns from its mistakes.

> On an 8 GB consumer GPU, how much everyday coding work can a small model do when the agent is built for it?

Built in public: the rest of [docs/](docs/) is the build log ([status](docs/STATUS.md),
[decisions](docs/DECISIONS.md), [changelog](CHANGELOG.md)). Starts from
[local-codex](https://github.com/prashanth-ds-ml/local-codex); ideas from deepseek-harness, Google Research
Harness², Uber's Debug Assist, LangChain Deep Agents and langgraph-bigtool ([SCOPE](docs/SCOPE.md)). MIT licence.
