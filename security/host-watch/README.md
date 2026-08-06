# host-watch

Periodic host security scanner for Linux workstations. It looks for suspicious
processes, unexpected network listeners, and unfamiliar remote peers, then
pushes alerts via [ntfy](https://ntfy.sh).

Designed for a remote-dev box (Cursor / Claude Code / Docker / Node) where
noise from IDEs and language tooling is filtered with allowlists.

## What it checks

| Check | Alert when |
| --- | --- |
| Deleted executables | `/proc/PID/exe` points at a deleted binary |
| Forbidden paths | Process running from `/tmp`, `/var/tmp`, `/dev/shm` |
| Suspicious cmdline | Regex hits (`xmrig`, `curl\|sh`, `nc -e`, …) |
| Unknown high CPU/RAM | Non-allowlisted process above thresholds for N consecutive scans |
| Listeners | Non-localhost bind on ports outside the allowlist |
| Remote peers | Established peers whose IP/org is not allowlisted |

Findings are de-duplicated in `~/.local/state/host-watch/state.json` so you only
get notified the **first** time something appears.

## Quick start

```bash
# From homelab-forge (preferred):
./security/scripts/install-host-watch.sh

# Or directly:
cd security/host-watch
./scripts/install.sh
```

Then:

1. Edit `~/.config/host-watch/config.toml` and set a private ntfy topic:

   ```toml
   [notify]
   url = "https://ntfy.sh/your-long-random-topic"
   ```

2. Install the [ntfy app](https://ntfy.sh) on your phone and subscribe to that topic.

3. Dry-run once:

   ```bash
   ~/.local/share/host-watch/venv/bin/python -m host_watch --dry-run -v
   ```

4. Trigger a real run:

   ```bash
   systemctl --user start host-watch.service
   journalctl --user -u host-watch.service -n 50
   ```

The timer runs every **10 minutes** (see `systemd/host-watch.timer`).

### Linger (recommended)

So scans keep running without an active SSH/login session:

```bash
sudo loginctl enable-linger $USER
```

## Manual usage

```bash
python -m host_watch                 # scan + notify
python -m host_watch --dry-run -v    # no push, verbose
python -m host_watch --json          # machine-readable
python -m host_watch --no-notify     # update state only
```

Exit code `1` means there were **new** findings (useful for hooks).

## Config

| File | Purpose |
| --- | --- |
| `~/.config/host-watch/config.toml` | thresholds, ntfy URL, logging |
| `~/.config/host-watch/allowlists.toml` | process / binary / peer / listener allowlists |
| `~/.local/state/host-watch/state.json` | prior findings + ipinfo cache |

Examples live in `config/`. After install, customize allowlists for your machine
(home path prefixes are rewritten to `$HOME` automatically).

### Tuning tips

- Remove `5050` from `listeners.allow_ports` if pgAdmin is gone.
- Add org substrings under `[peers].allow_org_substrings` when a legitimate
  SaaS shows up once (check the alert detail / ipinfo org).
- Raise `cpu_percent_threshold` / `cpu_consecutive` if builds keep alerting.

## Uninstall

```bash
./scripts/uninstall.sh
# optional:
# rm -rf ~/.local/share/host-watch ~/.config/host-watch ~/.local/state/host-watch
```

## Security notes

- This is a **heuristic** watcher, not an EDR. It will miss sophisticated malware
  and can false-positive on new tools you install.
- Prefer a **private/random ntfy topic** (or a self-hosted ntfy with auth).
- Keep SSH hardened (`PasswordAuthentication no`, `AllowUsers`) — this scanner
  complements that; it does not replace it.
- Peer org lookups call `https://ipinfo.io/<ip>/json` (cached 24h). Disable with
  `resolve_peer_orgs = false` if you want fully offline scans (peer checks then
  only use CIDR allowlists).

## Layout

```
host-watch/
  host_watch/           # Python package (stdlib only)
  config/               # example config + allowlists
  systemd/              # user service + timer
  scripts/install.sh
  scripts/uninstall.sh
```
