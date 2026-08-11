# Factory (Phase 4 + ADR-009)

Git-backed agentic software factory (ADR-004) with Slack plan gate + Cursor SDK
workers (ADR-009).

| Piece | Path |
| --- | --- |
| Schema + state machine | [`schema/`](./schema/) |
| Tasks (SoT) | [`tasks/`](./tasks/) |
| Plan docs (Slack PR bodies) | [`plans/`](./plans/) |
| Projects board mapping | [`PROJECTS.md`](./PROJECTS.md) |
| Orchestrator playbook + Slack intake | [`orchestrator/`](./orchestrator/) |
| Worker playbook + Cursor SDK + daemon | [`worker/`](./worker/) |
| GitHub App / Cursor Vault helpers | [`scripts/`](./scripts/) |
| Review gate | [`review/CHECKLIST.md`](./review/CHECKLIST.md) |
| Demo script | [`demo/run-demo.sh`](./demo/run-demo.sh) |
| Operator runbook | [`../docs/runbooks/factory.md`](../docs/runbooks/factory.md) |

## Quick CLI

```bash
./forge factory validate
./forge factory list
./forge factory sync                 # git → GitHub Projects
./forge factory approve TASK-NNN     # planning → proposed
./forge factory worker --once        # claim + Cursor SDK (or hook)
./forge factory orchestrator         # Slack Socket Mode (foreground)
./forge factory demo                 # guided portfolio path
```

Worker artifacts (logs, diffs) live on the data disk under
`/media/diestrin/data/forge/factory/` — not in git.
