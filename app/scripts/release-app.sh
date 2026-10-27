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
plist_version="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$(dirname "$here")/Info.plist")"
pack_version="$(cat "$pack_root/VERSION")"
if [ "$plist_version" != "$pack_version" ]; then
    echo "The app says it is $plist_version and the pack says it is $pack_version. They must agree:"
    echo "the app compares the two to decide whether to offer an update. Nothing was built."
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

# (v0.15.0) The updater's key. The public half is in Info.plist; the private half
# is in this Mac's keychain, where generate_keys put it, and nowhere else. A build
# whose Info.plist key is missing, or differs from the keychain's, would ship an
# app that refuses every future update, so it is stopped here. So is any test
# setting left in Info.plist, and any key-shaped file in the repository.
if [ -n "${MOBLEE_TEST_ED_KEY:-}${MOBLEE_TEST_VERSION:-}" ]; then
    echo "A test setting (MOBLEE_TEST_ED_KEY or MOBLEE_TEST_VERSION) is set in this Terminal. Close it and use a new window. Nothing was built."
    exit 1
fi
plist_key="$(/usr/libexec/PlistBuddy -c 'Print :SUPublicEDKey' "$(dirname "$here")/Info.plist" 2>/dev/null || true)"
if [ -z "$plist_key" ] || [ "$plist_key" = "SET-BY-MAINTAINER" ]; then
    echo "Info.plist has no update key yet (SUPublicEDKey). Run app/scripts/make-update-key.sh once. Nothing was built."
    exit 1
fi
if /usr/libexec/PlistBuddy -c 'Print :NSAppTransportSecurity' "$(dirname "$here")/Info.plist" >/dev/null 2>&1; then
    echo "Info.plist allows plain local connections (a test setting). Take it out. Nothing was built."
    exit 1
fi
if git -C "$pack_root" ls-files | grep -iE '(ed25519|eddsa|sparkle).*(key|private)|\.pem$|private.?key' ; then
    echo "The files above look like keys and are in the repository. Take them out. Nothing was built."
    exit 1
fi

bash "$here/build-app.sh" universal
app="$(cat "$out/latest.txt")"
version="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$app/Contents/Info.plist")"
build="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$app/Contents/Info.plist")"
sparkle_bin="$(dirname "$(find "$out/swiftpm/artifacts" -name generate_keys -path '*/bin/*' -maxdepth 5 | head -1)")"
if [ ! -x "$sparkle_bin/generate_appcast" ]; then echo "Sparkle's tools were not found under $out/swiftpm/artifacts. Nothing was signed."; exit 1; fi
keychain_key="$("$sparkle_bin/generate_keys" -p 2>/dev/null || true)"
if [ "$keychain_key" != "$plist_key" ]; then
    echo "The update key in Info.plist is not the one in this Mac's keychain."
    echo "  Info.plist: $plist_key"
    echo "  keychain:   ${keychain_key:-none found}"
    echo "Every owner's app trusts the Info.plist key, so updates signed with any other would be refused. Nothing was signed."
    exit 1
fi

# The hardened runtime is required for notarisation. The app needs no
# exceptions to it: it runs the Mac's own bash and python3 on the pack's
# scripts, which are data to those programs.
# (v0.15.0) Sparkle's two helpers and the framework are signed first, inside
# out, as Sparkle's documentation sets out (never --deep).
fw="$app/Contents/Frameworks/Sparkle.framework"
codesign --force --options runtime --timestamp --sign "$identity" "$fw/Versions/B/Autoupdate"
codesign --force --options runtime --timestamp --sign "$identity" "$fw/Versions/B/Updater.app"
codesign --force --options runtime --timestamp --sign "$identity" "$fw"
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

# (v0.15.0) The signed list of updates that every owner's Moblee reads. Made in a
# folder holding only this release's zip and its notes, so the list names this
# version alone; generate_appcast reads the private key from the keychain (macOS
# may ask once to allow it: Always Allow), signs the zip and the list itself, and
# embeds the notes so they are covered by the same signature.
feed="$stage/appcast"
mkdir -p "$feed"
cp "$stage/Moblee-$version.zip" "$feed/"
notes="$(awk -v v="## v$version " 'index($0, v) == 1 {on = 1; next} on && /^## / {exit} on' "$pack_root/CHANGELOG.md")"
if [ -z "$notes" ]; then echo "CHANGELOG.md has no section for $version. The app is ready but no update list was made."; exit 1; fi
printf '%s\n' "$notes" > "$feed/Moblee-$version.md"
"$sparkle_bin/generate_appcast" --embed-release-notes \
    --download-url-prefix "https://github.com/mosabs2/moblee/releases/download/v$version/" \
    --link "https://github.com/mosabs2/moblee/releases/tag/v$version" \
    "$feed"
grep -q "sparkle:edSignature" "$feed/appcast.xml" || { echo "The update list has no signature for the zip. Not ready."; exit 1; }
grep -qE "sparkle:version>$build<|sparkle:version=\"$build\"" "$feed/appcast.xml" || { echo "The update list does not name build $build. Not ready."; exit 1; }
cp "$feed/appcast.xml" "$stage/appcast.xml"
echo "Ready to share: $stage/Moblee-$version.zip"
echo "Its update list: $stage/appcast.xml (attach both to the release)"
