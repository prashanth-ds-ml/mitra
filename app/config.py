from __future__ import annotations

import ctypes
import getpass
import os
import pathlib
import re
import subprocess
from dataclasses import dataclass

try:
    import psutil
except ImportError:
    psutil = None

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

try:
    import tomli_w
except ImportError:
    tomli_w = None

_TOML_NAME = "codemitra.toml"
_LOCAL_TOML_NAME = "local.toml"
_RULES_NAME = "CODEMITRA.md"
_USER_CONFIG_DIR = pathlib.Path.home() / ".config" / "codemitra"
_USER_CONFIG_FILE = _USER_CONFIG_DIR / "codemitra.toml"
_PROJECT_ROOT_MARKERS = (
    _TOML_NAME,
    "pyproject.toml",
    ".git",
)
_DEFAULT_INSTRUCTION_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    ".codemitra/instructions.md",
    ".github/copilot-instructions.md",
]
_DEFAULT_SKILL_DIRS = [
    "skills",
    ".codemitra/skills",
]
_DEFAULT_PLUGIN_DIRS = [
    "plugins",
    ".codemitra/plugins",
]
_DEFAULT_MCP_SERVERS = [
    {
        "name": "filesystem",
        "description": "Workspace file access through MCP-compatible filesystem servers.",
        "fallback": "Built-in filesystem tools",
        "transport": "local-fallback",
        "command": "python",
        "args": ["-m", "app.mcp_servers.filesystem"],
        "enabled": True,
    },
    {
        "name": "git",
        "description": "Repository inspection through an MCP git server.",
        "fallback": "Built-in git helpers",
        "transport": "local-fallback",
    },
    {
        "name": "sqlite",
        "description": "Structured local memory through an MCP SQLite server.",
        "fallback": "Built-in memory and trace storage",
        "transport": "local-fallback",
    },
    {
        "name": "context7",
        "description": "Reference lookup through a Context7-compatible MCP server.",
        "fallback": "Built-in web and docs tools",
        "transport": "local-fallback",
    },
]
_MAX_INSTRUCTION_CHARS = 12000
_BYTES_PER_GIB = 1024 ** 3

_DEFAULTS: dict = {
    "model": "",          # legacy fallback; prefer local_model
    "local_model": "",    # empty = prompt user to pick at startup
    "codegen_model": "",  # empty = use local_model for code generation too
    "agent_models": {
        "planner": "qwen3:14b",
        "prd": "qwen3:14b",
        "task": "qwen3:14b",
        "coder": "qwen2.5-coder:14b",
        "tester": "qwen2.5-coder:7b",
        "reviewer": "qwen3:14b",
        "docs": "qwen2.5-coder:7b",
        "decision": "qwen3:14b",
    },
    "temperature": 0.2,
    "session_mode": "approve",
    "work_mode": "builder",
    "show_reasoning": False,
    "memory_enabled": False,
    "require_diff_approval": True,
    "auto_compact_threshold": 120000,  # combined tokens before auto-compact
    "num_ctx": 131072,                # Ollama context window to request when supported
    "gpu_layers": "auto",             # "auto" | 0 (CPU only) | -1 (full GPU) | N (N layers)
    "ollama_api_key": "",
    "ollama_local_base_url": "http://localhost:11434",
    "ollama_cloud_base_url": "https://ollama.com",
    "allowed_roots": [],
    "disabled_tools": [],
    "disabled_commands": [],
    "policy_path": "",
    "instruction_files": list(_DEFAULT_INSTRUCTION_FILES),
    "skill_dirs": list(_DEFAULT_SKILL_DIRS),
    "playbook_dirs": ["playbooks", ".codemitra/playbooks"],
    "plugin_dirs": list(_DEFAULT_PLUGIN_DIRS),
    "mcp_servers": list(_DEFAULT_MCP_SERVERS),
}


