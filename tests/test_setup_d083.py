"""D-083: `codemitra setup` does everything after `git clone`, checks before it acts, never undoes your choices, and
says plainly what only you can do (a Kaggle account, your phone)."""
from pathlib import Path

import pytest

from app import backend, config
from app import kaggle as K
from app import setup_wizard as W


class Fake:
    """The outside world: which programs exist, what commands answer, what the user types."""

    def __init__(self, have=("ollama",), answers=(), models="", ollama_up=True, gpu=""):
        self.have, self.answers, self.models, self.up, self.gpu = set(have), list(answers), models, ollama_up, gpu
        self.ran, self.said, self.opened, self.asked = [], [], [], []

    def io(self):
        return W.IO(say=self.said.append, ask=self.ask, run=self.run, which=self.which, open_url=self.opened.append,
                    ollama_up=lambda: self.up, sleep=lambda s: None)

    def ask(self, q, default=""):
        self.asked.append(q)
        return self.answers.pop(0) if self.answers else default

    def which(self, name):
        return f"/bin/{name}" if name in self.have else None

    def run(self, args, timeout=0, stream=False):
        self.ran.append(args)
        if args[0] == "nvidia-smi":
            return (0, self.gpu) if self.gpu else (1, "not found")
        if args[:2] == ["ollama", "list"]:
            return 0, "NAME ID SIZE MODIFIED\n" + self.models
        if args[:2] == ["ollama", "pull"]:
            self.models += f"{args[2]} x 1GB now\n"
            return 0, ""
        if args[0] == "winget":
            self.have.add("ollama")
            return 0, "installed"
        return 0, ""


M8 = W.Machine("windows", 24.0, 8.0, "RTX 4060")


@pytest.mark.parametrize("m, model", [
    (W.Machine("windows", 24, 8, "RTX 4060"), W.SMALL),
    (W.Machine("windows", 32, 6, "x"), W.LARGE),
    (W.Machine("linux", 16, 12, "x"), W.LARGE),
    (W.Machine("linux", 16, None), W.SMALL),
    (W.Machine("mac", 24, 24, "Apple silicon"), W.LARGE),
])
def test_the_model_fits_the_machine(m, model):
    assert W.pick_model(m)[0] == model


def test_the_gpu_is_read_from_nvidia_smi():
    f = Fake(gpu="NVIDIA GeForce RTX 4060 Laptop GPU, 8188")
    m = W.machine(f.run)
    assert m.vram_gb == 8.0 and "4060" in m.gpu


def test_ollama_missing_is_installed_with_winget_after_asking():
    f = Fake(have=("winget",), answers=["y", "y"])
    r = W.step_ollama(f.io(), M8, auto=False)
    assert r.ok and any(a[0] == "winget" and "Ollama.Ollama" in a for a in f.ran)
    assert "Install Ollama now? (Y/n)" in f.asked[0]


def test_saying_no_to_ollama_explains_what_to_do():
    f = Fake(have=(), answers=["n"])
    r = W.step_ollama(f.io(), M8, auto=False)
    assert r.ok is False and "ollama.com/download" in r.note and not any(a[0] == "winget" for a in f.ran)


def test_ollama_not_running_and_not_starting_says_so(monkeypatch):
    monkeypatch.setattr(W, "_start_ollama", lambda exe: None)
    f = Fake(ollama_up=False)
    r = W.step_ollama(f.io(), W.Machine("linux", 16, None), auto=True)
    assert r.ok is False and "not running" in r.note


def test_the_model_is_downloaded_once_and_remembered(monkeypatch):
    monkeypatch.setattr(config, "load_last_model", lambda: "")
    saved = []
    monkeypatch.setattr(config, "save_last_model", saved.append)
    f = Fake()
    assert W.step_model(f.io(), M8, auto=True).ok
    assert ["ollama", "pull", W.SMALL] in f.ran and saved == [W.SMALL]
    f.ran.clear()
    assert W.step_model(f.io(), M8, auto=True).ok and not any(a[:2] == ["ollama", "pull"] for a in f.ran)


