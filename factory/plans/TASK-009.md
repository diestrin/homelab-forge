# TASK-009 plan — Family Agile ledger sync (Notion ↔ Habitica)

## What

A scheduled two-way sync between the household's **Family Agile** Notion workspace and
**Habitica**, deployed as Kubernetes CronJobs on k3s and delivered by Argo CD from `main`.

- **`apps/family-agile-sync/`** — Python service, one subcommand per job, no long-running
  process.
- **`k8s/apps/family-agile-sync/`** — namespace, NetworkPolicies, ExternalSecret,
  ConfigMap and four CronJobs.
- **`docs/decisions/ADR-011-family-agile-sync.md`** — records why Notion stays the system
  of record for money and why Habitica's own economy is never used for it.

The chore points this service settles are the children's **real allowance**, converted at
a fixed rate to colones. This is a financial ledger with a game skin, not a gamification
feature.

## Why

The previous iteration of the household system collapsed, and the cause is measurable. A
snapshot of the Notion workspace on 2026-08-24 found:

| Signal | Value |
| --- | --- |
| Penalty rows vs credit rows in the chore ledger | 2,240 vs 1,223 (65% punishment) |
| Members with any activity after 2026-08-06 | 1 of 5 |
| Rows dated in the future, any table | 0 |
| Distinct free-text fields naming a person in one table | 4, none a relation |

Points were credited only when a parent reviewed each row, and "not done" was the
**default** for anything not reviewed in time. When the reviewer fell behind, the
allowance stopped tracking effort and the children disengaged.

The design constraint that follows is the whole point of this task: **the system must
keep working on days nobody reviews it.**

## How

1. **Plan gate:** task stays `planning` until the operator approves and
   `./forge factory approve TASK-009` moves status to `proposed`.
2. **Rules as pure code:** every value that decides money lives in
   `src/family_agile_sync/rules.py`, which performs no I/O and is unit-tested. Notion
   formula and rollup fields return null over the API, so nothing the ledger depends on
   may be a Notion formula — the sync computes and writes plain numbers.
3. **Four jobs, one loop:**

   | Job | Schedule (`America/Costa_Rica`) | Direction |
   | --- | --- | --- |
   | `push-definitions` | Mondays 05:00 | Notion → Habitica |
   | `pull-completions` | Hourly 06:00–22:00 | Habitica → Notion |
   | `reconcile` | Daily 04:45 | Notion only |
   | `close-cycle` | Fridays 18:00 | Notion only |

4. **Secrets:** Vault paths `secret/family-agile/notion` and
   `secret/family-agile/habitica`, projected by External Secrets (ADR-007). Habitica API
   tokens grant full account control including task deletion; they never enter Notion or
   git.
5. **Network:** the target namespace carries its own default-deny plus DNS and egress
   HTTPS, mirroring `k8s/platform/network-policies/`.
6. **CI:** `family-agile-sync-image.yml` runs `pytest` before building, and gates the
   image push on `main`. All existing checks must be green — `ci.yml`, gitleaks,
   kustomize/kubeconform, markdownlint.
7. **Deploy:** **human merge to `main` only.** Argo CD syncs the new Application (ADR-008).
   No worker `kubectl apply`.

## Requirements

### Functional

- **R1** — Mirror every active routine and every approved to-do from Notion into Habitica
  as the matching task type: mandatory recurring → Daily, optional recurring → Habit with
  only the positive side enabled, one-off → To-Do.
- **R2** — Record each completion into the pre-existing Agenda row with signed points,
  colones, and the timestamp at which the sync observed it.
- **R3** — Mark yesterday's unfinished **mandatory** work as failed. Optional work and
  to-dos left undone stay pending and are worth nothing.
- **R4** — Settle a 14-day cycle on every second Friday and write one summary row per
  member into the Corte quincenal ledger.
- **R5** — Skip any member without Habitica credentials rather than failing the run, so
  onboarding one account at a time is possible.

