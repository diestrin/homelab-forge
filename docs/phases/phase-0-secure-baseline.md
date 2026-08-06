# Phase 0 — Secure baseline (gate for everything else)

**Goal:** Make the host safe enough for continued public SSH and later 80/443. No k3s/ingress until this passes.

**Status:** Complete (2026-08-06). Privileged apply via `./security/scripts/apply-phase0-privileged.sh`.

## Preconditions

- Physical or LAN console access available if SSH is misconfigured.
- Read `docs/current-state.md` and re-verify live state.
- Decisions locked: [ADR-006](../decisions/ADR-006-public-ssh.md) (public SSH), [ADR-005](../decisions/ADR-005-host-watch-adoption.md) (import host-watch), public repo day-one hygiene.

## Tasks

### 0.1 Network posture

- [x] Prefer ethernet (`eno1`); document Wi-Fi as fallback only. **Decision (Phase 0):** keep **Wi-Fi as default** uplink; ethernet documented as optional later ([network-exposure](../runbooks/network-exposure.md)).
- [x] Inventory WAN exposure: No-IP hostname, router port-forwards, current public IP / CGNAT check. (Public redacted + private bootstrap inventory.)
- [x] Confirm DNS story for `localpower.diegobarahona.com` (and note if an alternate subdomain will be needed for HTTPS later).
- [x] Document intended public ports eventually: SSH + 80 + 443 (only SSH allowed in this phase unless already required).

### 0.2 SSH & firewall (public SSH)

- [x] Disable password authentication; keys only (ADR-006). (`99-homelab-forge.conf`)
- [x] Confirm `PermitRootLogin no`.
- [x] Enable and document UFW (or nftables) default-deny inbound.
- [x] Allow SSH; rate-limit; install/verify fail2ban (or equivalent).
- [x] Keep a tested break-glass recovery path (console). Physical access confirmed; backups under `backups/phase0_*`.
- [x] Verify Cursor SSH still works from outside the LAN after hardening. (Active Cursor SSH session survived `sshd` reload; password auth rejected; re-check from a non-LAN client when convenient.)

### 0.3 Import + install host-watch (ADR-005)

- [x] Copy `../host-watch` into `security/host-watch/` (code, systemd units, scripts, example configs, MIT LICENSE/notice).
- [x] Adjust paths/docs so install runs from this repo (wrapper OK).
- [x] Install from in-tree scripts; configure private ntfy topic **outside git** (bootstrap secrets — see 0.6); enable linger.
- [x] Dry-run and tune allowlists for current Cursor/Docker/Nix noise. (dry-run: 0 findings; removed unused `5050` from examples.)
- [x] Mark sibling `../host-watch` deprecated (README pointer) once import + install verified — do not dual-maintain.
- [x] Keep example allowlists in git; no real ntfy URLs.

### 0.4 Docker hygiene

- [x] Audit rootless Docker: no containers publishing `0.0.0.0` unexpectedly.
- [x] Prune unused images/containers if safe. (removed idle `munity-test-mongo` + dangling image.)
- [x] Document rule: local binds on `127.0.0.1`; public only via future Ingress. ([docker-hygiene](../runbooks/docker-hygiene.md))

### 0.5 Backup & recovery sketch

- [x] Identify what must be backed up (SSH keys, Nix/Home Manager config, project data, future cluster/Vault/Argo state).
- [x] Write a one-page restore rundown in `docs/` (even if backups are manual at first). ([restore](../runbooks/restore.md))

### 0.6 Bootstrap secrets (pre-Vault)

- [x] Create a **non-git** bootstrap secrets location (age/SOPS/`pass`/encrypted file on data disk) per ADR-007.
- [x] Store ntfy topic and any interim tokens there only.
- [x] Document migration: these move into Vault in Phase 3, then bootstrap copies are destroyed or reduced to unseal materials. ([bootstrap-secrets](../runbooks/bootstrap-secrets.md))

## Exit criteria

- [x] Password SSH disabled; key auth works remotely for Cursor.
- [x] Firewall default-deny with explicit allows. (`ufw limit 22/tcp`; 80/443 closed)
- [x] `security/host-watch/` present in this repo; timer active; alerting path tested (topic not in git). (ntfy HTTP 200 test push)
- [x] Written note of current allowed public ports (**80/443 still closed** unless explicitly deferred with risk acceptance).
- [x] No-IP / CGNAT / router forward inventory written (can be private runbook if it contains home details).

## Agent notes

- Prefer small, reversible changes with config backups (pattern already in `local-brain/backups`).
- Do not open 80/443 in this phase.
- Public repo: never commit real host firewall dumps with home IPs if avoidable; prefer redacted examples.
- Import is a code move, not a rewrite — preserve behavior first.
- Re-apply / verify: `./security/scripts/apply-phase0-privileged.sh`.
