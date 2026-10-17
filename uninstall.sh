#!/usr/bin/env bash
# Removes what install.sh installed for the current user.
set -euo pipefail

DATADIR="${DATADIR:-${XDG_DATA_HOME:-$HOME/.local/share}}"
APPDIR="$DATADIR/krunner-layoutfix"
SERVICE=io.github.felixdes.KRunnerLayoutFix

rm -rf "$APPDIR"
rm -f "$DATADIR/krunner/dbusplugins/krunner-layoutfix.desktop" "$DATADIR/dbus-1/services/$SERVICE.service" \
      "$DATADIR/icons/hicolor/scalable/apps/$SERVICE.svg"

pkill -f "$APPDIR/runner.py" || true
kquitapp6 krunner 2>/dev/null || kquitapp5 krunner 2>/dev/null || true
echo "Removed. Settings in ~/.config/krunner-layoutfixrc, if any, were kept."
