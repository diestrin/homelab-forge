---
name: homelab-task
description: Create and manage homelab-forge development tasks as GitHub Issues. Use when the user requests new work, feature implementation, bug fixes, or infrastructure changes.
---

# Homelab Task Management

homelab-forge uses **GitHub Issues** for task tracking (ADR-012, replacing the custom
factory YAML task system). When the user requests new work, create a structured issue
following these conventions.

## When to Create an Issue

Create an issue when:

- User requests a new feature or infrastructure change
- User reports a bug or problem to fix
- Planning work that will result in a PR
- User says "create a task for..." or similar

Do NOT create an issue for:

- Direct questions about the codebase
- Immediate one-line changes user asks you to make now
- Exploratory work with no clear deliverable

## Title Format

Use component prefix for categorization:

```text
[component] Brief description (imperative mood)
```

**Component prefixes:**

- `[k8s]` — Kubernetes manifests, deployments, services
- `[docs]` — Documentation, runbooks, ADRs
- `[security]` — host-watch, firewall, SSH, secrets
- `[nix]` — Nix flakes, Home Manager, system config
- `[ci]` — GitHub Actions, linting, validation
- `[ingress]` — Traefik, certificates, Let's Encrypt
- `[vault]` — HashiCorp Vault, secrets management
- `[argo]` — Argo CD, GitOps configuration
- `[infra]` — Host-level infrastructure, systemd

**Examples:**

- `[k8s] Add Redis deployment for session storage`
- `[docs] Update operations runbook for Cursor My Machines`
- `[security] Rotate Vault AppRole tokens`
- `[nix] Add terraform to home profile`

## Issue Body Template

Structure the issue body as:

```markdown
## Goal

[One-sentence objective in imperative mood]

## Acceptance Criteria

- [ ] Criterion 1 (measurable outcome)
- [ ] Criterion 2
- [ ] Criterion 3

## Context

[Background, motivation, links to ADRs/runbooks/prior work]

## Risk Level

- [ ] **Low** — Docs, comments, safe refactors
- [ ] **Medium** — Feature work, dependencies, app code
- [ ] **High** — Host config, secrets, ingress, SSH

**Justification:** [Why this risk level?]

## Related

- Related issues: #NNN
- Related PRs: #NNN  
- ADRs: [ADR-NNN](../docs/decisions/ADR-NNN-title.md)
```

## Labels

Apply these labels when creating the issue:

**Required:**

- `task` (always, marks this as an agent-implementable task)
- `needs-triage` (operator reviews and removes this)

**Risk level (pick one):**

- `risk:low` — Safe changes, no infrastructure impact
- `risk:medium` — Feature work, new dependencies
- `risk:high` — Infrastructure, host changes, secrets, public exposure

**Component (optional but recommended):**

- `k8s`, `docs`, `security`, `nix`, `ci`, `ingress`, `vault`, `argo`, `infra`

**Example `gh` command:**

```bash
gh issue create \
  --title "[k8s] Add Redis deployment" \
  --label "task,needs-triage,risk:medium,k8s" \
  --body "$(cat issue-body.md)"
```

## Risk Level Guidelines

### Low Risk

- Documentation updates (ADRs, runbooks, README)
- Code comments and docstrings
- Refactors with tests passing
- CI configuration tweaks
- Non-functional changes

### Medium Risk

- New application features
- Adding dependencies (npm, pip, Nix packages)
- Database schema changes (with migrations)
- New k8s Deployments (non-public)
- MCP server changes

### High Risk

- Host systemd units
- SSH configuration
- UFW firewall rules
- Vault unseal/setup
- Public Ingress (80/443)
- Let's Encrypt certificate changes
- Secrets rotation
- host-watch allowlists

## Workflow States

Track task progress via labels (operator or agent applies):

1. **needs-triage** — New issue, awaiting operator review
2. **in-progress** — Agent working on it (self-assign + add label)
3. **review** — PR open, awaiting review (agent adds when PR ready)
4. **blocked** — Waiting on external dependency or decision
5. **(closed)** — Completed, PR merged

## Linking Issues and PRs

When opening a PR for a task:

```markdown
Closes #123

## What Changed

[Summary of implementation]

## Testing

[How was this verified?]
```

## Creating Issues via GitHub CLI

```bash
# From the homelab-forge repository
gh issue create \
  --title "[docs] Update My Machines migration runbook" \
  --label "task,needs-triage,risk:low,docs" \
  --body "## Goal

Document post-migration steady-state operations.

## Acceptance Criteria

- [ ] Worker lifecycle documented
- [ ] Restart procedures added
- [ ] Troubleshooting section complete

## Risk Level

- [x] Low — Documentation only
"
```

## Best Practices

1. **Be specific:** "Add health check endpoint to forge-site API" vs "improve API"
2. **Measurable AC:** Checklist items that can be verified objectively
3. **Link context:** Reference ADRs, runbooks, prior issues
4. **Right-size:** One issue per logical change; split large work into multiple issues
5. **Risk justification:** Explain why you chose the risk level

## Supersedes

This skill replaces the custom factory task system (`factory/tasks/TASK-NNN-*.yaml`)
per ADR-012. Historical factory tasks remain in git for reference but are not active.
