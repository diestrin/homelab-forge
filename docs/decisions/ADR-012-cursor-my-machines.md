# ADR-012: Migrate to Cursor My Machines

## Status

Accepted (2026-09-01) — supersedes the custom factory orchestration pipeline (ADR-009, ADR-010, ADR-011).

## Context

The homelab-forge factory was built with a custom orchestration pipeline to enable
away-from-keyboard task planning and implementation:

- Slack Socket Mode intake client on host
- forge-site Next.js backend as control plane (Postgres + pg-boss job queue)
- Host worker daemon running Cursor SDK agents in isolated git worktrees
- Custom MCP server for control plane tools
- systemd services orchestrating the pipeline

This architecture achieved the goal of agent-driven development but introduced operational
complexity: custom job queue, database migrations, worker daemon lifecycle management,
dual git worktree coordination, and maintenance burden for integration glue code.

Cursor now offers **My Machines**, a native feature that connects a host directly to
Cursor's backend, enabling agent requests from Slack, mobile app, and web interface with
local execution context. This provides the same operator experience with significantly
reduced custom infrastructure.

## Decision

**Retire the custom factory pipeline and adopt Cursor My Machines as the primary agent
interface.**

### Architecture

**Before (ADR-009/010/011):**

```
Slack Socket Mode (host) → POST /api/v1/slack/intake
                           ↓
                    forge-site control plane
                    (Postgres + pg-boss)
                           ↓
                    worker daemon claims jobs
                           ↓
                    Cursor SDK in worktrees
                           ↓
                    notify queue → Slack replies
```

**After (ADR-012):**

```
Cursor Slack / mobile / web → Cursor backend
                              ↓
                        My Machines worker (host)
                              ↓
                        Local execution
                        (git, tools, MCP servers)
```

### Component Decisions

1. **forge-site control plane:** Retire entirely
   - Postgres database retired (no export needed per operator decision)
   - pg-boss job queue retired
   - Next.js backend retired (or repurposed for unrelated projects)
   - MCP server retired

2. **Task management:** GitHub Issues via Cursor skill instructions
   - GitHub Projects board retired
   - Tasks tracked as Issues with appropriate labels
   - Cursor agents guided by skill files to manage backlog

