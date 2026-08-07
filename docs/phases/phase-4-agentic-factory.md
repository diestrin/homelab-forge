# Phase 4 — Agentic software factory

**Goal:** Chat-driven orchestration that creates tasks; workers execute inside sandboxes; humans review before deploy.

**Status:** Complete (2026-08-07) — picks: **git task SoT** + **GitHub Projects mirror** + **always-on worker daemon (opt-in systemd)** + **Vault AppRole secrets**.

## Preconditions

- Phase 2 sandboxes usable.
- Phase 3 cluster + Vault available for optional deploy targets and worker credentials.

## Tasks

### 4.1 Task contract

- [x] Finalize task schema (ADR-004) under `factory/schema/`.
- [x] Example tasks and state machine: `proposed → claimed → in_progress → review → done/failed`.
- [x] GitHub Projects board linked to this repo; column ↔ status mapping documented.
- [x] Sync convention: **git is source of truth**; Projects is the kanban mirror (script or manual v1 OK).

### 4.2 Orchestrator playbook

- [x] Document prompts/skills for the orchestrator agent (create tasks, never silent-prod-deploy).
- [x] Map user intents to sandbox profiles and risk levels.
- [x] Store conversation-derived decisions as ADRs or task notes.

### 4.3 Worker runtime

- [x] Worker bootstrap: claim task → create agent-cell → clone/worktree → implement → tests → artifacts.
- [x] Fetch GitHub / deploy credentials from Vault (AppRole or short-lived token); no long-lived PATs on disk.
- [x] Artifact conventions: PR link, logs, screenshots, `kubectl` diff.
- [x] Time/budget limits per task; auto-fail and cleanup sandbox.

### 4.4 Review & deploy

- [x] Human (default) or reviewer-agent checklist before merge to `main`.
- [x] Cluster changes land via **Argo CD sync from `main`** (ADR-008), not ad-hoc kubectl from workers.
- [x] Audit log: git history + Argo sync history / Application status.

### 4.5 Portfolio demo path

- [x] Scripted demo: “ask for a small web service → task → worker PR → deploy to forge-demo → public HTTPS.”
- [x] Record architecture diagram and threat model in README.

## Exit criteria

- [x] End-to-end demo completable in one sitting by a follow-up agent + human review.
- [x] No worker requires host Docker socket.
- [x] Task history retained in git; board reflects status via GitHub Projects.
- [x] Worker secrets come from Vault, not committed files.
- [x] Demo deploy path uses merge-to-`main` → Argo CD, not manual apply.

## Agent notes

- Optimize for reliability and clear contracts over autonomous spectacle.
- Keep v1 boring: filesystem/git task board + Projects UI beats a custom distributed queue.
- Phase 4 chose **1B**: opt-in long-running `forge factory worker` daemon (systemd user unit installed, not started by default) in addition to the boring contracts.
- Verified: worker claimed `TASK-001` in `agent-cell`, opened PR #2; board column Review; human merges → Argo.
