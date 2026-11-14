"""Web search that works without an API key (E-024).

General search pages (DuckDuckGo, Bing, Mojeek) block or garble automated requests from this machine, so CodeMitra asks
open APIs that allow it, in parallel, and labels each result with its source:

    Wikipedia (topics, background) · Hugging Face (models, datasets) · GitHub (code, libraries) ·
    arXiv (papers) · Ollama library (local models)

DuckDuckGo is still tried first with a short timeout; after one failure it is skipped for the rest of the session.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

USER_AGENT = "CodeMitra/0.1 (local coding assistant; https://github.com/prashanth-ds-ml/codemitra)"
SOURCE_TIMEOUT = 8  # seconds per source; they run in parallel


@dataclass
class Result:
    source: str
    title: str
    url: str
    snippet: str = ""


def _get(url: str, timeout: float = SOURCE_TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(400_000)
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def _clean(text: str, n: int = 200) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


# ── sources ──────────────────────────────────────────────────────────────────

def wikipedia(query: str, n: int) -> list[Result]:
    data = json.loads(_get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": n})))
    return [Result("Wikipedia", r["title"], "https://en.wikipedia.org/wiki/" + urllib.parse.quote(r["title"].replace(" ", "_")),
                   _clean(r.get("snippet", ""))) for r in data.get("query", {}).get("search", [])]


def short_query(query: str, words: int = 2) -> str:
    """Name-based search (Hugging Face, GitHub, Ollama) finds nothing for long questions; keep the first words."""
    return " ".join(re.findall(r"[\w.+-]+", query)[:words]) or query


def _with_fallback(fn, query: str, n: int) -> list[Result]:
    results = fn(query, n)
    if not results and len(query.split()) > 2:
        results = fn(short_query(query), n)
    return results


def huggingface(query: str, n: int) -> list[Result]:
    return _with_fallback(_huggingface, query, n)


def github(query: str, n: int) -> list[Result]:
    return _with_fallback(_github, query, n)


def ollama_library(query: str, n: int) -> list[Result]:
    return _with_fallback(_ollama_library, query, n)


def _huggingface(query: str, n: int) -> list[Result]:
    data = json.loads(_get("https://huggingface.co/api/models?" + urllib.parse.urlencode(
        {"search": query, "sort": "downloads", "limit": n})))
    out = []
    for m in data:
        tags = [t for t in (m.get("pipeline_tag"), m.get("library_name")) if t]
        snippet = ", ".join(tags + [f"{m.get('downloads', 0):,} downloads", f"{m.get('likes', 0):,} likes"])
        out.append(Result("Hugging Face", m["id"], f"https://huggingface.co/{m['id']}", snippet))
    return out


def _github(query: str, n: int) -> list[Result]:
    data = json.loads(_get("https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": query, "sort": "stars", "per_page": n})))
    return [Result("GitHub", r["full_name"], r["html_url"],
                   _clean(f"{r.get('description') or ''} ({r.get('stargazers_count', 0):,} stars)"))
            for r in data.get("items", [])]


def arxiv(query: str, n: int) -> list[Result]:
    text = _get("http://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"search_query": f"all:{query}", "max_results": n, "sortBy": "relevance"}))
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", text, re.S):
        title = re.search(r"<title>(.*?)</title>", entry, re.S)
        link = re.search(r"<id>(.*?)</id>", entry, re.S)
        summary = re.search(r"<summary>(.*?)</summary>", entry, re.S)
        published = re.search(r"<published>(\d{4}-\d{2}-\d{2})", entry)
        if title and link:
            snippet = (published.group(1) + " · " if published else "") + _clean(summary.group(1) if summary else "")
            out.append(Result("arXiv", _clean(title.group(1), 150), link.group(1).strip(), snippet))
    return out


def _ollama_library(query: str, n: int) -> list[Result]:
    text = _get("https://ollama.com/search?" + urllib.parse.urlencode({"q": query}))
    out, seen = [], set()
    for name in re.findall(r'href="/library/([A-Za-z0-9._-]+)"', text):
        if name not in seen:
            seen.add(name)
            out.append(Result("Ollama", name, f"https://ollama.com/library/{name}", "model in the Ollama library"))
        if len(out) >= n:
            break
    return out


class _Ddg:
    """DuckDuckGo's HTML page; skipped for the session after it fails once."""
    available = True

    @classmethod
    def search(cls, query: str, n: int) -> list[Result]:
        if not cls.available:
            return []
        try:
            text = _get("https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query}), timeout=5)
        except Exception:
            cls.available = False
            raise
        out = []
        for href, title in re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', text, re.S):
            target = urllib.parse.parse_qs(urllib.parse.urlparse(html.unescape(href)).query).get("uddg", [href])[0]
            out.append(Result("Web", _clean(title, 150), target))
            if len(out) >= n:
                break
        return out


SOURCES = {
    "web": _Ddg.search,
    "wikipedia": wikipedia,
    "huggingface": huggingface,
    "github": github,
    "arxiv": arxiv,
    "ollama": ollama_library,
}


def search(query: str, *, per_source: int = 4, sources: dict | None = None) -> tuple[list[Result], dict[str, str]]:
    """Ask every source at once. Returns (results in source order, {source: error} for the ones that failed)."""
    sources = sources or SOURCES
    found: dict[str, list[Result]] = {}
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures = {pool.submit(fn, query, per_source): name for name, fn in sources.items()}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                found[name] = fut.result()
            except Exception as exc:
                errors[name] = _clean(str(exc), 120) or type(exc).__name__
    ordered = [r for name in sources if name in found for r in found[name]]
    return ordered, errors


def format_results(query: str, results: list[Result], errors: dict[str, str]) -> str:
    if not results:
        detail = "; ".join(f"{k}: {v}" for k, v in errors.items()) or "no results"
        return (f"✗ Web search failed: no source returned results for '{query}' ({detail}). "
                "CodeMitra may be offline.") if errors else f"No web results found for '{query}'."
    used = list(dict.fromkeys(r.source for r in results))
    lines = [f"# Web results for '{query}'", f"Sources: {', '.join(used)}. Use fetch_url on a result to read it."]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. [{r.source}] {r.title}")
        lines.append(f"   {r.url}")
        if r.snippet:
            lines.append(f"   {r.snippet}")
    return "\n".join(lines)
