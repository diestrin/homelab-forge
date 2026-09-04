# family-agile-sync

Two-way sync between the **Family Agile** Notion workspace and **Habitica**.

Notion is the system of record for the household's chore ledger, which is the
children's real allowance. Habitica is the interface the children use and the
game layer that makes it worth using. This service keeps them in step.

Design rationale and the failure it is fixing: [`docs/decisions/ADR-011-family-agile-sync.md`](../../docs/decisions/ADR-011-family-agile-sync.md).

## The loop

| Job | Schedule | Direction | Does |
| --- | --- | --- | --- |
| `generate-occurrences` | Daily 03:30 | Notion → Notion | Materialises the `Pendiente` Agenda rows from the `Rutinas` catalogue, on a rolling horizon |
| `push-definitions` | Mondays 05:00 | Notion → Habitica | Mirrors routines and approved to-dos as Habitica tasks; deletes a retired routine's mirrors, and (with `PRUNE_HABITICA=1`) any orphaned Family Agile mirror |
| `pull-completions` | Hourly, 06:00–22:00 | Habitica → Notion | Records completions, points and colones |
| `reconcile` | Daily 04:45 | — | Marks yesterday's unfinished **mandatory** work as `Fallada` |
| `close-cycle` | Fridays 18:00 | Notion → Notion | Settles the 14-day cycle, writes `Corte quincenal`, and deposits each member's net into their `💵 Sobres` via `🔁 Movimientos` |

All schedules are `America/Costa_Rica`.

## Rules that live here and not in Notion

Notion formula and rollup fields return null over the API, so anything the
ledger depends on is computed in [`rules.py`](src/family_agile_sync/rules.py)
and written back as a plain number.

| Rule | Value |
| --- | --- |
| Points earned — optional & to-dos | Fácil 5 · Intermedia 10 · Compleja 25 |
| Points earned — mandatory | Fácil 1 · Intermedia 2 · Compleja 3 (a small acknowledgement for an unavoidable responsibility) |
| Points lost — mandatory only, on `Fallada` | Fácil 2 · Intermedia 5 · Compleja 12 |
| Conversion | Per member, `Colones por punto` in `Miembros` |
| Daily cap | A day may not subtract more than 50% of that day's mandatory value |
| Cycle floor | A cycle never closes negative |
| Cycle | 14 days, closing on every second Friday from `CYCLE_ANCHOR_FRIDAY` |
| Cycle deposit | The net colones are split across the member's sobres by each sobre's `% de reparto`; the rounding remainder goes to the largest share (ADR-013) |

`rules.py` performs no I/O and is fully unit-tested — it is the file to review
carefully, since it is the one that decides money.

## Behaviour worth knowing before operating it

**`generate-occurrences` only ever creates.** It never edits or deletes an
Agenda row. An occurrence that already has a row — from an earlier run or typed
in by hand — is skipped, so it is safe to run as often as you like and a
`Manual` row is left alone. A **Personal** routine produces one row per listed
`Miembro`; a **Pool** routine produces a single unclaimed row (empty `Miembro`)
that `pull-completions` assigns to whoever finishes first. Non-weekly routines
get their Agenda rows here too — `reconcile` needs them to fail a missed
mandatory window — independently of the Habitica `todo` mirror `push-definitions`
keeps for them. The matching calendar is ADR-27's v0 algorithm, now in
`rules.occurs_on`. Horizon: `GENERATE_HORIZON_DAYS` days ahead (default 14).

**`pull-completions` runs hourly on purpose.** Habitica resets a Daily's
completed flag at each cron, and its history stores the cron's timestamp rather
than the moment the child ticked the box. A once-daily pull would silently lose
work. If the sync is down for a full day, that day may be unrecoverable.

**Manual rows always win.** Any Agenda row with `Origen = Manual` is never
overwritten. That is the escape hatch when the sync misses something — not the
normal path.

**Definitions come from the catalogue, not the occurrence.** An Agenda row
stores only the result (points applied, colones, who/when). Difficulty,
mandatory-vs-optional, whether it pays (`Paga`) and the Habitica mirror id are
read from the linked `Rutina` (or `Tarea`) at sync time — see ADR-32. A row
that resolves to no routine, or to one with `Paga` unchecked, produces no
ledger entry.

**Idempotent by construction.** Agenda rows already exist as `Pendiente` before
anything happens; jobs only transition `Pendiente → Hecha/Fallada`. Re-running
after a crash cannot double-credit.

**One routine, one mirror per person.** `push-definitions` creates a Habitica
task for every listed `Miembro` (Personal, ADR-28) or every `Elegible` (Pool,
ADR-33) and stores the ids as a `{member_id: task_id}` JSON map in the routine's
`Habitica Task ID`. For a Pool routine the single Agenda occurrence stays
unclaimed; the first eligible to tick it claims the row and the losing mirrors
are deleted so no one else can be credited. Two ticks inside the same hourly
window: the first one processed wins, the second keeps its Habitica gold and
earns nothing.

