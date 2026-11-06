"""Replay a recorded run without Ollama (M1 record/replay, dsh llm-replay).

Every run writes `.mitra/runs/<time>/*.jsonl`; its "model" rows hold what the model said and which tools it called.
`ReplayModel(path)` answers with those replies in order, so a real run can become a regression test.
"""
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage


class ReplayModel:
    def __init__(self, path: str | Path):
        rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
        self.replies = [AIMessage(content=r.get("text") or "", tool_calls=r.get("tool_calls") or [])
                        for r in rows if r.get("kind") == "model"]
        self.calls = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        if self.calls >= len(self.replies):
            raise RuntimeError(f"replay exhausted after {len(self.replies)} recorded replies")
        reply = self.replies[self.calls]
        self.calls += 1
        return reply

    def stream(self, messages):
        yield self.invoke(messages)
