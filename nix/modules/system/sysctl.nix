{
  # Mild IDE/Cursor-friendly inotify limits via drop-in (system-manager → /etc).
  environment.etc."sysctl.d/99-homelab-forge.conf".text = ''
    # homelab-forge Phase 1 — bump watches for large trees / Cursor
    fs.inotify.max_user_watches = 524288
    fs.inotify.max_user_instances = 1024
  '';
}
