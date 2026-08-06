from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_DIR = Path("~/.config/host-watch").expanduser()
DEFAULT_STATE_DIR = Path("~/.local/state/host-watch").expanduser()


def _expand(path: str | Path) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


@dataclass
class NotifyConfig:
    url: str = ""
    authorization: str = ""
    title_prefix: str = "host-watch"
    priority: str = "high"
    only_on_findings: bool = True


@dataclass
class ScanConfig:
    cpu_percent_threshold: float = 50.0
    rss_mib_threshold: float = 1024.0
    cpu_consecutive: int = 2
    resolve_peer_orgs: bool = True
    ipinfo_cache_seconds: int = 86400


@dataclass
class Allowlists:
    process_substrings: list[str] = field(default_factory=list)
    process_comms: list[str] = field(default_factory=list)
    binary_prefixes: list[str] = field(default_factory=list)
    suspicious_regexes: list[str] = field(default_factory=list)
    forbidden_exe_prefixes: list[str] = field(default_factory=list)
    allow_listener_ports: list[int] = field(default_factory=list)
    allow_org_substrings: list[str] = field(default_factory=list)
    allow_peers: list[str] = field(default_factory=list)
    ignore_local_ports: list[int] = field(default_factory=list)


@dataclass
class AppConfig:
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    scan: ScanConfig = field(default_factory=ScanConfig)
    allowlists: Allowlists = field(default_factory=Allowlists)
    state_dir: Path = field(default_factory=lambda: DEFAULT_STATE_DIR)
    log_level: str = "info"
    config_dir: Path = field(default_factory=lambda: DEFAULT_CONFIG_DIR)


def _section(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    return value if isinstance(value, dict) else {}


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_config(
    config_dir: Path | None = None,
    config_path: Path | None = None,
    allowlists_path: Path | None = None,
) -> AppConfig:
    config_dir = _expand(config_dir or DEFAULT_CONFIG_DIR)
    config_path = _expand(config_path or (config_dir / "config.toml"))
    allowlists_path = _expand(allowlists_path or (config_dir / "allowlists.toml"))

    cfg_data: dict[str, Any] = {}
    if config_path.exists():
        cfg_data = load_toml(config_path)

    allow_data: dict[str, Any] = {}
    if allowlists_path.exists():
        allow_data = load_toml(allowlists_path)

    notify_raw = _section(cfg_data, "notify")
    scan_raw = _section(cfg_data, "scan")
    paths_raw = _section(cfg_data, "paths")
    logging_raw = _section(cfg_data, "logging")

    processes = _section(allow_data, "processes")
    binaries = _section(allow_data, "binaries")
    suspicious = _section(allow_data, "suspicious")
    listeners = _section(allow_data, "listeners")
    peers = _section(allow_data, "peers")

    state_dir = _expand(paths_raw.get("state_dir", DEFAULT_STATE_DIR))

    return AppConfig(
        notify=NotifyConfig(
            url=str(notify_raw.get("url", "") or ""),
            authorization=str(notify_raw.get("authorization", "") or ""),
            title_prefix=str(notify_raw.get("title_prefix", "host-watch")),
            priority=str(notify_raw.get("priority", "high")),
            only_on_findings=bool(notify_raw.get("only_on_findings", True)),
        ),
        scan=ScanConfig(
            cpu_percent_threshold=float(scan_raw.get("cpu_percent_threshold", 50.0)),
            rss_mib_threshold=float(scan_raw.get("rss_mib_threshold", 1024.0)),
            cpu_consecutive=int(scan_raw.get("cpu_consecutive", 2)),
            resolve_peer_orgs=bool(scan_raw.get("resolve_peer_orgs", True)),
            ipinfo_cache_seconds=int(scan_raw.get("ipinfo_cache_seconds", 86400)),
        ),
        allowlists=Allowlists(
            process_substrings=[str(x) for x in processes.get("allow_substrings", [])],
            process_comms=[str(x) for x in processes.get("allow_comms", [])],
            binary_prefixes=[str(x) for x in binaries.get("allow_prefixes", [])],
            suspicious_regexes=[str(x) for x in suspicious.get("cmdline_regexes", [])],
            forbidden_exe_prefixes=[
                str(x) for x in suspicious.get("forbidden_exe_prefixes", [])
            ],
            allow_listener_ports=[int(x) for x in listeners.get("allow_ports", [])],
            allow_org_substrings=[str(x) for x in peers.get("allow_org_substrings", [])],
            allow_peers=[str(x) for x in peers.get("allow_peers", [])],
            ignore_local_ports=[int(x) for x in peers.get("ignore_local_ports", [22])],
        ),
        state_dir=state_dir,
        log_level=str(logging_raw.get("level", "info")).lower(),
        config_dir=config_dir,
    )
