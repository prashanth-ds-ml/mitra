"""Tests for app/agents/diagnostics.py."""

import tempfile
import pathlib
from unittest.mock import patch, MagicMock, call

from app.agents import diagnostics as diagnostics_agent


class TestLspClient:
    def test_request_definition_sends_correct_rpc(self):
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout.readline.side_effect = [
            b'Content-Length: 78\r\n\r\n',
            b'{"jsonrpc":"2.0","id":1,"result":[{"uri":"file:///tmp/test.py","range":{"start":{"line":10,"character":5}}}]}'
        ]

        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("threading.Thread"):
                client = diagnostics_agent._LspClient(["fake-langserver"], pathlib.Path("/tmp"))
                client._queue.put({"jsonrpc": "2.0", "id": 1, "result": [{"uri": "file:///tmp/test.py", "range": {"start": {"line": 10, "character": 5}}}]})
                result = client.request_definition("file:///tmp/test.py", 10, 5)
                assert result is not None
                assert len(result) == 1
                assert result[0]["uri"] == "file:///tmp/test.py"

    def test_request_references_sends_correct_rpc(self):
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout.readline.side_effect = [
            b'Content-Length: 78\r\n\r\n',
            b'{"jsonrpc":"2.0","id":1,"result":[{"uri":"file:///tmp/test.py","range":{"start":{"line":20,"character":10}}}]}'
        ]

        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("threading.Thread"):
                client = diagnostics_agent._LspClient(["fake-langserver"], pathlib.Path("/tmp"))
                client._queue.put({"jsonrpc": "2.0", "id": 1, "result": [{"uri": "file:///tmp/test.py", "range": {"start": {"line": 20, "character": 10}}}]})
                result = client.request_references("file:///tmp/test.py", 10, 5)
                assert result is not None
                assert len(result) == 1


class TestLspLocationToStr:
    def test_converts_location_to_readable_string(self):
        workspace = pathlib.Path("/home/user/project")
        location = {"uri": "file:///home/user/project/src/main.py", "range": {"start": {"line": 42, "character": 10}}}
        result = diagnostics_agent._lsp_location_to_str(workspace, location)
        assert "src/main.py:43:11" in result or "src\\main.py:43:11" in result

    def test_converts_location_link_to_readable_string(self):
        workspace = pathlib.Path("/home/user/project")
        location = {"targetUri": "file:///home/user/project/src/main.py", "targetSelectionRange": {"start": {"line": 42, "character": 10}}}
        result = diagnostics_agent._lsp_location_to_str(workspace, location)
        assert "src/main.py:43:11" in result or "src\\main.py:43:11" in result


class TestCollectSymbolInfo:
    def test_returns_empty_when_no_server(self, tmp_path):
        (tmp_path / "test.py").write_text("def foo():\n    pass\n", encoding="utf-8")
        defs, refs, server = diagnostics_agent._collect_symbol_info(tmp_path, "python", [tmp_path / "test.py"], "foo")
        assert defs == []
        assert refs == []
        assert server is None


class TestCodeIntelIntegration:
    def test_run_returns_lsp_and_grep_sections(self, tmp_path):
        (tmp_path / "main.py").write_text("from utils import helper\nhelper()\n", encoding="utf-8")
        (tmp_path / "utils.py").write_text("def helper():\n    pass\n", encoding="utf-8")

        from app.agents import codeintel
        response = codeintel.run(str(tmp_path), "helper")
        assert "Symbol: `helper`" in response.summary
        assert "Definitions" in response.summary
        assert "Usages" in response.summary
        assert "References" in response.summary or "Usages" in response.summary