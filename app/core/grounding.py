"""Claims that need proof (D-077 must-have 6, E-110): an answer that says it confirmed, verified, found or checked
something, or that the tests pass, must be backed by a tool result from the same turn. Pure functions, no model call:
a small model ignores "never state a number you did not check" in a prompt, so the check is code.

Live 2026-11-11: "Confirmed that India's DPDP Rules require compliance by May 2027" after a search that never ran,
and "Found ScrapUncle and Recykal" from a search that returned only an arXiv paper."""
from __future__ import annotations

import re

# says it checked something (now, in this turn)
_CHECKED = re.compile(
    r"\b(confirm(ed|s)?|verified|verify that|i (found|searched|looked (it )?up|checked)|we found|"
    r"according to (my|the) (search|results)|search(es)? (show|showed|shows|confirm)|found that)\b",
    re.IGNORECASE)
# says the tests pass
_TESTS = re.compile(r"\b(all (the )?tests? (now )?(pass|passed|passing)|tests? (now |all )?(pass|passed|are passing)|"
                    r"tests? (are )?green)\b", re.IGNORECASE)
# D-078 #3: says a change is finished (only checked when the turn changed files)
_DONE = re.compile(r"\b(done|fixed|works( now)?|is working|now working|implemented|completed|solved|resolved)\b",
                   re.IGNORECASE)
# the answer says the change was not tested (anywhere in it)
_UNTESTED = re.compile(r"\b(untested|not (been )?tested|no tests|without (running )?(the )?tests|tests? (still )?fail)",
                       re.IGNORECASE)
# honest "nothing found" / negations are not claims
_HONEST = re.compile(r"\b(not|n't|no|nothing|could not|couldn't|unable|without|fail(ed|s)?|unverified|untested|"
                     r"did not)\b", re.IGNORECASE)
_NUMBER = re.compile(r"\d[\d,.]*\d|\d")
_NAME = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][A-Za-z0-9]{2,}\b")
_COMMON = {"The", "This", "That", "These", "Those", "Mitra", "Here", "There", "Yes", "Also", "And", "But", "For",
           "With", "From", "Your", "You", "Our", "Its", "What", "Which", "When", "Confirmed", "Verified", "Found",
           "Checked", "According", "Search", "Searches", "Results", "Tests", "Test", "All", "Key", "Note", "Why"}
MAX_SHOWN = 3


def _sentences(text: str) -> list[str]:
    plain = re.sub(r"[*_`#>|]+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+|\n+", plain)
    return [" ".join(p.split()) for p in parts if p.strip()]


def _numbers(sentence: str) -> list[str]:
    return [n.strip(".,") for n in _NUMBER.findall(sentence)]


def _names(sentence: str) -> list[str]:
    words = sentence.split(" ", 1)
    rest = words[1] if len(words) > 1 else ""  # the first word is capitalised anyway
    return [w for w in _NAME.findall(rest) if w not in _COMMON]


def _findings(output: str) -> str:
    """A tool's output without the lines that only repeat the request: a search result's header echoes the query
    ("# Web results for 'ScrapUncle Recykal'"), which is not evidence that anything was found."""
    return "\n".join(line for line in output.splitlines()
                     if not re.match(r"\s*(#\s*Web results for|Sources:|URL:)", line))


def _backed(sentence: str, evidence: str) -> bool:
    """Every number and at least half of the names in the sentence appear in this turn's tool output."""
    nums, names = _numbers(sentence), _names(sentence)
    if not nums and not names:
        return bool(evidence)  # nothing specific to check: some tool must have answered in this turn
    if any(n not in evidence for n in nums):
        return False
    if names:
        hits = sum(1 for n in names if n.lower() in evidence)
        return hits * 2 >= len(names)
    return True


def unbacked(text: str, tools: list[tuple[str, bool, str]], changed: bool = False) -> list[str]:
    """The sentences of `text` that claim a check no tool result of this turn backs. `tools`: (name, ok, output)
    of every tool run in the turn, in order. `changed`: the turn changed files, so "done" / "fixed" needs the last
    test run of the turn to have passed (D-078 #3)."""
    evidence = " ".join(_findings(out) for _, ok, out in tools if ok).lower()
    test_runs = [ok for name, ok, _ in tools if name == "run_tests"]
    tested_ok = bool(test_runs and test_runs[-1])
    # B9 live: "Done. … The project has no tests, so this change is untested." is honest: the caveat is elsewhere
    says_untested = bool(_UNTESTED.search(text or ""))
    out = []
    for s in _sentences(text or ""):
        if _HONEST.search(s):
            continue
        if _TESTS.search(s) or (changed and _DONE.search(s) and not says_untested):
            if not tested_ok:
                out.append(s)
            continue
        if _CHECKED.search(s) and not _backed(s, evidence):
            out.append(s)
    return out


def warning(claims: list[str]) -> str:
    """One line for the screen."""
    shown = "; ".join(f"“{c[:90]}{'…' if len(c) > 90 else ''}”" for c in claims[:MAX_SHOWN])
    more = f" (+{len(claims) - MAX_SHOWN} more)" if len(claims) > MAX_SHOWN else ""
    return f"not backed by a tool result in this turn: {shown}{more}. Treat as unverified."
