"""Tool calls written as text (M1: tolerant tool-call parsing).

Small models sometimes answer with the call as JSON in the text instead of a native tool call:
    {"name": "read_file", "arguments": {"path": "a.py"}}
    <tool_call>{"name": "run_tests", "arguments": {}}</tool_call>
    ```json {"tool": "edit_file", "parameters": {...}} ```
These are turned into real tool calls. Text that clearly tries to call a tool but is not valid JSON gets a short
error back, so the model can try once more.
"""
from __future__ import annotations

import json
import re
import uuid

_TAGGED = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.S)
_FENCED = re.compile(r"```(?:json|tool_call)?\s*(\{.*?\})\s*```", re.S)


def _objects(text: str) -> list[str]:
    """Top-level {...} blocks in text (brace matching that respects strings)."""
    out, depth, start, in_str, esc = [], 0, -1, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start >= 0:
                out.append(text[start:i + 1])
    return out


def _as_call(obj, known: set[str]) -> dict | None:
    if not isinstance(obj, dict):
        return None
    name = obj.get("name") or obj.get("tool") or obj.get("function")
    if isinstance(name, dict):  # {"function": {"name": ..., "arguments": ...}}
        obj, name = name, name.get("name")
    if not isinstance(name, str) or name not in known:
        return None
    args = obj.get("arguments", obj.get("parameters", obj.get("args", {})))
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except json.JSONDecodeError:
            return None
    if not isinstance(args, dict):
        return None
    return {"name": name, "args": args, "id": f"text-{uuid.uuid4().hex[:8]}", "type": "tool_call"}


def text_tool_calls(text: str, known: set[str]) -> tuple[list[dict], str]:
    """Return (tool calls found in the text, error message for a broken attempt or "")."""
    if not text or "{" not in text:
        return [], ""
    candidates = _TAGGED.findall(text) + _FENCED.findall(text) + _objects(text)
    calls, seen = [], set()
    broken = False
    for raw in candidates:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            if any(f'"{n}"' in raw for n in known):
                broken = True
            continue
        objs = obj if isinstance(obj, list) else [obj]
        for o in objs:
            call = _as_call(o, known)
            if call:
                key = (call["name"], json.dumps(call["args"], sort_keys=True))
                if key not in seen:
                    seen.add(key)
                    calls.append(call)
    if calls:
        return calls, ""
    if broken or _TAGGED.search(text):
        return [], ("✗ Your tool call was written as text and is not valid JSON. Call the tool again as a "
                    "proper tool call, with valid JSON arguments.")
    return [], ""
