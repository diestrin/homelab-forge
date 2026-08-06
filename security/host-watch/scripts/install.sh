#!/usr/bin/env bash
# Install host-watch as a systemd --user timer.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARE_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/host-watch"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/host-watch"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/host-watch"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

echo "==> Installing host-watch from $REPO_ROOT"

mkdir -p "$SHARE_DIR" "$CONFIG_DIR" "$STATE_DIR" "$UNIT_DIR"

# Prefer system Python >=3.11 (uv's default toolchain may be older).
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 \
    && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    PYTHON_BIN="$(command -v "$candidate")"
    break
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "error: need Python >=3.11 (python3.12 recommended on Ubuntu 24.04)" >&2
  exit 1
fi
echo "    using $PYTHON_BIN"

# Install into a dedicated venv (stdlib-only package; venv keeps the module path stable).
if [[ ! -d "$SHARE_DIR/venv" ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --python "$PYTHON_BIN" "$SHARE_DIR/venv"
  elif "$PYTHON_BIN" -m venv "$SHARE_DIR/venv"; then
    :
  else
    echo "error: need 'uv' or python3-venv to create $SHARE_DIR/venv" >&2
    exit 1
  fi
fi
if command -v uv >/dev/null 2>&1; then
  uv pip install -e "$REPO_ROOT" --python "$SHARE_DIR/venv/bin/python"
else
  # shellcheck disable=SC1091
  source "$SHARE_DIR/venv/bin/activate"
  pip -q install --upgrade pip
  pip -q install -e "$REPO_ROOT"
fi

# Seed config if missing
if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
  cp "$REPO_ROOT/config/config.example.toml" "$CONFIG_DIR/config.toml"
  echo "    wrote $CONFIG_DIR/config.toml  (edit notify.url)"
fi
if [[ ! -f "$CONFIG_DIR/allowlists.toml" ]]; then
  cp "$REPO_ROOT/config/allowlists.example.toml" "$CONFIG_DIR/allowlists.toml"
  # Rewrite home-specific binary prefixes for current user
  if grep -q '/home/diestrin/' "$CONFIG_DIR/allowlists.toml"; then
    sed -i "s|/home/diestrin/|$HOME/|g" "$CONFIG_DIR/allowlists.toml"
  fi
  echo "    wrote $CONFIG_DIR/allowlists.toml"
fi

cp "$REPO_ROOT/README.md" "$SHARE_DIR/README.md"
cp "$REPO_ROOT/systemd/host-watch.service" "$UNIT_DIR/host-watch.service"
cp "$REPO_ROOT/systemd/host-watch.timer" "$UNIT_DIR/host-watch.timer"

systemctl --user daemon-reload
systemctl --user enable --now host-watch.timer

# Linger so the timer runs even without an interactive login session (optional).
if command -v loginctl >/dev/null 2>&1; then
  if ! loginctl show-user "$USER" -p Linger 2>/dev/null | grep -q 'Linger=yes'; then
    echo "    Tip: enable lingering so scans run without an SSH session:"
    echo "         sudo loginctl enable-linger $USER"
  fi
fi

echo
echo "==> Installed."
echo "    Config:  $CONFIG_DIR"
echo "    State:   $STATE_DIR"
echo "    Timer:   systemctl --user status host-watch.timer"
echo
echo "Next steps:"
echo "  1. Edit $CONFIG_DIR/config.toml and set notify.url"
echo "     e.g. url = \"https://ntfy.sh/my-private-topic-$(openssl rand -hex 8)\""
echo "  2. Install the ntfy app and subscribe to that topic"
echo "  3. Test:  $SHARE_DIR/venv/bin/python -m host_watch --dry-run -v"
echo "  4. Run:   systemctl --user start host-watch.service"
echo "  5. Logs:  journalctl --user -u host-watch.service -f"
