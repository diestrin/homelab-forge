{
  # Bound journal growth; kernel/firmware stay on apt/fwupd (ADR-001).
  environment.etc."systemd/journald.conf.d/99-homelab-forge.conf".text = ''
    [Journal]
    SystemMaxUse=500M
    RuntimeMaxUse=100M
    MaxRetentionSec=30day
  '';
}
