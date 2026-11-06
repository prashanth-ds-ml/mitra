"""Tests for app/llm.py cloud/local client construction."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import app.llm as llm


class TestGetLocalLlm:
    def test_uses_local_base_url(self, monkeypatch):
        captured = {}

        def fake_chat_ollama(**kwargs):
            captured.update(kwargs)
            return kwargs

        monkeypatch.setattr(llm, "ChatOllama", fake_chat_ollama)

        llm.get_local_llm("qwen3.5:latest", temperature=0.1, num_ctx=32768)

        assert captured["model"] == "qwen3.5:latest"
        assert captured["temperature"] == 0.1
        assert captured["num_ctx"] == 32768
        assert captured["base_url"] == "http://localhost:11434"
        assert "client_kwargs" not in captured

    def test_thinking_models_get_reasoning_on_so_thinking_is_not_dropped(self, monkeypatch):
        """E-016: with reasoning unset, langchain-ollama drops a thinking model's reasoning; Mitra looked frozen."""
        captured = {}
        monkeypatch.setattr(llm, "ChatOllama", lambda **kw: captured.update(kw) or kw)
        monkeypatch.setattr("app.config.get_model_facts", lambda name: {"capabilities": ("completion", "tools", "thinking")})

        llm.get_local_llm("qwen3.5:4b")

        assert captured["reasoning"] is True

    def test_non_thinking_models_keep_their_default(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(llm, "ChatOllama", lambda **kw: captured.update(kw) or kw)
        monkeypatch.setattr("app.config.get_model_facts", lambda name: {"capabilities": ("completion", "tools")})

        llm.get_local_llm("llama3.1:8b")

        assert "reasoning" not in captured


class TestGetCloudLlm:
    def test_uses_cloud_base_url_and_auth(self, monkeypatch):
        captured = {}

        def fake_chat_ollama(**kwargs):
            captured.update(kwargs)
            return kwargs

        monkeypatch.setattr(llm, "ChatOllama", fake_chat_ollama)

        llm.get_cloud_llm("kimi-k2.5:cloud", temperature=0.3, api_key="secret-key", num_ctx=65536)

        assert captured["model"] == "kimi-k2.5:cloud"
        assert captured["temperature"] == 0.3
        assert captured["num_ctx"] == 65536
        assert captured["base_url"] == "https://ollama.com"
        assert captured["client_kwargs"] == {
            "headers": {"Authorization": "Bearer secret-key"}
        }

    def test_reads_api_key_from_env(self, monkeypatch):
        captured = {}

        def fake_chat_ollama(**kwargs):
            captured.update(kwargs)
            return kwargs

        monkeypatch.setattr(llm, "ChatOllama", fake_chat_ollama)
        monkeypatch.setenv("OLLAMA_API_KEY", "env-secret")

        llm.get_cloud_llm("kimi-k2.5:cloud")

        assert captured["client_kwargs"] == {
            "headers": {"Authorization": "Bearer env-secret"}
        }


class TestProbeOllama:
    def test_reports_connected_with_model_count(self, monkeypatch):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"models":[{"name":"qwen3:8b"},{"name":"qwen2.5-coder:14b"}]}'

        monkeypatch.setattr(llm.request, "urlopen", lambda *args, **kwargs: FakeResponse())

        ok, message = llm.probe_ollama()

        assert ok is True
        assert "2 local models" in message

    def test_reports_unavailable_on_url_error(self, monkeypatch):
        monkeypatch.setattr(
            llm.request,
            "urlopen",
            lambda *args, **kwargs: (_ for _ in ()).throw(llm.error.URLError("connection refused")),
        )

        ok, message = llm.probe_ollama()

        assert ok is False
        assert "Unavailable" in message
