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

if [ "${1:-}" = "universal" ]; then arch=(--arch arm64 --arch x86_64); else arch=(); fi
swift build --package-path "$app_src" --scratch-path "$out/swiftpm" -c release "${arch[@]}"
# (v0.15.0) Where the program was built is asked of Swift, never assumed. Until
# 27 October 2026 a universal build read swiftpm/apple/Products/Release, which
# newer Swift no longer writes to: every release signed on the MacBook from then
# on carried the program last built there, on 27 September 2026, under whatever
# version number Info.plist gave it. Two checks stop it happening again.
binary="$(swift build --package-path "$app_src" --scratch-path "$out/swiftpm" -c release "${arch[@]}" --show-bin-path)/Moblee"
newest="$(find "$app_src/Sources" "$app_src/Package.swift" -type f -newer "$binary" | head -1)"
if [ ! -x "$binary" ] || [ -n "$newest" ]; then
    echo "The program at $binary is missing or older than its source (${newest:-no program}). Nothing was built."
    exit 1
fi
if [ "${1:-}" = "universal" ] && [ "$(lipo -archs "$binary")" != "x86_64 arm64" ]; then
    echo "The program at $binary is not built for both Apple silicon and Intel ($(lipo -archs "$binary")). Nothing was built."
    exit 1
fi

mkdir -p "$bundle/Contents/MacOS" "$bundle/Contents/Resources/pack" "$bundle/Contents/Frameworks"
cp "$binary" "$bundle/Contents/MacOS/Moblee"
cp "$app_src/Info.plist" "$bundle/Contents/Info.plist"
if [ -f "$app_src/Moblee.icns" ]; then cp "$app_src/Moblee.icns" "$bundle/Contents/Resources/Moblee.icns"; fi

# (v0.15.0) The updater. Sparkle.framework comes from the exact version pinned in
# Package.swift, which Swift Package Manager unpacked under the scratch folder;
# ditto keeps its links. Moblee is not sandboxed, so Sparkle's XPC services are
# not needed (its own documentation says such apps may leave them out), which
# leaves two helpers inside the framework to sign, not four.
framework="$(find "$out/swiftpm/artifacts" -path '*macos-arm64_x86_64/Sparkle.framework' -maxdepth 6 -type d | head -1)"
if [ -z "$framework" ]; then echo "Sparkle.framework was not found under $out/swiftpm/artifacts; nothing was built."; exit 1; fi
rsync -a --exclude XPCServices "$framework/" "$bundle/Contents/Frameworks/Sparkle.framework/"

# (v0.15.0) A practice build for the update test can carry its own update key and
# be allowed to read a list of updates from this Mac itself (plain http to
# 127.0.0.1). Neither is ever set for a release, and release-app.sh refuses a
# build that has either.
if [ -n "${MOBLEE_TEST_ED_KEY:-}" ]; then
    /usr/libexec/PlistBuddy -c "Set :SUPublicEDKey $MOBLEE_TEST_ED_KEY" "$bundle/Contents/Info.plist"
    /usr/libexec/PlistBuddy -c "Add :NSAppTransportSecurity dict" -c "Add :NSAppTransportSecurity:NSAllowsLocalNetworking bool true" "$bundle/Contents/Info.plist"
fi
if [ -n "${MOBLEE_TEST_VERSION:-}" ]; then
    /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString ${MOBLEE_TEST_VERSION%%/*}" -c "Set :CFBundleVersion ${MOBLEE_TEST_VERSION##*/}" "$bundle/Contents/Info.plist"
fi

# the pack, as committed, without the app's own source
git -C "$pack_root" archive --format=tar HEAD -- . ':(exclude)app' \
    | tar -x -C "$bundle/Contents/Resources/pack"

# Signed for this Mac only, inside out: Sparkle's helpers, the framework, then the app.
fw="$bundle/Contents/Frameworks/Sparkle.framework"
codesign --force --sign - "$fw/Versions/B/Autoupdate" >/dev/null 2>&1
codesign --force --sign - "$fw/Versions/B/Updater.app" >/dev/null 2>&1
codesign --force --sign - "$fw" >/dev/null 2>&1
codesign --force --sign - "$bundle" >/dev/null 2>&1

printf '%s\n' "$bundle" > "$out/latest.txt"
echo "Built: $bundle"
