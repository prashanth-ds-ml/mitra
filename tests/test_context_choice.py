"""E-046: compaction follows the context (80%), and /context 128k|256k|auto picks the size per model."""
from app import config as C


def test_compaction_point_follows_the_context():
    assert C.compact_threshold({}, 262_144) == 209_715          # was 120,000: half the 256K never used
    assert C.compact_threshold({}, 131_072) == 104_857          # unchanged for 128K
    assert C.compact_threshold({"auto_compact_threshold": 0}, 262_144) == 209_715
    assert C.compact_threshold({"auto_compact_threshold": 50_000}, 262_144) == 50_000  # a cap in mitra.toml still wins
    assert C.compact_threshold({"auto_compact_threshold": 500_000}, 131_072) == 104_857  # never past 80%


def test_default_config_no_longer_caps_at_120k():
    assert C._DEFAULTS["auto_compact_threshold"] == 0


def test_parse_context_choice():
    assert C.parse_context_choice("128k") == (131_072, "")
    assert C.parse_context_choice(" 256K ") == (262_144, "")
    assert C.parse_context_choice("auto") == (0, "")
    assert C.parse_context_choice("65536") == (65_536, "")
    assert C.parse_context_choice("16k")[1].startswith("Unknown")
    assert "At least" in C.parse_context_choice("8192")[1]
    assert "at most 256K" in C.parse_context_choice("999999", 262_144)[1]


def test_choice_is_kept_per_model_and_auto_removes_it(monkeypatch):
    monkeypatch.setattr(C, "get_model_facts", lambda name: {"parameters": 9_600_000_000})
    assert C.context_for_model("qwen3.5:latest") == C.LARGE_MODEL_CONTEXT  # measured default: 256K
    C.save_context_choice("qwen3.5:latest", 131_072)
    assert C.context_for_model("qwen3.5:latest") == 131_072
    assert C.load_context_choice("qwen3.5:4b") == 0                    # other models untouched
    C.save_context_choice("qwen3.5:latest", 0)
    assert C.context_for_model("qwen3.5:latest") == C.LARGE_MODEL_CONTEXT


def test_context_command_is_wired_in_the_chat():
    import inspect

    from app import main
    src = inspect.getsource(main._chat)
    block = src[src.index('if cmd.startswith("/context "):'):]
    block = block[: block.index('if cmd == "/context":')]
    for needed in ("save_context_choice", "compact_threshold", "chat.llm, chat.num_ctx", "_print_memory_fit"):
        assert needed in block
