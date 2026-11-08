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
  <key>CFBundleShortVersionString</key><string>0.9.0</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
</dict>
</plist>
PLIST
# borrow Blender's icon until the Studio has its own
if [ -f "$APP/Contents/Resources/blender icon.icns" ]; then
  cp "$APP/Contents/Resources/blender icon.icns" "$OUT/Contents/Resources/AppIcon.icns"
  /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string AppIcon" "$OUT/Contents/Info.plist" >/dev/null 2>&1 || true
fi
echo "Made $OUT"
echo "Open it from ~/Applications (first time: right-click > Open, as it isn't signed)."
