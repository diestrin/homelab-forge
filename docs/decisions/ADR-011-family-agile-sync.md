# ADR-011: Family Agile ledger sync (Notion + Habitica)

- Status: Proposed
- Date: 2026-08-24
- Related: ADR-007 (Vault secrets), ADR-008 (GitOps via Argo CD)

## Context

The household runs a "Family Agile" system in Notion covering schedules, meals,
chores and extracurriculars for five people. Chore points are the children's
real allowance, converted at a fixed rate to colones.

The previous iteration collapsed. Points were only credited when a parent
reviewed each row, and the "not done" state was the *default* for anything not
reviewed in time. A measurement on 2026-08-24 found 2,240 penalty rows against
1,223 credit rows — 65% of the ledger was punishment, much of it produced by
missed reviews rather than missed chores. Once the allowance stopped tracking
effort, the children disengaged and the system died.

Children will now interact through Habitica rather than Notion directly.

## Decision

Run a scheduled two-way sync in-cluster as Kubernetes CronJobs.

1. **Notion is the system of record for money.** Habitica reports what
   happened; Notion decides what it is worth. Habitica's gold, XP and levels
   are a separate, deliberately generous play currency with no exchange rate.
2. **The child emits the completion event.** Parents audit by exception rather
   than gating every row. This is the specific failure the refactor targets.
3. **Absence is neutral.** Only mandatory dailies can subtract. Habitica's
   per-task damage flag is switched off for everything else.
4. **Money rules live in code, not in Notion formulas.** Notion formula and
   rollup fields return null over the API, so every value the ledger needs is
   stored as a plain number written by the sync.
5. **Habitica API v3 only.** v4 is incomplete and unsuitable for third-party
   tools. The client never calls `/api/v3/cron`, which would apply damage for
   every incomplete Daily.

## Consequences

- Four CronJobs, one per phase of the loop. `pull-completions` runs hourly
  because Habitica resets the completed flag at each cron and its history keeps
  the cron timestamp rather than the moment the child ticked the box.
- A lost day is a lost day: if the sync is down for 24h, that day's completions
  may be unrecoverable. Mitigated by `Origen = Manual` rows, which the sync
  never overwrites, letting a parent record directly in Notion.
- Cron cannot express "every second Friday", so `close-cycle` fires weekly and
  the payday calendar is enforced in code.
- Habitica asks background tools to pace calls 30s apart, so runs are slow by
  design; job deadlines are set accordingly.
- Habitica API tokens grant full account control and live only in Vault.
- The daily penalty cap is currently inert: because each penalty is half its
  earned value, a fully failed day already lands under the cap. It is retained
  as a guard against recalibration and against appeals that add penalties.

## Alternatives considered

- **GitHub Actions cron.** Rejected: the homelab already runs k3s + Argo CD,
  and family data should not transit a shared CI runner.
- **Habitica Group Plan** ($9/mo + $3/member; $21/mo for five). Rejected for
  now: it buys a shared board and task approval, but assignment already comes
  from Notion and approval is precisely the bottleneck being removed.
- **Deriving points from Habitica gold.** Rejected: gold is balanced for
  engagement, with drops and critical hits, and would make the allowance vary
  for reasons unrelated to effort.
