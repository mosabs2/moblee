#!/bin/bash
# Build Moblee.app from the Swift package, for running on this Mac.
#
#   bash app/scripts/build-app.sh            build for this Mac's processor
#   bash app/scripts/build-app.sh universal  build for Apple silicon and Intel
#
# The build and the finished app are kept outside the Moblee folder, under
# ~/Library/Caches/moblee-build, so nothing generated lands in the repository.
# The app is signed for local use only; signing for distribution is a separate
# step at release.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_src="$(dirname "$here")"
out="${MOBLEE_BUILD_DIR:-$HOME/Library/Caches/moblee-build}"
bundle="$out/Moblee.app"

mkdir -p "$out/swiftpm"

if [ "${1:-}" = "universal" ]; then
    swift build --package-path "$app_src" --scratch-path "$out/swiftpm" \
        -c release --arch arm64 --arch x86_64
    binary="$out/swiftpm/apple/Products/Release/Moblee"
else
    swift build --package-path "$app_src" --scratch-path "$out/swiftpm" -c release
    binary="$out/swiftpm/release/Moblee"
fi

mkdir -p "$bundle/Contents/MacOS" "$bundle/Contents/Resources"
cp "$binary" "$bundle/Contents/MacOS/Moblee"
cp "$app_src/Info.plist" "$bundle/Contents/Info.plist"

codesign --force --sign - "$bundle" >/dev/null 2>&1

echo "Built: $bundle"
