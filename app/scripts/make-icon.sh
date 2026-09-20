#!/bin/bash
# Make app/Moblee.icns from the icon the app draws itself.
#   bash app/scripts/make-icon.sh        (after app/scripts/build-app.sh)
# The work is done under ~/Library/Caches/moblee-build; only the finished
# Moblee.icns is written into app/. Run it again only when the icon's drawing
# (Snapshots.swift, drawIcon) changes.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_src="$(dirname "$here")"
out="${MOBLEE_BUILD_DIR:-$HOME/Library/Caches/moblee-build}"
bin="$(cat "$out/latest.txt")/Contents/MacOS/Moblee"
work="$out/icon-$(date '+%Y%m%d-%H%M%S')"
set="$work/Moblee.iconset"
mkdir -p "$set"

MOBLEE_PRACTICE=1 "$bin" --icon "$work/icon-1024.png"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$work/icon-1024.png" --out "$set/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" "$work/icon-1024.png" --out "$set/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$set" -o "$work/Moblee.icns"
cp "$work/Moblee.icns" "$app_src/Moblee.icns"
echo "Made: $app_src/Moblee.icns"
