"""Live 2026-11-11: a long answer block (a list or table with no blank line) vanished while it was written, because
the live area is cropped to the screen; and the status line was gone during a turn. Now a block taller than the
screen is printed for good as it grows, and a footer under the live part shows this machine and the speed."""
import io
import re

from langchain_core.messages import AIMessageChunk
from rich.console import Console

from app.ui import stream, sysmon

LIST = "\n".join(f"{n}. item number {n}" for n in range(1, 61))
CODE = "Here:\n```python\n" + "\n".join(f"x{n} = {n}" for n in range(1, 51)) + "\n```\nDone."


def _chunks(text, size=7):
    return [AIMessageChunk(content=text[i:i + size]) for i in range(0, len(text), size)]


def _run(text, height=15, terminal=True, **kw):
    out = io.StringIO()
    console = Console(file=out, width=80, height=height, force_terminal=terminal, color_system=None)
    res = stream.stream_reply(console, _chunks(text), **kw)
    return res, out.getvalue()


def test_block_part_reopens_and_closes_a_cut_code_fence():
    block = "```python\na = 1\nb = 2\nc = 3\n```"
    assert stream.block_part(block, 0, 3) == "```python\na = 1\nb = 2\n```"
    assert stream.block_part(block, 3) == "```python\nc = 3\n```"
    assert stream.block_part("1. a\n2. b\n3. c", 1) == "2. b\n3. c"


def test_overflow_cut_only_when_taller_than_the_screen():
    assert stream.overflow_cut("1. a\n2. b", 0, 8) is None
    assert stream.overflow_cut(LIST, 0, 8) == 59                       # all but the line being written
    assert stream.overflow_cut(LIST, 55, 8) is None                    # the rest fits
    assert stream.overflow_cut("x\n```py\ny", 0, 1) == 1               # never leaves an empty code block


def test_a_long_list_is_printed_once_and_whole_on_a_small_screen():
    res, out = _run(LIST, terminal=False)        # only what is printed for good, no live frames
    assert res.text == LIST
    counts = {n: len(re.findall(rf"\bitem number {n}\b", out)) for n in range(1, 61)}
    assert set(counts.values()) == {1}, {n: c for n, c in counts.items() if c != 1}


def test_while_it_is_written_the_top_of_a_long_list_is_already_on_screen_for_good():
    """The bug itself: before, nothing of the block was printed until it ended, and the live area showed only what
    fit the screen, so the top vanished. Checked in the middle of the stream."""
    out = io.StringIO()
    console = Console(file=out, width=80, height=15, force_terminal=False, color_system=None)
    seen_mid = {}

    def chunks():
        sent = ""
        for c in _chunks(LIST):
            if "item number 50" in sent and "printed" not in seen_mid:
                seen_mid["printed"] = out.getvalue()
            sent += c.content
            yield c

    stream.stream_reply(console, chunks())
    assert "item number 10" in seen_mid["printed"] and "item number 40" in seen_mid["printed"]


def test_a_long_code_block_keeps_every_line_once():
    res, out = _run(CODE, terminal=False)
    assert res.text == CODE
    assert all(out.count(f"x{n} = {n}") == 1 for n in range(1, 51)) and out.count("Done.") == 1
    assert "```" not in out                       # the cut fence is rendered as code, not shown as text


def test_the_footer_is_drawn_under_the_live_part():
    seen = []

    def footer(speed, writing):
        seen.append((speed, writing))
        return sysmon.working_footer(3, sysmon.Sample(cpu_pct=10, ram_free_gb=6.0), speed=speed, writing=writing)

    _run(LIST[:400], footer=footer)
    assert seen and any(w for _, w in seen)                             # shown while the answer is written


def test_working_footer_text():
    s = sysmon.Sample(cpu_pct=35, ram_free_gb=1.2, gpu_used_gb=5.2, gpu_total_gb=8, gpu_pct=92, gpu_temp_c=74)
    t = sysmon.working_footer(12.4, s, speed=24)
    assert t.plain == "  working 12s · 24 tok/s · CPU 35% · RAM 1.2G free · GPU 5.2/8G 92% 74°C   esc to stop"
    assert any(span.style == "m.err" and t.plain[span.start:span.end] == "RAM 1.2G free" for span in t.spans)
    assert "esc to stop" not in sysmon.working_footer(1, s, writing=False).plain
