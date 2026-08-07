# Package ownership (apt vs Nix)

Phase 1 is **additive Nix**. Do not aggressively remove apt packages.

| Tool | Owner | Notes |
| --- | --- | --- |
| Kernel / firmware | apt / fwupd | ADR-001 — not Nix |
| OpenSSH, UFW, fail2ban | apt + Phase 0 scripts | Not system-manager |
| `zsh` binary | apt | HM configures via Nix oh-my-zsh / plugins |
| `git`, `jq`, `fzf`, `direnv` | apt **and** Nix HM | Nix profile usually wins on PATH; OK if versions differ |
| `rg`, `fd`, `bat`, `gh`, `age`, `tree` | Nix (Home Manager) | Prefer HM over `nix-env -i` |
| `nix` | single-user installer (`nix-env`) | Keep; do not replace casually |
| Language runtimes (Node via nvm, etc.) | unmanaged / project flakes | Not global HM packages |
| Project toolchains | per-repo flake + direnv | See `sandbox/templates/flake-direnv/` |

## Conflicts

If `home-manager switch` fails with “conflict for the following files”, remove the imperative package:

```bash
nix-env -q
nix-env -e <pkg>
```

Then re-run `./bootstrap`.
