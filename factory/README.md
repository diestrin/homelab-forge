# Factory (Phase 4)

Git-backed agentic software factory (ADR-004).

| Piece | Path |
| --- | --- |
| Schema + state machine | [`schema/`](./schema/) |
| Tasks (SoT) | [`tasks/`](./tasks/) |
| Projects board mapping | [`PROJECTS.md`](./PROJECTS.md) |
| Orchestrator playbook | [`orchestrator/PLAYBOOK.md`](./orchestrator/PLAYBOOK.md) |
| Worker playbook + daemon | [`worker/`](./worker/) |
| Review gate | [`review/CHECKLIST.md`](./review/CHECKLIST.md) |
| Demo script | [`demo/run-demo.sh`](./demo/run-demo.sh) |
| Operator runbook | [`../docs/runbooks/factory.md`](../docs/runbooks/factory.md) |

## Quick CLI

```bash
./forge factory validate
./forge factory list
./forge factory sync                 # git → GitHub Projects
./forge factory worker --once        # claim + run one task
./forge factory demo                 # guided portfolio path
```

Worker artifacts (logs, diffs) live on the data disk under
`/media/diestrin/data/forge/factory/` — not in git.
