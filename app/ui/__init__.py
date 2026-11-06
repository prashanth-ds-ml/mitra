"""Mitra's terminal interface (D-031): Phosphor theme, live reply streaming, one-line tool steps, status line."""
from app.ui.render import (
    action_for,
    agent_steps,
    detail_block,
    format_tokens,
    shell_done,
    shell_start,
    step_line,
    thinking_done,
    tool_line,
    turn_footer,
    turn_summary,
)
from app.ui import files, header, menu, notify
from app.ui.input import InputBox, UiState, mode_label, next_mode
from app.ui.keys import KeyWatcher
from app.ui.status import framed_status, git_branch, prompt_message, status_line
from app.ui.stream import StreamResult, ThinkSplitter, split_blocks, stream_reply
from app.ui.theme import PHOSPHOR, THEME, apply, prompt_style

__all__ = [
    "PHOSPHOR", "THEME", "apply", "prompt_style",
    "action_for", "agent_steps", "detail_block", "menu", "format_tokens", "shell_done", "shell_start", "step_line",
    "thinking_done", "tool_line", "turn_footer", "turn_summary", "files",
    "InputBox", "UiState", "mode_label", "next_mode", "KeyWatcher", "notify",
    "header", "framed_status", "git_branch", "prompt_message", "status_line",
    "StreamResult", "ThinkSplitter", "split_blocks", "stream_reply",
]