@dataclass(frozen=True)
class LocalModelInfo:
    name: str
    size_text: str = ""
    size_gib: float | None = None
    recommended: bool = True
    placement: str = "gpu"   # "gpu" | "split" | "cpu"


@dataclass(frozen=True)
class GpuMemoryInfo:
    total_gib: float
    used_gib: float
    free_gib: float
    gpu_name: str | None = None

    @property
    def usage_pct(self) -> int:
        if self.total_gib <= 0:
            return 0
        return min(100, max(0, int(round((self.used_gib / self.total_gib) * 100))))


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    memory_gib: float | None = None
    cpu_pct: float | None = None
    command: str = ""
    gpu_memory_gib: float | None = None
    owner: str = ""
    category: str = "process"


def _load_dotenv(path: pathlib.Path) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from a .env file if present."""
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_project_instructions(root: pathlib.Path, entries) -> list[dict[str, str]]:
    """Load configured project instruction files from inside the workspace."""
    if not entries:
        return []
    if isinstance(entries, str):
        entries = [entries]

    loaded: list[dict[str, str]] = []
    seen: set[pathlib.Path] = set()
    for raw_entry in entries:
        entry = str(raw_entry).strip()
        if not entry:
            continue
        path = pathlib.Path(entry)
        target = path if path.is_absolute() else root / path
        try:
            resolved = target.resolve()
            resolved.relative_to(root.resolve())
        except (OSError, ValueError):
            continue
        if resolved in seen or not resolved.is_file():
            continue
        try:
            text = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        loaded.append(
            {
                "path": str(resolved.relative_to(root.resolve())),
                "content": text[:_MAX_INSTRUCTION_CHARS],
            }
        )
        seen.add(resolved)
    return loaded


def _parse_size_to_gib(value: str, unit: str) -> float | None:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None

    scale = {
        "B": 1 / _BYTES_PER_GIB,
        "KB": 1 / (1024 ** 2),
        "MB": 1 / 1024,
        "GB": 1,
        "TB": 1024,
    }.get((unit or "").upper())
    if scale is None:
        return None
    return round(amount * scale, 2)


def get_total_system_memory_gib() -> float | None:
    """Return detected physical system RAM in GiB."""
    try:
        if os.name == "nt":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return round(status.ullTotalPhys / _BYTES_PER_GIB, 1)
            return None

        page_size = os.sysconf("SC_PAGE_SIZE")
        phys_pages = os.sysconf("SC_PHYS_PAGES")
        return round((page_size * phys_pages) / _BYTES_PER_GIB, 1)
    except Exception:
        return None


def get_available_system_memory_gib() -> float | None:
    """Return currently available physical RAM in GiB."""
    try:
        if os.name == "nt":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return round(status.ullAvailPhys / _BYTES_PER_GIB, 1)
            return None

        page_size = os.sysconf("SC_PAGE_SIZE")
        avail_pages = os.sysconf("SC_AVPHYS_PAGES")
        return round((page_size * avail_pages) / _BYTES_PER_GIB, 1)
    except Exception:
        return None


def get_gpu_vram_gib() -> float | None:
    """Return total VRAM of the first NVIDIA GPU in GiB, or None if not found."""
    info = get_gpu_memory_info()
    return info.total_gib if info else None


def get_gpu_memory_info() -> GpuMemoryInfo | None:
    """Return live VRAM totals for the first NVIDIA GPU, or None if unavailable."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        lines = result.stdout.strip().splitlines()
        if not lines:
            return None
        first_line = lines[0].strip()
        if not first_line:
            return None
        parts = [part.strip() for part in first_line.split(",")]
        if len(parts) < 4:
            return None
        gpu_name, total_mib, used_mib, free_mib = parts[:4]
        return GpuMemoryInfo(
            gpu_name=gpu_name or None,
            total_gib=round(float(total_mib) / 1024, 1),
            used_gib=round(float(used_mib) / 1024, 1),
            free_gib=round(float(free_mib) / 1024, 1),
        )
    except Exception:
        return None


