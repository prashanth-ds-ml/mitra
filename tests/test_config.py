from types import SimpleNamespace

from app import config


def test_detect_project_root_walks_up_to_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    nested = tmp_path / "src" / "feature"
    nested.mkdir(parents=True)

    root = config.detect_project_root(str(nested))

    assert root == tmp_path.resolve()


def test_load_uses_detected_project_root_for_nested_paths(tmp_path):
    (tmp_path / "codemitra.toml").write_text('local_model = "qwen3:8b"\n', encoding="utf-8")
    nested = tmp_path / "app" / "cli"
    nested.mkdir(parents=True)

    cfg = config.load(cwd=str(nested))

    assert cfg["workspace"] == str(tmp_path.resolve())
    assert cfg["local_model"] == "qwen3:8b"


def test_get_gpu_vram_gib_returns_none_on_empty_stdout(monkeypatch):
    monkeypatch.setattr(
        config.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    assert config.get_gpu_vram_gib() is None


def test_get_gpu_memory_info_parses_live_usage(monkeypatch):
    monkeypatch.setattr(
        config.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="NVIDIA GeForce RTX 5050 Laptop GPU, 8151, 2048, 6103\n",
            stderr="",
        ),
    )
    info = config.get_gpu_memory_info()

    assert info is not None
    assert info.gpu_name == "NVIDIA GeForce RTX 5050 Laptop GPU"
    assert info.total_gib == 8.0
    assert info.used_gib == 2.0
    assert info.free_gib == 6.0


def test_get_cpu_usage_pct_uses_psutil(monkeypatch):
    monkeypatch.setattr(config, "psutil", SimpleNamespace(cpu_percent=lambda interval=0.1: 27.4))
    assert config.get_cpu_usage_pct() == 27.4


def test_list_local_ai_processes_filters_ollama(monkeypatch):
    class FakeProc:
        def __init__(self, pid, name, cmdline, rss):
            self.info = {
                "pid": pid,
                "name": name,
                "cmdline": cmdline,
                "memory_info": SimpleNamespace(rss=rss),
            }

    fake_psutil = SimpleNamespace(
        process_iter=lambda fields: [
            FakeProc(111, "ollama.exe", ["ollama", "serve"], 2 * 1024 ** 3),
            FakeProc(222, "python.exe", ["python", "app.py"], 1 * 1024 ** 3),
        ],
    )
    monkeypatch.setattr(config, "psutil", fake_psutil)
    monkeypatch.setattr(config.os, "getpid", lambda: 9999)

    processes = config.list_local_ai_processes()

    assert len(processes) == 1
    assert processes[0].name == "ollama.exe"
    assert processes[0].memory_gib == 2.0


def test_list_user_gpu_processes_filters_to_current_user(monkeypatch):
    class FakeProc:
        def __init__(self, pid, name, username, cmdline, rss):
            self._pid = pid
            self._name = name
            self._username = username
            self._cmdline = cmdline
            self._memory_info = SimpleNamespace(rss=rss)

        def username(self):
            return self._username

        def memory_info(self):
            return self._memory_info

        def cmdline(self):
            return self._cmdline

        def name(self):
            return self._name

    monkeypatch.setattr(config, "psutil", SimpleNamespace(Process=lambda pid: {
        111: FakeProc(111, "python.exe", "PRASH\\prash", ["python", "serve.py"], 2 * 1024 ** 3),
        222: FakeProc(222, "chrome.exe", "OTHER\\user", ["chrome"], 1 * 1024 ** 3),
    }[pid]))
    monkeypatch.setattr(config, "_current_username", lambda: "prash")
    monkeypatch.setattr(config.os, "getpid", lambda: 9999)
    monkeypatch.setattr(
        config.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=(
                "|    0   N/A  N/A      111    C+G   python.exe                           1024MiB |\n"
                "|    0   N/A  N/A      222    C+G   chrome.exe                            512MiB |\n"
            ),
            stderr="",
        ),
    )

    processes = config.list_user_gpu_processes()

    assert len(processes) == 1
    assert processes[0].pid == 111
    assert processes[0].name == "python.exe"
    assert processes[0].gpu_memory_gib == 1.0


def test_list_reclaimable_processes_merges_local_ai_and_gpu(monkeypatch):
    monkeypatch.setattr(
        config,
        "list_local_ai_processes",
        lambda: [SimpleNamespace(pid=111, name="ollama.exe", memory_gib=2.0, cpu_pct=None, command="ollama serve", gpu_memory_gib=None, owner="prash", category="local-ai")],
    )
    monkeypatch.setattr(
        config,
        "list_user_gpu_processes",
        lambda: [
            SimpleNamespace(pid=111, name="ollama.exe", memory_gib=2.0, cpu_pct=None, command="ollama serve", gpu_memory_gib=3.0, owner="prash", category="gpu"),
            SimpleNamespace(pid=333, name="python.exe", memory_gib=1.0, cpu_pct=None, command="python train.py", gpu_memory_gib=1.5, owner="prash", category="gpu"),
        ],
    )

    processes = config.list_reclaimable_processes()

    assert len(processes) == 2
    merged = next(proc for proc in processes if proc.pid == 111)
    assert merged.category == "local-ai+gpu"
    assert merged.gpu_memory_gib == 3.0


def test_load_exposes_default_plugin_dirs(tmp_path):
    cfg = config.load(cwd=str(tmp_path))
    assert cfg["plugin_dirs"] == ["plugins", ".codemitra/plugins"]


def test_load_exposes_default_mcp_servers(tmp_path):
    cfg = config.load(cwd=str(tmp_path))

    assert [server["name"] for server in cfg["mcp_servers"]] == ["filesystem", "git", "sqlite", "context7"]
    assert cfg["mcp_servers"][0]["command"] == "python"
    assert cfg["mcp_servers"][0]["args"] == ["-m", "app.mcp_servers.filesystem"]
    assert cfg["mcp_servers"][0]["enabled"] is True


def test_load_exposes_default_agent_model_mapping(tmp_path):
    cfg = config.load(cwd=str(tmp_path))

    assert cfg["agent_models"]["planner"] == "qwen3:14b"
    assert cfg["agent_models"]["coder"] == "qwen2.5-coder:14b"


def test_load_exposes_default_work_mode(tmp_path):
    cfg = config.load(cwd=str(tmp_path))

    assert cfg["work_mode"] == "builder"


def test_load_merges_agent_model_overrides(tmp_path):
    (tmp_path / "codemitra.toml").write_text(
        "[agent_models]\nplanner = \"custom-planner\"\ndocs = \"custom-docs\"\n",
        encoding="utf-8",
    )

    cfg = config.load(cwd=str(tmp_path))

    assert cfg["agent_models"]["planner"] == "custom-planner"
    assert cfg["agent_models"]["docs"] == "custom-docs"
    assert cfg["agent_models"]["reviewer"] == "qwen3:14b"
