# Package ownership (apt vs Nix)

Phase 1 is **additive Nix**. Do not aggressively remove apt packages.

| Tool | Owner | Notes |
| --- | --- | --- |
| Kernel / firmware | apt / fwupd | ADR-001 — not Nix |
| OpenSSH, UFW, fail2ban | apt + Phase 0 scripts | Not system-manager |
| `zsh` binary | apt | HM configures via Nix oh-my-zsh / plugins |
| `git`, `jq`, `fzf`, `direnv` | apt **and** Nix HM | Nix profile usually wins on PATH; OK if versions differ |
| `rg`, `fd`, `bat`, `gh`, `age`, `tree`, `gnumake` | Nix (Home Manager) | Prefer HM over `nix-env -i` |
| `forge` | Nix HM wrapper → repo `./forge` | Phase 2 sandbox CLI |
| Rootless Docker | apt (Docker CE) | L1/L4 runtime; never mount socket into agent-cells |
| `nix` | single-user installer (`nix-env`) | Keep; do not replace casually |
| Language runtimes (Node via nvm, etc.) | unmanaged / project flakes | Not global HM packages |
| Project toolchains | per-repo flake + direnv | See `sandbox/templates/flake-direnv/` |
| L1/L4 image packages | `sandbox/images/Dockerfile` | Nix + direnv inside container |

## Conflicts

If `home-manager switch` fails with “conflict for the following files”, remove the imperative package:

```bash
nix-env -q
nix-env -e <pkg>
```

Then re-run `./bootstrap`.
