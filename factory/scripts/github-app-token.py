#!/usr/bin/env python3
"""Mint a short-lived GitHub App installation access token.

Required for acting as the App (bot PRs/pushes), not a personal user.

GitHub requires an RS256 JWT signed with the App *private key*. The OAuth
client_secret cannot mint installation tokens; it may still be stored in Vault
for other App flows. JWT `iss` prefers client_id (current GitHub docs), else app_id.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    import jwt
except ImportError as e:  # pragma: no cover
    print("PyJWT required (python3-jwt / PyJWT)", file=sys.stderr)
    raise SystemExit(2) from e


API = "https://api.github.com"
API_VERSION = "2022-11-28"


def die(msg: str, code: int = 1) -> None:
    print(f"github-app-token: {msg}", file=sys.stderr)
    raise SystemExit(code)


def make_jwt(issuer: str, private_key: str) -> str:
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 9 * 60,
        "iss": issuer,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def api_request(method: str, url: str, bearer: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {bearer}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "homelab-forge-factory",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        die(f"HTTP {e.code} {url}: {detail}", 1)


def resolve_installation_id(app_jwt: str, explicit: str | None, owner: str, repo: str) -> str:
    if explicit:
        return explicit
    # Prefer repo installation lookup
    if owner and repo:
        data = api_request("GET", f"{API}/repos/{owner}/{repo}/installation", app_jwt)
        iid = str(data.get("id") or "")
        if iid:
            return iid
    data = api_request("GET", f"{API}/app/installations", app_jwt)
    if isinstance(data, list) and data:
        return str(data[0]["id"])
    die("could not resolve installation_id (install the App on the repo, or set installation_id)")


def mint(app_id: str, client_id: str, private_key: str, installation_id: str | None,
         owner: str, repo: str) -> str:
    # GitHub currently requires JWT iss to be the numeric App ID (integer-as-string).
    # client_id is still stored/validated for ops clarity; client_secret is unused here.
    issuer = (app_id or "").strip()
    if not issuer:
        die("app_id required (numeric App ID for JWT iss)")
    if not issuer.isdigit():
        die(f"app_id must be numeric for JWT iss, got {issuer!r}")
    if not private_key.strip():
        die("private_key (PEM) required — client_secret cannot mint installation tokens")
    app_jwt = make_jwt(issuer, private_key)
    iid = resolve_installation_id(app_jwt, installation_id, owner, repo)
    token_resp = api_request(
        "POST",
        f"{API}/app/installations/{iid}/access_tokens",
        app_jwt,
        body={},
    )
    token = token_resp.get("token")
    if not token:
        die(f"no token in response: {token_resp}")
    return token


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--app-id", default=os.environ.get("GITHUB_APP_ID", ""))
    p.add_argument("--client-id", default=os.environ.get("GITHUB_CLIENT_ID", ""))
    p.add_argument("--private-key-file", default=os.environ.get("GITHUB_PRIVATE_KEY_FILE", ""))
    p.add_argument("--installation-id", default=os.environ.get("GITHUB_INSTALLATION_ID", ""))
    p.add_argument("--owner", default=os.environ.get("GITHUB_OWNER", "diestrin"))
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPO", "homelab-forge"))
    p.add_argument(
        "--from-json",
        action="store_true",
        help="read JSON object from stdin with app_id, client_id, private_key, installation_id, …",
    )
    args = p.parse_args()

    private_key = ""
    app_id = args.app_id
    client_id = args.client_id
    installation_id = args.installation_id or None

    if args.from_json:
        payload = json.load(sys.stdin)
        app_id = str(payload.get("app_id") or app_id or "")
        client_id = str(payload.get("client_id") or client_id or "")
        private_key = str(payload.get("private_key") or "")
        if payload.get("installation_id"):
            installation_id = str(payload["installation_id"])
        # client_secret intentionally unused for installation tokens
    elif args.private_key_file:
        private_key = open(args.private_key_file, encoding="utf-8").read()
    else:
        private_key = os.environ.get("GITHUB_PRIVATE_KEY", "")

    token = mint(app_id, client_id, private_key, installation_id, args.owner, args.repo)
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
