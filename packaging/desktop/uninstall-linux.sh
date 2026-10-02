#!/bin/sh
set -eu
ROLE='@ROLE@'
DATA=${XDG_DATA_HOME:-"$HOME/.local/share"}
CONFIG=${XDG_CONFIG_HOME:-"$HOME/.config"}
DEST="$DATA/tb4-apps/$ROLE"
case "$DATA" in /*) ;; *) echo 'XDG_DATA_HOME must be absolute' >&2; exit 2;; esac
case "$CONFIG" in /*) ;; *) echo 'XDG_CONFIG_HOME must be absolute' >&2; exit 2;; esac
[ ! -L "$DEST" ] || { echo 'Refusing symlink installation destination' >&2; exit 1; }
[ ! -e "$DEST/network-table" ] && [ ! -L "$DEST/network-table" ] || { echo 'Move the local network table through TB4 settings before removing this installation.' >&2; exit 1; }
[ -x "$DEST/tb4-$ROLE-worker" ] || { echo 'Expected installed worker is missing' >&2; exit 1; }
"$DEST/tb4-$ROLE-worker" --action probe-lock || { echo 'Stop this role and exit its tray app first.' >&2; exit 1; }
rm -f -- "$DATA/applications/tb4-$ROLE.desktop" "$CONFIG/autostart/tb4-$ROLE.desktop"
rm -rf -- "$DEST"
printf 'Removed TB4 %s binaries. Private profile and any previous-version rollback copy were preserved.\n' "$ROLE"
