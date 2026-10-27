#!/bin/bash
# Make the Moblee update key, once, on the maintainer's Mac (v0.15.0).
#
#   bash app/scripts/make-update-key.sh
#
# Every Moblee from 0.15.0 on installs an update only if it is signed with this
# key. Sparkle's generate_keys makes it and keeps the private half in this Mac's
# login keychain, where nothing can copy it out without the keychain's own
# permission; it is never written to a file. The public half is written into
# app/Info.plist (SUPublicEDKey), which every owner's app carries.
#
# Run it again at any time: an existing key is kept and only read back, never
# replaced. Replacing it would leave every owner's app refusing every update.
#
# Keep a copy of the private key somewhere safe and off this Mac (a password
# manager), because a MacBook lost without one means the next update cannot be
# signed: `generate_keys -x <file>` exports it, and the file must then be moved
# into the password manager and deleted, never left in a folder or the repository.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_src="$(dirname "$here")"
out="${MOBLEE_BUILD_DIR:-$HOME/Library/Caches/moblee-build}"

swift package --package-path "$app_src" --scratch-path "$out/swiftpm" resolve
tool="$(find "$out/swiftpm/artifacts" -name generate_keys -path '*/bin/*' -maxdepth 5 | head -1)"
if [ -z "$tool" ]; then echo "Sparkle's generate_keys was not found. Nothing was done."; exit 1; fi

echo "Making the update key (or reading the one already made)."
echo "If macOS asks to allow access to the keychain, click Always Allow."
"$tool" >/dev/null
key="$("$tool" -p)"
if [ -z "$key" ]; then echo "No key came back from the keychain. Nothing was written."; exit 1; fi
# Written with sed, on the one line after the SUPublicEDKey key, and not with
# PlistBuddy: PlistBuddy rewrites the whole file and drops every comment in it
# (met on the first run, 27 October 2026).
plist="$app_src/Info.plist"
sed -i '' "/<key>SUPublicEDKey<\/key>/{n;s#<string>.*</string>#<string>$key</string>#;}" "$plist"
if [ "$(/usr/libexec/PlistBuddy -c 'Print :SUPublicEDKey' "$plist")" != "$key" ]; then
    echo "The key could not be written into app/Info.plist. Nothing else was changed."; exit 1
fi
echo
echo "Done. The update key's public half is now in app/Info.plist:"
echo "  $key"
echo "The private half stays in this Mac's keychain."
