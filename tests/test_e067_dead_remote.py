"""E-067: a Kaggle run that stopped by itself left CodeMitra on a dead address ("no compatible local Ollama models")."""
import os

from app import remote


def _cfg():
    return remote.apply({"ollama_local_base_url": "http://localhost:11434", "num_ctx": 0})


def test_a_dead_kaggle_address_is_forgotten_and_this_machine_used(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    remote.set_remote("https://gone.trycloudflare.com/tok", 262144, "kaggle")
    cfg = _cfg()
    monkeypatch.setattr(remote, "probe", lambda url, timeout=15: ([], "URLError: getaddrinfo failed"))
    said = []
    assert remote.check_alive(cfg, echo=said.append) is False
    assert cfg["ollama_local_base_url"] == "http://localhost:11434" and cfg["num_ctx"] == 0 and "remote" not in cfg
    assert "OLLAMA_HOST" not in os.environ and remote.active() is None
    assert "run has ended" in said[0] and "codemitra kaggle start" in said[0]


def test_a_live_remote_is_kept(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    remote.set_remote("https://up.trycloudflare.com/tok", 262144, "kaggle")
    cfg = _cfg()
    monkeypatch.setattr(remote, "probe", lambda url, timeout=15: ([{"name": "m"}], ""))
    said = []
    assert remote.check_alive(cfg, echo=said.append) is True
    assert cfg["remote"] == "kaggle" and said == [] and remote.active()
    remote.clear()
    monkeypatch.delenv("OLLAMA_HOST", raising=False)


def test_another_dead_remote_stays_set_but_is_not_used_now(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    remote.set_remote("http://gpu-box:8000/tok", 65536, "office")
    cfg = _cfg()
    monkeypatch.setattr(remote, "probe", lambda url, timeout=15: ([], "timed out"))
    said = []
    assert remote.check_alive(cfg, echo=said.append) is False
    assert "remote" not in cfg and remote.active()["name"] == "office" and "codemitra remote off" in said[0]
    remote.clear()


def test_no_remote_nothing_happens():
    said = []
    assert remote.check_alive({"ollama_local_base_url": "x"}, echo=said.append) is False and said == []
