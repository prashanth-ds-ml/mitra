"""D-061: `mitra kaggle start | stop | status` with a stand-in Kaggle API (no network, no GPU hours)."""
import importlib.util
import json
import os
import pathlib
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app import kaggle, remote

KAGGLE_DIR = pathlib.Path(__file__).resolve().parents[1] / "remote" / "kaggle"


class FakeApi:
    """Push, status, live log and quota, scripted."""

    def __init__(self, log_lines, statuses=("RUNNING",), used_h=1.0):
        self.log_lines, self.statuses, self.used_h = list(log_lines), list(statuses), used_h
        self.pushed = []

    def get_config_value(self, key):
        return "someone"

    def kernels_status(self, ref):
        name = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return SimpleNamespace(status=SimpleNamespace(name=name), failure_message="")

    def kernels_push(self, folder, timeout=None, acc=None):
        meta = json.loads((pathlib.Path(folder) / "kernel-metadata.json").read_text(encoding="utf-8"))
        nb = json.loads((pathlib.Path(folder) / f"{kaggle.SLUG}.ipynb").read_text(encoding="utf-8"))
        self.pushed.append({"meta": meta, "nb": nb, "timeout": timeout, "acc": acc})
        return SimpleNamespace(error="", url="https://www.kaggle.com/code/someone/mitra-gpu-server")

    def kernels_logs_stream(self, ref):
        for line in self.log_lines:
            yield {"data": line + "\n"}


@pytest.fixture
def fake_quota(monkeypatch):
    q = {"used_h": 1.0, "total_h": 30.0, "left_h": 29.0,
         "refresh": datetime(2026, 11, 14, tzinfo=timezone.utc)}
    monkeypatch.setattr(kaggle, "quota", lambda api: dict(q))
    return q


def test_start_pushes_a_private_gpu_notebook_and_switches_mitra_when_ready(monkeypatch, fake_quota):
    api = FakeApi(["MITRA|started|model=mimo-v2.6:9b|context=262144", "MITRA|installing",
                   "MITRA|loaded|model=mimo-v2.6:9b|gb=14.5|context=262144|where=fully on GPU",
                   "MITRA|ready|url=https://a-b.trycloudflare.com|model=mimo-v2.6:9b"])
    monkeypatch.setattr(remote, "probe", lambda url, timeout=20: ([{"name": "mimo-v2.6:9b"}], ""))
    said = []
    data = kaggle.start("mimo-v2.6:9b", 262144, echo=said.append, api=api, sleep=lambda s: None)
    push = api.pushed[0]
    assert push["acc"] == "NvidiaTeslaT4" and push["meta"]["is_private"] is True
    assert push["meta"]["enable_gpu"] and push["meta"]["enable_internet"]
    assert push["meta"]["id"] == "someone/mitra-gpu-server" and float(push["timeout"]) == 11.5 * 3600
    token = kaggle.load_state()["token"]
    settings = "".join(push["nb"]["cells"][1]["source"])
    assert f"TOKEN = {token!r}" in settings and "IDLE_MIN = 30" in settings
    assert data["url"] == f"https://a-b.trycloudflare.com/{token}" and remote.active()["name"] == "kaggle"
    assert any("14.5 GB" in s and "fully on GPU" in s for s in said) and any("ready" in s for s in said)
    assert not any(token in s for s in said)  # the token is never shown
    remote.clear()


def test_start_refuses_without_hours_left(monkeypatch, fake_quota):
    fake_quota.update(used_h=29.9, left_h=0.1)
    api = FakeApi([])
    with pytest.raises(kaggle.KaggleError, match="Less than 15 minutes"):
        kaggle.start("m", api=api, echo=lambda s: None, sleep=lambda s: None)
    assert api.pushed == []


def test_a_notebook_error_is_reported(monkeypatch, fake_quota):
    api = FakeApi(["MITRA|installing", "MITRA|error|detail=Ollama did not start"])
    with pytest.raises(kaggle.KaggleError, match="Ollama did not start"):
        kaggle.start("m", api=api, echo=lambda s: None, sleep=lambda s: None)
    assert remote.active() is None


def test_a_run_that_ends_before_ready_is_reported(monkeypatch, fake_quota):
    api = FakeApi([], statuses=("ERROR",))
    with pytest.raises(kaggle.KaggleError, match="ended \\(error"):
        kaggle.start("m", api=api, echo=lambda s: None, sleep=lambda s: None)


