"""`mitra dashboard`: the dashboard on localhost (D-042). Standard library only, 127.0.0.1 only, read-only.

The page is the same as `~/.mitra/dashboard.html`, plus a Refresh button. A normal load is served from cache while
the store has not changed; the button (`/?refresh=1`) always rebuilds, merging any old records into the store first.
"""
from __future__ import annotations

import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.core import dashboard as D
from app.core import store

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}/"

_BUTTON = ("<a href='/?refresh=1' style='float:right;padding:4px 12px;border:1px solid var(--acc);border-radius:6px;"
           "color:var(--acc);text-decoration:none'>Refresh</a>")


def store_signature() -> tuple:
    """Changes whenever a record or trace is added to or grows in the store."""
    base = store.runs_root()
    if not base.is_dir():
        return ()
    return tuple(sorted((str(p), p.stat().st_size) for p in base.rglob("*.jsonl")))


class Pages:
    """Page cache keyed by the store signature. Thread-safe: one rebuild at a time."""

    def __init__(self, roots: list[Path] | None = None):
        self.roots = roots
        self.lock = threading.Lock()
        self.html, self.sig, self.builds = "", None, 0

    def get(self, force: bool = False) -> str:
        with self.lock:
            sig = store_signature()
            if force or not self.html or sig != self.sig:
                page, _ = D.page_html(self.roots)  # merges old records, so take the signature after it
                self.html = page.replace("<h1>Mitra dashboard</h1>", f"{_BUTTON}<h1>Mitra dashboard</h1>", 1)
                self.sig, self.builds = store_signature(), self.builds + 1
            return self.html


def make_server(port: int = PORT, roots: list[Path] | None = None) -> ThreadingHTTPServer:
    pages = Pages(roots)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str, ctype: str = "text/html; charset=utf-8") -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802 (http.server API)
            path, _, query = self.path.partition("?")
            if path == "/health":
                return self._send(200, "mitra dashboard", "text/plain; charset=utf-8")
            if path != "/":
                return self._send(404, "not found", "text/plain; charset=utf-8")
            try:
                force = "refresh=1" in query
                html = pages.get(force=force)
            except Exception as exc:  # show the error, keep serving
                return self._send(500, f"dashboard failed: {exc}", "text/plain; charset=utf-8")
            if force:  # back to the clean URL, so a browser reload does not rebuild again
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
                return
            self._send(200, html)

        def log_message(self, *args):  # quiet: no request log in the terminal
            pass

    server = ThreadingHTTPServer((HOST, port), Handler)
    server.pages = pages
    return server


def running(port: int = PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/health", timeout=0.5) as r:
            return r.read().startswith(b"mitra dashboard")
    except OSError:
        return False
