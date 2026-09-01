# Cursor My Machines Worker systemd Setup

This document describes how to set up the Cursor My Machines worker as a systemd
user service for automatic startup on boot.

## Overview

The systemd service ensures the Cursor worker:

- Starts automatically when the host boots
- Restarts automatically if it crashes
- Logs output to systemd journal
- Runs as the `diestrin` user (no root required)

## Installation

### 1. Copy Service File

```bash
# From the homelab-forge repository root
cp systemd/cursor-my-machines-worker.service ~/.config/systemd/user/
```

### 2. Configure Linger (Enable User Services at Boot)

User systemd services only run when the user is logged in by default. Enable
"linger" to start services at boot:

```bash
loginctl enable-linger diestrin
```

Verify linger is enabled:

```bash
loginctl show-user diestrin | grep Linger
# Should output: Linger=yes
```

### 3. Reload systemd and Enable Service

```bash
systemctl --user daemon-reload
systemctl --user enable cursor-my-machines-worker.service
```

### 4. Start the Service

```bash
systemctl --user start cursor-my-machines-worker.service
```

## Management

### Check Status

```bash
systemctl --user status cursor-my-machines-worker.service
```

### View Logs

```bash
# Follow live logs
journalctl --user -u cursor-my-machines-worker.service -f

# View recent logs
journalctl --user -u cursor-my-machines-worker.service -n 100

# View logs since last boot
journalctl --user -u cursor-my-machines-worker.service -b
```

### Stop Service

```bash
systemctl --user stop cursor-my-machines-worker.service
```

### Restart Service

```bash
systemctl --user restart cursor-my-machines-worker.service
```

### Disable Autostart

```bash
systemctl --user disable cursor-my-machines-worker.service
```

## Configuration

The service file is located at:

```text
~/.config/systemd/user/cursor-my-machines-worker.service
```

### Key Configuration Points

**Working Directory:**

```ini
WorkingDirectory=/media/diestrin/data/Projects/homelab-forge
```

The worker runs from the homelab-forge repository root.

**Executable Path:**

```ini
ExecStart=/home/diestrin/.local/bin/agent worker --name "localpower-forge" start
```

Assumes Cursor CLI is installed at `~/.local/bin/agent`. Adjust if installed elsewhere.

**Worker Name:**

```ini
--name "localpower-forge"
```

This name appears in the Cursor UI when selecting a machine. Change to a different
name if desired.

**Environment:**

```ini
Environment="PATH=/home/diestrin/.nix-profile/bin:/home/diestrin/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="HOME=/home/diestrin"
```

Includes Nix profile in PATH so worker can access Nix-installed tools (gh, kubectl, vault).

**Security Hardening:**

```ini
PrivateTmp=yes
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/media/diestrin/data/Projects/homelab-forge
```

- `PrivateTmp`: Isolated `/tmp` for the service
- `NoNewPrivileges`: Prevents privilege escalation
- `ProtectSystem=strict`: Read-only system directories
- `ProtectHome=read-only`: Read-only home, except working directory
- `ReadWritePaths`: Allows writes to homelab-forge repository only

## Troubleshooting

### Service Fails to Start

Check logs for errors:

```bash
journalctl --user -u cursor-my-machines-worker.service -n 50
```

Common issues:

**Cursor CLI not found:**

```text
Failed to execute command: No such file or directory
```

Solution: Verify Cursor CLI is installed:

```bash
which agent
# Should output: /home/diestrin/.local/bin/agent
```

If installed elsewhere, update `ExecStart` in the service file.

**Working directory doesn't exist:**

```text
Failed to change to directory: No such file or directory
```

Solution: Update `WorkingDirectory` to the correct path.

**Authentication issues:**

```text
Error: Not authenticated
```

Solution: Authenticate Cursor CLI before enabling the service:

```bash
agent login
```

### Worker Not Connecting

Check if the service is running:

```bash
systemctl --user is-active cursor-my-machines-worker.service
```

Check network connectivity:

```bash
# Worker needs outbound HTTPS access
curl -I https://api.cursor.com
```

View detailed logs:

```bash
journalctl --user -u cursor-my-machines-worker.service -f
```

### Linger Not Working

Verify linger is enabled:

```bash
loginctl show-user diestrin | grep Linger
```

If `Linger=no`, enable it:

```bash
sudo loginctl enable-linger diestrin
```

Check if user services are running after reboot:

```bash
systemctl --user status
```

### Service Crashes Repeatedly

Check logs for crash details:

```bash
journalctl --user -u cursor-my-machines-worker.service -n 200
```

The service has `Restart=always` with `RestartSec=10`, so it will retry every 10
seconds. If crashes persist, investigate the root cause before re-enabling.

## Migration from Old Factory Services

If migrating from the custom factory pipeline (ADR-009/010/011), stop and disable
the old services:

```bash
systemctl --user stop forge-factory-worker.service
systemctl --user stop forge-factory-orchestrator.service
systemctl --user disable forge-factory-worker.service
systemctl --user disable forge-factory-orchestrator.service
```

Then install and start the new Cursor worker service as described above.

## Verification

After installation, verify the worker is:

1. **Running:**

   ```bash
   systemctl --user status cursor-my-machines-worker.service
   # Should show: Active: active (running)
   ```

2. **Connected to Cursor:**

   Check logs for connection confirmation:

   ```bash
   journalctl --user -u cursor-my-machines-worker.service -n 20
   ```

   Look for messages like "Connected" or "Worker registered".

3. **Visible in Cursor UI:**

   - Open cursor.com/agents
   - Navigate to Settings → My Machines
   - Verify "localpower-forge" appears in the list

4. **Responsive to requests:**

   Test with a Slack message:

   ```text
   @Cursor help
   ```

   Cursor should route the request to your worker and respond.

## Post-Installation

After successful installation and verification:

1. Update `/workspace/docs/runbooks/cursor-my-machines-migration.md` Phase 3
   to reference this runbook for the systemd setup step.

2. Add to host operations checklist in `/workspace/docs/runbooks/operations.md`:

   ```markdown
   - [ ] Verify Cursor worker: `systemctl --user status cursor-my-machines-worker.service`
   ```

3. Test reboot behavior:

   ```bash
   sudo reboot
   ```

   After reboot, verify worker auto-started:

   ```bash
   systemctl --user status cursor-my-machines-worker.service
   ```

## Related

- [Cursor My Machines Migration Runbook](./cursor-my-machines-migration.md)
- [Cursor My Machines Documentation](https://cursor.com/docs/cloud-agent/bring-your-own-machine/my-machines)
- [ADR-012: Cursor My Machines](../decisions/ADR-012-cursor-my-machines.md)
