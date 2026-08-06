# Phase 4 — Agentic software factory

**Goal:** Chat-driven orchestration that creates tasks; workers execute inside sandboxes; humans review before deploy.

## Preconditions

- Phase 2 sandboxes usable.
- Phase 3 cluster + Vault available for optional deploy targets and worker credentials.

## Tasks

### 4.1 Task contract

- [ ] Finalize task schema (ADR-004) under `factory/schema/`.
- [ ] Example tasks and state machine: `proposed → claimed → in_progress → review → done/failed`.
- [ ] GitHub Projects board linked to this repo; column ↔ status mapping documented.
- [ ] Sync convention: **git is source of truth**; Projects is the kanban mirror (script or manual v1 OK).

### 4.2 Orchestrator playbook

- [ ] Document prompts/skills for the orchestrator agent (create tasks, never silent-prod-deploy).
- [ ] Map user intents to sandbox profiles and risk levels.
- [ ] Store conversation-derived decisions as ADRs or task notes.

### 4.3 Worker runtime

- [ ] Worker bootstrap: claim task → create agent-cell → clone/worktree → implement → tests → artifacts.
- [ ] Fetch GitHub / deploy credentials from Vault (AppRole or short-lived token); no long-lived PATs on disk.
- [ ] Artifact conventions: PR link, logs, screenshots, `kubectl` diff.
- [ ] Time/budget limits per task; auto-fail and cleanup sandbox.

### 4.4 Review & deploy

- [ ] Human (default) or reviewer-agent checklist before merge to `main`.
- [ ] Cluster changes land via **Argo CD sync from `main`** (ADR-008), not ad-hoc kubectl from workers.
- [ ] Audit log: git history + Argo sync history / Application status.

### 4.5 Portfolio demo path

- [ ] Scripted demo: “ask for a small web service → task → worker PR → deploy to forge-demo → public HTTPS.”
- [ ] Record architecture diagram and threat model in README.

## Exit criteria

- [ ] End-to-end demo completable in one sitting by a follow-up agent + human review.
- [ ] No worker requires host Docker socket.
- [ ] Task history retained in git; board reflects status via GitHub Projects.
- [ ] Worker secrets come from Vault, not committed files.
- [ ] Demo deploy path uses merge-to-`main` → Argo CD, not manual apply.

## Agent notes

- Optimize for reliability and clear contracts over autonomous spectacle.
- Keep v1 boring: filesystem/git task board + Projects UI beats a custom distributed queue.
