#!/usr/bin/env bash
# Builds dist/krunner-layoutfix-<version>.tar.gz to upload to the KDE Store,
# from where System Settings → Search → Plasma Search → "Get New Plugins…" installs it.
# The version comes from data/krunner-layoutfix.desktop.
set -euo pipefail
cd "$(dirname "$0")"

VERSION=$(sed -n 's/^X-KDE-PluginInfo-Version=//p' data/krunner-layoutfix.desktop)
ARCHIVE="dist/krunner-layoutfix-$VERSION.tar.gz"
FILES=(README.md LICENSE install.sh uninstall.sh krunner-plugininstallerrc data/krunner-layoutfix.desktop src/*.py)

mkdir -p dist
# A single top-level folder: the store installer unpacks it as
# ~/.local/share/krunner-sources/krunner-layoutfix and runs krunner-plugininstallerrc there.
tar --create --gzip --file "$ARCHIVE" --owner=0 --group=0 --sort=name \
    --transform 's,^,krunner-layoutfix/,' "${FILES[@]}"
echo "$ARCHIVE"
