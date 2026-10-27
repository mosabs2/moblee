#!/bin/bash
# Stop a Moblee release from reaching anyone else (v0.15.0).
#
#   bash app/scripts/withdraw-release.sh 0.15.0
#
# Every owner's Moblee reads the update list from GitHub's "latest" release.
# Marking a release as a pre-release takes it out of "latest", so GitHub's latest
# falls back to the release before, whose list names only the older version, and
# no owner who has not yet updated is offered the withdrawn one. Nothing is
# deleted: the release, its zip and its notes stay on GitHub, and an owner who
# already updated keeps it until a fixed version is published.
#
# Needs the GitHub command line signed in (gh auth status). To put a withdrawn
# release back: gh release edit v<version> --repo mosabs2/moblee --prerelease=false --latest
set -euo pipefail
version="${1:-}"
case "$version" in
    [0-9]*.[0-9]*.[0-9]*) ;;
    *) echo "Give the version to withdraw, for example: bash app/scripts/withdraw-release.sh 0.15.0"; exit 1 ;;
esac
# (v0.15.1) Every Moblee reads its update list from whichever release becomes
# latest, so that release must carry one (appcast.xml). Releases before 0.15.0
# have none, and falling back to one would leave every Moblee's "Check for
# Updates" with nothing to read until a fixed version is out. Such a withdrawal
# is refused: publish the fixed version instead, which replaces it as latest.
next="$(gh release list --repo mosabs2/moblee --exclude-pre-releases --exclude-drafts --limit 20 --json tagName,isLatest --jq '[.[] | select(.tagName != "v'"$version"'")][0].tagName')"
if [ -z "$next" ]; then echo "There is no other release to fall back to. Nothing was changed."; exit 1; fi
if ! gh release view "$next" --repo mosabs2/moblee --json assets --jq '.assets[].name' | grep -qx 'appcast.xml'; then
    echo "Withdrawing v$version would make $next the latest release, and $next has no update list (appcast.xml),"
    echo "so no Moblee could check for updates until a new release is out. Nothing was changed."
    echo "Publish the fixed version instead: it becomes the latest, and every Moblee is offered it."
    exit 1
fi
gh release edit "v$version" --repo mosabs2/moblee --prerelease --latest=false
latest="$(gh release view --repo mosabs2/moblee --json tagName --jq .tagName)"
echo "Withdrawn: v$version is now a pre-release. GitHub's latest is $latest, and that is what every Moblee is offered."
