# family-agile-sync

Two-way sync between the **Family Agile** Notion workspace and **Habitica**.

Notion is the system of record for the household's chore ledger, which is the
children's real allowance. Habitica is the interface the children use and the
game layer that makes it worth using. This service keeps them in step.

Design rationale and the failure it is fixing: [`docs/decisions/ADR-011-family-agile-sync.md`](../../docs/decisions/ADR-011-family-agile-sync.md).

## The loop

| Job | Schedule | Direction | Does |
| --- | --- | --- | --- |
| `push-definitions` | Mondays 05:00 | Notion → Habitica | Mirrors routines and approved to-dos as Habitica tasks |
| `pull-completions` | Hourly, 06:00–22:00 | Habitica → Notion | Records completions, points and colones |
| `reconcile` | Daily 04:45 | — | Marks yesterday's unfinished **mandatory** work as `Fallada` |
| `close-cycle` | Fridays 18:00 | — | Settles the 14-day cycle and writes `Corte quincenal` |

All schedules are `America/Costa_Rica`.

## Rules that live here and not in Notion

Notion formula and rollup fields return null over the API, so anything the
ledger depends on is computed in [`rules.py`](src/family_agile_sync/rules.py)
and written back as a plain number.

| Rule | Value |
| --- | --- |
| Points earned | Fácil 5 · Intermedia 10 · Compleja 25 |
| Points lost (mandatory only) | Fácil 2 · Intermedia 5 · Compleja 12 |
| Conversion | Per member, `Colones por punto` in `Miembros` |
| Daily cap | A day may not subtract more than 50% of that day's mandatory value |
| Cycle floor | A cycle never closes negative |
| Cycle | 14 days, closing on every second Friday from `CYCLE_ANCHOR_FRIDAY` |

`rules.py` performs no I/O and is fully unit-tested — it is the file to review
carefully, since it is the one that decides money.

## Behaviour worth knowing before operating it

**`pull-completions` runs hourly on purpose.** Habitica resets a Daily's
completed flag at each cron, and its history stores the cron's timestamp rather
than the moment the child ticked the box. A once-daily pull would silently lose
work. If the sync is down for a full day, that day may be unrecoverable.

**Manual rows always win.** Any Agenda row with `Origen = Manual` is never
overwritten. That is the escape hatch when the sync misses something — not the
normal path.

**Idempotent by construction.** Agenda rows already exist as `Pendiente` before
anything happens; jobs only transition `Pendiente → Hecha/Fallada`. Re-running
after a crash cannot double-credit.

**`close-cycle` fires weekly but settles biweekly.** Cron cannot express "every
second Friday", so the job checks the payday calendar itself and exits quietly
on off-Fridays. Set `FORCE_CLOSE=1` only for the parallel dry run.

**Habitica paces third-party calls 30s apart**, so runs are slow by design.
Lower `HABITICA_REQUEST_DELAY` only for local experiments.

**`/api/v3/cron` is never called.** Running it on a user's behalf applies damage
for every incomplete Daily, which would penalise children for our scheduling.

## Configuration

Non-secret values come from the ConfigMap; secrets come from Vault via External
Secrets (ADR-007).

| Variable | Source | Notes |
| --- | --- | --- |
| `NOTION_TOKEN` | Vault | Internal integration token; each database must be shared with it |
| `NOTION_DB_*` | ConfigMap | Database ids for Miembros, Rutinas, Agenda, Tareas, Corte |
| `CYCLE_ANCHOR_FRIDAY` | ConfigMap | Any payday Friday, `YYYY-MM-DD` |
| `HABITICA_CLIENT` | ConfigMap | `<owner UserID>-family-agile-sync`, required on every request |
| `HABITICA_REQUEST_DELAY` | ConfigMap | Seconds between calls, default 30 |
| `HABITICA_<NAME>_USER` / `_KEY` | Vault | Per member; a member without credentials is skipped, not failed |
| `DRY_RUN` | optional | Log intended writes, perform none |

Habitica API tokens grant full control of an account, including task deletion.
They belong in Vault only — never in Notion, never in git.

## Local development

```bash
cd apps/family-agile-sync
pip install -r requirements-dev.txt
python -m pytest -q          # rules are covered; clients are not exercised
DRY_RUN=1 python -m src.family_agile_sync pull-completions
```

## Rollout

Bring it up in `DRY_RUN=1` and run one full cycle **without paying**, then
compare the computed `Corte quincenal` against what the parents would have
estimated by hand. This is real money owed to children; they will notice an
error before you do.
