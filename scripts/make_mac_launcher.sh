#!/bin/sh
# Makes "Stop Motion Studio.app" in ~/Applications. It starts Blender with
# the Stop Motion Studio app template, so it opens straight into the
# Studio with Blender hidden. (Blender itself isn't rebuilt or copied.)
#
#   scripts/make_mac_launcher.sh
#   BLENDER_APP=/Applications/Blender\ 5.2.app scripts/make_mac_launcher.sh
set -e
APP=${BLENDER_APP:-/Applications/Blender.app}
if [ ! -x "$APP/Contents/MacOS/Blender" ]; then
  echo "Blender not found at $APP (set BLENDER_APP=/path/to/Blender.app)"; exit 1
fi
OUT="$HOME/Applications/Stop Motion Studio.app"
rm -rf "$OUT"
mkdir -p "$OUT/Contents/MacOS" "$OUT/Contents/Resources"
cat > "$OUT/Contents/MacOS/Stop Motion Studio" <<SH
#!/bin/sh
exec "$APP/Contents/MacOS/Blender" --app-template StopMotionStudio "\$@"
SH
chmod +x "$OUT/Contents/MacOS/Stop Motion Studio"
cat > "$OUT/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Stop Motion Studio</string>
  <key>CFBundleDisplayName</key><string>Stop Motion Studio</string>
  <key>CFBundleIdentifier</key><string>com.randyberkwick.stopmotionstudio</string>
  <key>CFBundleExecutable</key><string>Stop Motion Studio</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.1.0</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
</dict>
</plist>
PLIST
# the Studio's own icon (made from app_template/StopMotionStudio/icon.png)
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PNG="$HERE/app_template/StopMotionStudio/icon.png"
if [ -f "$PNG" ] && command -v iconutil >/dev/null 2>&1; then
  SET="$(mktemp -d)/AppIcon.iconset"
  mkdir -p "$SET"
  for sz in 16 32 64 128 256 512; do
    sips -z $sz $sz "$PNG" --out "$SET/icon_${sz}x${sz}.png" >/dev/null
    d=$((sz * 2))
    sips -z $d $d "$PNG" --out "$SET/icon_${sz}x${sz}@2x.png" >/dev/null
  done
  iconutil -c icns "$SET" -o "$OUT/Contents/Resources/AppIcon.icns"
elif [ -f "$APP/Contents/Resources/blender icon.icns" ]; then
  cp "$APP/Contents/Resources/blender icon.icns" "$OUT/Contents/Resources/AppIcon.icns"
fi
/usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string AppIcon" "$OUT/Contents/Info.plist" >/dev/null 2>&1 || true
# Finder caches icons: nudge it
touch "$OUT"
echo "Made $OUT"
echo "Open it from ~/Applications (first time: right-click > Open, as it isn't signed)."
