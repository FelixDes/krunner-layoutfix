#!/usr/bin/env bash
# Installs the plugin for the current user. Run it again to update.
# Packagers: DATADIR=/usr/share DESTDIR="$pkgdir" ./install.sh
set -euo pipefail
cd "$(dirname "$0")"

DATADIR="${DATADIR:-${XDG_DATA_HOME:-$HOME/.local/share}}"
DESTDIR="${DESTDIR:-}"
APPDIR="$DATADIR/krunner-layoutfix"
SERVICE=io.github.felixdes.KRunnerLayoutFix

if [[ -z "$DESTDIR" ]] && ! /usr/bin/python3 -c 'import gi; gi.require_version("Gio", "2.0")' 2>/dev/null; then
  cat >&2 <<'EOF'
PyGObject is missing. Install it, then run this script again:
  Arch:          sudo pacman -S python-gobject
  Debian/Ubuntu: sudo apt install python3-gi
  Fedora:        sudo dnf install python3-gobject
  openSUSE:      sudo zypper install python3-gobject
EOF
  exit 1
fi

install -Dm644 -t "$DESTDIR$APPDIR" src/*.py
install -Dm644 data/krunner-layoutfix.desktop "$DESTDIR$DATADIR/krunner/dbusplugins/krunner-layoutfix.desktop"
install -d "$DESTDIR$DATADIR/dbus-1/services"
cat > "$DESTDIR$DATADIR/dbus-1/services/$SERVICE.service" <<EOF
[D-BUS Service]
Name=$SERVICE
Exec=/usr/bin/python3 $APPDIR/runner.py
EOF

if [[ -z "$DESTDIR" ]]; then
  # Restart the plugin and KRunner so that they pick up the new files.
  pkill -f "$APPDIR/runner.py" || true
  kquitapp6 krunner 2>/dev/null || kquitapp5 krunner 2>/dev/null || true
  echo "Installed. Try it in KRunner (Alt+Space): type 'ыеуфь' to find Steam."
  echo "If the Application Launcher does not show it yet, log out and back in."
fi