def get_cpu_usage_pct() -> float | None:
    """Return current total CPU usage percentage, or None if unavailable."""
    if psutil is None:
        return None
    try:
        return round(float(psutil.cpu_percent(interval=0.1)), 1)
    except Exception:
        return None


def _process_matches_local_ai(name: str, command: str) -> bool:
    lowered_name = (name or "").lower()
    lowered_command = (command or "").lower()
    return "ollama" in lowered_name or "ollama" in lowered_command


def _normalize_username(username: str | None) -> str:
    value = (username or "").strip().lower()
    if "\\" in value:
        value = value.split("\\")[-1]
    if "@" in value:
        value = value.split("@")[0]
    return value


def _current_username() -> str:
    return _normalize_username(getpass.getuser())


def _process_owner(proc) -> str:
    try:
        return str(proc.username() or "")
    except Exception:
        return ""


def _parse_nvidia_smi_process_table(output: str) -> list[tuple[int, str, float | None]]:
    processes: list[tuple[int, str, float | None]] = []
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        match = re.match(
            r"^\|\s*\d+\s+[^|]*?\s+(?P<pid>\d+)\s+(?P<kind>[A-Z+]+)\s+(?P<name>.+?)\s+(?P<memory>\d+|N/A)MiB\s*\|$",
            line,
        )
        if not match:
            continue
        memory_text = match.group("memory")
        gpu_memory_gib = None if memory_text == "N/A" else round(float(memory_text) / 1024, 2)
        processes.append((int(match.group("pid")), match.group("name").strip(), gpu_memory_gib))
    return processes


def list_user_gpu_processes() -> list[ProcessInfo]:
    """Return user-owned GPU processes reported by nvidia-smi."""
    if psutil is None:
        return []
    current_user = _current_username()
    current_pid = os.getpid()
    seen: dict[int, ProcessInfo] = {}

    def add_candidate(pid: int, name_hint: str = "", gpu_memory_gib: float | None = None) -> None:
        if pid == current_pid or pid in seen:
            return
        try:
            proc = psutil.Process(pid)
            owner = _process_owner(proc)
            if _normalize_username(owner) != current_user:
                return
            memory_info = proc.memory_info()
            command = " ".join(proc.cmdline()).strip()
            seen[pid] = ProcessInfo(
                pid=pid,
                name=(proc.name() or name_hint or f"pid-{pid}"),
                memory_gib=round(memory_info.rss / _BYTES_PER_GIB, 2) if memory_info else None,
                command=command,
                gpu_memory_gib=gpu_memory_gib,
                owner=owner,
                category="gpu",
            )
        except Exception:
            return

    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []
        for pid, name_hint, gpu_memory_gib in _parse_nvidia_smi_process_table(result.stdout):
            add_candidate(pid, name_hint=name_hint, gpu_memory_gib=gpu_memory_gib)
    except Exception:
        return []

    return sorted(seen.values(), key=lambda item: (item.name.lower(), item.pid))


def list_local_ai_processes() -> list[ProcessInfo]:
    """Return running Ollama/local AI processes that can be stopped to free resources."""
    if psutil is None:
        return []
    matches: list[ProcessInfo] = []
    current_pid = os.getpid()
    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline", "memory_info"]):
            info = proc.info
            pid = int(info.get("pid") or 0)
            if pid == current_pid:
                continue
            name = str(info.get("name") or "")
            cmdline = info.get("cmdline") or []
            command = " ".join(str(part) for part in cmdline).strip()
            if not _process_matches_local_ai(name, command):
                continue
            memory_info = info.get("memory_info")
            rss = getattr(memory_info, "rss", None)
            matches.append(
                ProcessInfo(
                    pid=pid,
                    name=name or f"pid-{pid}",
                    memory_gib=round(rss / _BYTES_PER_GIB, 2) if isinstance(rss, (int, float)) else None,
                    command=command,
                    owner=_process_owner(proc),
                    category="local-ai",
                )
            )
    except Exception:
        return []
    return sorted(matches, key=lambda item: (item.name.lower(), item.pid))


