{
  imports = [
    ../modules/home/shell.nix
    ../modules/home/git.nix
    ../modules/home/cli.nix
    ../modules/home/direnv.nix
  ];

  home.username = "diestrin";
  home.homeDirectory = "/home/diestrin";
  home.stateVersion = "25.05";

  # Keep using the existing single-user Nix install; only manage user nix.conf.
  xdg.configFile."nix/nix.conf".text = ''
    experimental-features = nix-command flakes
  '';

  # On first switch, keep backups of files HM replaces (e.g. .zshrc).
  home.file.".homelab-forge-hm".text = ''
    Managed by homelab-forge nix/home/diestrin.nix
  '';

  programs.home-manager.enable = true;
}
