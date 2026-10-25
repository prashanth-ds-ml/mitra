"""Tests for bench/preflight.py against a fake Ollama."""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
from collections import namedtuple
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "bench" / "preflight.py"
_spec = importlib.util.spec_from_file_location("mitra_bench_preflight", _PATH)
preflight = importlib.util.module_from_spec(_spec)
sys.modules["mitra_bench_preflight"] = preflight
_spec.loader.exec_module(preflight)

Mem = namedtuple("Mem", "available")
GB = 2**30


def _fake_ollama(loaded, context=65536):
    loaded = list(loaded)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, payload):
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._send(
                {
                    "/api/version": {"version": "0.40.8"},
                    "/api/tags": {"models": [{"name": "qwen3.5:4b", "digest": "abc", "size": int(3.4 * GB)}]},
                    "/api/ps": {
                        "models": [{"name": n, "context_length": context, "size": 4 * GB, "size_vram": 4 * GB} for n in loaded]
                    },
                }[self.path]
            )

        def do_POST(self):
            model = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))["model"]
            if model not in loaded:
                loaded.append(model)
            self._send({"done": True})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def _ram(monkeypatch, gb):
    monkeypatch.setattr(preflight.psutil, "virtual_memory", lambda: Mem(gb * GB))
    monkeypatch.setattr(preflight, "gpu_status", lambda: None)


def _check(model="qwen3.5:4b", loaded=(), context=65536, **kw):
    server, url = _fake_ollama(loaded, context)
    try:
        return preflight.check(url, model, **kw)
    finally:
        server.shutdown()


def test_ready_and_context_recorded(monkeypatch):
    _ram(monkeypatch, 16)
    facts, problems = _check()
    assert problems == []
    assert facts["ollama_version"] == "0.40.8"
    assert facts["model_digest"] == "abc"
    assert facts["loaded"] == {"context_length": 65536, "gpu_share": 1.0}


def test_small_context_blocks(monkeypatch):
    _ram(monkeypatch, 16)
    _, problems = _check(context=4096)
    assert any("context 4096 < 65536" in p for p in problems)


def test_missing_model_and_other_model_loaded(monkeypatch):
    _ram(monkeypatch, 16)
    _, problems = _check(model="qwen3:8b", loaded=["gemma4:e4b"])
    assert any("not pulled" in p for p in problems)
    assert any("other models are loaded" in p for p in problems)


def test_ram_need_follows_model_size(monkeypatch):
    _ram(monkeypatch, 6.5)  # 3.4 GB model + 3 GB headroom = 6.4 GB
    facts, problems = _check()
    assert problems == [] and facts["min_free_ram_gb"] == 6.4
    _ram(monkeypatch, 5)
    _, problems = _check()
    assert any("free RAM" in p for p in problems)


def test_loaded_model_needs_only_headroom(monkeypatch):
    """E-009: the second run in a row was blocked because the loaded model's RAM was counted twice."""
    _ram(monkeypatch, 5.5)
    facts, problems = _check(loaded=["qwen3.5:4b"])
    assert problems == [] and facts["min_free_ram_gb"] == 3.0


def test_explicit_ram_floor_wins(monkeypatch):
    _ram(monkeypatch, 8)
    _, problems = _check(min_free_ram_gb=11)
    assert any("free RAM" in p for p in problems)


def test_ollama_down_blocks():
    _, problems = preflight.check("http://127.0.0.1:9", "qwen3.5:4b")
    assert problems and "not reachable" in problems[0]


@pytest.mark.parametrize("key", ["OLLAMA_CONTEXT_LENGTH", "OLLAMA_HOST", "OLLAMA_MAX_LOADED_MODELS", "OLLAMA_NUM_PARALLEL"])
def test_bench_server_settings(key):
    import ollama_server

    env = ollama_server.server_env({"OLLAMA_HOST": "0.0.0.0:11434", "PATH": "x"})
    assert env[key] == ollama_server.SETTINGS[key]
    assert env["PATH"] == "x" and env["OLLAMA_CONTEXT_LENGTH"] == "65536"
