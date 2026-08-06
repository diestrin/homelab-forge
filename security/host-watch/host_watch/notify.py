from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import NotifyConfig

log = logging.getLogger(__name__)


@dataclass
class NotificationResult:
    sent: bool
    detail: str


def notify_ntfy(
    cfg: NotifyConfig,
    *,
    title: str,
    body: str,
    tags: list[str] | None = None,
    dry_run: bool = False,
) -> NotificationResult:
    if not cfg.url:
        return NotificationResult(False, "notify.url is empty; skipping push")

    if dry_run:
        log.info("[dry-run] would notify %s\n%s\n%s", cfg.url, title, body)
        return NotificationResult(False, "dry-run")

    data = body.encode("utf-8")
    req = urllib.request.Request(cfg.url, data=data, method="POST")
    req.add_header("Title", f"{cfg.title_prefix}: {title}"[:250])
    req.add_header("Priority", cfg.priority)
    if tags:
        req.add_header("Tags", ",".join(tags))
    if cfg.authorization:
        req.add_header("Authorization", cfg.authorization)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
            return NotificationResult(True, payload or f"HTTP {resp.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        log.error("ntfy HTTP %s: %s", exc.code, detail)
        return NotificationResult(False, f"HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        log.error("ntfy request failed: %s", exc)
        return NotificationResult(False, str(exc.reason))


def lookup_ipinfo(ip: str, cache: dict, cache_seconds: int) -> dict:
    """Return {org, hostname, ...} for an IP, with simple JSON cache."""
    import time

    now = time.time()
    cached = cache.get(ip)
    if cached and now - float(cached.get("ts", 0)) < cache_seconds:
        return cached.get("data", {})

    url = f"https://ipinfo.io/{ip}/json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "host-watch/0.1"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — network best-effort
        log.debug("ipinfo lookup failed for %s: %s", ip, exc)
        data = {}

    cache[ip] = {"ts": now, "data": data}
    return data
