"""Web Agent — searches the web and reads specific URLs."""
from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from app.prompts import WEB_SYSTEM_PROMPT as _SYSTEM_PROMPT

_USER_AGENT = "Mitra/1.0 (+https://github.com)"
_MAX_FETCH_CHARS = 6000
_DEFAULT_TIMEOUT = 15


def _invoke_with_status(llm_with_tools, messages: list, console: Console | None, label: str) -> AIMessage:
    if console is None:
        return llm_with_tools.invoke(messages)
    with console.status(f"[m.dim]{label}[/m.dim]", spinner="dots", spinner_style="m.accent"):
        return llm_with_tools.invoke(messages)


def _run_tool_with_status(fn, args: dict, console: Console | None, label: str) -> str:
    from app.agents.filesystem import safe_invoke  # bad arguments go back to the model (E-018)

    name = getattr(fn, "name", "tool")
    if console is None:
        return safe_invoke(fn, name, args)
    with console.status(f"[m.dim]{label}[/m.dim]", spinner="dots", spinner_style="m.accent"):
        return safe_invoke(fn, name, args)


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


def _resolve_search_result_url(href: str) -> str | None:
    if not href:
        return None
    candidate = href.strip()
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    parsed = urllib.parse.urlparse(candidate)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        query = urllib.parse.parse_qs(parsed.query)
        target = query.get("uddg", [])
        if target:
            candidate = urllib.parse.unquote(target[0])
    if candidate.startswith("http://") or candidate.startswith("https://"):
        return candidate
    return None


class _SearchResultsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_map = dict(attrs)
        class_name = attrs_map.get("class") or ""
        href = attrs_map.get("href") or ""
        resolved = _resolve_search_result_url(href)
        if not resolved:
            return
        if "result__a" not in class_name and "result-link" not in class_name and "result-link" not in href:
            return
        self._current_href = resolved
        self._current_chunks = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return
        title = re.sub(r"\s+", " ", "".join(self._current_chunks)).strip()
        if title and not any(url == self._current_href for _, url in self.results):
            self.results.append((title, self._current_href))
        self._current_href = None
        self._current_chunks = []


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



@dataclass
class WebResponse:
    request: str
    findings: list[str] = field(default_factory=list)
    tool_outputs: list[str] = field(default_factory=list)
    summary: str = ""
    tokens_in: int = 0
    tokens_out: int = 0


def _first_failure_text(tool_outputs: list[str]) -> str:
    for output in tool_outputs:
        cleaned = (output or "").strip()
        if cleaned.startswith("✗"):
            return cleaned.lstrip("✗").strip().splitlines()[0]
    return ""


def _finalize_summary(tool_outputs: list[str], model_summary: str) -> str:
    # Refused repeats are not errors; a failed call never hides the model's answer (E-024).
    failures = [output for output in tool_outputs
                if (output or "").strip().startswith("✗") and not (output or "").startswith("✗ Not run:")]
    if not failures:
        return model_summary
    real_calls = [o for o in tool_outputs if not (o or "").startswith("✗ Not run:")]
    if model_summary.strip() and len(failures) < len(real_calls):  # if every call failed, the answer was made up
        return f"{model_summary.rstrip()}\n\n_{len(failures)} of {len(real_calls)} web calls failed._"

    first_error = _first_failure_text(tool_outputs)
    if len(failures) == len(real_calls):
        return f"Could not complete the web request. {first_error}." if first_error else "Could not complete the web request."
    if first_error:
        return f"Completed part of the web request, but hit {len(failures)} error{'s' if len(failures) != 1 else ''}. {first_error}."
    return f"Completed part of the web request, but hit {len(failures)} error{'s' if len(failures) != 1 else ''}."


