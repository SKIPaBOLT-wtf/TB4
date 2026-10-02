#!/bin/sh
set -eu
ROLE='@ROLE@'
SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DATA=${XDG_DATA_HOME:-"$HOME/.local/share"}
CONFIG=${XDG_CONFIG_HOME:-"$HOME/.config"}
DEST="$DATA/tb4-apps/$ROLE"
case "$DATA:$CONFIG" in *'"'*|*'%'*|*'\\'*) echo 'Unsupported desktop-entry path characters' >&2; exit 2;; esac
case "$DATA" in /*) ;; *) echo 'XDG_DATA_HOME must be absolute' >&2; exit 2;; esac
case "$CONFIG" in /*) ;; *) echo 'XDG_CONFIG_HOME must be absolute' >&2; exit 2;; esac
if [ -x "$DEST/tb4-$ROLE-worker" ]; then
    "$DEST/tb4-$ROLE-worker" --action probe-lock || { echo 'Stop this role and exit its tray app first.' >&2; exit 1; }
fi
[ ! -L "$DEST" ] || { echo 'Refusing symlink installation destination' >&2; exit 1; }
[ ! -e "$DEST/network-table" ] && [ ! -L "$DEST/network-table" ] || { echo 'Move the local network table through TB4 settings before replacing this installation.' >&2; exit 1; }
if [ -d "$DEST" ]; then
    if ! TABLE_FRAMES=$(find "$DEST" \( -name settings.json -o -name settings.pending \) -print -quit 2>/dev/null); then
        echo 'Local data could not be verified. Inspect it before replacing this installation.' >&2
        exit 1
    fi
    [ -z "$TABLE_FRAMES" ] || { echo 'Preserve local table data outside this installation before replacing it.' >&2; exit 1; }
fi
mkdir -p "$DATA/tb4-apps" "$DATA/applications" "$CONFIG/autostart"
STAGE=$(mktemp -d "$DATA/tb4-apps/.$ROLE-install.XXXXXX")
trap 'rm -rf -- "$STAGE"' EXIT HUP INT TERM
cp -R "$SOURCE/tb4-$ROLE/." "$STAGE/"
cp "$SOURCE/uninstall.sh" "$STAGE/uninstall.sh"
chmod +x "$STAGE/uninstall.sh"
"$STAGE/tb4-$ROLE-worker" --action self-test
if [ -e "$DEST.previous" ]; then
    echo 'A rollback copy already exists; inspect it before another upgrade.' >&2
    exit 1
fi
if [ -d "$DEST" ]; then mv "$DEST" "$DEST.previous"; fi
if ! mv "$STAGE" "$DEST"; then
    if [ -d "$DEST.previous" ]; then mv "$DEST.previous" "$DEST"; fi
    exit 1
fi
printf '[Desktop Entry]\nType=Application\nName=TB4 %s\nExec="%s/tb4-%s"\nTerminal=false\nCategories=Utility;\n' "$ROLE" "$DEST" "$ROLE" > "$DATA/applications/tb4-$ROLE.desktop"
if [ "${1:-}" = '--autostart' ]; then
    cp "$DATA/applications/tb4-$ROLE.desktop" "$CONFIG/autostart/tb4-$ROLE.desktop"
fi
printf 'Installed TB4 %s. Open its application menu entry to configure it.\n' "$ROLE"
