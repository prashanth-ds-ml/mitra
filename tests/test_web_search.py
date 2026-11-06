"""Web search without an API key (E-024). The network is mocked; a live run is recorded in ERROR_LOG E-024."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage

from app.agents import search_sources as ss
from app.agents import web

HF = json.dumps([{"id": "Qwen/Qwen3.5-9B", "pipeline_tag": "image-text-to-text", "downloads": 6297572, "likes": 2323}])
WIKI = json.dumps({"query": {"search": [{"title": "Qwen", "snippet": "models by <b>Alibaba</b> Cloud"}]}})
GH = json.dumps({"items": [{"full_name": "QwenLM/Qwen3", "html_url": "https://github.com/QwenLM/Qwen3",
                            "description": "Qwen3 models", "stargazers_count": 20000}]})
ARXIV = ("<feed><entry><id>http://arxiv.org/abs/2604.1</id><published>2026-04-17T00:00:00Z</published>"
         "<title>Qwen3.5-Omni Technical Report</title><summary>We present Qwen3.5-Omni.</summary></entry></feed>")
OLLAMA = '<a href="/library/qwen3.5">qwen3.5</a><a href="/library/qwen3.5">again</a>'


def fake_get(responses):
    def _get(url, timeout=None):
        for key, body in responses.items():
            if key in url:
                if isinstance(body, Exception):
                    raise body
                return body
        raise OSError("timed out")
    return _get


def test_all_sources_are_merged_and_labelled(monkeypatch):
    monkeypatch.setattr(ss, "_get", fake_get({"huggingface": HF, "wikipedia": WIKI, "api.github": GH,
                                              "arxiv": ARXIV, "ollama.com": OLLAMA}))
    monkeypatch.setattr(ss._Ddg, "available", True)
    results, errors = ss.search("Qwen3.5", per_source=3)
    sources = [r.source for r in results]
    assert sources == ["Wikipedia", "Hugging Face", "GitHub", "arXiv", "Ollama"]
    assert "web" in errors                       # DuckDuckGo failed ...
    assert ss._Ddg.available is False            # ... and is skipped from now on
    text = ss.format_results("Qwen3.5", results, errors)
    assert "[Hugging Face] Qwen/Qwen3.5-9B" in text and "6,297,572 downloads" in text
    assert "2026-04-17 · We present Qwen3.5-Omni." in text
    assert "Sources: Wikipedia, Hugging Face, GitHub, arXiv, Ollama." in text


def test_nothing_reachable_is_an_error_that_says_offline(monkeypatch):
    monkeypatch.setattr(ss, "_get", fake_get({}))
    results, errors = ss.search("anything")
    assert results == []
    out = ss.format_results("anything", results, errors)
    assert out.startswith("✗ Web search failed") and "offline" in out


def test_long_questions_fall_back_to_short_names(monkeypatch):
    seen = []

    def hf(url, timeout=None):
        seen.append(url)
        return HF if "search=Qwen3.5+specifications&" in url else "[]"

    monkeypatch.setattr(ss, "_get", hf)
    results = ss.huggingface("Qwen3.5 specifications context window parameters", 3)
    assert [r.title for r in results] == ["Qwen/Qwen3.5-9B"] and len(seen) == 2
    assert ss.short_query("Qwen3.5 model context length") == "Qwen3.5 model"


def test_model_and_repo_pages_are_read_from_their_readme():
    assert web.readme_url("https://huggingface.co/Qwen/Qwen3.5-9B") == "https://huggingface.co/Qwen/Qwen3.5-9B/raw/main/README.md"
    assert web.readme_url("https://github.com/QwenLM/Qwen3") == "https://raw.githubusercontent.com/QwenLM/Qwen3/HEAD/README.md"
    assert web.readme_url("https://huggingface.co/docs/transformers") is None
    assert web.readme_url("https://en.wikipedia.org/wiki/Qwen") is None




class Repeater:
    """Searches the same thing forever; answers when asked without tools."""

    def __init__(self):
        self.tool_calls = self.plain_calls = 0

    def bind_tools(self, tools):
        outer = self

        class Bound:
            def invoke(self, messages):
                outer.tool_calls += 1
                return AIMessage(content="", tool_calls=[{"name": "search_web", "args": {"query": "Qwen3.5"},
                                                          "id": f"c{outer.tool_calls}"}])
        return Bound()

    def invoke(self, messages):
        self.plain_calls += 1
        return AIMessage(content="Qwen3.5 comes in 0.8B to 122B sizes.")