def run(llm, user_request: str, console: Console | None = None) -> WebResponse:
    llm_with_tools = llm.bind_tools(_ALL_TOOLS)
    tool_map = {tool_obj.name: tool_obj for tool_obj in _ALL_TOOLS}
    response_obj = WebResponse(request=user_request)
    messages: list = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_request),
    ]

    from app.agents.limits import MAX_AGENT_STEPS, RepeatGuard, stopped_message

    guard = RepeatGuard()  # E-023: no identical repeats; stop after 3 failures in a row
    for _step in range(MAX_AGENT_STEPS):  # E-002: never loop forever
        phase = "Summarizing web findings..." if any(isinstance(m, ToolMessage) for m in messages) else "Planning web steps..."
        response: AIMessage = _invoke_with_status(llm_with_tools, messages, console, phase)
        meta = getattr(response, "usage_metadata", None) or {}
        response_obj.tokens_in += meta.get("input_tokens", 0)
        response_obj.tokens_out += meta.get("output_tokens", 0)
        messages.append(response)

        if not response.tool_calls:
            response_obj.summary = _finalize_summary(response_obj.tool_outputs, (response.content or "").strip())
            return response_obj

        for tc in response.tool_calls:
            fn = tool_map.get(tc["name"])
            repeat = guard.before(tc["name"], tc["args"])
            if repeat is not None:
                output = repeat
            elif fn is None:
                output = f"✗ Unknown tool: {tc['name']}"
            else:
                tool_label = "Fetching webpage..." if tc["name"] == "fetch_url" else "Searching public web..."
                output = _run_tool_with_status(fn, tc["args"], console, tool_label)
            response_obj.tool_outputs.append(str(output))
            response_obj.findings.append(f"{tc['name']}: {str(output)[:200]}")
            if console is not None:
                from app.ui import tool_line
                target = str(tc["args"].get("url") or tc["args"].get("query") or "")[:80]
                failed = str(output).lstrip().startswith("✗")
                console.print(tool_line("Fetch" if tc["name"] == "fetch_url" else "Search", target, ok=not failed,
                                        detail=str(output).strip().splitlines()[0][:110] if failed else ""))
            messages.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
            stop = guard.after(tc["name"], str(output))
            if stop is not None:
                if "failed" in stop and tc["name"] == "search_web":
                    stop += " Mitra may be offline, or the search sites are blocking requests."
                return _answer_now(llm, messages, response_obj, stop, console)
    return _answer_now(llm, messages, response_obj, stopped_message(), console)


def _answer_now(llm, messages: list, response_obj, reason: str, console) -> "WebResponse":
    """The loop was stopped: one last call without tools, so the user still gets an answer (E-024)."""
    from langchain_core.messages import HumanMessage as _Human

    if not response_obj.tool_outputs or all(str(o).startswith("✗") for o in response_obj.tool_outputs):
        response_obj.summary = reason
        return response_obj
    messages.append(_Human(content=(
        "Stop searching now. Answer the original request using only the results above. "
        "Say clearly what you could not find. Cite the URLs you used.")))
    try:
        final = _invoke_with_status(llm, messages, console, "Writing the answer...")
    except Exception as exc:  # the stop reason is still worth showing
        response_obj.summary = f"{reason} (and the final answer failed: {exc})"
        return response_obj
    meta = getattr(final, "usage_metadata", None) or {}
    response_obj.tokens_in += meta.get("input_tokens", 0)
    response_obj.tokens_out += meta.get("output_tokens", 0)
    text = (getattr(final, "content", "") or "").strip()
    response_obj.summary = (text + f"\n\n_{reason.lstrip('✗ ')}_") if text else reason
    return response_obj


def render(response: WebResponse):
    return Markdown(response.summary or "")


def make_routing_tool(llm, console: Console | None = None):
    @tool
    def browse_web(request: str) -> str:
        """
        Search the web or inspect a specific webpage.
        Use for internet research, public documentation, current information, or when the user provides a URL.
        Pass the full user request unchanged.
        """
        response = run(llm, request, console=console)
        return response.summary

    return browse_web
