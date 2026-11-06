"""/doctor Ollama checks, with fake /api/ps responses."""

import urllib.error

from app.doctor import ollama_report

GIB = 1024 ** 3


def _fake(response: dict, seen: list | None = None):
    def get(url):
        if seen is not None:
            seen.append(url)
        return response
    return get


def _loaded(name="qwen3.5:4b", ctx=131072, size=4 * GIB, vram=3 * GIB):
    entry = {"name": name, "model": name, "size": size, "size_vram": vram}
    if ctx is not None:
        entry["context_length"] = ctx
    return {"models": [entry]}


def test_reachable_and_loaded_with_matching_context():
    seen = []
    out = ollama_report("qwen3.5:4b", 131072, base_url="http://h:1/", get=_fake(_loaded(), seen))
    assert seen == ["http://h:1/api/ps"]
    assert "reachable at `http://h:1/`" in out
    assert "`qwen3.5:4b`: 4.0 GiB, 75% on GPU, context 131,072" in out
    assert "**`qwen3.5:4b`:** loaded" in out
    assert "131,072, as Mitra asked" in out
    assert "smaller context" not in out


def test_unreachable():
    def get(url):
        raise urllib.error.URLError("connection refused")
    out = ollama_report("qwen3.5:4b", 131072, get=get)
    assert "not reachable" in out
    assert "ollama serve" in out


def test_model_not_loaded():
    out = ollama_report("qwen3.5:9b", 65536, get=_fake(_loaded("qwen3.5:4b")))
    assert "`qwen3.5:4b`" in out
    assert "**`qwen3.5:9b`:** not loaded" in out


def test_nothing_loaded():
    out = ollama_report("qwen3.5:9b", 65536, get=_fake({"models": []}))
    assert "**Loaded models:** none" in out
    assert "not loaded" in out


def test_smaller_context_warns():
    out = ollama_report("qwen3.5:4b", 131072, get=_fake(_loaded(ctx=4096)))
    assert "Ollama is running it with a smaller context than Mitra asked for" in out
    assert "4,096 < 131,072" in out


def test_larger_context_is_fine():
    out = ollama_report("qwen3.5:4b", 65536, get=_fake(_loaded(ctx=131072)))
    assert "larger is fine" in out
    assert "smaller context" not in out


def test_no_context_length_in_response():
    out = ollama_report("qwen3.5:4b", 65536, get=_fake(_loaded(ctx=None)))
    assert "does not report it" in out
    assert "context 0" not in out


def test_latest_tag_matches_untagged_name():
    out = ollama_report("mymodel", 8192, get=_fake(_loaded("mymodel:latest", ctx=8192)))
    assert "**`mymodel`:** loaded" in out


def test_zero_size_does_not_divide_by_zero():
    out = ollama_report("x", 8192, get=_fake(_loaded("x:latest", size=0, vram=0, ctx=8192)))
    assert "GPU share unknown" in out


def test_doctor_handler_includes_ollama_section():
    import inspect

    from app import main
    src = inspect.getsource(main._chat)
    block = src[src.index('if cmd == "/doctor":'):]
    block = block[: block.index("continue")]
    assert "## Ollama" in block
    assert "ollama_report(" in block
