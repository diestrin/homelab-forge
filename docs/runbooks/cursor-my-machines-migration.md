# Cursor My Machines Migration Runbook

This runbook documents the migration from the custom factory orchestration pipeline
to Cursor's native My Machines feature (ADR-012).

**Operator:** Diego  
**Host:** localpower  
**Date:** 2026-09-01  
**Status:** In progress

## Prerequisites

- [ ] Ubuntu 24.04 host with Nix + Home Manager installed (✓ already present)
- [ ] k3s cluster running with Vault, Argo CD deployed
- [ ] homelab-forge repository checked out at `/media/diestrin/data/Projects/homelab-forge`
- [ ] Cursor account with access to My Machines feature
- [ ] Admin access to Slack workspace for Cursor app installation

## Phase 1: Setup My Machines (Non-Disruptive)

### 1.1 Install Cursor CLI

```bash
# Install Cursor CLI
curl -fsSL https://cursor.sh/install.sh | sh

# Verify installation
agent --version
```

Expected: Cursor CLI version info displayed.

### 1.2 Authenticate with Cursor

```bash
# Login via browser (will open browser for OAuth)
agent login

# OR use API key if headless
# Get API key from: https://cursor.com/settings/api-keys
agent worker --api-key "$CURSOR_API_KEY" start --help
```

Expected: Authentication success message.

### 1.3 Test Worker in Dry-Run Mode

```bash
# Create test directory
mkdir -p ~/cursor-test
cd ~/cursor-test
git init

# Start worker (will run in foreground for testing)
agent worker --name "localpower-test" start
```

Expected: Worker connects to Cursor backend, shows "Connected" status.
Press Ctrl+C to stop after verifying connectivity.

### 1.4 Configure MCP Servers

Create `.cursor/mcp.json` in homelab-forge repository:

```json
{
  "mcpServers": {
    "vault-local": {
      "command": "/path/to/vault-mcp-server",
      "args": ["--vault-addr", "http://127.0.0.1:8200"],
      "env": {
        "VAULT_TOKEN": "s.from-approle-or-token-file"
      }
    }
  }
}
```

**Note:** Vault MCP server implementation is placeholder; needs actual implementation
or use existing Vault HTTP API directly via Cursor SDK.

### 1.5 Create Environment Configuration

Already created: `.cursor/environment.json` defines Nix-based setup.

Verify it works:

```bash
cd /media/diestrin/data/Projects/homelab-forge

# Cursor CLI can validate environment locally
# (This is conceptual; actual validation happens when worker starts)
```

## Phase 2: Enable Cursor Slack Integration

### 2.1 Install Cursor Slack App

1. Visit Slack App Directory or Cursor Dashboard
2. Search for "Cursor" app
3. Click "Add to Slack"
4. Select your workspace
5. Authorize requested permissions:
   - Read channel messages where @Cursor is mentioned
   - Post messages
   - Read user profiles
   - Upload files

### 2.2 Configure Workspace

In Cursor Dashboard (cursor.com/agents):

1. Navigate to Settings → Integrations
2. Select Slack workspace
3. Configure default repository: homelab-forge
4. Set default agent settings:
   - Execution environment: My Machines
   - Machine: localpower-forge (will be available after Phase 3)

### 2.3 Test Integration

From Slack:

```
@Cursor help
```

Expected: Cursor bot responds with help text.

**Do not request actual code changes yet** — worker not running on homelab-forge yet.

## Phase 3: Cutover to My Machines (Disruptive)

### 3.1 Pre-Cutover Checklist

- [ ] Backup current task state (optional, per operator decision to retire Postgres)
- [ ] Verify no critical in-flight tasks in factory worker queue
- [ ] Confirm k3s cluster is healthy (`kubectl get pods -A`)
- [ ] Verify Vault is unsealed and accessible

### 3.2 Stop Custom Factory Services

