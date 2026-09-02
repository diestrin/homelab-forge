# ADR-013: close-cycle deposits the cycle net into the sobres module

- Status: Accepted
- Date: 2026-09-02
- Related: ADR-011 (family-agile ledger sync), Notion ADR-35 (finance module:
  Sobres / Movimientos / Metas)

## Context

`close-cycle` already settles each member's 14-day cycle and produces a
`CycleSummary` with the net colones owed. Until now it wrote only a
`Corte quincenal` summary row; the money never reached the finance module that
ADR-35 introduced (💵 Sobres balances, 🔁 Movimientos ledger). Parents moved it
by hand.

The finance module is seeded for all five members (Luna, Lucas, Sol, and — as of
2026-09-02 — Fer and Diego, who now earn and are penalised like everyone else).
Each member has one 💵 Sobres row per jar type with a `% de reparto` that sums to
100.

## Decision

`close-cycle` deposits the cycle net, on the same payday run that writes the
Corte.

1. **The sync does the split.** For each member, the net colones are divided
   across their sobres in proportion to `% de reparto`
   (`rules.split_by_weights` / `rules.plan_deposits`, both pure). Each part is
   `floor(total * w / sum(w))`; the rounding remainder goes to the single
   largest share. `sum(parts) == net` exactly.
2. **One income movement, then one transfer per sobre.** A single
   `Ingreso mesada` 🔁 Movimiento records the whole net; then one
   `Transferencia a sobre` Movimiento per jar, each bumping that sobre's
   `Saldo`. Every movement carries a new `Corte` relation back to the summary
   row.
3. **Idempotent on a payday.** The Corte row is looked up before it is written
   (retry reuses it). The deposit runs only when the Corte is not `Pagado` and
   has no Movimiento linked to it; it flips `Pagado` last. A second run on the
   same payday is a no-op.
4. **`DISTRIBUTE=0` writes Cortes, moves no money.** This is the parallel run
   Fase 4 needs — `DRY_RUN=1` writes nothing, so there is nothing to compare
   the hand estimate against. If `NOTION_DB_SOBRES` / `NOTION_DB_MOVIMIENTOS`
   are not both set the deposit is skipped with a log line and the Cortes are
   still written.
5. **A member with no sobres** gets the `Ingreso mesada` recorded and a
   warning; the split is left for a human. The Corte is still marked `Pagado`.

## Alternatives considered

- **Lump-sum deposit, human distributes.** Rejected: the `% de reparto` fields
  exist precisely so the split is mechanical, and a manual step is the failure
  mode ADR-011 was written to remove.
- **A separate `distribute-income` CronJob** reading unpaid Cortes. Rejected
  for now: more moving parts, another schedule, and `close-cycle` already loads
  every input it needs. Can be split out later if the deposit grows.

## Consequences

- New optional config: `NOTION_DB_SOBRES`, `NOTION_DB_MOVIMIENTOS`,
  `DISTRIBUTE`. `NOTION_DB_CORTE` is no longer "Fase 5, doesn't exist" — the
  base is created and wired.
- 🔁 Movimientos gains a `Corte` relation property.
- The `Meta` sobre's balance grows but is not yet reflected in 🎯 Metas
  `Ahorrado` — a follow-up.
- Penalty magnitudes still floor the cycle at zero, so a deposit is never
  negative; a bad cycle just deposits less.
