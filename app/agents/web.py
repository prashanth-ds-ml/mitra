"""Web Agent — searches the web and reads specific URLs."""
from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from langchain_core.tools import tool


_USER_AGENT = "Mitra/1.0 (+https://github.com)"
_MAX_FETCH_CHARS = 6000
_DEFAULT_TIMEOUT = 15

# D-077 (local first): with no internet the web tools say so at once and plainly, instead of waiting on timeouts
# and leaving the model to answer from memory as if it had searched
OFFLINE = ("✗ Offline: there is no internet connection, so nothing was searched or opened. Tell the user plainly "
           "that you are offline; if you answer from what you already know, say it is not checked.")
_PROBES = (("1.1.1.1", 53), ("8.8.8.8", 53))
_ONLINE_TTL = 30.0
_online_cache: dict = {"t": -1e9, "ok": True}


def is_online(timeout: float = 1.5) -> bool:
    """A quick TCP connect to a public DNS server; remembered for 30 s so a turn with several searches asks once."""
    import socket
    import time

    now = time.monotonic()
    if now - _online_cache["t"] < _ONLINE_TTL:
        return _online_cache["ok"]
    ok = False
    for host, port in _PROBES:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                ok = True
                break
        except OSError:
            continue
    _online_cache.update(t=now, ok=ok)
    return ok






def _http_get(url: str, timeout: int = _DEFAULT_TIMEOUT) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(250_000)
        charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()






class _PageTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._capture_title = False
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif tag == "title":
            self._capture_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._capture_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self._capture_title:
            self.title = text
        else:
            self._chunks.append(text)

    def text(self, max_chars: int) -> str:
        joined = " ".join(self._chunks)
        compact = re.sub(r"\s+", " ", html.unescape(joined)).strip()
        return compact[:max_chars].rstrip()


@tool
def search_web(query: str, max_results: int = 5) -> str:
    """
    Search Wikipedia, Hugging Face (models), GitHub (code), arXiv (papers) and the Ollama library at once.
    Returns titles, URLs and short snippets labelled by source; read a result with fetch_url.
    Use short queries (2-5 words), e.g. "Qwen3.5" or "qwen3.5 benchmark".
    """
    from app.agents.search_sources import format_results, search

    q = (query or "").strip()
    if not q:
        return "✗ No search query provided."
    if not is_online():
        return OFFLINE
    per_source = max(2, min(int(max_results or 4), 8))
    results, errors = search(q, per_source=per_source)
    return format_results(q, results, errors)


def readme_url(url: str) -> str | None:
    """Raw README for a Hugging Face model/dataset page or a GitHub repo page, else None."""
    m = re.match(r"^https?://huggingface\.co/(datasets/)?([\w.-]+)/([\w.-]+)/?$", url)
    if m and m.group(2) not in {"docs", "blog", "spaces", "papers", "models", "datasets"}:
        return f"https://huggingface.co/{m.group(1) or ''}{m.group(2)}/{m.group(3)}/raw/main/README.md"
    m = re.match(r"^https?://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", url)
    if m and m.group(1) not in {"orgs", "topics", "search", "marketplace", "features"}:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/HEAD/README.md"
    return None


@tool
def fetch_url(url: str, max_chars: int = _MAX_FETCH_CHARS) -> str:
    """
    Fetch a specific URL and return the page title plus the main readable text.
    Use when the user gives a webpage URL or asks to inspect a specific page.
    """
    target = (url or "").strip()
    if not target:
        return "✗ No URL provided."
    if not re.match(r"^https?://", target, re.IGNORECASE):
        target = "https://" + target
    if not is_online():
        return OFFLINE
    # E-024: model and repo pages are mostly site menus; read their README instead.
    raw = readme_url(target)
    if raw:
        try:
            text = _http_get(raw)
            return f"# README of {target}\nURL: {target}\n\n{text[:max_chars].rstrip()}"
        except Exception:
            pass  # fall back to the page itself
    try:
        html_text = _http_get(target)
    except Exception as exc:
        return f"✗ URL fetch failed: {exc}"

    parser = _PageTextParser()
    parser.feed(html_text)
    page_text = parser.text(max(500, max_chars))
    if not page_text:
        page_text = _strip_tags(html_text)[:max_chars].rstrip()
    title = parser.title or target
    return f"# {title}\nURL: {target}\n\n{page_text[:max_chars].rstrip()}"


_ALL_TOOLS = [search_web, fetch_url]















