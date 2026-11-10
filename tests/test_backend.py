"""D-062 B0, B1, B2, B5, B6: the pure backend decisions."""
from app import backend as B
from app import remote


# ── B5 routing ────────────────────────────────────────────────────────────────

def test_read_work_on_the_laptop_write_work_on_the_remote():
    assert B.route("plan", "chat") == B.LAPTOP
    assert B.route("read-only", "builder") == B.LAPTOP
    assert B.route("approve", "planner") == B.LAPTOP and B.route("auto", "reviewer") == B.LAPTOP
    for mode in ("approve", "auto"):
        for role in ("chat", "builder", "tester", "debugger"):
            assert B.route(mode, role) == B.REMOTE


# ── B2 laptop model ───────────────────────────────────────────────────────────

INSTALLED = {"mimo-v2.6:9b", "qwen3.5:4b"}


def test_plenty_of_ram_keeps_the_preferred_model():
    m, c, note = B.laptop_choice("mimo-v2.6:9b", 131072, INSTALLED, lambda m, c: "ok")
    assert (m, c, note) == ("mimo-v2.6:9b", 131072, "")


def test_short_ram_quietly_takes_a_smaller_one():
    fits = {("mimo-v2.6:9b", 131072): "no", ("mimo-v2.6:9b", 65536): "no", ("qwen3.5:4b", 65536): "tight"}
    m, c, note = B.laptop_choice("mimo-v2.6:9b", 131072, INSTALLED, lambda m, c: fits.get((m, c), "no"))
    assert (m, c) == ("qwen3.5:4b", 65536) and "RAM is short" in note


def test_nothing_fits_takes_the_smallest_and_says_so():
    m, c, note = B.laptop_choice("mimo-v2.6:9b", 131072, INSTALLED, lambda m, c: "no")
    assert (m, c) == ("qwen3.5:4b", 32768) and "/free" in note


def test_only_installed_models_and_configured_list():
    assert B.candidates("mimo-v2.6:9b", 131072, {"mimo-v2.6:9b"}) == [("mimo-v2.6:9b", 131072),
                                                                        ("mimo-v2.6:9b", 65536)]
    assert B.candidates("x", 131072, set(), ["qwen3.5:9b@128k", "qwen3.5:4b@64k"]) == [
        ("qwen3.5:9b", 131072), ("qwen3.5:4b", 65536)]
    assert B.parse_choice("mimo-v2.6:9b@128k") == ("mimo-v2.6:9b", 131072)


# ── B0 health ─────────────────────────────────────────────────────────────────

def _health(up=True, hours=None, active=True):
    calls = {"probe": 0, "quota": 0}

    def probe(url):
        calls["probe"] += 1
        return ([], "") if up else ([], "getaddrinfo failed")

    def quota():
        calls["quota"] += 1
        return hours

    h = B.Health(probe=probe, quota=quota, active=lambda: {"url": "u", "name": "kaggle"} if active else None,
                 clock=lambda: 1000.0)
    return h, calls


def test_health_up_down_and_hours():
    h, calls = _health(up=True, hours={"left_h": 28.1, "total_h": 30.0})
    s = h.check()
    assert s.state == "up" and s.hours_left == 28.1 and calls["quota"] == 1
    h.check()
    assert calls["quota"] == 1  # hours only every 10 minutes
    h2, _ = _health(up=False)
    assert h2.check().state == "down" and "getaddrinfo" in h2.s.error
    h3, calls3 = _health(active=False)
    assert h3.check().state == "none" and calls3["probe"] == 0


def test_starting_is_kept_until_the_remote_answers():
    h, _ = _health(active=False)
    h.starting("loading the model")
    assert h.check().state == "starting"  # no remote yet: still starting
    h._active = lambda: {"url": "u", "name": "kaggle"}
    assert h.check().state == "up" and h.s.stage == ""


# ── B1 status text ────────────────────────────────────────────────────────────

def test_status_text():
    up = B.HealthState(state="up", name="kaggle", hours_left=28.14)
    assert B.status_text(B.REMOTE, "mimo-v2.6:9b", 262144, up) == ("☁ kaggle · mimo-v2.6 256K · 28.1 h left", "ok")
    low = B.HealthState(state="up", name="kaggle", hours_left=0.5)
    assert B.status_text(B.REMOTE, "mimo-v2.6:9b", 262144, low)[1] == "warn"
    down = B.HealthState(state="down", name="kaggle")
    assert B.status_text(B.REMOTE, "mimo-v2.6:9b", 262144, down) == ("☁ kaggle not answering · mimo-v2.6 256K", "err")
    assert B.status_text(B.LAPTOP, "qwen3.5:4b", 65536, B.HealthState()) == ("💻 laptop · qwen3.5 64K", "ok")
    starting = B.HealthState(state="starting", stage="loading the model")
    assert B.status_text(B.LAPTOP, "qwen3.5:4b", 65536, starting)[0].endswith("☁ starting: loading the model")


# ── B6 prefs ──────────────────────────────────────────────────────────────────

def test_prefs_are_remembered():
    assert B.prefs() == {}
    B.save_prefs(kaggle_offer="no")
    B.save_prefs(onboarded=True)
    assert B.prefs() == {"kaggle_offer": "no", "onboarded": True}
    remote.clear()
