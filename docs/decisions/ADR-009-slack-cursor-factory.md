# ADR-009: Slack intake + Cursor SDK factory agents

## Status

Accepted (2026-08-11) — implements the away-from-keyboard path sketched under ADR-004.

## Context

ADR-004 defined the factory control plane with Cursor chat as the orchestrator UI
and sandboxed workers claiming git tasks. The operator wants to submit feature
requests from Slack while away, iterate a **plan PR** in a Slack thread, explicitly
approve, then have a worker implement with the **Cursor SDK** and update that PR.
WAN surface must not grow (no new Ingress / Events Request URL).

## Decision

1. **Slack Socket Mode** is an additional orchestrator intake + plan-approval
   channel. Outbound WebSocket only; no public Request URL, no Traefik route, no
   UFW change.
2. **Cursor SDK** (local runtime against a repo `cwd`) is the programmatic agent
   for:
   - Orchestrator: draft/revise `factory/tasks/*.yaml` + `factory/plans/*.md`
   - Worker: implement approved tasks in the factory worktree
3. **State machine:** add non-claimable status `planning`. Workers claim only
   `proposed`. Slack (or `./forge factory approve`) transitions `planning` →
   `proposed` after explicit approval.
4. **Same PR:** orchestrator opens the plan PR; worker pushes implementation
   commits to the same branch/PR; humans still merge (Slack is not a merge/deploy
   console). Argo CD remains the steady-state deploy path (ADR-008).
5. **Secrets:** Vault `secret/forge/agents/slack` and `secret/forge/agents/cursor`;
   allowlisted Slack user IDs only. Never commit tokens or real user IDs.
6. **Host systemd** runs the Slack orchestrator beside the existing worker daemon.

## Consequences

- Requires host venv deps (`factory/orchestrator/requirements.txt`) and Vault
  material before smoke-test.
- GitHub Projects gains a Planning column; option ids live in `factory/PROJECTS.md`.
- Scripted `worker_hook` demos remain; hookless tasks prefer Cursor SDK when a key
  is available, else legacy attach-and-wait.
- High-risk host intents stay non-auto-approved; operator must not rubber-stamp them
  into `proposed`.
