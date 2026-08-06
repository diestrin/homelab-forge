# ADR-001: Nix on Ubuntu (not NixOS first)

## Status

Accepted (2026-08-06)

## Context

The host is a daily Cursor/SSH remote-dev machine. A full NixOS migration maximizes
reproducibility but risks locking the operator out or breaking the development
loop mid-migration. Nix is already installed.

## Decision

1. **Stay on Ubuntu + Nix for the foreseeable roadmap** (Phases 0–5).
2. **Phase 1–2:** Declarative **user + selected system** configuration via Nix flakes:
   - Home Manager for user tooling (shell, git, direnv, language CLIs).
   - Prefer [`system-manager`](https://github.com/numtide/system-manager) or carefully scoped Nix modules / scripts for host packages/services that must be root-owned.
3. **Defer NixOS** until the forge bootstrap path is proven and a tested recovery path exists (USB/live + documented restore, or secondary access). No migration is scheduled in v1.
4. Optionally encode a *future* NixOS module sketch later; not a Phase 0–5 deliverable.

## Consequences

- Slightly less “pure” than NixOS, but safer for a single production personal server.
- Portfolio narrative still strong: flakes, modules, reproducible envs.
- Apt remains the escape hatch for kernel/firmware and some proprietary bits.
