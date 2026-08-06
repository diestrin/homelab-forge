# Phase 1 — Nix foundation

**Goal:** Make developer/host tooling declarative and reproducible without leaving Ubuntu.

## Preconditions

- Phase 0 exit criteria met (or explicitly waived with written risk acceptance).

## Tasks

### 1.1 Flake skeleton

- [ ] Create `nix/flake.nix` for this host (`localpower`) with inputs pinned.
- [ ] Add Home Manager integration for user `diestrin`.
- [ ] Encode shell, git, direnv, essential CLIs; avoid dumping every language runtime globally.

### 1.2 Project-local environments

- [ ] Standardize on flakes + `direnv` (`use flake`) per project.
- [ ] Document template for new projects under `sandbox/templates/` (when implementing).
- [ ] Align with `../dev-machine` image ideas for containerized Nix shells.

### 1.3 System-managed pieces

- [ ] Choose mechanism for root-owned bits (`system-manager` vs scripted idempotent bootstrap).
- [ ] Represent: base packages, sysctl knobs, journald limits, maybe SSH hardening snippets as code.
- [ ] Keep Ubuntu kernel/firmware on apt/fwupd unless/until NixOS migration.

### 1.4 Bootstrap UX

- [ ] Single entrypoint doc/script: `./bootstrap` or `nh`/`home-manager switch` instructions.
- [ ] Idempotent apply; CI-friendly `nix flake check` where feasible.

## Exit criteria

- [ ] Fresh login gets expected tooling from Home Manager.
- [ ] Applying config is documented and non-interactive enough for agents.
- [ ] At least one sample project uses flake+direnv successfully over Cursor SSH.

## Agent notes

- Do not remove apt packages aggressively; prefer additive Nix first.
- Record package ownership (apt vs Nix) to avoid PATH fights.
