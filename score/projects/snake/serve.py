"""Play the game: python serve.py, then open http://localhost:8000"""
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from snake.api import handle

WEB = Path(__file__).resolve().parent / "web"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def _api(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}") if length else None
        status, data = handle(method, self.path, body)
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._api("GET")
        else:
            super().do_GET()

    def do_POST(self):
        self._api("POST")


if __name__ == "__main__":
    print("Snake on http://localhost:8000")
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
