#!/bin/bash
# Make the Moblee app that other people can open: built for Apple silicon and
# Intel, signed with the maintainer's Developer ID, notarised by Apple, stapled,
# and zipped.
#
#   bash app/scripts/release-app.sh            sign, notarise, staple, zip
#   bash app/scripts/release-app.sh sign-only  stop after signing (no Apple round trip)
#
# Needs, once, on the maintainer's Mac:
#   - a "Developer ID Application" certificate in the login keychain
#     (Xcode, Settings, Accounts, Manage Certificates, +);
#   - notarisation credentials saved under the name moblee-notary:
#       xcrun notarytool store-credentials "moblee-notary" --apple-id <id> --team-id <team>
#     (the app-specific password is typed by the maintainer and kept in the
#     keychain; it never appears in this script or anywhere in the repository).
#
# Everything is made under ~/Library/Caches/moblee-build; nothing generated
# lands in the repository. The finished zip's path is printed at the end.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="${MOBLEE_BUILD_DIR:-$HOME/Library/Caches/moblee-build}"
profile="${MOBLEE_NOTARY_PROFILE:-moblee-notary}"

pack_root="$(dirname "$(dirname "$here")")"

# The app carries the pack as it was last COMMITTED, so anything not committed
# would be left out of what ships, silently. And the delete guard inside it
# recognises the pack's own scripts by their hashes: shipped stale, the guard
# on every owner's Mac would refuse Claude the pack's own tools (the galaxy
# build, for one). Both are checked before anything is built or sent to Apple.
if [ -n "$(git -C "$pack_root" status --porcelain)" ]; then
    echo "There are changes that are not committed, and they would not be in the app:"
    git -C "$pack_root" status --short
    echo "Commit them (or put them aside), then run this again. Nothing was built."
    exit 1
fi
if ! ( cd "$pack_root" && python3 safety/release-hashes.py --check ); then
    echo "The guard's hashes are out of date. Run:  python3 safety/release-hashes.py"
    echo "then commit safety/bash-guard.py and run this again. Nothing was built."
    exit 1
fi

identity="$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1 | sed -e 's/^[^"]*"//' -e 's/"$//' || true)"
if [ -z "$identity" ]; then echo "No Developer ID Application certificate was found in the keychain."; exit 1; fi
echo "Signing as: $identity"

bash "$here/build-app.sh" universal
app="$(cat "$out/latest.txt")"
version="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$app/Contents/Info.plist")"

# The hardened runtime is required for notarisation. The app needs no
# exceptions to it: it runs the Mac's own bash and python3 on the pack's
# scripts, which are data to those programs.
codesign --force --options runtime --timestamp --sign "$identity" "$app"
codesign --verify --strict --verbose=2 "$app"
lipo -archs "$app/Contents/MacOS/Moblee"

if [ "${1:-}" = "sign-only" ]; then echo "Signed (not notarised): $app"; exit 0; fi

stage="$(dirname "$app")"
ditto -c -k --keepParent "$app" "$stage/Moblee-to-notarise.zip"
xcrun notarytool submit "$stage/Moblee-to-notarise.zip" --keychain-profile "$profile" --wait
xcrun stapler staple "$app"
xcrun stapler validate "$app"
spctl --assess --type execute --verbose=2 "$app"

ditto -c -k --keepParent "$app" "$stage/Moblee-$version.zip"
echo "Ready to share: $stage/Moblee-$version.zip"
