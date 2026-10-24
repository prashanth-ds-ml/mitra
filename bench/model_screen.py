"""Model screen: which local model handles coding-agent tool calls best on this machine?

Calls Ollama's native /api/chat directly (no agent in between) with five coding tools and 12 scenarios:
picking the right tool, exact str_replace arguments, using a tool result, recovering from a tool error,
not calling tools when none is needed, and the same edit buried in a long prompt. Also measures speed and
how much of the model sits in VRAM at 32K and 64K context.

    python bench/model_screen.py --models qwen3.5:4b qwen3:8b ... [--out results/model_screen.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

OLLAMA = "http://127.0.0.1:11434"
SCREEN_CTX = 16384
SYSTEM = (
    "You are a coding agent working in a Python repository. Use the tools to inspect and change code. "
    "Call exactly one tool per step. When the task is done, call finish."
)


def _fn(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


TOOLS = [
    _fn("read_file", "Read a file and return its content with line numbers.", {"path": {"type": "string"}}, ["path"]),
    _fn(
        "search",
        "Search the repository for a text pattern; returns matching lines with file:line.",
        {"pattern": {"type": "string"}},
        ["pattern"],
    ),
    _fn(
        "str_replace",
        "Replace one exact, unique occurrence of old with new in a file. old must match the file exactly.",
        {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}},
        ["path", "old", "new"],
    ),
    _fn("run_tests", "Run the test suite and return the output.", {}, []),
    _fn("finish", "Finish the task with a short summary.", {"summary": {"type": "string"}}, ["summary"]),
]

PAYMENTS_SNIPPET = """\
1  def charge_order(client, order, sleep=time.sleep):
2      key = f"order-{order.id}"
3      for attempt in range(MAX_RETRIES + 1):
4          try:
5              result = client.charges.create(order_total(order), idempotency_key=key)
6          except RateLimited as err:
7              if attempt == MAX_RETRIES:
8                  raise
9              sleep(err.retry_after)
10             continue
11         return result.value
"""
FILLER = "\n".join(f"{i:<4} # helper {i}: formats a receipt line for audit export (unrelated to payments)" for i in range(1, 700))


def _tool_turn(name: str, args: dict, result: str) -> list[dict]:
    return [
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]},
        {"role": "tool", "content": result},
    ]


@dataclass(frozen=True)
class Case:
    id: str
    what: str
    messages: list[dict]
    expect_tool: str | None  # None = no tool call expected
    check: dict  # arg name -> required substring (or exact text for str_replace "old")
    exact: tuple[str, ...] = ()


def cases() -> list[Case]:
    fix = 'Fix: the idempotency key must not change between retries. In shop/payments.py replace `key = f"order-{order.id}"` with `key = f"order-{order.id}-v2"`.'
    return [
        Case("C01", "open a named file", [{"role": "user", "content": "Show me shop/payments.py."}], "read_file", {"path": "payments.py"}),
        Case("C02", "search for a symbol", [{"role": "user", "content": "Where is RateLimited handled in this repo?"}], "search", {"pattern": "RateLimited"}),
        Case("C03", "run the tests", [{"role": "user", "content": "Run the test suite and tell me what fails."}], "run_tests", {}),
        Case(
            "C04",
            "exact str_replace with quotes and braces",
            [{"role": "user", "content": fix}, *_tool_turn("read_file", {"path": "shop/payments.py"}, PAYMENTS_SNIPPET)],
            "str_replace",
            {"path": "payments.py", "old": 'key = f"order-{order.id}"', "new": 'key = f"order-{order.id}-v2"'},
            exact=("old", "new"),
        ),
        Case(
            "C05",
            "follow a traceback to the file",
            [
                {"role": "user", "content": "The tests fail, find out why."},
                *_tool_turn(
                    "run_tests",
                    {},
                    'FAILED tests/test_t03.py::test_over_refund - AttributeError\n  File "shop/payments.py", line 58, in refund_order\n    return result.value.id\nAttributeError: \'NoneType\' object has no attribute \'id\'',
                ),
            ],
            "read_file",
            {"path": "payments.py"},
        ),
        Case(
            "C06",
            "edit using a line from the tool result",
            [
                {"role": "user", "content": "In shop/payments.py, the function returns result.value without checking result.ok. Make it raise PaymentFailed(result.error) when not ok. Edit only the return line."},
                *_tool_turn("read_file", {"path": "shop/payments.py"}, PAYMENTS_SNIPPET),
            ],
            "str_replace",
            {"path": "payments.py", "old": "return result.value", "new": "PaymentFailed"},
        ),
        Case(
            "C07",
            "finish when tests pass",
            [
                {"role": "user", "content": "Make the failing test pass."},
                *_tool_turn("str_replace", {"path": "shop/app.py", "old": "a", "new": "b"}, "Edited shop/app.py"),
                *_tool_turn("run_tests", {}, "....................\n20 passed in 0.41s"),
            ],
            "finish",
            {},
        ),
        Case("C08", "no tool for a plain question", [{"role": "user", "content": "In one sentence, what is an idempotency key? Do not use any tools."}], None, {}),
        Case(
            "C09",
            "same exact edit inside a long prompt (~10K tokens)",
            [
                {"role": "user", "content": fix},
                *_tool_turn("read_file", {"path": "shop/receipts.py"}, FILLER),
                *_tool_turn("read_file", {"path": "shop/payments.py"}, PAYMENTS_SNIPPET),
            ],
            "str_replace",
            {"path": "payments.py", "old": 'key = f"order-{order.id}"', "new": 'key = f"order-{order.id}-v2"'},
            exact=("old", "new"),
        ),
        Case(
            "C10",
            "search when the file is unknown",
            [{"role": "user", "content": "Find the function that lists all charges and check whether it follows next_cursor."}],
            "search",
            {"pattern": ""},
        ),
        Case(
            "C11",
            "recover from a failed edit by re-reading",
            [
                {"role": "user", "content": fix},
                *_tool_turn(
                    "str_replace",
                    {"path": "shop/payments.py", "old": "key = order.id", "new": "key = order.id"},
                    "Error: old text not found in shop/payments.py. Read the file and copy the exact text.",
                ),
            ],
            "read_file",
            {"path": "payments.py"},
        ),
        Case(
            "C12",
            "pick the tool after reading the SDK rules",
            [
                {"role": "user", "content": "Retry rate-limited charges in shop/payments.py. First check how the SDK reports rate limits."},
                *_tool_turn("search", {"pattern": "RateLimited"}, "paysdk/errors.py:42: class RateLimited(PayError):\nshop/payments.py:6: except RateLimited as err:"),
            ],
            "read_file",
            {"path": "errors.py"},
        ),
    ]


def _post(path: str, payload: dict, timeout: float = 600) -> dict:
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def score(case: Case, message: dict) -> tuple[bool, str]:
    calls = message.get("tool_calls") or []
    content = message.get("content") or ""
    if case.expect_tool is None:
        return (not calls, "ok" if not calls else "called a tool when none was needed")
    if not calls:
        if any(t["function"]["name"] in content for t in TOOLS) and "{" in content:
            return False, "tool call written as text, not a native call"
        return False, "no tool call"
    fn = calls[0].get("function", {})
    if fn.get("name") != case.expect_tool:
        return False, f"wrong tool {fn.get('name')} (expected {case.expect_tool})"
    args = fn.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return False, "arguments are not valid JSON"
    if not isinstance(args, dict):
        return False, "arguments are not an object"
    for key, want in case.check.items():
        got = args.get(key)
        if not isinstance(got, str):
            return False, f"missing argument {key}"
        if key in case.exact and got.strip() != want:
            return False, f"{key} not exact: {got!r}"
        if key not in case.exact and want not in got:
            return False, f"{key}={got!r} lacks {want!r}"
    return True, "ok"


def vram_fit(model: str, num_ctx: int) -> dict:
    """Load the model at a context size and report how much of it sits in VRAM."""
    try:
        _post("/api/generate", {"model": model, "prompt": "", "keep_alive": "2m", "options": {"num_ctx": num_ctx}})
        ps = _post_get("/api/ps")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"num_ctx": num_ctx, "error": str(exc)}
    entry = next((m for m in ps.get("models", []) if m.get("name") == model or m.get("model") == model), {})
    size, vram = entry.get("size") or 0, entry.get("size_vram") or 0
    return {"num_ctx": num_ctx, "size_gb": round(size / 2**30, 2), "gpu_share": round(vram / size, 3) if size else None}


def _post_get(path: str) -> dict:
    with urllib.request.urlopen(OLLAMA + path, timeout=30) as resp:
        return json.loads(resp.read())


def unload(model: str) -> None:
    try:
        _post("/api/generate", {"model": model, "prompt": "", "keep_alive": 0})
    except (urllib.error.URLError, OSError, ValueError):
        pass


def screen(model: str) -> dict:
    results = []
    gen_tps, prompt_tps = [], []
    for case in cases():
        started = time.time()
        try:
            resp = _post(
                "/api/chat",
                {
                    "model": model,
                    "messages": [{"role": "system", "content": SYSTEM}, *case.messages],
                    "tools": TOOLS,
                    "stream": False,
                    "options": {"num_ctx": SCREEN_CTX, "temperature": 0, "seed": 0},
                },
            )
        except (urllib.error.URLError, OSError, ValueError) as exc:
            results.append({"case": case.id, "passed": False, "why": f"infra: {exc}", "seconds": round(time.time() - started, 1)})
            continue
        passed, why = score(case, resp.get("message", {}))
        if resp.get("eval_duration"):
            gen_tps.append(resp["eval_count"] / (resp["eval_duration"] / 1e9))
        if resp.get("prompt_eval_duration") and resp.get("prompt_eval_count", 0) > 1000:
            prompt_tps.append(resp["prompt_eval_count"] / (resp["prompt_eval_duration"] / 1e9))
        results.append(
            {
                "case": case.id,
                "passed": passed,
                "why": why,
                "seconds": round(time.time() - started, 1),
                "prompt_tokens": resp.get("prompt_eval_count"),
                "output_tokens": resp.get("eval_count"),
                "thinking_chars": len(resp.get("message", {}).get("thinking") or ""),
            }
        )
    fits = [vram_fit(model, ctx) for ctx in (32768, 65536)]
    unload(model)
    return {
        "model": model,
        "passed": sum(r["passed"] for r in results),
        "total": len(results),
        "native_call_failures": sum("as text" in r["why"] for r in results),
        "gen_tokens_per_s": round(sum(gen_tps) / len(gen_tps), 1) if gen_tps else None,
        "prompt_tokens_per_s": round(sum(prompt_tps) / len(prompt_tps), 1) if prompt_tps else None,
        "seconds": round(sum(r["seconds"] for r in results), 1),
        "vram": fits,
        "cases": results,
    }


def main(argv: list[str] | None = None) -> int:
    global OLLAMA
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--ollama", default=OLLAMA)
    parser.add_argument("--out", type=Path, default=Path("results/model_screen.json"))
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    OLLAMA = args.ollama
    args.out.parent.mkdir(parents=True, exist_ok=True)
    report = json.loads(args.out.read_text(encoding="utf-8")) if args.out.exists() else {}
    for model in args.models:
        r = screen(model)
        report[model] = r
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")  # save after each model
        fit = " ".join(f"{v['num_ctx'] // 1024}K:{v.get('gpu_share')}" for v in r["vram"])
        print(f"{model:<22} {r['passed']:>2}/{r['total']}  gen {r['gen_tokens_per_s']} tok/s  prompt {r['prompt_tokens_per_s']} tok/s  {r['seconds']}s  gpu share {fit}", flush=True)
        for c in r["cases"]:
            if not c["passed"]:
                print(f"    {c['case']}: {c['why'][:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
