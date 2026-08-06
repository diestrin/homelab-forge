# Bootstrap secrets (pre-Vault)

Public pattern only — **no real topics, keys, or tokens in git**.

## Location (host)

```text
/media/diestrin/data/secrets/bootstrap/   # mode 700, outside the repo
  age-key.txt       # age identity (chmod 600); back up offline
  secrets.age       # encrypted ntfy URL + interim tokens
  inventory.private.md
  README.md
```

## Tooling

- **age** (installed via Nix profile on this host for Phase 0).
- Encrypt to the age recipient; never commit plaintext or `age-key.txt`.

```bash
export PATH="$HOME/.nix-profile/bin:$PATH"
age -d -i /media/diestrin/data/secrets/bootstrap/age-key.txt \
  /media/diestrin/data/secrets/bootstrap/secrets.age
```

## What belongs here (Phase 0)

- Private ntfy topic URL for host-watch
- Short-lived notes needed before Vault exists

## What does not

- Nothing under `homelab-forge/` git tree
- Long-lived cloud PATs (prefer generate later into Vault)

## Migration (Phase 3)

1. Deploy Vault on k3s (ADR-007).
2. Write secrets into Vault KV; update consumers.
3. Destroy bootstrap plaintext remnants; keep only what is required for unseal.
