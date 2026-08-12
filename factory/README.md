# Factory (Phase 4 + ADR-009 + ADR-010)

Git-backed agentic software factory with **Postgres runtime control plane** (ADR-010),
Slack plan gate + Cursor SDK workers (ADR-009), and git/code SoT (ADR-004/008).

| Piece | Path |
| --- | --- |
| Schema + state machine | [`schema/`](./schema/) |
| Tasks (optional git mirror) | [`tasks/`](./tasks/) |
| **Runtime SoT** | Postgres via forge-site API |
| Plan docs (Slack PR bodies) | [`plans/`](./plans/) |
| Control plane API + MCP | [`../apps/forge-site/`](../apps/forge-site/) |
| API client | [`scripts/control_plane_client.py`](./scripts/control_plane_client.py) |
| Orchestrator playbook + Slack intake | [`orchestrator/`](./orchestrator/) |
| Worker playbook + Cursor SDK + daemon | [`worker/`](./worker/) |
| Review gate | [`review/CHECKLIST.md`](./review/CHECKLIST.md) |
| Operator runbook | [`../docs/runbooks/factory.md`](../docs/runbooks/factory.md) |

## Quick CLI

```bash
export FORGE_CONTROL_PLANE_URL=https://localpower.diegobarahona.com
export FORGE_API_TOKEN=…   # from Vault secret/forge/control-plane — never commit

./forge factory list
./forge factory migrate-yaml      # one-time YAML → Postgres
./forge factory export-yaml       # optional mirror Postgres → YAML
./forge factory approve TASK-NNN
./forge factory worker --once
./forge factory orchestrator      # Slack /forge slash (Socket Mode)
```

Workers **do not** scan `factory/tasks/*.yaml` for claimable work when ADR-010 env is set.
