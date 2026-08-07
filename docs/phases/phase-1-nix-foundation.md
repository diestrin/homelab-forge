# Phase 1 — Nix foundation

**Goal:** Make developer/host tooling declarative and reproducible without leaving Ubuntu.

**Status:** Complete (2026-08-06) for Home Manager + flake/direnv sample. system-manager modules built; privileged host apply via `./nix/scripts/apply-system-privileged.sh` (sudo TTY).

## Preconditions

- Phase 0 exit criteria met (or explicitly waived with written risk acceptance).

## Tasks

### 1.1 Flake skeleton

- [x] Create `nix/flake.nix` for this host (`localpower`) with inputs pinned.
- [x] Add Home Manager integration for user `diestrin`.
- [x] Encode shell, git, direnv, essential CLIs; avoid dumping every language runtime globally.

### 1.2 Project-local environments

- [x] Standardize on flakes + `direnv` (`use flake`) per project.
- [x] Document template for new projects under `sandbox/templates/` (when implementing).
- [x] Align with `../dev-machine` image ideas for containerized Nix shells.

### 1.3 System-managed pieces

- [x] Choose mechanism for root-owned bits (`system-manager` vs scripted idempotent bootstrap).
- [x] Represent: base packages, sysctl knobs, journald limits, maybe SSH hardening snippets as code.
- [x] Keep Ubuntu kernel/firmware on apt/fwupd unless/until NixOS migration.

**Decision:** `system-manager` for sysctl + journald drop-ins only. SSH/UFW/fail2ban remain Phase 0 scripts. Apply with `./bootstrap --system` or `./nix/scripts/apply-system-privileged.sh`.

### 1.4 Bootstrap UX

- [x] Single entrypoint doc/script: `./bootstrap` or `nh`/`home-manager switch` instructions.
- [x] Idempotent apply; CI-friendly `nix flake check` where feasible.

## Exit criteria

- [x] Fresh login gets expected tooling from Home Manager.
- [x] Applying config is documented and non-interactive enough for agents.
- [x] At least one sample project uses flake+direnv successfully over Cursor SSH.

## Agent notes

- Do not remove apt packages aggressively; prefer additive Nix first.
- Record package ownership (apt vs Nix) to avoid PATH fights — [`docs/runbooks/package-ownership.md`](../runbooks/package-ownership.md).
- Re-apply user config: `./bootstrap`. Re-apply host knobs: `./bootstrap --system`.
