#!/bin/bash
# Attach the two films to this version's release on GitHub, so the app can play
# them at the end of the install (v0.13.0). Run once the release exists.
#
#   bash app/scripts/attach-films.sh <folder holding the two films>
#
# The folder holds the films under their studio names. Each is checked against
# the size and SHA-256 the app holds in Sources/Moblee/Films.swift before it is
# sent: the app refuses to play a film that differs from those, so a wrong file
# on the release would only ever show the owner "could not be fetched". Nothing
# is deleted; the films are copied under their release names into a folder of
# their own under the Mac's temporary folder.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pack="$(dirname "$(dirname "$here")")"
src="${1:?give the folder holding the two films}"
version="$(tr -d '[:space:]' < "$pack/VERSION")"
films="$pack/app/Sources/Moblee/Films.swift"
stage="$(mktemp -d "${TMPDIR:-/tmp}/moblee-films.XXXXXX")"

pair() {   # studio name, release name
    local from="$src/$1" to="$stage/$2"
    [ -f "$from" ] || { echo "missing: $from"; exit 1; }
    cp "$from" "$to"
    local want_sha want_bytes got_sha got_bytes
    want_sha="$(grep -A3 "\"$2\"" "$films" | grep -o 'sha256: "[0-9a-f]*"' | grep -o '[0-9a-f]\{64\}')"
    want_bytes="$(grep -A3 "\"$2\"" "$films" | grep -o 'bytes: [0-9_]*' | tr -dc '0-9')"
    got_sha="$(shasum -a 256 "$to" | cut -d' ' -f1)"
    got_bytes="$(stat -f %z "$to")"
    if [ "$got_sha" != "$want_sha" ] || [ "$got_bytes" != "$want_bytes" ]; then
        echo "does not match what the app expects: $2 ($got_bytes bytes, $got_sha)"
        exit 1
    fi
    echo "ok  $2  $got_bytes bytes"
}

pair "Moblee 0.12.0 explainer.mp4" "moblee-film-what-moblee-does.mp4"
pair "The Village and the Shelf.mp4" "moblee-film-the-village-and-the-shelf.mp4"

gh release view "v$version" --repo mosabs2/moblee > /dev/null || { echo "no release v$version yet"; exit 1; }
gh release upload "v$version" --repo mosabs2/moblee \
    "$stage/moblee-film-what-moblee-does.mp4" "$stage/moblee-film-the-village-and-the-shelf.mp4"
for f in moblee-film-what-moblee-does.mp4 moblee-film-the-village-and-the-shelf.mp4; do
    code="$(curl -s -o /dev/null -w '%{http_code}' -L -r 0-0 "https://github.com/mosabs2/moblee/releases/download/v$version/$f")"
    echo "$f: $code from the release"
done
echo "Attached to v$version."
