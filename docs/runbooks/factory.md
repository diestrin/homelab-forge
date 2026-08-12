# Factory (Phase 4 + ADR-010)

Agentic software factory: **Postgres control plane** + GitHub Projects mirror +
sandboxed workers + human review + Argo CD deploy (ADR-004 / ADR-008 / ADR-010).

## Layout

See [`factory/README.md`](../../factory/README.md).

## Control plane (ADR-010)

Runtime SoT is Postgres on k3s (`k8s/platform/postgres/`). forge-site exposes HTTP API
and MCP. Host clients need:

```bash
export FORGE_CONTROL_PLANE_URL=https://localpower.diegobarahona.com
export FORGE_API_TOKEN=…   # Vault secret/forge/control-plane api_token
```

Vault bootstrap (operator, never commit):

```bash
vault kv put secret/forge/postgres username=forge password='…' database=forge
vault kv put secret/forge/control-plane api_token="$(openssl rand -hex 32)"
```

After Argo sync, one-time migration from git mirror:

```bash
./forge factory migrate-yaml
```

Optional export back to git for portfolio audit:

```bash
./forge factory export-yaml
```

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
```

### 2. GitHub App credentials (bot identity — not a personal PAT)

Workers mint a short-lived **installation access token** and push/open PRs as the App.

| Vault field | Required | Notes |
| --- | --- | --- |
| `app_id` | **yes** | Numeric App ID — used as JWT `iss` |
| `client_id` | recommended | Stored for ops; not used for installation-token mint |
| `client_secret` | optional | Stored only — **cannot** mint installation tokens |
| `private_key` | **yes** | PEM from App settings → Generate private key |
| `installation_id` | recommended | From App → Installations; auto-resolved from repo if omitted |

Create / install the App on `diestrin/homelab-forge` with at least: **Contents: Read & write**, **Pull requests: Read & write**, **Metadata: Read**. For `./forge factory sync` as the App, also **Projects: Read & write** (or keep sync on a user `gh` login).

```bash
# private_key.pem downloaded once from GitHub App settings (never commit)
python3 - <<'PY' > /tmp/github-app-vault.json
import json, pathlib
print(json.dumps({
  "app_id": "REPLACE_APP_ID",
  "client_id": "REPLACE_CLIENT_ID",
  "client_secret": "REPLACE_CLIENT_SECRET",
  "installation_id": "REPLACE_INSTALLATION_ID",
  "private_key": pathlib.Path("private_key.pem").read_text(),
}))
PY
vault kv put secret/forge/agents/github @/tmp/github-app-vault.json
shred -u /tmp/github-app-vault.json private_key.pem 2>/dev/null || rm -f /tmp/github-app-vault.json
```

Verify mint (prints a `ghs_…` token; do not log it):

```bash
./forge factory github-token >/dev/null && echo ok
```

Legacy `token=` (PAT / pre-minted install token) still works as a fallback with a warning — migrate to App fields above.

### 3. GitHub Projects board

Board: <https://github.com/users/diestrin/projects/1>  
Mapping: [`factory/PROJECTS.md`](../../factory/PROJECTS.md)

`forge factory sync` prefers a Vault-minted App token when AppRole + App credentials exist; otherwise uses host `gh` auth (`project` + `read:project` scopes).

### 4. Cursor SDK + Python venv (ADR-009)

```bash
python3 -m venv /media/diestrin/data/forge/factory/venv
/media/diestrin/data/forge/factory/venv/bin/pip install -r factory/orchestrator/requirements.txt
```

Store the Cursor API key in Vault (never git):

```bash
vault kv put secret/forge/agents/cursor api_key="cursor_…"
```

Workers load it via `factory/scripts/fetch-cursor-key.sh` after AppRole login.

### 5. Slack Socket Mode orchestrator (ADR-009)

Create a Slack app with **Socket Mode** enabled (no Request URL / no Ingress). Register
slash command `/forge`. Bot scopes include `chat:write`, `commands`, and channel history.

Host env file must include control plane URL + API token:

```bash
FORGE_CONTROL_PLANE_URL=https://localpower.diegobarahona.com
FORGE_API_TOKEN=…
SLACK_BOT_TOKEN=xoxb-…
SLACK_APP_TOKEN=xapp-…
FORGE_SLACK_ALLOWLIST=U0…
```

Smoke-test: `/forge plan …` → plan PR (`planning`) → thread reply → `approve` → worker
implements → human merges.

```bash
vault kv put secret/forge/agents/slack \
  bot_token="xoxb-…" \
  app_token="xapp-…" \
  signing_secret="…" \
  allowlist_user_ids="U0XXXX,U0YYYY"
```

Write a host env file (mode 600) for systemd — placeholders shown; paste real values
from Vault, never commit the file:

```bash
umask 077
cat >/media/diestrin/data/secrets/forge/slack-orchestrator.env <<'EOF'
SLACK_BOT_TOKEN=xoxb-REPLACE
SLACK_APP_TOKEN=xapp-REPLACE
FORGE_SLACK_ALLOWLIST=U0REPLACE
EOF
chmod 600 /media/diestrin/data/secrets/forge/slack-orchestrator.env
```

Unit: `factory/systemd/forge-factory-orchestrator.service`.

```bash
cp factory/systemd/forge-factory-orchestrator.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user start forge-factory-orchestrator.service
journalctl --user -u forge-factory-orchestrator -f
```

Or foreground: `./forge factory orchestrator` (venv `python` on `PATH`).

Smoke-test: post in the private channel → plan PR (`planning`) → thread reply →
`approve` → task `proposed` → worker updates the same PR → human merges.

**ADR-010:** use `/forge plan …` slash command; top-level channel messages are ignored.

### 6. Worker daemon (opt-in always-on)

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

Ensure Vault is reachable (port-forward) so workers can AppRole-login and mint GitHub App + Cursor tokens.

## Daily commands

```bash
./forge factory validate
./forge factory list
./forge factory sync
./forge factory approve TASK-NNN   # planning → proposed
./forge factory github-token       # mint only (debug)
./forge factory claim              # manual claim next proposed
./forge factory run TASK-001       # run without daemon
./forge factory worker --once
./forge factory orchestrator
./forge factory demo
```

## Examples

TASK-002 is an illustrative docs task. Prefer scripted hooks only for demo/low-risk
chores; real implementation omits `worker_hook` so the Cursor SDK worker runs
(`factory/worker/cursor_implement.py`).

Demo worker PR (TASK-001): <https://github.com/diestrin/homelab-forge/pull/2> — merge
after [`factory/review/CHECKLIST.md`](../../factory/review/CHECKLIST.md), then confirm
Argo sync + `curl` for the Phase 4 hello copy.

## Threat notes

- Daemon runs as your user; with App credentials it pushes/PRs as the **GitHub App**,
  not your personal account. Keep the `proposed` queue intentional — `planning` is
  not claimable until Slack/CLI approve.
- Slack allowlist is mandatory; thread replies from others are ignored.
- Cells still lack docker.sock and `$HOME` mounts; Cursor SDK runs on the host with
  worktree `cwd`.
- Board is a mirror; **Postgres/API wins** over board or git YAML on conflict.
- Never commit `private_key.pem`, `client_secret`, Slack tokens, Cursor API keys, or
  real Slack user IDs.
