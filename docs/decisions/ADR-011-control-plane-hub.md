# ADR-011: forge-site control plane as the factory communication hub

## Status

Accepted (2026-08-30) — amends ADR-009 and ADR-010 (TASK-011). Slack plan gate,
state machine, review gate, and GitOps deploy path are unchanged.

## Context

After live factory failures (duplicate plan PRs #16→#19 and #18→#20, a
post-approve Slack reply spawning a host planner that tried `sudo apt-get`,
fire-and-forget SDK runs with no inspectable conversation, lint failures and
red CI left for the operator to notice), the host Slack orchestrator had grown
into a second brain: it ran the Cursor SDK, git, and `gh` directly, posted its
own Slack replies, and serialized all work behind one process.

## Decision

1. **forge-site is the communication bridge** between Slack and the LLM/agents.
   - Host `slack_intake.py` is a **thin intake client**: Socket Mode slash
     commands and thread replies POST to `POST /api/v1/slack/intake`. It never
     calls the Cursor SDK, git, or `gh`.
   - The control plane creates/updates tasks, enqueues `plan` / `implement` /
     `watch-checks` / `notify` jobs, and is the **only** path that posts agent
     progress and failures back to Slack (the ADR-010 `notify` queue, consumed
     in-process by forge-site). Bot token comes from Vault
     `secret/forge/agents/slack` via ExternalSecret — never git. Socket Mode
     stays an outbound WebSocket on the host (no new Ingress).

2. **Durable agent runs.** pg-boss jobs are completed on claim, so a new
   `agent_runs` table is the operator-visible record: one row per SDK run
   (plan/implement/fix) with a **redacted** conversation transcript (assistant
   messages + tool calls/results), SDK agent/run ids, branch, and outcome.
   Agents use `Agent.create` + `run.messages()` (not fire-and-forget
   `Agent.prompt`) and stream events to `POST /api/v1/runs/{id}/events`.
   Exposed via `GET /api/v1/tasks/{id}/runs`, `GET /api/v1/runs/{id}`, and the
   dashboard task page.

3. **One stable PR per task.** The branch is pinned in Postgres
   (`tasks.branch`) once at intake and never rewritten by planner YAML; the PR
   URL is pinned on first open (`slack_threads.pr_url` + artifact `kind: pr`).
   All later pushes go to the pinned branch; `gh pr create` runs only when no
   pinned/open PR exists.

4. **Post-approve thread replies are stored, not re-planned.** Only tasks in
   `planning` get plan-update jobs; anything later is recorded on the task and
   acknowledged via notify. Implementation requests never spawn a host planner.

5. **Runtime card.** Every plan/implement prompt states role (plan-only vs
   implement), sandbox profile, no TTY, no host sudo/apt, and ADR-002
   restrictions; blocked agents end with `FORGE_BLOCKED: <reason>`, which flows
   worker → control plane → Slack thread.

6. **Lint before push, CI watch after push.** Workers (and the planner when it
   commits markdown/YAML) run `factory/scripts/lint-local.sh` — the CI checks
   that need no GitHub-hosted secrets (markdownlint-cli2, factory schema,
   shellcheck, actionlint, kubeconform when installed) — and fix findings in
   the same SDK run. After every plan/implement push, a `watch-checks` job
   polls GitHub checks; on red it enqueues a fix run against the same
   branch/PR and re-watches. Slack is notified only when green, when fix
   retries are exhausted, or on watch timeout. The loop never merges.

7. **Concurrency.** The worker daemon claims plan, implement, and
   watch-checks jobs and runs up to `FORGE_WORKER_CONCURRENCY` (default 2) in
   parallel with separate worktrees; same-task jobs serialize on a lock.
   Multiple `in_progress` tasks are allowed.

## Consequences

- Slack outage or host worker downtime no longer loses intent: it is recorded
  in Postgres and jobs wait in the queue.
- forge-site gains an outbound dependency (slack.com) and a bot token secret;
  egress 443 was already allowed in `forge-demo`.
- Transcripts are public on the dashboard — redaction (tokens, env secret
  values, Slack user IDs) happens host-side before events leave the machine.
- `factory/worker/PLAYBOOK.md` "one task at a time" is superseded by
  per-task locking + `FORGE_WORKER_CONCURRENCY`.

## Amends

- **ADR-009**: orchestrator no longer runs SDK/git/gh; plan PR flow retained.
- **ADR-010**: notify queue now implemented in forge-site; job kinds grow
  `watch-checks`; `agent_runs` joins the runtime SoT tables.