def list_reclaimable_processes() -> list[ProcessInfo]:
    """Return processes CodeMitra can stop to reclaim local CPU/GPU resources."""
    combined: dict[int, ProcessInfo] = {}
    for process in list_local_ai_processes():
        combined[process.pid] = process
    for process in list_user_gpu_processes():
        existing = combined.get(process.pid)
        if existing is None:
            combined[process.pid] = process
            continue
        combined[process.pid] = ProcessInfo(
            pid=existing.pid,
            name=existing.name,
            memory_gib=existing.memory_gib if existing.memory_gib is not None else process.memory_gib,
            cpu_pct=existing.cpu_pct if existing.cpu_pct is not None else process.cpu_pct,
            command=existing.command or process.command,
            gpu_memory_gib=process.gpu_memory_gib,
            owner=existing.owner or process.owner,
            category="local-ai+gpu",
        )
    return sorted(combined.values(), key=lambda item: (item.name.lower(), item.pid))


def stop_reclaimable_processes() -> tuple[list[ProcessInfo], list[str]]:
    """Terminate reclaimable processes and return (stopped, errors)."""
    if psutil is None:
        return [], ["psutil is not available."]
    candidates = list_reclaimable_processes()
    stopped: list[ProcessInfo] = []
    errors: list[str] = []
    for candidate in candidates:
        try:
            proc = psutil.Process(candidate.pid)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            stopped.append(candidate)
        except psutil.NoSuchProcess:
            stopped.append(candidate)
        except Exception as exc:
            errors.append(f"{candidate.name} ({candidate.pid}): {exc}")
    return stopped, errors


def get_model_placement(size_gib: float | None, vram_gib: float | None) -> str:
    """Classify a model's expected execution placement.

    Returns:
      "gpu"   — fits entirely in VRAM (fast, full GPU)
      "split" — partially offloaded (GPU + CPU, moderate speed)
      "cpu"   — too large for meaningful GPU use (slow, RAM only)
    """
    if size_gib is None or vram_gib is None:
        return "gpu"  # unknown — optimistic default
    gpu_threshold = vram_gib * 0.92   # fits with ~8 % overhead
    split_threshold = vram_gib * 1.75  # up to ~75 % overflow still worth splitting
    if size_gib <= gpu_threshold:
        return "gpu"
    if size_gib <= split_threshold:
        return "split"
    return "cpu"


def get_num_gpu_for_placement(placement: str, gpu_layers_cfg: str | int = "auto") -> int | None:
    """Return the num_gpu value to pass to Ollama based on placement and config.

    Returns None to let Ollama decide automatically (its default behaviour),
    0 to force CPU-only, or -1 to force all layers on GPU.
    """
    raw = str(gpu_layers_cfg).strip().lower()
    if raw != "auto":
        try:
            return int(raw)
        except ValueError:
            pass
    # auto mode: let Ollama decide for gpu/split; force CPU-only for cpu models
    if placement == "cpu":
        return 0
    return None  # Ollama picks the optimal layer split


def get_recommended_model_budget_gib() -> float | None:
    """Return the practical local-model size budget for this machine.

    GPU VRAM is preferred when available since inference runs on the GPU.
    Falls back to 50 % of system RAM when no GPU is detected.
    """
    vram_gib = get_gpu_vram_gib()
    if vram_gib is not None:
        # Leave ~8 % headroom for GPU overhead / OS
        return round(vram_gib * 0.92, 1)
    total_gib = get_total_system_memory_gib()
    if total_gib is None:
        return None
    return round(max(2.0, total_gib * 0.5), 1)


