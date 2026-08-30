#!/usr/bin/env python3
"""Redaction helpers for factory logs and SDK transcripts (TASK-011).

Public repo + public dashboard: transcripts and journal lines must never leak
tokens, env secret values, or Slack user IDs.
"""
from __future__ import annotations

import os
import re
from typing import Any

# Known credential shapes. Order matters: URL userinfo first.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"x-access-token:[^@\s]+@"), "x-access-token:[REDACTED]@"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{8,}"), "[REDACTED-SLACK-TOKEN]"),
    (re.compile(r"\bxapp-[A-Za-z0-9-]{8,}"), "[REDACTED-SLACK-TOKEN]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"), "[REDACTED-GITHUB-TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b"), "[REDACTED-GITHUB-TOKEN]"),
    (re.compile(r"\bcursor_[A-Za-z0-9]{16,}\b"), "[REDACTED-CURSOR-KEY]"),
    (re.compile(r"\bhv[sbr]\.[A-Za-z0-9_-]{16,}\b"), "[REDACTED-VAULT-TOKEN]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "[REDACTED-JWT]"),
    (re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1[REDACTED]"),
    # Slack user/workspace IDs (never publish operator identifiers).
    (re.compile(r"\b[UW][A-Z0-9]{8,}\b"), "[SLACK-USER]"),
]

_SENSITIVE_ENV_RE = re.compile(r"(TOKEN|SECRET|KEY|PASSWORD|PASSWD)", re.IGNORECASE)


def _sensitive_env_values() -> list[str]:
    vals = []
    for name, value in os.environ.items():
        if _SENSITIVE_ENV_RE.search(name) and value and len(value) >= 8:
            vals.append(value)
    # Longest first so substrings don't leave residue.
    return sorted(vals, key=len, reverse=True)


def redact_text(text: str) -> str:
    if not text:
        return text
    for value in _sensitive_env_values():
        if value in text:
            text = text.replace(value, "[REDACTED-ENV]")
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


def redact_obj(obj: Any, max_str: int = 8000) -> Any:
    """Recursively redact strings inside JSON-serializable structures."""
    if isinstance(obj, str):
        out = redact_text(obj)
        if len(out) > max_str:
            out = out[:max_str] + f"… [truncated {len(out) - max_str} chars]"
        return out
    if isinstance(obj, dict):
        return {str(k): redact_obj(v, max_str) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v, max_str) for v in obj]
    return obj