def test_your_current_model_is_never_replaced(monkeypatch):
    """Live: on the maintainer's 8 GB laptop the pick is 4B, but qwen3.5:latest was the chosen model."""
    monkeypatch.setattr(config, "load_last_model", lambda: "qwen3.5:latest")
    saved = []
    monkeypatch.setattr(config, "save_last_model", saved.append)
    f = Fake(models="qwen3.5:latest abc 6.6GB x\nqwen3.5:4b def 3.4GB x\n")
    r = W.step_model(f.io(), M8, auto=True)
    assert r.ok and "qwen3.5:latest" in r.note and saved == []


def test_kaggle_without_an_account_guides_opens_the_page_and_takes_the_token(monkeypatch, tmp_path):
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(K, "token_path", lambda: tmp_path / "access_token")
    got = []
    monkeypatch.setattr(K, "setup", lambda token, echo=print, api_factory=None: got.append(token) or token == "KGAT_x")
    f = Fake(answers=["y", "y", "wrong", "KGAT_x"])
    r = W.step_kaggle(f.io(), M8, auto=False)
    assert r.ok and got == ["wrong", "KGAT_x"] and f.opened == [W.KAGGLE_SETTINGS]
    said = "\n".join(f.said)
    assert "Phone verification" in said and "Generate New Token" in said and "sign up" in said
    assert backend.kaggle_use() == "when-needed"


def test_kaggle_never_overwrites_your_choice(monkeypatch, tmp_path):
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(K, "token_path", lambda: tmp_path / "access_token")
    backend.save_prefs(kaggle_use="now", onboarded=True)
    f = Fake(answers=["n"])
    r = W.step_kaggle(f.io(), M8, auto=False)
    assert r.ok is None and backend.kaggle_use() == "now"


def test_yes_mode_asks_nothing_and_leaves_kaggle_to_you(monkeypatch, tmp_path):
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(K, "token_path", lambda: tmp_path / "access_token")
    monkeypatch.setattr(config, "load_last_model", lambda: "")
    monkeypatch.setattr(config, "save_last_model", lambda m: None)
    monkeypatch.setattr(W, "machine", lambda run=None: M8)
    f = Fake(have=("ollama",))
    results = W.run(f.io(), auto=True)
    assert f.asked == []
    by = {r.step: r for r in results}
    assert by["Ollama"].ok and by["Model"].ok and by["Kaggle"].ok is False and "kaggle setup" in by["Kaggle"].note
    assert by["Sharing"].ok is None
    assert "Ready." in W.summary(results)


def test_your_name_goes_into_me_md(monkeypatch):
    from app.core import harness as H
    f = Fake(answers=["Ravi"])
    assert W.step_me(f.io(), auto=False).ok
    text = (H.home() / "me.md").read_text(encoding="utf-8")
    assert "Name: Ravi" in text and "<your name>" not in text and "    Ravi" in text
    f2 = Fake()
    W.step_me(f2.io(), auto=False)
    assert f2.asked == []                                  # filled: never asked again


def test_sharing_setup_names_the_next_step_when_there_is_no_access(monkeypatch):
    from app.core import share as SH
    monkeypatch.setattr(SH, "check_access", lambda repo: (False, "denied"))
    f = Fake(have=("gh",), answers=["y", "ravi", "ask"])
    r = W.step_share(f.io(), auto=False)
    assert r.ok is False and "GitHub username" in r.note and "gh auth setup-git" in r.note
    assert SH.settings()["at_exit"] == "ask"


def test_the_one_command_scripts_exist_and_run_codemitra_setup():
    root = Path(__file__).resolve().parents[1]
    ps1, sh = (root / "setup.ps1").read_text(encoding="utf-8"), (root / "setup.sh").read_text(encoding="utf-8")
    for s in (ps1, sh):
        assert "uv tool install --reinstall -e . --python 3.12" in s and "setup" in s and "astral.sh/uv" in s
    assert "setup.ps1" in sh                                # Git Bash on Windows hands over to PowerShell