def test_stages_are_read_from_plain_and_escaped_logs():
    text = 'MITRA|ready|url=https://x.trycloudflare.com|context=262144\n{"data": "MITRA|loaded|where=fully on GPU"}'
    assert kaggle.parse_stages(text) == [("ready", {"url": "https://x.trycloudflare.com", "context": "262144"}),
                                         ("loaded", {"where": "fully on GPU"})]


def test_quota_line_reads_like_kaggle():
    q = {"used_h": 1.06, "total_h": 30.0, "left_h": 28.94, "refresh": datetime(2026, 11, 14, tzinfo=timezone.utc)}
    line = kaggle.quota_line(q)
    assert line.startswith("Kaggle GPU: 1.1 h used of 30 · 28.9 h left · resets ")


def test_quota_reads_the_kaggle_api_numbers(monkeypatch):
    resp = SimpleNamespace(quota_refresh_time=datetime(2026, 11, 14),
                           gpu_quota=SimpleNamespace(time_used=timedelta(seconds=3648),
                                                     total_time_allowed=timedelta(days=1, hours=6)))

    class Client:
        def __enter__(self):
            return SimpleNamespace(kernels=SimpleNamespace(kernels_api_client=SimpleNamespace(
                get_accelerator_quota_statistics=lambda req: resp)))

        def __exit__(self, *a):
            return False

    q = kaggle.quota(SimpleNamespace(build_kaggle_client=lambda: Client()))
    assert q["used_h"] == 1.01 and q["total_h"] == 30.0 and q["left_h"] == 28.99
    assert q["refresh"].tzinfo is not None


@pytest.fixture
def proxy_stack(tmp_path):
    """The real proxy with a state dir, in front of nothing (Mitra's own commands never reach Ollama)."""
    spec = importlib.util.spec_from_file_location("kaggle_proxy2", KAGGLE_DIR / "proxy.py")
    proxy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proxy)
    server = proxy.serve("tok", 0, "127.0.0.1:9", str(tmp_path))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", tmp_path
    server.shutdown()


def test_stop_asks_the_notebook_to_stop_and_goes_back_local(proxy_stack, fake_quota):
    url, state_dir = proxy_stack
    remote.set_remote(url + "/tok", 262144, "kaggle")
    kaggle.save_state({"ref": "someone/mitra-gpu-server", "token": "tok", "public": url, "url": "u"})
    api = FakeApi([], statuses=("RUNNING", "COMPLETE"))
    said = []
    kaggle.stop(echo=said.append, api=api, sleep=lambda s: None)
    assert (state_dir / "stop").exists()  # the notebook's watch loop sees this and shuts down
    assert remote.active() is None
    assert any("no more GPU hours used" in s for s in said) and any("Kaggle GPU:" in s for s in said)


def test_the_proxy_counts_only_real_use_and_refuses_stop_without_token(proxy_stack):
    import urllib.error
    import urllib.request
    url, state_dir = proxy_stack
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(urllib.request.Request(url + "/wrong/mitra/stop", data=b"{}"), timeout=5)
    assert not (state_dir / "stop").exists()
    for path in ("/tok/api/tags", "/tok/api/ps", "/tok/mitra/ping"):
        try:
            urllib.request.urlopen(url + path, timeout=5)
        except Exception:
            pass  # nothing behind the proxy: a 502 is fine here
    assert not (state_dir / "last_request").exists()  # status checks do not keep the GPU alive
    try:
        urllib.request.urlopen(urllib.request.Request(url + "/tok/api/chat", data=b"{}"), timeout=5)
    except Exception:
        pass
    assert (state_dir / "last_request").exists()


def test_remote_unapply_restores_this_machine(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    remote.set_remote("https://x.trycloudflare.com/tok", 262144, "kaggle")
    cfg = remote.apply({"ollama_local_base_url": "http://localhost:11434", "num_ctx": 0})
    assert cfg["num_ctx"] == 262144 and os.environ["OLLAMA_HOST"].startswith("https://x")
    remote.clear()
    remote.unapply(cfg)
    assert cfg["ollama_local_base_url"] == "http://localhost:11434" and cfg["num_ctx"] == 0
    assert "remote" not in cfg and "OLLAMA_HOST" not in os.environ


def test_the_auto_notebook_stops_itself_and_reports_stages():
    spec = importlib.util.spec_from_file_location("build_nb2", KAGGLE_DIR / "build_notebook.py")
    nb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nb)
    code = "".join("".join(c["source"]) for c in nb.build({"model": "m", "ctx": 1, "token": "t",
                                                          "idle_min": 30})["cells"])
    for needed in ('say("ready", url=public', 'say("loaded"', 'say("stopping"', "/kaggle/working/stop",
                   "IDLE_MIN * 60", '"/kaggle/working"]'):
        assert needed in code
    manual = "".join("".join(c["source"]) for c in nb.build()["cells"])
    assert "IDLE_MIN = 0" in manual and "TOKEN = secrets.token_urlsafe(24)" in manual


