#!/bin/sh
# Builds dist/stop_motion_studio-<version>.zip for Blender's "Install from Disk".
set -e
cd "$(dirname "$0")/.."
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' stop_motion_studio/blender_manifest.toml)
mkdir -p dist
rm -f "dist/stop_motion_studio-$VERSION.zip"
(cd stop_motion_studio && zip -q -r "../dist/stop_motion_studio-$VERSION.zip" . -x "__pycache__/*" "*.pyc" ".DS_Store")
echo "dist/stop_motion_studio-$VERSION.zip"
