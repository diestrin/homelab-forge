# Factory (Phase 4)

Agentic software factory: git tasks + GitHub Projects + sandboxed workers +
human review + Argo CD deploy (ADR-004 / ADR-008).

## Layout

See [`factory/README.md`](../../factory/README.md).

## One-time host setup

### 1. Vault AppRole material (outside git)

Vault must be unsealed; API reachable (port-forward):

```bash
kubectl -n forge-system port-forward svc/vault 8200:8200 &
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN="$(cat /media/diestrin/data/secrets/vault/root.token)"

ROLE_ID=$(vault read -field=role_id auth/approle/role/forge-agent/role-id)
SECRET_ID=$(vault write -field=secret_id -f auth/approle/role/forge-agent/secret-id)
umask 077
printf 'ROLE_ID=%s\nSECRET_ID=%s\n' "$ROLE_ID" "$SECRET_ID" \
  >/media/diestrin/data/secrets/vault/approle-forge-agent.env
chmod 600 /media/diestrin/data/secrets/vault/approle-forge-agent.env

# Worker GitHub token (fine-scoped PAT or github-app install token) — never commit
vault kv put secret/forge/agents/github token="github_pat_***"
```

Login test:

```bash
source factory/scripts/vault-agent-login.sh
vault token lookup
```

### 2. GitHub Projects

Board already created for this forge:

- https://github.com/users/diestrin/projects/1  
- Mapping: [`factory/PROJECTS.md`](../../factory/PROJECTS.md)

`gh` needs `project` + `read:project` scopes (`gh auth refresh -h github.com -s project,read:project`).

### 3. Worker daemon (opt-in always-on)

Unit file: `factory/systemd/forge-factory-worker.service`.

```bash
mkdir -p ~/.config/systemd/user
cp factory/systemd/forge-factory-worker.service ~/.config/systemd/user/
systemctl --user daemon-reload
# Prefer start without enable until the proposed queue is intentional:
systemctl --user start forge-factory-worker.service
journalctl --user -u forge-factory-worker -f
```

Or foreground: `./forge factory worker` / `./forge factory worker --once`.

Ensure Vault port-forward (or in-cluster addr) is available if workers need AppRole.
For push/PR without `secret/forge/agents/github`, host `gh` auth is used.

## Daily commands

```bash
./forge factory validate
./forge factory list
./forge factory sync
./forge factory claim              # manual claim next proposed
./forge factory run TASK-001       # run without daemon
./forge factory worker --once
./forge factory demo
```

## Examples

TASK-002 is an illustrative `proposed` docs task (left proposed on purpose). Prefer
scripted hooks only for demo/low-risk chores; real implementation usually omits
`worker_hook` and uses Cursor inside the prepared `agent-cell`.

Demo worker PR (TASK-001): https://github.com/diestrin/homelab-forge/pull/2 — merge
after [`factory/review/CHECKLIST.md`](../../factory/review/CHECKLIST.md), then confirm
Argo sync + `curl` for the Phase 4 hello copy.

## Threat notes

- Daemon runs as your user; it can commit/push if credentials exist — keep
  `proposed` queue intentional.
- Cells still lack docker.sock and `$HOME` mounts.
- Board is a mirror; ignore board-only edits when they disagree with git.