```bash
# Check current status
systemctl --user status forge-factory-worker.service
systemctl --user status forge-factory-orchestrator.service

# Stop services
systemctl --user stop forge-factory-worker.service
systemctl --user stop forge-factory-orchestrator.service

# Disable auto-start
systemctl --user disable forge-factory-worker.service
systemctl --user disable forge-factory-orchestrator.service

# Verify stopped
systemctl --user status forge-factory-worker.service
systemctl --user status forge-factory-orchestrator.service
```

Expected: Both services stopped and disabled.

### 3.3 Archive Factory Data (Optional)

```bash
# Export task YAML (already in git)
cd /media/diestrin/data/Projects/homelab-forge
git log --oneline factory/tasks/

# Postgres backup (if desired for historical reference)
# Note: Per operator decision, this is being retired without migration
kubectl -n forge-system exec -it postgres-0 -- \
  pg_dump -U forge forge > /tmp/factory-postgres-backup-$(date +%Y%m%d).sql
```

### 3.4 Start My Machines Worker on homelab-forge

```bash
# Navigate to repository
cd /media/diestrin/data/Projects/homelab-forge

# Start worker (foreground for initial verification)
agent worker --name "localpower-forge" start
```

Expected: Worker connects, shows homelab-forge repository registered.

Press Ctrl+C after verifying, then start as background service:

```bash
# Start in background (or use tmux/screen)
nohup agent worker --name "localpower-forge" start > ~/cursor-worker.log 2>&1 &

# Verify running
ps aux | grep 'agent worker'
tail -f ~/cursor-worker.log
```

### 3.5 Create systemd Unit for Worker (Optional)

For auto-restart on host reboot:

```bash
mkdir -p ~/.config/systemd/user
```

Create `~/.config/systemd/user/cursor-my-machines-worker.service`:

```ini
[Unit]
Description=Cursor My Machines Worker (homelab-forge)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/media/diestrin/data/Projects/homelab-forge
ExecStart=/home/diestrin/.local/bin/agent worker --name "localpower-forge" start
Restart=always
RestartSec=10
Environment="PATH=/home/diestrin/.nix-profile/bin:/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=default.target
```

Enable and start:

```bash
systemctl --user daemon-reload
systemctl --user enable cursor-my-machines-worker.service
systemctl --user start cursor-my-machines-worker.service
systemctl --user status cursor-my-machines-worker.service
```

### 3.6 Test End-to-End Flow

From Slack:

```
@Cursor create a simple test file in homelab-forge with today's date
```

Expected:
1. Cursor routes request to localpower-forge worker
2. Agent creates file, commits, pushes branch
3. Agent opens PR
4. Slack thread shows progress and PR link

Verify:
- PR appears on GitHub
- File exists in repository
- Agent transcript visible in Cursor dashboard

## Phase 4: Cleanup and Documentation

### 4.1 Retire forge-site Control Plane (If Deployed)

Check if forge-site is deployed:

```bash
kubectl -n forge-system get deployment forge-site
```

If deployed, remove via GitOps:

```bash
cd /media/diestrin/data/Projects/homelab-forge
git checkout -b retire-forge-site

# Remove forge-site manifests
rm -rf k8s/apps/forge-site/

# Commit and open PR
git add -A
git commit -m "chore: retire forge-site control plane per ADR-012"
git push -u origin retire-forge-site
gh pr create --title "Retire forge-site control plane" --body "Per ADR-012 migration to Cursor My Machines"

# After PR merged and Argo syncs, verify removal
kubectl -n forge-system get deployment forge-site
# Should show: Error from server (NotFound)
```

### 4.2 Archive Postgres PVC (Optional)

```bash
# List PVCs
kubectl -n forge-system get pvc

# If Postgres PVC exists and needs archival:
# 1. Take final backup (see 3.3)
# 2. Delete PVC via GitOps after forge-site removed
```

### 4.3 Update Documentation

- [x] Create ADR-012 documenting migration
- [ ] Update `docs/current-state.md` with new architecture
- [ ] Update `operations.md` with My Machines worker lifecycle
- [ ] Update `PLAN.md` to reflect factory retirement
- [ ] Mark ADR-009, ADR-010, ADR-011 as superseded

### 4.4 Create GitHub Issue Management Workflow

