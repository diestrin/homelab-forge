from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .config import AppConfig
from .notify import lookup_ipinfo, notify_ntfy
from .state import StateStore

log = logging.getLogger(__name__)


@dataclass
class Finding:
    kind: str
    key: str
    summary: str
    detail: str = ""
    severity: str = "warning"  # info | warning | critical

    def fingerprint(self) -> str:
        return f"{self.kind}:{self.key}"


@dataclass
class ScanReport:
    findings: list[Finding] = field(default_factory=list)
    new_findings: list[Finding] = field(default_factory=list)
    scanned_at: float = field(default_factory=time.time)

    @property
    def ok(self) -> bool:
        return not self.new_findings


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _cmdline(pid: int) -> str:
    raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()


def _comm(pid: int) -> str:
    return _read_text(Path(f"/proc/{pid}/comm"))


def _exe(pid: int) -> tuple[str, bool]:
    """Return (exe_path, deleted)."""
    link = Path(f"/proc/{pid}/exe")
    try:
        target = os.readlink(link)
    except OSError:
        return "", False
    deleted = target.endswith(" (deleted)") or " (deleted)" in target
    return target.replace(" (deleted)", ""), deleted


def _status_field(pid: int, field_name: str) -> str:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith(field_name + ":"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def _rss_kib(pid: int) -> int:
    value = _status_field(pid, "VmRSS").split()
    try:
        return int(value[0])
    except (IndexError, ValueError):
        return 0


def _cpu_times(pid: int) -> float | None:
    try:
        parts = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
        # utime + stime
        return (int(parts[13]) + int(parts[14])) / os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    except (OSError, IndexError, ValueError, KeyError):
        return None


def _iter_pids() -> Iterable[int]:
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            yield int(entry.name)


def _is_allowed_process(comm: str, cmdline: str, allow: AppConfig) -> bool:
    hay = f"{comm} {cmdline}".lower()
    for item in allow.allowlists.process_comms:
        if comm.lower() == item.lower():
            return True
    for item in allow.allowlists.process_substrings:
        if item.lower() in hay:
            return True
    return False


def _is_allowed_binary(exe: str, allow: AppConfig) -> bool:
    if not exe:
        return True  # kernel threads / permission denied
    for prefix in allow.allowlists.binary_prefixes:
        if exe.startswith(os.path.expanduser(prefix)):
            return True
    return False


def check_processes(cfg: AppConfig, state: StateStore) -> list[Finding]:
    findings: list[Finding] = []
    compiled = [
        re.compile(pat, re.IGNORECASE) for pat in cfg.allowlists.suspicious_regexes
    ]
    cpu_active: set[str] = set()

    # Sample CPU over a short window
    sample_a: dict[int, float] = {}
    for pid in _iter_pids():
        t = _cpu_times(pid)
        if t is not None:
            sample_a[pid] = t
    time.sleep(1.0)
    ncpu = os.cpu_count() or 1

    for pid in _iter_pids():
        try:
            comm = _comm(pid)
            cmdline = _cmdline(pid)
            exe, deleted = _exe(pid)
        except OSError:
            continue

        if not comm and not cmdline:
            continue

        # Deleted executable still running
        if deleted and exe:
            findings.append(
                Finding(
                    kind="deleted_exe",
                    key=f"{pid}:{exe}",
                    summary=f"deleted binary still running: pid={pid} {exe}",
                    detail=cmdline[:300],
                    severity="critical",
                )
            )

        # Forbidden path
        for prefix in cfg.allowlists.forbidden_exe_prefixes:
            if exe.startswith(prefix):
                findings.append(
                    Finding(
                        kind="forbidden_path",
                        key=f"{pid}:{exe}",
                        summary=f"process running from {prefix}: pid={pid}",
                        detail=f"exe={exe} cmd={cmdline[:300]}",
                        severity="critical",
                    )
                )
                break

        # Suspicious cmdline
        for rx in compiled:
            if rx.search(cmdline):
                findings.append(
                    Finding(
                        kind="suspicious_cmdline",
                        key=f"{rx.pattern}:{pid}",
                        summary=f"suspicious cmdline matched /{rx.pattern}/ pid={pid}",
                        detail=cmdline[:400],
                        severity="critical",
                    )
                )
                break

        allowed = _is_allowed_process(comm, cmdline, cfg) and _is_allowed_binary(exe, cfg)

        # High CPU for unknown processes
        t0 = sample_a.get(pid)
        t1 = _cpu_times(pid)
        if t0 is not None and t1 is not None and t1 >= t0:
            cpu_pct = ((t1 - t0) / 1.0) * 100.0
            rss_mib = _rss_kib(pid) / 1024.0
            identity = f"{comm}|{exe}|{cmdline[:120]}"
            cpu_key = f"cpu:{identity}"
            if not allowed and (
                cpu_pct >= cfg.scan.cpu_percent_threshold
                or rss_mib >= cfg.scan.rss_mib_threshold
            ):
                cpu_active.add(cpu_key)
                hits = state.bump_cpu(cpu_key)
                if hits >= cfg.scan.cpu_consecutive:
                    findings.append(
                        Finding(
                            kind="resource_unknown",
                            key=cpu_key,
                            summary=(
                                f"unknown process high resource: pid={pid} "
                                f"cpu~{cpu_pct:.0f}% rss={rss_mib:.0f}MiB comm={comm}"
                            ),
                            detail=f"exe={exe} cmd={cmdline[:300]}",
                            severity="warning",
                        )
                    )
            elif allowed:
                state.clear_cpu(cpu_key)

        # Unknown process (informational only when also high-resource handled above;
        # we don't alert on every unknown idle process)
        if not allowed and not exe.startswith("/"):
            # skip kernel threads like [kworker]
            continue

    state.prune_cpu(cpu_active)
    return findings


def _parse_ss_listen() -> list[dict]:
    """Parse `ss -H -tulpn` into dicts."""
    try:
        out = subprocess.check_output(
            ["ss", "-H", "-tulpn"], text=True, stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        log.warning("ss listen failed: %s", exc)
        return []

    rows: list[dict] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        proto, _state, _rq, _sq, local = parts[:5]
        process = ""
        if "users:(" in line:
            process = line.split("users:(", 1)[1]
        host, port = _split_host_port(local)
        rows.append(
            {
                "proto": proto,
                "host": host,
                "port": port,
                "process": process[:200],
                "raw": line,
            }
        )
    return rows


def _split_host_port(local: str) -> tuple[str, int | None]:
    # Formats: 0.0.0.0:22, [::]:22, 127.0.0.53%lo:53, *:4500
    if local.startswith("["):
        # [addr]:port or [addr%zone]:port
        try:
            host_part, port_s = local.rsplit("]:", 1)
            host = host_part[1:]
            return host.split("%", 1)[0], int(port_s)
        except ValueError:
            return local, None
    if ":" not in local:
        return local, None
    host, port_s = local.rsplit(":", 1)
    host = host.split("%", 1)[0]
    try:
        return host, int(port_s)
    except ValueError:
        return host, None


def _is_localhost(host: str) -> bool:
    h = host.strip("[]").lower()
    return h in {"127.0.0.1", "::1", "localhost"} or h.startswith("127.")


def check_listeners(cfg: AppConfig) -> list[Finding]:
    findings: list[Finding] = []
    allowed = set(cfg.allowlists.allow_listener_ports)
    for row in _parse_ss_listen():
        host = row["host"]
        port = row["port"]
        if port is None or _is_localhost(host):
            continue
        # Wildcard / all-interfaces
        if host not in {"*", "0.0.0.0", "::", "::0"} and not host.startswith("fe80:"):
            # Bound to a specific NIC IP — still public-ish; treat as non-local
            pass
        if port in allowed:
            continue
        findings.append(
            Finding(
                kind="listener",
                key=f"{row['proto']}:{host}:{port}",
                summary=f"unexpected listener {row['proto']} {host}:{port}",
                detail=row["raw"][:300],
                severity="warning",
            )
        )
    return findings


def _parse_ss_established() -> list[dict]:
    try:
        out = subprocess.check_output(
            ["ss", "-H", "-tpn", "state", "established"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        log.warning("ss established failed: %s", exc)
        return []

    rows: list[dict] = []
    for line in out.splitlines():
        # ss -tpn established: Recv-Q Send-Q Local Peer [users:(...)]
        parts = line.split()
        if len(parts) < 4:
            continue
        local, peer = parts[2], parts[3]
        if peer.startswith("users:("):
            continue
        lhost, lport = _split_host_port(local)
        phost, pport = _split_host_port(peer)
        if not phost or pport is None:
            continue
        proc = ""
        if "users:(" in line:
            m = re.search(r'users:\(\("([^"]+)"', line)
            proc = m.group(1) if m else ""
        rows.append(
            {
                "local_host": lhost,
                "local_port": lport,
                "peer_host": phost,
                "peer_port": pport,
                "process": proc,
                "raw": line,
            }
        )
    return rows


def _peer_allowed(ip: str, cfg: AppConfig) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for item in cfg.allowlists.allow_peers:
        try:
            if "/" in item:
                if addr in ipaddress.ip_network(item, strict=False):
                    return True
            else:
                if addr == ipaddress.ip_address(item):
                    return True
        except ValueError:
            continue
    return False


def _org_allowed(org: str, cfg: AppConfig) -> bool:
    if not org:
        return False
    low = org.lower()
    return any(s.lower() in low for s in cfg.allowlists.allow_org_substrings)


def check_peers(cfg: AppConfig, state: StateStore) -> list[Finding]:
    findings: list[Finding] = []
    ignore_ports = set(cfg.allowlists.ignore_local_ports)
    seen: set[str] = set()

    for row in _parse_ss_established():
        peer = (row["peer_host"] or "").strip("[]")
        lport = row["local_port"]
        if not peer or _is_localhost(peer):
            continue
        if lport in ignore_ports:
            continue
        if peer in seen:
            continue
        seen.add(peer)

        if _peer_allowed(peer, cfg):
            continue

        org = ""
        hostname = ""
        if cfg.scan.resolve_peer_orgs:
            info = lookup_ipinfo(peer, state.ipinfo_cache, cfg.scan.ipinfo_cache_seconds)
            org = str(info.get("org") or "")
            hostname = str(info.get("hostname") or "")
            if _org_allowed(org, cfg):
                continue

        findings.append(
            Finding(
                kind="peer",
                key=f"{peer}:{org or hostname or 'unknown'}",
                summary=f"unexpected remote peer {peer}"
                + (f" ({org})" if org else ""),
                detail=(
                    f"process={row['process']} local_port={lport} "
                    f"peer_port={row['peer_port']} host={hostname}"
                ),
                severity="warning",
            )
        )
    return findings


def run_scan(cfg: AppConfig, *, dry_run: bool = False, notify: bool = True) -> ScanReport:
    state = StateStore(cfg.state_dir)
    findings: list[Finding] = []
    findings.extend(check_processes(cfg, state))
    findings.extend(check_listeners(cfg))
    findings.extend(check_peers(cfg, state))

    active_keys = {f.fingerprint() for f in findings}
    new_findings: list[Finding] = []
    for finding in findings:
        is_new = state.mark_finding(
            finding.fingerprint(),
            {
                "kind": finding.kind,
                "summary": finding.summary,
                "detail": finding.detail,
                "severity": finding.severity,
            },
        )
        if is_new:
            new_findings.append(finding)

    state.prune_missing(active_keys)
    state.save()

    report = ScanReport(findings=findings, new_findings=new_findings)

    if notify and (new_findings or not cfg.notify.only_on_findings):
        if new_findings:
            body_lines = [
                f"[{f.severity}] {f.summary}"
                + (f"\n  {f.detail}" if f.detail else "")
                for f in new_findings
            ]
            host = socket.gethostname()
            body = f"host={host}\n" + "\n".join(body_lines)
            title = f"{len(new_findings)} new finding(s)"
            tags = ["warning", "host-watch"]
            if any(f.severity == "critical" for f in new_findings):
                tags = ["rotating_light", "host-watch"]
            result = notify_ntfy(
                cfg.notify,
                title=title,
                body=body,
                tags=tags,
                dry_run=dry_run,
            )
            log.info("notify: sent=%s detail=%s", result.sent, result.detail[:200])
        elif not cfg.notify.only_on_findings:
            notify_ntfy(
                cfg.notify,
                title="scan clean",
                body=f"host={socket.gethostname()} findings=0",
                tags=["white_check_mark", "host-watch"],
                dry_run=dry_run,
            )

    return report


def format_report(report: ScanReport) -> str:
    lines = [
        f"scanned_at={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(report.scanned_at))}",
        f"findings={len(report.findings)} new={len(report.new_findings)}",
    ]
    for f in report.findings:
        marker = "NEW" if f in report.new_findings else "seen"
        lines.append(f"[{marker}][{f.severity}] {f.kind}: {f.summary}")
        if f.detail:
            lines.append(f"         {f.detail}")
    if not report.findings:
        lines.append("ok: no findings")
    return "\n".join(lines)


def report_as_dict(report: ScanReport) -> dict:
    return {
        "scanned_at": report.scanned_at,
        "findings": [asdict(f) for f in report.findings],
        "new_findings": [asdict(f) for f in report.new_findings],
    }
