"""Logging proxy between a coding agent and Ollama.

Every request is forwarded unchanged (streaming included) and one JSON line is written per call:
what the agent sent (messages, tools, system prompt size) and what Ollama reported (prompt and output tokens).
Works for Ollama's native API (/api/chat), its OpenAI API (/v1/chat/completions) and its Anthropic API
(/v1/messages), so every agent is measured the same way.

    python bench/proxy.py --port 11500 --upstream http://127.0.0.1:11435 --log results/calls.jsonl
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HOP_HEADERS = {"host", "content-length", "connection", "transfer-encoding", "accept-encoding"}
MAX_SCAN_BYTES = 4_000_000
# usage fields across the three APIs; the largest value seen in a response is kept
PROMPT_KEYS = ("prompt_eval_count", "prompt_tokens", "input_tokens")
OUTPUT_KEYS = ("eval_count", "completion_tokens", "output_tokens")


def _text_len(content) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(_text_len(part.get("text", "")) if isinstance(part, dict) else _text_len(part) for part in content)
    return 0


def describe_request(body: bytes) -> dict:
    """Size of what the agent sent, independent of any tokenizer."""
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        return {"json": False, "bytes": len(body)}
    messages = data.get("messages") or data.get("input") or []  # Chat / Anthropic, or OpenAI Responses (Codex)
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    tools = data.get("tools") or []
    system_chars = _text_len(data.get("system", "")) + _text_len(data.get("instructions", ""))  # Anthropic, Responses
    system_chars += sum(_text_len(m.get("content", "")) for m in messages if m.get("role") == "system")
    return {
        "json": True,
        "bytes": len(body),
        "model": data.get("model"),
        "stream": data.get("stream"),
        "n_messages": len(messages),
        "n_tools": len(tools),
        "tool_names": sorted(t.get("name") or (t.get("function") or {}).get("name") or "?" for t in tools),
        "tools_chars": len(json.dumps(tools)) if tools else 0,
        "system_chars": system_chars,
        "num_ctx": (data.get("options") or {}).get("num_ctx"),
    }


def _max_int(text: str, keys: tuple[str, ...]) -> int | None:
    found = [int(m) for k in keys for m in re.findall(rf'"{k}"\s*:\s*(\d+)', text)]
    return max(found) if found else None


def describe_response(raw: bytes) -> dict:
    text = raw.decode("utf-8", errors="replace")
    return {
        "prompt_tokens": _max_int(text, PROMPT_KEYS),
        "output_tokens": _max_int(text, OUTPUT_KEYS),
        "has_tool_call": any(k in text for k in ('"tool_calls"', '"tool_use"')),
    }


class _Handler(BaseHTTPRequestHandler):
    upstream: str = "http://127.0.0.1:11434"
    log_path: Path | None = None
    lock = threading.Lock()

    def log_message(self, *args) -> None:  # keep stdout quiet
        pass

    def _proxy(self) -> None:
        started = time.time()
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        up = urlsplit(self.upstream)
        conn = http.client.HTTPConnection(up.hostname, up.port or 80, timeout=900)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_HEADERS}
        entry = {"t": round(started, 3), "method": self.command, "path": self.path, "request": describe_request(body)}
        scanned = bytearray()
        try:
            conn.request(self.command, self.path, body=body or None, headers=headers)
            resp = conn.getresponse()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in HOP_HEADERS:
                    self.send_header(k, v)
            self.send_header("Connection", "close")
            self.end_headers()
            while chunk := resp.read1(65536):
                self.wfile.write(chunk)
                self.wfile.flush()
                if len(scanned) < MAX_SCAN_BYTES:
                    scanned += chunk
            entry["status"] = resp.status
        except (OSError, http.client.HTTPException) as exc:
            entry["status"] = None
            entry["error"] = f"{type(exc).__name__}: {exc}"
            try:
                self.send_error(502, "upstream error")
            except OSError:
                pass
        finally:
            conn.close()
        entry["response"] = describe_response(bytes(scanned))
        entry["seconds"] = round(time.time() - started, 3)
        if self.log_path:
            with self.lock, self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = _proxy


def serve(port: int, upstream: str, log_path: Path) -> ThreadingHTTPServer:
    """Start the proxy in a background thread; call .shutdown() to stop."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = type("Handler", (_Handler,), {"upstream": upstream, "log_path": log_path})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.protocol_version = "HTTP/1.0"  # stream until close; no chunked encoding to rewrite
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=11500)
    parser.add_argument("--upstream", default="http://127.0.0.1:11435")
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    server = serve(args.port, args.upstream, args.log)
    print(f"proxy :{args.port} -> {args.upstream}, logging to {args.log}", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