3. **MCP servers:**
   - **stdio-based** (command transport): Run locally on My Machines worker
     - Vault integration (secret/forge/*)
     - Internal APIs requiring private network access
     - Local development tools
   - **HTTP-based** (url transport): Cursor backend handles these
     - External services with OAuth
     - Public APIs

4. **Sandbox/isolation:** Cursor environment isolation
   - `.cursor/environment.json` defines dev environment
   - Container-based environment builds
   - Retire custom forge sandbox CLI profiles (trusted, devcontainer, incus, k8s-workload, agent-cell)

5. **Secrets:** Vault via local MCP server
   - Keep existing Vault on k3s deployment
   - Integrate via stdio MCP server running on worker
   - Vault AppRole credentials configured on host

6. **GitOps:** Unchanged
   - Merge to `main` → Argo CD syncs k8s/ (ADR-008 still applies)
   - Cursor agents open PRs; humans review and merge

### My Machines Setup

```bash
# Install Cursor CLI (if not present)
curl -fsSL https://cursor.sh/install.sh | sh

# Authenticate
agent login

# Start worker on homelab-forge repository
cd /path/to/homelab-forge
agent worker --name "localpower-forge" start
```

Worker configuration:
- **Name:** `localpower-forge` (recognizable in Cursor UI)
- **Repository:** homelab-forge checkout on host
- **Network:** Outbound HTTPS to Cursor backend (no inbound ports)
- **MCP servers:** Configured via `.cursor/mcp.json` for local tools

### Cursor Slack Integration

Enable native Cursor Slack app in operator's workspace:
- Install from Slack App Directory or Cursor Dashboard
- Authorize bot permissions
- Request changes by mentioning @Cursor in channels/threads
- Cursor routes to My Machines worker automatically

### Migration Runbook

**Phase 1: Setup My Machines (non-disruptive)**

1. Install Cursor CLI on localpower host
2. Authenticate with operator's Cursor account
3. Start worker in test/dry-run mode (separate directory)
4. Verify connectivity and basic operations
5. Configure Vault MCP server for local worker
6. Create `.cursor/environment.json` for homelab-forge

**Phase 2: Enable Cursor Slack**

1. Install Cursor Slack app in operator's workspace
2. Configure workspace settings
3. Test agent request flow: Slack → Cursor → My Machines worker
4. Verify PR creation and iteration workflow

**Phase 3: Cutover (disruptive)**

1. Stop accepting new tasks in forge-site control plane
2. Let in-flight worker jobs complete
3. Stop systemd services:
   ```bash
   systemctl --user stop forge-factory-worker.service
   systemctl --user stop forge-factory-orchestrator.service
   systemctl --user disable forge-factory-worker.service
   systemctl --user disable forge-factory-orchestrator.service
   ```
4. Archive factory task YAML and Postgres data (optional backup)
5. Start My Machines worker on homelab-forge repository
6. Create systemd unit for My Machines worker (optional: for auto-restart)

**Phase 4: Cleanup**

1. Remove forge-site deployment from k3s (if deployed)
2. Archive or delete Postgres PVC
3. Update documentation to reflect new workflow
4. Create GitHub Issue templates and labels for task management
5. Write Cursor skill files for homelab-forge conventions

### Rollback

If My Machines doesn't meet needs:

1. Stop My Machines worker: `agent worker stop`
2. Restore forge-site control plane (redeploy k8s manifests)
3. Restore Postgres backup (if needed)
4. Restart systemd services
5. Resume custom pipeline operations

Rollback window: 30 days (while factory code still present in repository)

## Consequences

### Benefits

- **Reduced complexity:** No custom job queue, database, or worker daemon lifecycle
- **Native Slack:** Built-in Cursor Slack app vs custom Socket Mode client
- **Mobile/web access:** Operator can request changes from any Cursor interface
- **Simpler onboarding:** Standard Cursor CLI setup vs custom factory installation
- **Maintained by Cursor:** Backend infrastructure, agent routing, authentication
- **Better observability:** Cursor dashboard shows agent runs, transcripts, artifacts

### Trade-offs

- **Dependency on Cursor service:** Custom pipeline was self-hosted
- **Less customization:** Cursor's workflow vs fully custom job queue logic
- **Task management change:** GitHub Issues instead of custom Postgres schema
- **Worker must be running:** Host must maintain worker process (vs on-demand k3s jobs)

### Migration Impact

- **Retire:** forge-site control plane, Postgres, pg-boss, systemd services, custom MCP server
- **Preserve:** Vault, Argo CD, GitOps workflow, k3s cluster, host-watch
- **Adapt:** Task management (Issues), MCP integration (local stdio servers), documentation

### Open Questions

- **Worker lifecycle:** Should My Machines worker run as systemd service for auto-restart?
- **Concurrency:** How many concurrent agents can one worker handle? (Default: depends on host resources)
- **Environment builds:** Need to document `.cursor/environment.json` for reproducible setup

## Supersedes

- **ADR-009:** Slack intake + Cursor SDK factory agents
- **ADR-010:** DB-backed factory control plane (runtime SoT)
- **ADR-011:** Control plane hub (forge-site communication bridge)

These ADRs remain historically accurate but are no longer the active architecture.
ADR-004 (factory concept) is superseded in implementation but validated in intent: agent-driven
development with review gates and GitOps deploys.

## Related

- **ADR-004:** Agentic factory shape (concept validated, implementation replaced)
- **ADR-008:** GitOps with Argo CD (unchanged, still applies)
- **ADR-007:** Vault for secrets (unchanged, integrated via local MCP)
