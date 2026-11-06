"""Replace secrets with *** before text is logged, shown or sent to a model.

Pattern-based, so it is a safety net, not a guarantee: it catches the common
key formats and NAME=value pairs whose name says "secret".
"""

from __future__ import annotations

import re

MASK = "***"

# Words that mark a name (env var, dict key, JSON key) as holding a secret.
_SECRET_WORDS = ("key", "token", "secret", "password")

# Known token formats. Order matters: the PEM block goes first so its body is
# masked as one piece, and sk-ant- before the shorter sk- form.
_TOKEN_PATTERNS = [
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bgh[pos]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]

# "Bearer <token>": keep the word so the reader still sees what was there.
_BEARER = re.compile(r"\b(Bearer\s+)[A-Za-z0-9._~+/\-]+=*", re.IGNORECASE)

_NAME = r"[A-Za-z0-9_.\-]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Za-z0-9_.\-]*"

# NAME=value / NAME: value (env files, YAML, shell). The value must be a literal
# (quoted string or a bare word that is not a call or attribute), so code such as
# `api_key = self.key` or `token = get_token()` is left alone.
_ASSIGN = re.compile(
    r"(?i)\b(" + _NAME + r")(\s*[=:]\s*)"
    r"(\"[^\"\n]*\"|'[^'\n]*'|(?![A-Za-z_][\w.]*\s*[(.\[])[^\s\"',;(){}\[\]<>]+(?=[\s,;)}\]]|$))"
)

# "name": "value" in JSON.
_JSON_PAIR = re.compile(r"(?i)(\"" + _NAME + r"\"\s*:\s*)\"[^\"\n]*\"")


_IDENT = re.compile(r"[A-Za-z_]\w*")


def _is_secret_name(name: str) -> bool:
    low = name.lower()
    return any(word in low for word in _SECRET_WORDS)


def _mask_assign(m: re.Match) -> str:
    value = m.group(3)
    # Keep quotes so the line still parses the same way.
    if value[:1] in "\"'" and len(value) >= 2:
        return m.group(1) + m.group(2) + value[0] + MASK + value[0]
    if value in ("True", "False", "None", "null", "true", "false", MASK):
        return m.group(0)
    # Short numbers are counts and limits (`max_tokens=4096`), not secrets.
    if value.isdigit() and len(value) < 10:
        return m.group(0)
    # In code (lower/mixed-case names) a bare short identifier is a variable or a
    # type hint (`token: str`, `key = default_key`), not a secret. Env-style
    # UPPER names keep the strict rule: any bare value is masked.
    if not m.group(1).isupper() and _IDENT.fullmatch(value) \
            and not (len(value) >= 16 and any(c.isdigit() for c in value)):
        return m.group(0)
    return m.group(1) + m.group(2) + MASK


def scrub(text: str) -> str:
    """Return `text` with secrets replaced by ***."""
    if not text:
        return text
    for pattern in _TOKEN_PATTERNS:
        text = pattern.sub(MASK, text)
    text = _BEARER.sub(lambda m: m.group(1) + MASK, text)
    text = _JSON_PAIR.sub(lambda m: m.group(1) + '"' + MASK + '"', text)
    text = _ASSIGN.sub(_mask_assign, text)
    return text


def scrub_obj(obj):
    """Scrub every string inside dicts/lists/tuples; blank values under secret-looking keys.

    Returns a new object; the input is not changed.
    """
    if isinstance(obj, str):
        return scrub(obj)
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            # Only strings are blanked: numbers under such keys are counts
            # (`prompt_tokens`), and nested dicts/lists are walked instead.
            if isinstance(key, str) and _is_secret_name(key) and isinstance(value, str) and value:
                out[key] = MASK
            else:
                out[key] = scrub_obj(value)
        return out
    if isinstance(obj, list):
        return [scrub_obj(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(scrub_obj(v) for v in obj)
    return obj
