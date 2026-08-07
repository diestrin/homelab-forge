{ pkgs, ... }:
{
  imports = [
    ../../modules/system/sysctl.nix
    ../../modules/system/journald.nix
  ];

  nixpkgs.hostPlatform = "x86_64-linux";

  # Ubuntu is supported by system-manager; keep assertion on.
  system-manager.allowAnyDistro = false;

  # Do not manage SSH/UFW/fail2ban here — Phase 0 scripts remain authoritative.
  environment.systemPackages = [ ];

  # Apply sysctl drop-ins after /etc is populated.
  systemd.services.homelab-forge-sysctl = {
    enable = true;
    description = "Apply homelab-forge sysctl drop-in";
    wantedBy = [ "multi-user.target" ];
    after = [ "local-fs.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      # Prefer host procps (Ubuntu); fall back to Nix package if present.
      ExecStart = "${pkgs.procps}/bin/sysctl --system";
    };
  };
}