Create issue templates:

`.github/ISSUE_TEMPLATE/task.md`:

```markdown
---
name: Task
about: Agent-driven development task
labels: task, needs-triage
---

## Goal

[Clear, one-sentence goal]

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Context

[Additional background, links, decisions]

## Risk Level

- [ ] Low (docs, comments, safe refactors)
- [ ] Medium (feature work, dependencies)
- [ ] High (host config, secrets, ingress)
```

Create labels:

```bash
gh label create task --description "Agent-driven task" --color 0E8A16
gh label create risk:low --color C5DEF5
gh label create risk:medium --color FFA500
gh label create risk:high --color D93F0B
gh label create needs-triage --color FBCA04
gh label create in-progress --color 1D76DB
gh label create review --color 8B4789
```

### 4.5 Create Cursor Skills for homelab-forge

Create `.cursor/skills/homelab-task/SKILL.md`:

```markdown
---
name: homelab-task
description: Create and manage homelab-forge tasks as GitHub Issues
---

# Homelab Task Management

When the user requests new work, create a GitHub Issue following this template:

## Title Format

`[Component] Brief description`

Examples:
- `[k8s] Add Redis deployment`
- `[docs] Update My Machines migration runbook`
- `[security] Rotate Vault AppRole tokens`

## Issue Body

Include:
1. **Goal:** One-sentence objective
2. **Acceptance Criteria:** Checklist of measurable outcomes
3. **Risk Level:** Low/Medium/High with justification
4. **Context:** Links to ADRs, runbooks, prior issues

## Labels

- `task` (always)
- `risk:low` / `risk:medium` / `risk:high`
- Component labels: `k8s`, `docs`, `security`, etc.

## Workflow

1. Create issue with `needs-triage` label
2. Operator reviews and removes `needs-triage`
3. Agent self-assigns when starting work (add `in-progress`)
4. Agent opens PR and links to issue
5. When PR ready, remove `in-progress` and add `review`
6. After merge, close issue with "Completed in #PR"
```

## Phase 5: Verify Steady State

### 5.1 Worker Health Check

```bash
# Check worker process
systemctl --user status cursor-my-machines-worker.service

# Check worker logs
journalctl --user -u cursor-my-machines-worker.service -f
```

### 5.2 Request Test Change via Mobile

1. Open Cursor mobile app
2. Select homelab-forge repository
3. Request: "Update CHANGELOG.md with ADR-012 migration"
4. Verify PR created and linked in app

### 5.3 Verify GitOps Still Works

```bash
# Make a k8s change via PR
# After merge to main, verify Argo syncs
kubectl -n forge-system get applications
argocd app get forge-demo  # Should show Synced status
```

## Rollback Procedure

If My Machines doesn't meet needs (within 30-day window):

1. Stop worker:
   ```bash
   systemctl --user stop cursor-my-machines-worker.service
   ```

2. Restore forge-site control plane:
   ```bash
   git checkout factory/task-008-db-backed-factory-control-plane
   kubectl apply -k k8s/apps/forge-site/
   ```

3. Restore Postgres (if backed up):
   ```bash
   kubectl -n forge-system exec -it postgres-0 -- \
     psql -U forge forge < /tmp/factory-postgres-backup-YYYYMMDD.sql
   ```

4. Restart factory services:
   ```bash
   systemctl --user start forge-factory-orchestrator.service
   systemctl --user start forge-factory-worker.service
   ```

## Success Criteria

- [x] Cursor CLI installed and authenticated
- [ ] Worker running on homelab-forge repository
- [ ] Cursor Slack integration tested
- [ ] End-to-end flow verified (Slack → PR)
- [ ] Custom factory services stopped and disabled
- [ ] Documentation updated
- [ ] GitHub Issue workflow established
- [ ] Worker running as systemd service (optional)

## Post-Migration

After 30 days of successful My Machines operation:

- Remove factory worker/orchestrator code from repository
- Archive factory-related ADRs in `docs/decisions/archive/`
- Remove Postgres deployment if no other apps depend on it
- Update README to reflect Cursor-native workflow
