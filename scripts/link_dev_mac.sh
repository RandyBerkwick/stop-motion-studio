#!/bin/sh
# Links this repo's add-on into Blender on macOS, so edits show up after
# F3 > "Reload Scripts" (no reinstalling).
#
#   scripts/link_dev_mac.sh          uses the version of /Applications/Blender.app
#   scripts/link_dev_mac.sh 5.2      or name the version yourself
set -e

APP=${BLENDER_APP:-/Applications/Blender.app}
BV=$1
if [ -z "$BV" ] && [ -f "$APP/Contents/Info.plist" ]; then
  FULL=$(/usr/bin/defaults read "$APP/Contents/Info" CFBundleShortVersionString 2>/dev/null || true)
  BV=$(echo "$FULL" | sed -n 's/^\([0-9][0-9]*\.[0-9][0-9]*\).*/\1/p')
fi
case "$BV" in
  [0-9]*.[0-9]*) ;;
  *) echo "Couldn't tell which Blender version to link into (got '${BV}')."
     echo "Run it with the version, e.g.: scripts/link_dev_mac.sh 5.2"; exit 1 ;;
esac

SRC="$(cd "$(dirname "$0")/.." && pwd)/stop_motion_studio"
DEST="$HOME/Library/Application Support/Blender/$BV/extensions/user_default"
mkdir -p "$DEST"
if [ -e "$DEST/stop_motion_studio" ] && [ ! -L "$DEST/stop_motion_studio" ]; then
  echo "A real install already exists at $DEST/stop_motion_studio."
  echo "Remove it in Blender (Preferences > Get Extensions) first."; exit 1
fi
ln -sfn "$SRC" "$DEST/stop_motion_studio"
echo "Linked Blender $BV: $DEST/stop_motion_studio -> $SRC"
echo "Restart Blender, then enable Stop Motion Studio in Preferences > Add-ons."
