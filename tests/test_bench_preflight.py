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


def _fake_ollama(loaded):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            payload = {
                "/api/version": {"version": "0.40.8"},
                "/api/tags": {"models": [{"name": "qwen3.5:4b", "digest": "abc"}]},
                "/api/ps": {"models": [{"name": n} for n in loaded]},
            }[self.path]
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


@pytest.fixture
def plenty_of_ram(monkeypatch):
    monkeypatch.setattr(preflight.psutil, "virtual_memory", lambda: Mem(16 * 2**30))
    monkeypatch.setattr(preflight, "gpu_status", lambda: None)


def test_ready(plenty_of_ram):
    server, url = _fake_ollama(loaded=[])
    try:
        facts, problems = preflight.check(url, "qwen3.5:4b")
    finally:
        server.shutdown()
    assert problems == []
    assert facts["ollama_version"] == "0.40.8"
    assert facts["model_digest"] == "abc"


def test_missing_model_and_other_model_loaded(plenty_of_ram):
    server, url = _fake_ollama(loaded=["gemma4:e4b"])
    try:
        _, problems = preflight.check(url, "qwen3:8b")
    finally:
        server.shutdown()
    assert any("not pulled" in p for p in problems)
    assert any("other models are loaded" in p for p in problems)


def test_low_ram_blocks(monkeypatch):
    monkeypatch.setattr(preflight.psutil, "virtual_memory", lambda: Mem(3 * 2**30))
    monkeypatch.setattr(preflight, "gpu_status", lambda: None)
    server, url = _fake_ollama(loaded=[])
    try:
        _, problems = preflight.check(url, "qwen3.5:4b")
    finally:
        server.shutdown()
    assert any("free RAM" in p for p in problems)


def test_ollama_down_blocks():
    _, problems = preflight.check("http://127.0.0.1:9", "qwen3.5:4b")
    assert problems and "not reachable" in problems[0]
