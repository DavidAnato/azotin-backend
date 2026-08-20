"""Sanitizer des textes AI : tirets longs -> tirets simples."""

from __future__ import annotations

import re

LONG_DASH_CHARS = "\u2014\u2013\u2015\u2212"
_SPACED_LONG_DASH = re.compile(rf"\s*[{LONG_DASH_CHARS}]\s*")


def sanitize_ai_text(text: str) -> str:
    if not text or not isinstance(text, str):
        return text

    def _repl(match: re.Match[str]) -> str:
        raw = match.group(0)
        if raw.startswith(" ") or raw.endswith(" "):
            return " - "
        return "-"

    return _SPACED_LONG_DASH.sub(_repl, text)
