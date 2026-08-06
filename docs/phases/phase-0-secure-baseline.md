# Phase 0 — Secure baseline (gate for everything else)

**Goal:** Make the host safe enough for continued public SSH and later 80/443. No k3s/ingress until this passes.

## Preconditions

- Physical or LAN console access available if SSH is misconfigured.
- Read `docs/current-state.md` and re-verify live state.
- Decisions locked: [ADR-006](../decisions/ADR-006-public-ssh.md) (public SSH), [ADR-005](../decisions/ADR-005-host-watch-adoption.md) (import host-watch), public repo day-one hygiene.

## Tasks

### 0.1 Network posture

- [ ] Prefer ethernet (`eno1`); document Wi-Fi as fallback only.
- [ ] Inventory WAN exposure: No-IP hostname, router port-forwards, current public IP / CGNAT check.
- [ ] Confirm DNS story for `localpower.diegobarahona.com` (and note if an alternate subdomain will be needed for HTTPS later).
- [ ] Document intended public ports eventually: SSH + 80 + 443 (only SSH allowed in this phase unless already required).

### 0.2 SSH & firewall (public SSH)

- [ ] Disable password authentication; keys only (ADR-006).
- [ ] Confirm `PermitRootLogin no`.
- [ ] Enable and document UFW (or nftables) default-deny inbound.
- [ ] Allow SSH; rate-limit; install/verify fail2ban (or equivalent).
- [ ] Keep a tested break-glass recovery path (console).
- [ ] Verify Cursor SSH still works from outside the LAN after hardening.

### 0.3 Import + install host-watch (ADR-005)

- [ ] Copy `../host-watch` into `security/host-watch/` (code, systemd units, scripts, example configs, MIT LICENSE/notice).
- [ ] Adjust paths/docs so install runs from this repo (wrapper OK).
- [ ] Install from in-tree scripts; configure private ntfy topic **outside git** (bootstrap secrets — see 0.6); enable linger.
- [ ] Dry-run and tune allowlists for current Cursor/Docker/Nix noise.
- [ ] Mark sibling `../host-watch` deprecated (README pointer) once import + install verified — do not dual-maintain.
- [ ] Keep example allowlists in git; no real ntfy URLs.

### 0.4 Docker hygiene

- [ ] Audit rootless Docker: no containers publishing `0.0.0.0` unexpectedly.
- [ ] Prune unused images/containers if safe.
- [ ] Document rule: local binds on `127.0.0.1`; public only via future Ingress.

### 0.5 Backup & recovery sketch

- [ ] Identify what must be backed up (SSH keys, Nix/Home Manager config, project data, future cluster/Vault/Argo state).
- [ ] Write a one-page restore rundown in `docs/` (even if backups are manual at first).

### 0.6 Bootstrap secrets (pre-Vault)

- [ ] Create a **non-git** bootstrap secrets location (age/SOPS/`pass`/encrypted file on data disk) per ADR-007.
- [ ] Store ntfy topic and any interim tokens there only.
- [ ] Document migration: these move into Vault in Phase 3, then bootstrap copies are destroyed or reduced to unseal materials.

## Exit criteria

- [ ] Password SSH disabled; key auth works remotely for Cursor.
- [ ] Firewall default-deny with explicit allows.
- [ ] `security/host-watch/` present in this repo; timer active; alerting path tested (topic not in git).
- [ ] Written note of current allowed public ports (**80/443 still closed** unless explicitly deferred with risk acceptance).
- [ ] No-IP / CGNAT / router forward inventory written (can be private runbook if it contains home details).

## Agent notes

- Prefer small, reversible changes with config backups (pattern already in `local-brain/backups`).
- Do not open 80/443 in this phase.
- Public repo: never commit real host firewall dumps with home IPs if avoidable; prefer redacted examples.
- Import is a code move, not a rewrite — preserve behavior first.
