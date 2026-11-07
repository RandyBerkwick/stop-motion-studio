#!/bin/sh
# Links this repo's add-on into Blender on macOS, so edits show up after
# F3 > "Reload Scripts" (no reinstalling). Usage: scripts/link_dev_mac.sh [5.2]
set -e
BV=${1:-5.2}
SRC="$(cd "$(dirname "$0")/.." && pwd)/stop_motion_studio"
DEST="$HOME/Library/Application Support/Blender/$BV/extensions/user_default"
mkdir -p "$DEST"
if [ -e "$DEST/stop_motion_studio" ] && [ ! -L "$DEST/stop_motion_studio" ]; then
  echo "A real install already exists at $DEST/stop_motion_studio."
  echo "Remove it in Blender (Preferences > Get Extensions) first."; exit 1
fi
ln -sfn "$SRC" "$DEST/stop_motion_studio"
echo "Linked $DEST/stop_motion_studio -> $SRC"
echo "Restart Blender, then enable Stop Motion Studio in Preferences > Add-ons."