def test_kaggle_dependencies_include_what_kaggle_forgets():
    """E-065: kaggle 2.2.5 imports `six` without declaring it; the fresh tool install could not load it."""
    import tomllib
    deps = tomllib.loads((pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"))["project"]["dependencies"]
    names = {d.split(">")[0].split("=")[0].split("<")[0].strip() for d in deps}
    assert {"kaggle", "six"} <= names


def test_a_broken_kaggle_install_says_why(monkeypatch):
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name.startswith("kaggle"):
            raise ModuleNotFoundError("No module named 'six'")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(kaggle.KaggleError, match="No module named 'six'"):
        kaggle.client()


def test_no_api_key_gives_the_steps_without_noise(monkeypatch, tmp_path):
    """A new colleague without kaggle.json: the steps, no stray '(1)' from the library's exit code."""
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)
    monkeypatch.delenv("KAGGLE_API_TOKEN", raising=False)
    with pytest.raises(kaggle.KaggleError) as err:
        kaggle.client()
    assert "Generate New Token" in str(err.value) and not str(err.value).rstrip().endswith("(1)")


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "Downloads").mkdir(parents=True)
    monkeypatch.setattr(kaggle.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(tmp_path / "kcfg"))
    monkeypatch.setattr(kaggle, "token_path", lambda: tmp_path / "kdot" / "access_token")
    return home


def _ok_api():
    return FakeApi([])


def test_setup_finds_the_downloaded_key_and_checks_it(fake_home, fake_quota):
    (fake_home / "Downloads" / "kaggle.json").write_text('{"username": "friend", "key": "abc123"}', encoding="utf-8")
    said = []
    assert kaggle.setup(echo=said.append, api_factory=_ok_api)
    assert json.loads(kaggle.key_path().read_text(encoding="utf-8"))["username"] == "friend"
    assert any("saved to" in s for s in said) and any("Kaggle GPU:" in s for s in said)
    assert any("mitra kaggle start" in s for s in said)
    assert not any("abc123" in s for s in said)  # the key itself is never printed


def test_setup_takes_a_path_and_refuses_a_wrong_file(fake_home, fake_quota, tmp_path):
    bad = tmp_path / "notes.json"
    bad.write_text('{"hello": 1}', encoding="utf-8")
    said = []
    assert not kaggle.setup(str(bad), echo=said.append, api_factory=_ok_api)
    assert "not a Kaggle API key" in said[0] and not kaggle.key_path().exists()
    good = tmp_path / "kaggle (1).json"
    good.write_text('{"username": "friend", "key": "k"}', encoding="utf-8")
    assert kaggle.setup(str(good), echo=said.append, api_factory=_ok_api)


def test_setup_without_a_key_says_where_to_get_one(fake_home, fake_quota):
    said = []
    assert not kaggle.setup(echo=said.append, api_factory=_ok_api)
    assert "Generate New Token" in said[0]


def test_setup_warns_when_no_gpu_hours(fake_home, fake_quota):
    fake_quota.update(total_h=0.0, left_h=0.0)
    (fake_home / "Downloads" / "kaggle.json").write_text('{"username": "f", "key": "k"}', encoding="utf-8")
    said = []
    kaggle.setup(echo=said.append, api_factory=_ok_api)
    assert any("verify your phone" in s for s in said)


def test_setup_takes_the_newer_token_string(fake_home, fake_quota):
    """Kaggle's Settings → API now gives a token string (kagglesdk reads ~/.kaggle/access_token first)."""
    said = []
    assert kaggle.setup("KGAT_0123456789abcdefABCDEF", echo=said.append, api_factory=_ok_api)
    assert kaggle.token_path().read_text(encoding="utf-8") == "KGAT_0123456789abcdefABCDEF"
    assert not any("0123456789abcdef" in s for s in said)  # never printed
    said.clear()
    assert not kaggle.setup("nope", echo=said.append, api_factory=_ok_api)
    assert "neither a file nor a Kaggle token" in said[0]


def test_the_librarys_own_sign_in_help_is_not_printed(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(tmp_path))
    for var in ("KAGGLE_USERNAME", "KAGGLE_KEY", "KAGGLE_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(kaggle.os.path, "expanduser", lambda p: p.replace("~", str(tmp_path)), raising=False)
    with pytest.raises(kaggle.KaggleError):
        kaggle.client()
    out = capsys.readouterr()
    assert "Authentication required" not in out.out + out.err
