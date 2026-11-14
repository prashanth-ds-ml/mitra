"""D-060: CodeMitra on a remote Ollama (Kaggle) through the token proxy."""
import json
import os
import pathlib
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app import config, fit, remote

ROOT = pathlib.Path(__file__).resolve().parents[1]
KAGGLE = ROOT / "remote" / "kaggle"


class FakeOllama(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        FakeOllama.seen.append(("GET", self.path))
        body = json.dumps({"models": [{"name": "mimo-v2.6:9b", "model": "mimo-v2.6:9b", "size": 6_100_000_000}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        FakeOllama.seen.append(("POST", self.path, json.loads(self.rfile.read(n) or b"{}")))
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for word in ("he", "llo", ""):
            line = json.dumps({"message": {"content": word}, "done": word == ""}).encode() + b"\n"
            self.wfile.write(b"%x\r\n%s\r\n" % (len(line), line))
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")


def _serve(server):
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def stack():
    """A fake Ollama behind the real token proxy."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("kaggle_proxy", KAGGLE / "proxy.py")
    proxy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proxy)
    FakeOllama.seen = []
    up = _serve(ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama))
    px = _serve(proxy.serve("s3cret-tok", 0, f"127.0.0.1:{up.server_address[1]}"))
    yield f"http://127.0.0.1:{px.server_address[1]}"
    px.shutdown()
    up.shutdown()


def test_the_proxy_refuses_requests_without_the_token(stack):
    for path in ("/api/tags", "/wrong/api/tags", "/s3cret-tokX/api/tags", "/"):
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(stack + path, timeout=5)
        assert err.value.code == 404
    assert FakeOllama.seen == []  # nothing reached Ollama


def test_the_proxy_forwards_and_streams_with_the_token(stack):
    with urllib.request.urlopen(stack + "/s3cret-tok/api/tags", timeout=5) as r:
        assert json.loads(r.read())["models"][0]["name"] == "mimo-v2.6:9b"
    req = urllib.request.Request(stack + "/s3cret-tok/api/chat", data=json.dumps({"model": "m"}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        lines = [json.loads(line) for line in r.read().splitlines() if line.strip()]
    assert "".join(x["message"]["content"] for x in lines) == "hello" and lines[-1]["done"]
    assert FakeOllama.seen[-1] == ("POST", "/api/chat", {"model": "m"})


def test_chat_ollama_works_through_the_proxy_url(stack):
    """The token lives in the URL path: the ollama client keeps it (no header plumbing needed)."""
    import ollama
    client = ollama.Client(host=stack + "/s3cret-tok")
    assert [m.model for m in client.list().models] == ["mimo-v2.6:9b"]


def test_set_status_and_off(stack, monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    data = remote.set_remote(stack + "/s3cret-tok/api/", 262144)
    assert data["url"] == stack + "/s3cret-tok" and remote.active()["num_ctx"] == 262144
    assert remote.shown(data["url"]) == stack + "/…"  # the token is never shown
    cfg = remote.apply({"ollama_local_base_url": "http://localhost:11434", "num_ctx": 0})
    assert cfg["ollama_local_base_url"] == data["url"] and cfg["num_ctx"] == 262144 and cfg["remote"] == "kaggle"
    assert os.environ["OLLAMA_HOST"] == data["url"] and config._ollama_base_url() == data["url"]
    assert remote.apply({"num_ctx": 65536})["num_ctx"] == 65536  # codemitra.toml still wins
    assert remote.clear() and remote.active() is None
    monkeypatch.delenv("OLLAMA_HOST", raising=False)


def test_the_model_list_comes_from_the_remote(stack, monkeypatch):
    """`ollama list` would drop the token path: the inventory asks the remote's /api/tags."""
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    remote.set_remote(stack + "/s3cret-tok")
    monkeypatch.setattr(config, "get_model_facts", lambda name: {"capabilities": ("completion", "tools"),
                                                                 "parameters": 9e9, "context": 262144})
    real_run = config.subprocess.run

    def run(args, **kw):
        assert args[0] != "ollama", "ran `ollama list`"
        return real_run(args, **kw)

    monkeypatch.setattr(config.subprocess, "run", run)
    inv = config.get_local_model_inventory()
    assert [(m.name, m.placement) for m in inv] == [("mimo-v2.6:9b", "remote")]
    remote.clear()
    monkeypatch.delenv("OLLAMA_HOST", raising=False)


def test_memory_check_and_free_skip_this_machine(monkeypatch):
    remote.set_remote("https://x.trycloudflare.com/tok", 262144)
    monkeypatch.setattr(config, "get_gpu_memory_info", lambda: pytest.fail("checked the local GPU"))
    f = fit.check("mimo-v2.6:9b", 262144)
    assert f.verdict == "remote" and fit.summary(f) == "☁ runs on kaggle at 256K · this machine's RAM is not used"
    assert fit.advice(f) == []
    from app import main
    main._cmd_free("mimo-v2.6:9b", 262144, "x", tick=lambda *a: pytest.fail("offered to close programs"))
    remote.clear()


def test_codemitra_solve_uses_the_configured_address(monkeypatch, tmp_path):
    """Night runs (`codemitra solve`) always used localhost; they now follow codemitra.toml / the remote."""
    from app.core import cli
    seen = {}

    def fake_llm(model, **kw):
        seen.update(kw)
        raise SystemExit(0)

    monkeypatch.setattr(cli, "get_local_llm", fake_llm)
    monkeypatch.setattr(cli.config, "load", lambda: {"ollama_local_base_url": "https://x/tok", "num_ctx": 262144})
    with pytest.raises(SystemExit):
        cli.cmd_solve("t", workspace=str(tmp_path), model="mimo-v2.6:9b")
    assert seen["base_url"] == "https://x/tok" and seen["num_ctx"] == 262144


def test_the_notebook_embeds_the_tested_proxy_and_is_up_to_date():
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_nb", KAGGLE / "build_notebook.py")
    nb_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nb_mod)
    built = nb_mod.build()
    saved = json.loads((KAGGLE / "codemitra_kaggle_server.ipynb").read_text(encoding="utf-8"))
    assert saved == built, "run python remote/kaggle/build_notebook.py"
    proxy_cell = "".join(next(c["source"] for c in saved["cells"] if "".join(c["source"]).startswith("%%writefile")))
    assert proxy_cell.split("\n", 1)[1] == (KAGGLE / "proxy.py").read_text(encoding="utf-8")
    code = "".join("".join(c["source"]) for c in saved["cells"])
    for needed in ("OLLAMA_KV_CACHE_TYPE=\"q8_0\"", "OLLAMA_FLASH_ATTENTION=\"1\"", "CONTEXT = 262144",
                   "codemitra remote set {URL} --ctx {CONTEXT}", "trycloudflare"):
        assert needed in code
