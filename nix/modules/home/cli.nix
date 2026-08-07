{ pkgs, ... }:
{
  # Essential CLIs via Nix profile. Language runtimes stay project-local (flakes).
  home.packages = with pkgs; [
    age
    bat
    fd
    fzf
    gh
    jq
    ripgrep
    tree
  ];
}
