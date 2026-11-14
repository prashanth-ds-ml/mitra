"""Token proxy in front of Ollama, for the Kaggle notebook (D-060). Standard library only.

Ollama has no login, and the Cloudflare quick tunnel makes it public. This proxy answers only requests whose path
starts with /<token>/ (e.g. /<token>/api/chat), strips the token and forwards the rest to Ollama, streaming the reply
back as it comes (chat replies arrive token by token). Anything else gets 404, so a found URL without the token is
useless.

    python proxy.py <token> [port=8000] [ollama=127.0.0.1:11434] [state_dir]

With a state_dir (the notebook passes /kaggle/working): `POST /<token>/mitra/stop` writes `stop` there (the notebook
then shuts everything down, which ends the Kaggle run), and every model request touches `last_request`, so the
notebook can stop by itself when CodeMitra has not used it for a while.
"""
from __future__ import annotations

import hmac
import http.client
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

QUIET = {"/api/tags", "/api/ps", "/api/version", "/api/show"}  # status checks: not "CodeMitra is using it"

HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "proxy-authorization",
       "proxy-authenticate", "host", "content-length"}


def _touch(path: str) -> None:
    with open(path, "a", encoding="utf-8"):
        pass
    os.utime(path, None)


def make_handler(token: str, upstream: str, state_dir: str | None = None):
    host, _, port = upstream.partition(":")
    port_n = int(port or 11434)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # keep the notebook quiet; the token must not appear in logs
            pass

        def _refuse(self) -> None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _forward(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None  # read first: a refused client gets a clean 404
            parts = self.path.split("/", 2)  # "", token, rest
            if len(parts) < 2 or not hmac.compare_digest(parts[1].encode(), token.encode()):
                self._refuse()
                return
            tail = "/" + (parts[2] if len(parts) > 2 else "")
            if tail.startswith("/mitra/"):  # CodeMitra's own commands, never forwarded to Ollama
                ok = tail == "/mitra/ping" or (tail == "/mitra/stop" and state_dir is not None)
                if ok and tail == "/mitra/stop":
                    _touch(os.path.join(state_dir, "stop"))
                msg = (b'{"ok": true, "time": %d}' % int(time.time())) if ok else b'{"ok": false}'
                self.send_response(200 if ok else 404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
                return
            if state_dir is not None and tail.split("?")[0] not in QUIET:
                _touch(os.path.join(state_dir, "last_request"))
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
            conn = http.client.HTTPConnection(host, port_n, timeout=3600)  # a long generation is normal
            try:
                conn.request(self.command, tail, body=body, headers=headers)
                resp = conn.getresponse()
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() not in HOP:
                        self.send_header(k, v)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                while True:
                    chunk = resp.read1(65536)
                    if not chunk:
                        break
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except (ConnectionError, OSError) as exc:
                try:
                    msg = f'{{"error": "proxy: {type(exc).__name__}"}}'.encode()
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(msg)))
                    self.end_headers()
                    self.wfile.write(msg)
                except OSError:
                    pass
            finally:
                conn.close()

        do_GET = do_POST = do_DELETE = do_PUT = _forward

    return Handler


def serve(token: str, port: int = 8000, upstream: str = "127.0.0.1:11434",
          state_dir: str | None = None) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(token, upstream, state_dir))
    server.daemon_threads = True
    return server


if __name__ == "__main__":
    tok = sys.argv[1]
    prt = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    up = sys.argv[3] if len(sys.argv) > 3 else "127.0.0.1:11434"
    state = sys.argv[4] if len(sys.argv) > 4 else None
    print(f"proxy on 127.0.0.1:{prt} -> {up}", flush=True)
    serve(tok, prt, up, state).serve_forever()
