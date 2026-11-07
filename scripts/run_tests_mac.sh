#!/bin/sh
# Runs the headless tests with the installed Blender app.
set -e
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
cd "$(dirname "$0")/.."
for t in tests/test_*.py; do
  echo "== $t"
  "$BLENDER" -b --factory-startup --python-exit-code 1 --python "$t" 2>&1 | grep -v "OpenGL\|capture failed"
done
