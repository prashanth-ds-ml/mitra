"""Tests for bench/run.py with a fake agent and a fake Ollama (no model needed)."""

from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

BENCH_DIR = Path(__file__).resolve().parents[1] / "bench"
sys.path.insert(0, str(BENCH_DIR))
_spec = importlib.util.spec_from_file_location("mitra_bench_run", BENCH_DIR / "run.py")
run = importlib.util.module_from_spec(_spec)
sys.modules["mitra_bench_run"] = run
_spec.loader.exec_module(run)

FAKE_AGENT = textwrap.dedent(
    """
    import json, shutil, sys, time, urllib.request
    proxy, mode, base = sys.argv[1], sys.argv[2], sys.argv[3]
    if mode != "silent":
        req = urllib.request.Request(proxy + "/api/chat", data=json.dumps(
            {"model": "m", "messages": [{"role": "user", "content": "x"}], "tools": [{"name": "edit"}]}).encode())
        urllib.request.urlopen(req, timeout=10).read()
    if mode == "which":
        import os, shutil
        open("which_python.txt", "w").write(os.path.realpath(shutil.which("python")))
    if mode == "solve":
        for name in ("shop", "paysdk"):
            shutil.copytree(f"{base}/{name}", name, dirs_exist_ok=True)
    if mode == "hang":
        import subprocess
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        open("child.pid", "w").write(str(child.pid))
        time.sleep(60)
    """
)


class _Ollama(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = b'{"done":true,"prompt_eval_count":2500,"eval_count":7}\n'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def ollama():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Ollama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _agent(tmp_path, mode, timeout_s=120):
    script = tmp_path / "fake_agent.py"
    script.write_text(FAKE_AGENT, encoding="utf-8")
    cfg = tmp_path / f"fake-{mode}.toml"
    base = run.bench.BASE.as_posix()
    cfg.write_text(
        f'name = "fake-{mode}"\ntimeout_s = {timeout_s}\n'
        f'cmd = ["{Path(sys.executable).as_posix()}", "{script.as_posix()}", "{{proxy}}", "{mode}", "{base}"]\n',
        encoding="utf-8",
    )
    return run.AgentConfig.load(cfg)


def _task(task_id="T08"):
    (task,) = run.bench.load_tasks(task_id)
    return task


def test_pass_is_recorded_and_cached(tmp_path, ollama):
    cfg, out = _agent(tmp_path, "solve"), tmp_path / "runs"
    first = run.run_one(cfg, _task(), "m:1", 1, ollama, {}, out_root=out)
    assert first["outcome"] == "pass"
    assert first["calls"]["model_calls"] == 1
    assert first["calls"]["first_call_prompt_tokens"] == 2500
    assert first["calls"]["first_call_tools"] == 1
    run_dir = out / "fake-solve" / "m_1" / "T08" / "r1"
    assert (run_dir / ".complete").read_text(encoding="utf-8") == first["fingerprint"]
    assert "AlreadyPaid" in (run_dir / "diff.patch").read_text(encoding="utf-8")
    second = run.run_one(cfg, _task(), "m:1", 1, ollama, {}, out_root=out)
    assert second.get("cached") is True


def test_config_change_reruns(tmp_path, ollama):
    cfg, out = _agent(tmp_path, "solve"), tmp_path / "runs"
    first = run.run_one(cfg, _task(), "m:1", 1, ollama, {}, out_root=out)
    cfg.path.write_text(cfg.path.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    second = run.run_one(run.AgentConfig.load(cfg.path), _task(), "m:1", 1, ollama, {}, out_root=out)
    assert "cached" not in second
    assert second["fingerprint"] != first["fingerprint"]


def test_unfinished_run_is_redone(tmp_path, ollama):
    cfg, out = _agent(tmp_path, "solve"), tmp_path / "runs"
    run.run_one(cfg, _task(), "m:1", 1, ollama, {}, out_root=out)
    (out / "fake-solve" / "m_1" / "T08" / "r1" / ".complete").unlink()
    assert "cached" not in run.run_one(cfg, _task(), "m:1", 1, ollama, {}, out_root=out)


def test_no_model_call_is_infra(tmp_path, ollama):
    result = run.run_one(_agent(tmp_path, "silent"), _task(), "m:1", 1, ollama, {}, out_root=tmp_path / "runs")
    assert result["outcome"] == "infra"


def test_unsolved_is_fail(tmp_path, ollama):
    result = run.run_one(_agent(tmp_path, "noop"), _task(), "m:1", 1, ollama, {}, out_root=tmp_path / "runs")
    assert result["outcome"] == "fail"


def test_ollama_down_is_infra(tmp_path):
    result = run.run_one(_agent(tmp_path, "noop"), _task(), "m:1", 1, "http://127.0.0.1:9", {}, out_root=tmp_path / "runs")
    assert result["outcome"] == "infra"


def test_hang_is_timeout_and_children_are_killed(tmp_path, ollama, monkeypatch):
    seen = {}
    real_grade = run.bench.grade

    def grade_and_read_pid(task, ws):
        seen["pid"] = int((ws / "child.pid").read_text())
        return real_grade(task, ws)

    monkeypatch.setattr(run.bench, "grade", grade_and_read_pid)
    result = run.run_one(_agent(tmp_path, "hang", timeout_s=5), _task(), "m:1", 1, ollama, {}, out_root=tmp_path / "runs")
    assert result["outcome"] == "timeout"
    assert not run.psutil.pid_exists(seen["pid"]) or run.psutil.Process(seen["pid"]).status() == "zombie"


def test_agent_python_is_the_grader_python(tmp_path, ollama):
    out = tmp_path / "runs"
    run.run_one(_agent(tmp_path, "which"), _task(), "m:1", 1, ollama, {}, out_root=out)
    patch = (out / "fake-which" / "m_1" / "T08" / "r1" / "diff.patch").read_text(encoding="utf-8")
    assert "which_python.txt" in patch
    expected = Path(sys.executable).resolve().parent.as_posix().lower()
    assert expected in patch.replace("\\", "/").lower()


def test_summarize_ignores_non_model_calls():
    calls = [
        {"method": "GET", "request": {"json": False}, "response": {"prompt_tokens": None}, "status": 200},
        {
            "method": "POST",
            "status": 200,
            "seconds": 1.5,
            "request": {"n_messages": 2, "n_tools": 3, "tools_chars": 900, "system_chars": 40},
            "response": {"prompt_tokens": 4000, "output_tokens": 10},
        },
    ]
    s = run.summarize_calls(calls)
    assert s["model_calls"] == 1
    assert s["first_call_tools"] == 3
    assert json.dumps(s)
