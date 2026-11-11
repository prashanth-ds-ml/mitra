"""The status line (user, 2026-11-11): only what you can act on. Left: machine/model · mode · ctx % · folder.
Right: the last answer's speed · CPU · RAM free · GPU memory, load, temperature. No token counts."""
import time

from app.core import chat as C
from app.ui import status, sysmon
from tests.test_chat_core import Model, fake_hooks

S = sysmon.Sample(cpu_pct=18.2, ram_free_gb=3.71, gpu_used_gb=5.2, gpu_total_gb=7.96, gpu_pct=41, gpu_temp_c=63)


def _text(parts):
    return "".join(t for _, t in parts)


def _warned(parts):
    return [t for style, t in parts if style == "class:status.warn"]


def test_nvidia_smi_output_is_parsed():
    assert sysmon.parse_gpu("409, 8151, 11, 60\n") == (409 / 1024, 8151 / 1024, 11.0, 60.0)
    assert sysmon.parse_gpu("") is None and sysmon.parse_gpu("[N/A], 8151, 11, 60") is None


def test_the_machine_block_full_and_compact():
    full = _text(sysmon.segments(S, speed=24.4))
    assert full == "24 tok/s · CPU 18% · RAM 3.7G free · GPU 5.2/8G 41% 63°C"
    assert _text(sysmon.segments(S, speed=24.4, compact=True)) == "24 tok/s · CPU 18% · RAM 3.7G · GPU 41%"
    assert _text(sysmon.segments(sysmon.Sample(cpu_pct=5, ram_free_gb=10))) == "CPU 5% · RAM 10.0G free"  # no GPU


def test_orange_only_for_what_needs_you():
    assert _warned(sysmon.segments(S, speed=24)) == []
    assert _warned(sysmon.segments(S, speed=6, slow=True)) == ["6 tok/s"]
    assert _warned(sysmon.segments(S, ram_warn_gb=5.4)) == ["RAM 3.7G free"]      # less than the model needs
    hot = sysmon.Sample(gpu_used_gb=7, gpu_total_gb=8, gpu_pct=99, gpu_temp_c=88)
    assert _warned(sysmon.segments(hot)) == ["GPU 7.0/8G 99% 88°C"]


def _line(width, **kw):
    return status.status_line(model="mimo", mode="auto", total_tokens=21_600, context_limit=131_072, cwd="C:/x/proj",
                              branch="main", width=width, right=sysmon.segments(S, speed=24),
                              right_compact=sysmon.segments(S, speed=24, compact=True), **kw)


def test_the_status_line_has_no_token_count_and_puts_the_machine_on_the_right():
    wide = _text(_line(160))
    assert "tokens" not in wide and "ctx 16%" in wide and "proj (main)" in wide
    assert wide.endswith("GPU 5.2/8G 41% 63°C") and len(wide) == 159        # flush with the right edge
    assert "shift+tab" not in wide                                          # the hint gives way to the machine


def test_a_narrow_terminal_gets_the_short_block_or_none():
    mid = _text(_line(95))
    assert mid.endswith("GPU 41%") and len(mid) == 94
    narrow = _text(_line(50))
    assert "CPU" not in narrow and "ctx 16%" in narrow
    plain = _text(status.status_line(model="m", mode="auto", total_tokens=0, context_limit=1, cwd="C:/x/p",
                                     branch="", width=120))
    assert "shift+tab mode · /help" in plain                                # no machine block: the hint stays


def test_the_monitor_samples_in_the_background():
    calls = []
    mon = sysmon.Monitor(interval_s=0.2, sampler=lambda: calls.append(1) or sysmon.Sample(cpu_pct=len(calls)))
    mon.start()
    assert mon.last.cpu_pct is None                                         # the meaningless first 0%
    time.sleep(0.9)
    mon.stop()
    assert len(calls) >= 3 and mon.last.cpu_pct >= 3


def test_speed_comes_from_ollamas_timing_and_slow_is_relative_to_this_machine(tmp_path):
    s = C.ChatSession(workspace=tmp_path, llm=Model(), hooks=fake_hooks()[0])
    s._note_speed({"eval_count": 240, "eval_duration": 10 * 10**9})
    assert s.last_speed == 24.0 and not s.speed_is_slow
    s._note_speed({"eval_count": 5, "eval_duration": 10**9})                # too short to count
    assert s.last_speed == 24.0
    s._note_speed({"eval_count": 100, "eval_duration": 10 * 10**9})          # 10 tok/s: spilled to the CPU
    assert s.last_speed == 10.0 and s.speed_is_slow
    s.backend_kind = "remote"                                                # Kaggle has its own best
    assert not s.speed_is_slow
