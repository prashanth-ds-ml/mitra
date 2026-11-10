"""I-21 /free: show what the model needs, tick programs, close them politely (force only on a second yes)."""
from types import SimpleNamespace

from app import fit as F
from app import main as M


def _progs():
    return F.group_programs([
        (1, "msedge.exe", 3 * F.GIB, []), (2, "msedge.exe", 1 * F.GIB, []),
        (3, "Code.exe", 2.3 * F.GIB, []), (4, "claude.exe", 1.5 * F.GIB, []),
        (5, "chrome.exe", 0.5 * F.GIB, []), (6, "tiny.exe", 0.1 * F.GIB, []),
        (7, "svchost.exe", 2 * F.GIB, []),  # never listed
    ])


def test_programs_keep_their_processes():
    edge = next(p for p in _progs() if p.name == "msedge")
    assert edge.pids == [1, 2] and edge.count == 2 and edge.gb == 4.0


def test_the_shortfall_is_pre_ticked_but_never_your_editor_or_claude():
    fit = F.Fit("no", "mimo-v2.6:9b", 131072, 5.6, 5.0, 3.7, -1.9)
    shown, pre = F.free_choices(fit, _progs())
    names = [p.name for p in shown]
    assert names == ["msedge", "Code", "claude", "chrome"]  # tiny and svchost are not listed
    assert {names[i] for i in pre} == {"msedge", "chrome"}
    ok = F.Fit("ok", "m", 131072, 1.0, 1.0, 9.0, 8.0)
    assert F.free_choices(ok, _progs())[1] == set()  # comfortable: list only, nothing ticked


def test_labels_warn_what_closing_does():
    edge = next(p for p in _progs() if p.name == "msedge")
    assert F.label(edge) == ("msedge (2 processes) · 4.0 GB · reopens your tabs on restart if 'continue where you "
                             "left off' is on")


def test_close_is_polite_first_and_reports_what_closed(monkeypatch):
    monkeypatch.setattr(F.os, "name", "nt")
    calls = []
    gone = set()

    def run(args, **kw):
        calls.append(args)
        gone.update(int(a) for a in args if a.isdigit())

    progs = [p for p in _progs() if p.name in ("msedge", "chrome")]
    out = F.close_programs(progs, run=run, alive=lambda pids: [p for p in pids if p not in gone], sleep=lambda s: None)
    assert out == {"msedge": True, "chrome": True}
    assert all("/F" not in c for c in calls) and calls[0][:3] == ["taskkill", "/PID", "1"]


def test_a_program_that_stays_open_is_reported_and_force_kills_the_tree(monkeypatch):
    monkeypatch.setattr(F.os, "name", "nt")
    calls = []
    progs = [p for p in _progs() if p.name == "Code"]
    out = F.close_programs(progs, run=lambda a, **k: calls.append(a), alive=lambda pids: list(pids),
                           sleep=lambda s: None, wait_s=1.0)
    assert out == {"Code": False}
    F.close_programs(progs, force=True, run=lambda a, **k: calls.append(a), alive=lambda pids: [],
                     sleep=lambda s: None)
    assert calls[-1][:3] == ["taskkill", "/F", "/T"]


def _fake_fit(results, alive_after_polite=()):
    """A fit module stand-in: two checks (before, after), the programs, and recorded closes."""
    rec = {"closed": [], "unloaded": []}
    before = F.Fit("no", "mimo-v2.6:9b", 131072, 5.6, 5.0, 3.7, -1.9, unload=["deepseek-r1:8b"])
    after = F.Fit("ok", "mimo-v2.6:9b", 131072, 5.6, 5.0, 9.1, 3.5)
    checks = iter([before, after])

    def close(programs, force=False, wait_s=10.0):
        rec["closed"].append(([p.name for p in programs], force))
        return {p.name: force or p.name not in alive_after_polite for p in programs}

    fake = SimpleNamespace(check=lambda *a, **k: next(checks), summary=F.summary, live_programs=_progs,
                           free_choices=F.free_choices, label=F.label, close_programs=close,
                           unload_models=lambda names, url: rec["unloaded"].extend(names) or names)
    return fake, rec


def test_free_closes_the_ticked_programs_and_unloads_models():
    fake, rec = _fake_fit({})
    asked = {}

    def tick(console, q, options, pre):
        asked["options"], asked["pre"] = options, pre
        return sorted(pre)  # the user accepts the ticks

    M._cmd_free("mimo-v2.6:9b", 131072, "http://x", fit_mod=fake, tick=tick, choose=lambda *a, **k: "no")
    assert asked["options"][-1] == "unload deepseek-r1:8b from Ollama"
    assert rec["unloaded"] == ["deepseek-r1:8b"]
    assert rec["closed"] == [(["msedge", "chrome"], False)]


def test_force_needs_a_second_yes():
    for answer, forced in (("no", False), ("yes", True)):
        fake, rec = _fake_fit({}, alive_after_polite={"msedge"})
        M._cmd_free("m", 131072, "http://x", fit_mod=fake, tick=lambda c, q, o, p: [0],
                    choose=lambda *a, **k: answer)
        assert rec["closed"][0] == (["msedge"], False)
        assert (len(rec["closed"]) == 2 and rec["closed"][1] == (["msedge"], True)) == forced


def test_cancel_closes_nothing():
    fake, rec = _fake_fit({})
    M._cmd_free("m", 131072, "http://x", fit_mod=fake, tick=lambda *a: None, choose=lambda *a, **k: "yes")
    assert rec["closed"] == [] and rec["unloaded"] == []


def test_start_line_points_to_free():
    fit = F.Fit("no", "m", 131072, 5.6, 5.0, 3.7, -1.9, close=_progs()[:2])
    assert any("/free closes the ones you pick" in line for line in F.advice(fit))


def test_shared_and_wsl_processes_are_not_offered_blindly():
    progs = F.group_programs([(1, "msedgewebview2.exe", 3 * F.GIB, []), (2, "vmmemWSL", 2 * F.GIB, []),
                              (3, "Teams.exe", 1 * F.GIB, [])])
    assert [p.name for p in progs] == ["msedgewebview2", "Teams"]  # WSL memory: `wsl --shutdown`, not a close
    shown, pre = F.free_choices(F.Fit("no", "m", 131072, 5.6, 5.0, 1.0, -4.6), progs)
    assert {shown[i].name for i in pre} == {"Teams"} and "closing can break them" in F.label(shown[0])


def test_typed_numbers_work_when_the_list_cannot_run():
    from app.ui import menu

    class Con:
        def print(self, *a, **k): pass
        def input(self, *a, **k): return "2, 3"

    def broken(options, ticked):
        raise RuntimeError("no terminal")

    assert menu.tick(Con(), "q", ["a", "b", "c"], {0}, runner=broken) == [1, 2]
    assert menu.tick(Con(), "q", ["a", "b"], {0}, runner=lambda o, t: {1, 0}) == [0, 1]


def test_windows_memory_compression_is_never_offered():
    """E-068: newer Windows names it MemCompression (no space): it was suggested for closing at start."""
    progs = F.group_programs([(1, "MemCompression", 2 * F.GIB, []), (2, "Memory Compression", 2 * F.GIB, []),
                              (3, "Code.exe", 1.5 * F.GIB, [])])
    assert [p.name for p in progs] == ["Code"]
