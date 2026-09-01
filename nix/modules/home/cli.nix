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
    # Phase 2: forge on PATH without cd'ing to the repo.
    (pkgs.writeShellScriptBin "forge" ''
      exec /media/diestrin/data/Projects/homelab-forge/forge "$@"
    '')
  ];
}
