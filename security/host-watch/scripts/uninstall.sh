#!/usr/bin/env bash
set -euo pipefail

UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SHARE_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/host-watch"

systemctl --user disable --now host-watch.timer 2>/dev/null || true
systemctl --user stop host-watch.service 2>/dev/null || true
rm -f "$UNIT_DIR/host-watch.service" "$UNIT_DIR/host-watch.timer"
systemctl --user daemon-reload

echo "Timer/service removed."
echo "Config (~/.config/host-watch) and state (~/.local/state/host-watch) were kept."
echo "Remove $SHARE_DIR if you also want the venv gone."
