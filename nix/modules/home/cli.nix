{ pkgs, ... }:
{
  # Essential CLIs via Nix profile. Language runtimes stay project-local (flakes).
  home.packages = with pkgs; [
    age
    bat
    fd
    fzf
    gh
    gnumake
    jq
    kubectl
    kubernetes-helm
    k9s
    ripgrep
    tree
    vault
    claude-code
    codex
    # GBrain client (ADR-017). Not on npm: run upstream from GitHub, pinned to the
    # commit behind the `stable` tag (bump deliberately). State/credentials live in
    # ~/.gbrain and ~/.config/gbrain, never in the store or git.
    bun
    (pkgs.writeShellScriptBin "gbrain" ''
      exec ${pkgs.bun}/bin/bunx --bun "github:garrytan/gbrain#98dda48fb9fd339609d6d4eef009811280ff648d" "$@"
    '')
    # Phase 2: forge on PATH without cd'ing to the repo.
    (pkgs.writeShellScriptBin "forge" ''
      exec /media/diestrin/data/Projects/homelab-forge/forge "$@"
    '')
  ];
}
