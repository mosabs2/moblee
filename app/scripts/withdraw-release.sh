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
gh release edit "v$version" --repo mosabs2/moblee --prerelease --latest=false
latest="$(gh release view --repo mosabs2/moblee --json tagName --jq .tagName)"
echo "Withdrawn: v$version is now a pre-release. GitHub's latest is $latest, and that is what every Moblee is offered."
