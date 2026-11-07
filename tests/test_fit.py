"""Startup memory check (D-040, E-043): can the model run, and what to close."""
from app import fit as F

GB = F.GIB


def _assess(**kw):
    args = dict(model="qwen3.5:latest", context=262_144, free_ram_gb=9.4, free_vram_gb=7.5, file_gb=6.6,
                loaded=[], programs=[], alternatives=["/model use qwen3.5:4b"])
    args.update(kw)
    return F.assess(**args)


def test_measured_9b_256k_with_room_is_ok():
    fit = _assess(free_ram_gb=12.0)
    assert fit.source == "measured" and fit.need_ram_gb == 6.8 and fit.verdict == "ok"
    assert fit.close == [] and fit.alternatives == []


def test_9b_256k_with_9gb_free_is_tight_and_lists_programs():
    progs = [F.Program("chrome", 3.2, 25), F.Program("msedge", 1.8, 12), F.Program("notepad", 0.1)]
    fit = _assess(programs=progs)  # 9.4 - 6.8 = 2.6 left
    assert fit.verdict == "tight" and fit.left_gb == 2.6
    assert [p.name for p in fit.close] == ["chrome", "msedge"]  # notepad too small to matter
    assert fit.alternatives == ["/model use qwen3.5:4b"]


def test_not_enough_ram_is_no():
    assert _assess(free_ram_gb=5.0).verdict == "no"


def test_already_loaded_at_the_same_context_needs_no_more_ram():
    loaded = [{"name": "qwen3.5:latest", "size": 12 * GB, "size_vram": int(5.2 * GB), "context_length": 262_144}]
    fit = _assess(free_ram_gb=3.5, loaded=loaded)
    assert fit.source == "loaded" and fit.need_ram_gb == 0 and fit.verdict == "ok"


def test_loaded_at_smaller_context_reloads_and_its_ram_counts_as_free():
    loaded = [{"name": "qwen3.5:latest", "size": int(9.5 * GB), "size_vram": int(5.5 * GB), "context_length": 131_072}]
    fit = _assess(free_ram_gb=6.0, loaded=loaded)  # 6 + 4 freed - 6.8 = 3.2
    assert fit.source == "measured" and fit.verdict == "ok"
    assert "reloads" in fit.unload[0]


def test_other_loaded_model_is_unloaded_and_counted():
    loaded = [{"name": "qwen3.5:4b", "size": int(6.7 * GB), "size_vram": int(5.8 * GB), "context_length": 131_072}]
    fit = _assess(free_ram_gb=9.0, loaded=loaded)  # 9 + 0.9 - 6.8 = 3.1
    assert fit.verdict == "ok" and fit.unload == ["qwen3.5:4b"]


def test_unknown_model_uses_an_estimate():
    fit = _assess(model="qwen3.5:27b", context=131_072, file_gb=17.0, free_ram_gb=10.0)
    assert fit.source == "estimate" and fit.verdict == "no"
    assert "~" in F.summary(fit)


def test_no_ram_reading_is_unknown_not_ok():
    fit = _assess(free_ram_gb=None)
    assert fit.verdict == "unknown" and F.summary(fit).startswith("?")


def test_no_size_and_not_measured_is_unknown():
    assert _assess(model="other:1b", context=8192, file_gb=None).verdict == "unknown"


def test_group_programs_merges_by_name_splits_interpreters_and_skips_system():
    procs = [
        (1, "chrome.exe", 1 * GB, []), (2, "chrome.exe", 2 * GB, []),
        (3, "svchost.exe", 5 * GB, []), (4, "ollama.exe", 8 * GB, []),
        (5, "python.exe", 1 * GB, ["C:/venv/Scripts/python.exe", "C:/venv/Scripts/langgraph.exe", "dev", "--port", "2025"]),
        (6, "python.exe", int(0.5 * GB), ["python", "train.py"]),
        (7, "WindowsTerminal.exe", 1 * GB, []), (8, "Code.exe", 2 * GB, []),
    ]
    progs = F.group_programs(procs, skip_pids={8})
    by = {(p.name, p.hint): p for p in progs}
    assert by[("chrome", "")].gb == 3.0 and by[("chrome", "")].count == 2
    assert ("python", "langgraph dev") in by and ("python", "train.py") in by
    names = {p.name for p in progs}
    assert not names & {"svchost", "ollama", "WindowsTerminal", "Code"}


def test_pick_to_close_stops_once_the_shortfall_is_covered():
    progs = [F.Program(n, g) for n, g in (("a", 4.0), ("b", 2.0), ("c", 1.0), ("d", 0.2))]
    assert [p.name for p in F.pick_to_close(progs, 1.0)] == ["a", "b"]
    assert [p.name for p in F.pick_to_close(progs, 99)] == ["a", "b", "c"]


def test_advice_and_markdown_text():
    progs = [F.Program("chrome", 3.2, 25), F.Program("python", 0.9, 1, "langgraph dev")]
    fit = _assess(programs=progs)
    text = "\n".join(F.advice(fit))
    assert "chrome 3.2 GB" in text and "python (langgraph dev) 0.9 GB" in text and "/model use qwen3.5:4b" in text
    md = F.markdown(fit)
    assert "RAM left after loading:** 2.6 GB" in md and md.startswith("- **Fit:** ⚠")


def test_check_gathers_live_facts_and_lists_programs_only_when_needed(monkeypatch):
    from types import SimpleNamespace

    from app import config
    monkeypatch.setattr(config, "get_gpu_memory_info", lambda: SimpleNamespace(free_gib=7.5))
    monkeypatch.setattr(config, "get_local_model_inventory",
                        lambda: [SimpleNamespace(name="qwen3.5:latest", size_gib=6.6),
                                 SimpleNamespace(name="qwen3.5:4b", size_gib=3.4)])
    monkeypatch.setattr(F, "_ollama_ps", lambda url: [])
    calls = []
    monkeypatch.setattr(F, "live_programs", lambda: calls.append(1) or [F.Program("chrome", 4.0)])

    monkeypatch.setattr(config, "get_available_system_memory_gib", lambda: 14.0)
    assert F.check("qwen3.5:latest", 262_144).verdict == "ok" and calls == []

    monkeypatch.setattr(config, "get_available_system_memory_gib", lambda: 8.0)
    fit = F.check("qwen3.5:latest", 262_144)
    assert fit.verdict == "tight" and calls == [1] and fit.close[0].name == "chrome"
    assert fit.alternatives[0] == "/model use qwen3.5:4b" and "131072" in fit.alternatives[1]


def test_startup_line_never_blocks_when_the_check_fails(monkeypatch, capsys):
    from app import main

    def boom(*a, **k):
        raise RuntimeError("nvidia-smi hung")
    monkeypatch.setattr(F, "check", boom)
    main._print_memory_fit("qwen3.5:latest", 262_144, "http://127.0.0.1:11434")  # must not raise


def test_startup_line_prints_verdict_and_advice(monkeypatch):
    from app import main
    fit = _assess(programs=[F.Program("chrome", 3.2, 25)])
    monkeypatch.setattr(F, "check", lambda *a, **k: fit)
    with main.console.capture() as cap:
        main._print_memory_fit("qwen3.5:latest", 262_144, "http://127.0.0.1:11434")
    out = cap.get()
    assert "⚠" in out and "Close to free RAM: chrome 3.2 GB" in out
