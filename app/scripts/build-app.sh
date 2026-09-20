#!/bin/bash
# Build Moblee.app from the Swift package, for running on this Mac.
#
#   bash app/scripts/build-app.sh            build for this Mac's processor
#   bash app/scripts/build-app.sh universal  build for Apple silicon and Intel
#
# The app carries the pack inside it (Contents/Resources/pack): the files of
# the last commit, without the app's own source. Commit before building if a
# change to the pack should travel.
#
# Everything generated is kept outside the Moblee folder, under
# ~/Library/Caches/moblee-build. Each build gets a fresh folder, so an old
# build's files can never linger inside a new app; the newest app's path is
# written to ~/Library/Caches/moblee-build/latest.txt. The app is signed for
# local use only; signing for distribution is a separate step at release.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_src="$(dirname "$here")"
pack_root="$(dirname "$app_src")"
out="${MOBLEE_BUILD_DIR:-$HOME/Library/Caches/moblee-build}"
stamp="$(date '+%Y%m%d-%H%M%S')"
bundle="$out/builds/$stamp/Moblee.app"

mkdir -p "$out/swiftpm"

if [ "${1:-}" = "universal" ]; then
    swift build --package-path "$app_src" --scratch-path "$out/swiftpm" \
        -c release --arch arm64 --arch x86_64
    binary="$out/swiftpm/apple/Products/Release/Moblee"
else
    swift build --package-path "$app_src" --scratch-path "$out/swiftpm" -c release
    binary="$out/swiftpm/release/Moblee"
fi

mkdir -p "$bundle/Contents/MacOS" "$bundle/Contents/Resources/pack"
cp "$binary" "$bundle/Contents/MacOS/Moblee"
cp "$app_src/Info.plist" "$bundle/Contents/Info.plist"
if [ -f "$app_src/Moblee.icns" ]; then cp "$app_src/Moblee.icns" "$bundle/Contents/Resources/Moblee.icns"; fi

# the pack, as committed, without the app's own source
git -C "$pack_root" archive --format=tar HEAD -- . ':(exclude)app' \
    | tar -x -C "$bundle/Contents/Resources/pack"

codesign --force --sign - "$bundle" >/dev/null 2>&1

printf '%s\n' "$bundle" > "$out/latest.txt"
echo "Built: $bundle"