### Economic rules

- **R6** — Points by difficulty: Fácil 5, Intermedia 10, Compleja 25. Penalties are half,
  rounded down: 2, 5, 12.
- **R7** — Only mandatory work can subtract. Absence of a completion is neutral.
- **R8** — A single day may not subtract more than 50% of that day's mandatory value.
- **R9** — A cycle never closes negative. Penalties reduce earnings; they never create
  debt.
- **R10** — Conversion to colones uses the per-member rate stored in Notion, not a global
  constant.
- **R11** — To-Dos only pay when a parent assigned the difficulty. A to-do created by a
  child in Habitica with no mirror row in Notion earns Habitica gold and zero colones.

### Non-functional

- **R12** — Idempotent: jobs only transition rows out of `Pendiente`, so a re-run after a
  crash cannot double-credit.
- **R13** — Habitica API **v3 only**. v4 is incomplete and unsuitable for third-party
  tools.
- **R14** — Every Habitica request carries an `X-Client` header; background calls are
  paced 30s apart per the API guidelines. Jobs are slow by design and deadlines allow for
  it.
- **R15** — The client never calls `/api/v3/cron`. Running cron on a user's behalf applies
  damage for every incomplete Daily.
- **R16** — Rows with `Origen = Manual` are never overwritten, giving a parent a way to
  record something the sync missed.

## Acceptance criteria

- `pytest` green in CI; `rules.py` covered including the floor, the cap and the cycle
  calendar
- `kubectl kustomize k8s/apps/family-agile-sync` renders cleanly and passes kubeconform
- No credential in git; gitleaks green
- ExternalSecret resolves against Vault and the CronJobs start with a complete environment
- `close-cycle` exits without writing on a Friday that is not a payday
- A full cycle runs with `DRY_RUN=1` and the computed summary is reconciled against a
  manual estimate **before any money changes hands**
- ADR-011 merged; app README documents the operating constraints

## Risks

- **High** — this service computes payments owed to children. An arithmetic or mapping
  error is a real financial error, and the people affected will notice it before the
  operator does. Hence the mandatory dry-run cycle.
- **Data loss window** — Habitica resets a Daily's completed flag at each cron and its
  history keeps the cron timestamp rather than the moment the task was ticked. If
  `pull-completions` is down for a full day, that day's completions may be
  unrecoverable. Mitigation is manual entry, not retroactive reconstruction.
- **Habitica punishes by default** — its cron damages incomplete Dailies automatically.
  That is the same failure mode the refactor removes, so per-task damage must be off for
  everything except mandatory dailies. A misconfigured push job silently reintroduces the
  original bug.
- **Cron cannot express "every second Friday"** — the payday calendar is enforced in code
  from an anchor date. A wrong anchor shifts every future payment.
- **External API dependency** — rate limits, 429s and outages are handled with backoff,
  but a prolonged Habitica outage stalls the ledger.

## Out of scope (v1)

- Generating Agenda occurrences from the Rutinas catalogue — this task consumes rows that
  already exist; the generator is a separate refactor phase
- Migrating the 3,960 legacy Horario rows, and the cleanup of the 924-row stale backlog
- Habitica Group Plan ($9/mo + $3/member) — evaluated and deferred; assignment already
  comes from Notion and task approval is the bottleneck being removed
- Any use of Habitica gold, XP or levels in a monetary calculation
- A custom mobile app; Habitica is the children's interface for now
- Automated payment execution — the ledger computes what is owed, a human pays it

## Multi-phase / iteration

This task ships the sync only. It depends on refactor phases that create the `Rutinas`
and `Corte quincenal` databases and add the `Miembro` relation to Agenda; until those
land, the ConfigMap keeps `REPLACE_ME` placeholders and the CronJobs stay suspended.

Follow-on work lands as new `TASK-NNN` entries, not scope creep here: the occurrence
generator, per-member Notion dashboards, and the quarterly purge of settled rows.