**A retired routine loses its mirrors.** When a routine gets `Vigente hasta`,
`push-definitions` deletes every Habitica task in its `Habitica Task ID` map
and clears the map -- it no longer just skips it and leaves the tasks on the
child's account.

**`PRUNE_HABITICA=1` reconciles an account to the catalogue.** After the mirror
pass, `push-definitions` lists each member's tasks and deletes any whose
`notes` mark it as a Family Agile mirror (`"Family Agile — no editar
manualmente"`) that no active routine or approved tarea still points to. A task
without that marker -- something a child made for themselves -- is never
touched. Off by default; it is destructive, so it runs only when the flag is
set. Use it for a one-off cleanup after a big catalogue change, or after
routines were deleted (rather than retired) and left orphans behind.

**To-Dos have no pre-existing Agenda row.** Unlike a Rutina occurrence (which
already exists as `Pendiente` before anything happens), a Tarea only gets its
Agenda row once its Habitica mirror is completed -- `pull-completions` creates
it on the spot, links it back via `Tarea`, and marks the Tarea `Estado =
Hecha` in the same pass. A Tarea only pays once: `push-definitions` mirrors it
exactly once (a `Habitica Task ID` already set is never re-pushed), and
`pull-completions` skips a Tarea whose `Estado` is already `Hecha`.

**Non-weekly Rutinas (ADR-26) mirror as a `todo`, recreated by the sync
itself.** Quincenal/Mensual/Trimestral routines don't get a repeating Habitica
Daily -- `push-definitions` computes the current period's date from
`Vigente desde` and creates a fresh To-Do once the previous one is gone or
completed. Within a Mensual/Trimestral target month the date is `Día del mes`
if set; otherwise it is the weekday in `Días` on the same week-of-month index
`Vigente desde` lands on (ADR-43) -- e.g. `Vigente desde` on a 2nd Friday plus
`Días = V` means the 2nd Friday of every month, clamped to the last in a short
month. **An open, uncompleted
mirror is left alone even after its period has technically rolled over** --
the sync never deletes or duplicates a child's in-progress work. A Mandatory
routine missing its window still gets `Puntos falla` through the normal
Agenda/`reconcile` path, independent of what the Habitica mirror looks like.

**`close-cycle` fires weekly but settles biweekly.** Cron cannot express "every
second Friday", so the job checks the payday calendar itself and exits quietly
on off-Fridays. Set `FORCE_CLOSE=1` only for the parallel dry run.

**`close-cycle` is idempotent on a payday.** Before writing, it looks up the
`Corte quincenal` row for this cycle and member; a retry reuses it instead of
writing a second summary. The sobres deposit runs only for a Corte that is not
yet `Pagado` and has no `🔁 Movimientos` linked to it, then flips `Pagado` — so
running the job twice on the same payday moves money once. `DISTRIBUTE=0` writes
the Corte rows and skips the deposit entirely; that is the run for Fase 4's
parallel cycle, where `DRY_RUN=1` is no help because it writes nothing to
compare. If `NOTION_DB_SOBRES` / `NOTION_DB_MOVIMIENTOS` aren't both set the job
still writes the Cortes and just logs that the deposit was skipped. A member
with no sobres gets the `Ingreso mesada` movement recorded but not split, and a
warning.

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
| `NOTION_DB_*` | ConfigMap | Database ids for Miembros, Rutinas, Agenda, Tareas -- required |
| `NOTION_DB_CORTE` | ConfigMap | Corte quincenal database id. `push-definitions`, `pull-completions` and `reconcile` don't touch it. `close-cycle` only needs it on an actual payday Friday, and raises a clear error there if it's unset -- it doesn't block startup |
| `NOTION_DB_SOBRES` / `NOTION_DB_MOVIMIENTOS` | ConfigMap | 💵 Sobres / 🔁 Movimientos database ids. **Optional**; `close-cycle` deposits the cycle net into the sobres module only when both are set (and `DISTRIBUTE` is on). Missing either, it still writes the Cortes |
| `DISTRIBUTE` | optional | Default on. `DISTRIBUTE=0` makes `close-cycle` write the Corte rows but move no money -- the parallel run for Fase 4 |
| `CYCLE_ANCHOR_FRIDAY` | ConfigMap | Any payday Friday, `YYYY-MM-DD` |
| `HABITICA_CLIENT` | ConfigMap | `<owner UserID>-family-agile-sync`, required on every request |
| `HABITICA_REQUEST_DELAY` | ConfigMap | Seconds between calls, default 30 |
| `GENERATE_HORIZON_DAYS` | ConfigMap | Days ahead `generate-occurrences` fills Agenda, default 14 |
| `HABITICA_<NAME>_USER` / `_KEY` | Vault | Per member; a member without credentials is skipped, not failed |
| `PRUNE_HABITICA` | optional | `push-definitions` only. `1` deletes orphaned Family Agile mirrors from each account after the mirror pass -- a one-off reconcile. Off by default (destructive) |
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
