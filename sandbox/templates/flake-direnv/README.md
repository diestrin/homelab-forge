# Template: flake + direnv (L0)

Minimal project environment for trusted workspaces ([ADR-002](../../../docs/decisions/ADR-002-sandbox-model.md)).

## Use

```bash
cp -a sandbox/templates/flake-direnv/. /path/to/project/
cd /path/to/project
# Customize flake.nix packages for the language stack you need.
direnv allow
```

## Notes

- Uses `use flake` (not legacy `use nix` from `../dev-machine`).
- L1 wrap: `./forge sandbox enter . --profile devcontainer` ([`../../images/Dockerfile`](../../images/Dockerfile)).
- Do not put secrets in `.envrc`; use the bootstrap age store / later Vault.