def get_local_model_inventory() -> list[LocalModelInfo]:
    """Return local Ollama models with parsed sizes and hardware guidance."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=10,
        )
        lines = result.stdout.strip().splitlines()[1:]  # skip header
        budget_gib = get_recommended_model_budget_gib()
        vram_gib = get_gpu_vram_gib()
        models: list[LocalModelInfo] = []
        for line in lines:
            parts = line.split()
            if len(parts) < 4:
                continue
            name = parts[0]
            size_value = parts[2]
            size_unit = parts[3]
            if size_value == "-" or size_unit == "-":
                continue
            size_text = f"{size_value} {size_unit}"
            size_gib = _parse_size_to_gib(size_value, size_unit)
            placement = get_model_placement(size_gib, vram_gib)
            # Recommended = fits in GPU or is worth splitting (not pure CPU)
            recommended = placement in ("gpu", "split")
            models.append(
                LocalModelInfo(
                    name=name,
                    size_text=size_text,
                    size_gib=size_gib,
                    recommended=recommended,
                    placement=placement,
                )
            )
        return models
    except Exception:
        return []


def list_local_models(*, recommended_only: bool = False) -> list[str]:
    """Return model names available in the local Ollama installation."""
    inventory = get_local_model_inventory()
    if recommended_only:
        inventory = [model for model in inventory if model.recommended]
    return [model.name for model in inventory]


def stop_local_model(model_name: str) -> tuple[bool, str]:
    """Ask Ollama to unload a running model from memory."""
    target = (model_name or "").strip()
    if not target:
        return False, "No model name provided."

    try:
        result = subprocess.run(
            ["ollama", "stop", target],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        return False, f"Could not run `ollama stop`: {exc}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or f"Failed to stop `{target}`."
        return False, detail

    detail = (result.stdout or "").strip() or f"Stopped `{target}`."
    return True, detail


def remove_local_model(model_name: str) -> tuple[bool, str]:
    """Remove a local Ollama model by name."""
    target = (model_name or "").strip()
    if not target:
        return False, "No model name provided."

    try:
        result = subprocess.run(
            ["ollama", "rm", target],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:
        return False, f"Could not run `ollama rm`: {exc}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or f"Failed to remove `{target}`."
        return False, detail

    detail = (result.stdout or "").strip() or f"Removed `{target}`."
    return True, detail


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning new dict."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_config_layer(path: pathlib.Path) -> dict:
    """Load a single TOML config layer if it exists."""
    if path.exists():
        with open(path, "rb") as f:
            return tomllib.load(f)
    return {}


def detect_project_root(start: str | os.PathLike | None = None) -> pathlib.Path:
    """Find the nearest parent directory that looks like a project root."""
    raw_start = pathlib.Path(start).resolve() if start else pathlib.Path.cwd().resolve()
    current = raw_start if raw_start.is_dir() else raw_start.parent

    for candidate in (current, *current.parents):
        if any((candidate / marker).exists() for marker in _PROJECT_ROOT_MARKERS):
            return candidate
    return current


def get_config_paths(workspace: str | os.PathLike | None = None) -> dict[str, pathlib.Path]:
    """Return the layered config paths for the resolved workspace."""
    root = detect_project_root(workspace)
    return {
        "user": _USER_CONFIG_FILE,
        "project": root / _TOML_NAME,
        "local": root / ".codemitra" / _LOCAL_TOML_NAME,
        "rules": root / _RULES_NAME,
    }


def load(cwd: str | None = None, cli_overrides: dict | None = None) -> dict:
    """
    Load layered configuration with precedence:
    1. User defaults (~/.config/codemitra/codemitra.toml)
    2. Project settings (codemitra.toml in workspace)
    3. Local overrides (.codemitra/local.toml, gitignored)
    4. CLI/session overrides (passed via cli_overrides dict)
    5. Environment variables (.env, OLLAMA_API_KEY)
    """
    root = detect_project_root(cwd)
    cfg = dict(_DEFAULTS)

    # Layer 1: User defaults
    user_cfg = _load_config_layer(_USER_CONFIG_FILE)
    cfg = _deep_merge(cfg, user_cfg)

    # Layer 2: Project settings
    project_cfg = _load_config_layer(root / _TOML_NAME)
    cfg = _deep_merge(cfg, project_cfg)

    # Layer 3: Local overrides (gitignored)
    local_cfg = _load_config_layer(root / ".codemitra" / _LOCAL_TOML_NAME)
    cfg = _deep_merge(cfg, local_cfg)

    # Layer 4: CLI/session overrides
    if cli_overrides:
        cfg = _deep_merge(cfg, cli_overrides)

    # Layer 5: Environment variables
    dotenv_vars = _load_dotenv(root / ".env")
    cfg["ollama_api_key"] = (
        os.getenv("OLLAMA_API_KEY")
        or dotenv_vars.get("OLLAMA_API_KEY")
        or cfg.get("ollama_api_key", "")
    )

    # Post-processing
    rules_path = root / _RULES_NAME
    cfg["rules"] = rules_path.read_text(encoding="utf-8") if rules_path.exists() else None
    cfg["project_instructions"] = _load_project_instructions(root, cfg.get("instruction_files"))
    cfg["workspace"] = str(root)
    raw_roots = cfg.get("allowed_roots") or []
    if isinstance(raw_roots, str):
        raw_roots = [raw_roots]
    cfg["allowed_roots"] = [
        str((root / entry).resolve()) if not pathlib.Path(entry).is_absolute() else str(pathlib.Path(entry).resolve())
        for entry in raw_roots
    ]
    raw_disabled_tools = cfg.get("disabled_tools") or []
    cfg["disabled_tools"] = list(raw_disabled_tools) if isinstance(raw_disabled_tools, list) else [str(raw_disabled_tools)]
    raw_disabled_commands = cfg.get("disabled_commands") or []
    cfg["disabled_commands"] = list(raw_disabled_commands) if isinstance(raw_disabled_commands, list) else [str(raw_disabled_commands)]
    raw_skill_dirs = cfg.get("skill_dirs") or []
    if isinstance(raw_skill_dirs, str):
        raw_skill_dirs = [raw_skill_dirs]
    cfg["skill_dirs"] = list(raw_skill_dirs)
    raw_playbook_dirs = cfg.get("playbook_dirs") or []
    if isinstance(raw_playbook_dirs, str):
        raw_playbook_dirs = [raw_playbook_dirs]
    cfg["playbook_dirs"] = list(raw_playbook_dirs)
    raw_plugin_dirs = cfg.get("plugin_dirs") or []
    if isinstance(raw_plugin_dirs, str):
        raw_plugin_dirs = [raw_plugin_dirs]
    cfg["plugin_dirs"] = list(raw_plugin_dirs)
    raw_mcp_servers = cfg.get("mcp_servers") or []
    if isinstance(raw_mcp_servers, dict):
        raw_mcp_servers = [raw_mcp_servers]
    cfg["mcp_servers"] = list(raw_mcp_servers)

    return cfg


def save_user_config(config: dict) -> tuple[bool, str]:
    """Save configuration to user-level config file."""
    _USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if tomli_w is None:
        return False, "tomli_w not installed; cannot write TOML"
    try:
        with open(_USER_CONFIG_FILE, "wb") as f:
            tomli_w.dump(config, f)
        return True, f"Saved user config to {_USER_CONFIG_FILE}"
    except Exception as exc:
        return False, f"Failed to save user config: {exc}"


def save_local_config(config: dict, workspace: str) -> tuple[bool, str]:
    """Save configuration to local override file (.codemitra/local.toml)."""
    root = pathlib.Path(workspace).resolve()
    local_dir = root / ".codemitra"
    local_dir.mkdir(parents=True, exist_ok=True)
    local_file = local_dir / _LOCAL_TOML_NAME
    if tomli_w is None:
        return False, "tomli_w not installed; cannot write TOML"
    try:
        with open(local_file, "wb") as f:
            tomli_w.dump(config, f)
        return True, f"Saved local config to {local_file}"
    except Exception as exc:
        return False, f"Failed to save local config: {exc}"
