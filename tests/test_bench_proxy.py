"""Tests for bench/proxy.py against a fake upstream (no Ollama needed)."""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "bench" / "proxy.py"
_spec = importlib.util.spec_from_file_location("mitra_bench_proxy", _PATH)
proxy = importlib.util.module_from_spec(_spec)
sys.modules["mitra_bench_proxy"] = proxy
_spec.loader.exec_module(proxy)

NDJSON = b'{"message":{"content":"he"}}\n{"message":{"content":"llo"},"done":true,"prompt_eval_count":1234,"eval_count":5}\n'
SSE = (
    b'event: message_start\ndata: {"type":"message_start","message":{"usage":{"input_tokens":32800,"output_tokens":1}}}\n\n'
    b'event: content_block_start\ndata: {"type":"content_block_start","content_block":{"type":"tool_use","name":"Read"}}\n\n'
    b'event: message_delta\ndata: {"type":"message_delta","usage":{"output_tokens":42}}\n\n'
)


class _Upstream(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = SSE if self.path == "/v1/messages" else NDJSON
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for line in body.splitlines(keepends=True):
            self.wfile.write(line)
            self.wfile.flush()


@pytest.fixture
def upstream():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _start(upstream_url, log):
    server = proxy.serve(0, upstream_url, log)
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def _post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read()


def _entries(log):
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def test_native_chat_logged_and_streamed(tmp_path, upstream):
    log = tmp_path / "calls.jsonl"
    server, url = _start(upstream, log)
    try:
        payload = {
            "model": "qwen3.5:4b",
            "messages": [{"role": "system", "content": "x" * 300}, {"role": "user", "content": "hi"}],
            "tools": [{"type": "function", "function": {"name": "read_file", "parameters": {}}}],
            "options": {"num_ctx": 32768},
        }
        status, body = _post(url + "/api/chat", payload)
    finally:
        server.shutdown()
    assert status == 200
    assert body == NDJSON  # passed through unchanged
    (entry,) = _entries(log)
    assert entry["path"] == "/api/chat"
    assert entry["request"]["n_tools"] == 1
    assert entry["request"]["tool_names"] == ["read_file"]
    assert entry["request"]["system_chars"] == 300
    assert entry["request"]["num_ctx"] == 32768
    assert entry["response"]["prompt_tokens"] == 1234
    assert entry["response"]["output_tokens"] == 5


def test_anthropic_messages_usage(tmp_path, upstream):
    log = tmp_path / "calls.jsonl"
    server, url = _start(upstream, log)
    try:
        payload = {"model": "m", "system": [{"type": "text", "text": "abc"}], "messages": [], "tools": [{"name": "Read"}]}
        _post(url + "/v1/messages", payload)
    finally:
        server.shutdown()
    (entry,) = _entries(log)
    assert entry["request"]["system_chars"] == 3
    assert entry["request"]["tool_names"] == ["Read"]
    assert entry["response"]["prompt_tokens"] == 32800
    assert entry["response"]["output_tokens"] == 42
    assert entry["response"]["has_tool_call"] is True


def test_upstream_down_is_logged_as_error(tmp_path):
    log = tmp_path / "calls.jsonl"
    server, url = _start("http://127.0.0.1:9", log)  # nothing listens on port 9
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post(url + "/api/chat", {"messages": []})
    finally:
        server.shutdown()
    assert exc.value.code == 502
    (entry,) = _entries(log)
    assert entry["status"] is None
    assert "error" in entry
