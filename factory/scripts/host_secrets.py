#!/usr/bin/env python3
"""Best-effort Vault AppRole secrets for host factory jobs (ADR-007).

Mints GH_TOKEN (GitHub App installation token) and loads CURSOR_API_KEY into
the process env when missing. Never writes tokens to disk or git.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sdk_session import log  # noqa: E402


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def load_vault_secrets(task_id: str, need_cursor: bool = True) -> None:
    login = REPO_ROOT / "factory/scripts/vault-agent-login.sh"
    if not os.environ.get("VAULT_TOKEN") and login.is_file():
        tok = _run([str(login), "--print-token"])
        if tok.returncode == 0 and tok.stdout.strip():
            os.environ["VAULT_TOKEN"] = tok.stdout.strip()
            os.environ.setdefault("VAULT_ADDR", "http://127.0.0.1:8200")
    if not os.environ.get("GH_TOKEN"):
        mint = REPO_ROOT / "factory/scripts/github-app-token.sh"
        if mint.is_file():
            got = _run([str(mint)])
            if got.returncode == 0 and got.stdout.strip():
                os.environ["GH_TOKEN"] = got.stdout.strip()
                os.environ["GH_PROMPT_DISABLED"] = "1"
                log(task_id, "minted GitHub App installation token")
    if need_cursor and not os.environ.get("CURSOR_API_KEY"):
        fetch = REPO_ROOT / "factory/scripts/fetch-cursor-key.sh"
        if fetch.is_file():
            got = _run([str(fetch)])
            if got.returncode == 0 and got.stdout.strip():
                os.environ["CURSOR_API_KEY"] = got.stdout.strip()
                log(task_id, "loaded CURSOR_API_KEY from Vault")
