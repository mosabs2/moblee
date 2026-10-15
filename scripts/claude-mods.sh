#!/usr/bin/env bash
# claude-mods.sh - the Moblee mods: the small additions Claude makes to its own
# screen. There is one of them in 0.10.0, the band above the prompt that says
# when a long conversation has gone cold.
#
# This file declares functions and sentences and runs nothing of its own. It is
# sourced by scripts/install.sh and scripts/update.sh, which both have to do the
# same three things: lay the mods into the wiki, find a Claude new enough to
# take them, and register them. Written here once rather than in both scripts,
# because the two drifting apart is how an owner comes to have the band after an
# install and not after an update.
#
# The mods live in the wiki, at <vault>/scripts/claude-mods/, and Claude is
# pointed at that folder. So they travel with the wiki, an update refreshes them
# in place, and nothing of Moblee's is hidden away in a folder the owner cannot
# see.

# ----- the facts, in one place ------------------------------------------------
MODS_MARKETPLACE="moblee-mods"
MODS_PLUGIN="cold-cache-warning@moblee-mods"
MODS_IN_VAULT="scripts/claude-mods"
# Mods are a Claude Code feature, and it arrived in 2.1.287. An older Claude
# does not know the commands below and must not be asked to run them.
MODS_MIN_ENGINE="2.1.287"

# The sentences Moblee says about the mods, said in the same words wherever they
# are printed - the screen, the install diary, the check-up - so that the three
# cannot drift apart. The check-up carries its own copy of the first one, in its
# own file, because it is a Python program and reads none of this.
MODS_NO_ENGINE_SENTENCE="The Claude on this Mac is older than the band above the prompt needs, so the band was not installed; it appears on its own once Claude has updated itself, and nothing else is affected."
MODS_CHATGPT_SENTENCE="Moblee's band above the prompt is one of Claude's own additions, so there is nothing to install for a wiki used with ChatGPT alone."
# (v0.10.0) Not "costs full price": an owner on a subscription is not charged for
# a message at all, and a sentence that says they are is alarming and not plainly
# true. What is true for everybody is that the whole conversation gets read again.
MODS_YES_SENTENCE="Claude's band above the prompt is in place: it says when a long conversation has gone cold, so you know before your next message makes Claude read the whole of it again."

# What the last call to mods_do decided. One of:
#   installed   the band was registered on this run
#   already     it was registered before this run, and still is
#   updated     it was already there and was brought up to date
#   old-claude  no Claude on this Mac is new enough yet (MODS_NO_ENGINE_SENTENCE)
#   chatgpt     the wiki is used with ChatGPT alone (MODS_CHATGPT_SENTENCE)
#   no-mods     this copy of Moblee ships no mods folder
#   failed      a Claude new enough was found and the commands did not work
MODS_STATE=""
# What mods_copy did: added, refreshed, same or none.
MODS_COPIED=""
# The engine mods_find_engine settled on, and what it found on the way.
MODS_ENGINE=""          # the full path of a Claude new enough, or empty
MODS_ENGINE_VERSION=""  # its version
MODS_ENGINE_WHERE=""    # "on the PATH" or "in the Claude app"
MODS_ENGINE_BEST=""     # the newest version seen at all, qualifying or not
# The output and exit code of the last engine command mods_engine_run ran.
MODS_OUT=""
MODS_CODE=0

# ----- plumbing ---------------------------------------------------------------

# The diary both scripts keep. Called through this so that the helper can be
# sourced by something that keeps no diary (a test) without failing.
mods_diary() {
  if declare -f diary >/dev/null 2>&1; then diary "$*"; fi
}

# mods_version_of <engine> : the version it prints, as bare numbers, or nothing.
# `claude --version` prints "2.1.295 (Claude Code)"; only the numbers are read,
# so a build note or a suffix after them makes no difference.
mods_version_of() {
  local engine="$1"
  printf '%s' "$("$engine" --version 2>/dev/null < /dev/null \
                   | head -1 | tr -d '\r' \
                   | sed -n 's/^[^0-9]*\([0-9][0-9.]*[0-9]\).*/\1/p' || true)"
}

# mods_newer <a> <b> : true when a is a later version than b. By number, not by
# string: 2.1.295 is later than 2.1.9, which a plain string test gets wrong.
mods_newer() {
  [[ -n "$1" && "$1" != "$2" ]] || return 1
  [[ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)" == "$1" ]]
}

# mods_version_ok <version> : true when it is new enough to take a mod.
mods_version_ok() {
  [[ -n "$1" ]] || return 1
  [[ "$1" == "$MODS_MIN_ENGINE" ]] && return 0
  mods_newer "$1" "$MODS_MIN_ENGINE"
}

# The Claude app's own engines, newest first. One folder per version, with a
# build folder inside it, and `sort -rV` reads those version folders as numbers.
mods_app_engines() {
  ls -d "$HOME/Library/Application Support/Claude/claude-code"/*/*/claude.app/Contents/MacOS/claude 2>/dev/null \
    | sort -rV || true
}

# mods_find_engine : find a Claude new enough to take a mod, and say where from.
# Two places, in this order:
#   1. the `claude` on the owner's own PATH, which is the one they type;
#   2. the engine inside the Claude app, newest version first, which is there
#      whether or not the command line was ever set up and is the one that
#      updates itself.
# An engine that is there but too old is not an answer; its version is kept in
# MODS_ENGINE_BEST so that the diary can say what was found.
mods_find_engine() {
  MODS_ENGINE=""; MODS_ENGINE_VERSION=""; MODS_ENGINE_WHERE=""; MODS_ENGINE_BEST=""
  local cand v
  cand="$(command -v claude 2>/dev/null || true)"
  if [[ -n "$cand" ]]; then
    v="$(mods_version_of "$cand")"
    if mods_newer "$v" "$MODS_ENGINE_BEST"; then MODS_ENGINE_BEST="$v"; fi
    if mods_version_ok "$v"; then
      MODS_ENGINE="$cand"; MODS_ENGINE_VERSION="$v"; MODS_ENGINE_WHERE="on the PATH"
      return 0
    fi
  fi
  while IFS= read -r cand; do
    [[ -n "$cand" && -x "$cand" ]] || continue
    v="$(mods_version_of "$cand")"
    if mods_newer "$v" "$MODS_ENGINE_BEST"; then MODS_ENGINE_BEST="$v"; fi
    if mods_version_ok "$v"; then
      MODS_ENGINE="$cand"; MODS_ENGINE_VERSION="$v"; MODS_ENGINE_WHERE="in the Claude app"
      return 0
    fi
  done < <(mods_app_engines)
  return 1
}

# mods_engine_run <args...> : the engine, with nothing to read from, its output
# in MODS_OUT and its exit code in MODS_CODE. Never stops the calling script:
# the mods are an addition to Claude's screen and no part of the wiki depends on
# them, so a failure here is reported and the install carries on.
mods_engine_run() {
  MODS_OUT="$("$MODS_ENGINE" "$@" 2>&1 < /dev/null)" && MODS_CODE=0 || MODS_CODE=$?
  mods_diary "    \$ claude $* -> exit $MODS_CODE"
  local l
  while IFS= read -r l; do
    [[ -n "$l" ]] && mods_diary "    | $l"
  done <<< "$MODS_OUT"
  return 0
}

# ----- the mods in the wiki ---------------------------------------------------

# mods_same <pack mods folder> <the wiki's copy> : true when every file Moblee
# ships is there and identical. Anything extra in the wiki's copy is not counted
# a difference: Claude writes generated type files into the folder it reads a mod
# from, and a copy that was "different" for that reason would be replaced, and
# backed up, at every single update.
mods_same() {
  local src="$1" dst="$2" out
  out="$(diff -rq -x __pycache__ -x .DS_Store "$src" "$dst" 2>&1 \
           | awk -v p="Only in $dst" 'index($0, p) != 1' || true)"
  [[ -z "$out" ]]
}

# mods_copy <package root> <vault> : lay the mods into the wiki, only when they
# differ from the ones already there, the way the pack copies scripts/hooks and
# scripts/wiki-galaxy. Sets MODS_COPIED.
mods_copy() {
  local pack="$1" vault="$2"
  local src="$pack/mods" dst="$vault/$MODS_IN_VAULT"
  MODS_COPIED=none
  [[ -d "$src" ]] || return 0
  if [[ -d "$dst" ]]; then
    if mods_same "$src" "$dst"; then
      MODS_COPIED=same
      return 0
    fi
    MODS_COPIED=refreshed
    # The updater's promise: nothing it replaces is lost. It keeps the old copy
    # in ~/.config/moblee/backups/<stamp>/, and keep_copy is its own function for
    # that; the installer has no such function and lays these down fresh.
    if declare -f keep_copy >/dev/null 2>&1; then keep_copy "$dst"; fi
  else
    MODS_COPIED=added
  fi
  mkdir -p "$dst"
  cp -R "$src/." "$dst/"
  return 0
}

# ----- registering them with Claude -------------------------------------------

# mods_plugin_installed : true when Claude already has the band installed.
# --json first, as the checklist does, with the plain listing as the fallback
# for an engine that does not take it.
mods_plugin_installed() {
  local out
  out="$("$MODS_ENGINE" plugin list --json 2>/dev/null < /dev/null || true)"
  if [[ -z "$out" ]]; then
    out="$("$MODS_ENGINE" plugin list 2>/dev/null < /dev/null || true)"
  fi
  printf '%s' "$out" | grep -qF -- "$MODS_PLUGIN"
}

# mods_marketplace_known <vault> : true when Claude already reads the mods from
# this wiki's own folder. A wiki that has been moved or renamed since the first
# install is known under its old folder, which is no longer there, so the source
# is added again rather than updated.
#
# The test is the folder's path as plain text, so a path written two ways that
# mean the same folder — /private in front of it, a doubled slash in the middle
# — reads as "not known". That costs one `plugin marketplace add`, which is
# idempotent and says so ("already on disk"), and never costs anything else;
# the opposite mistake, taking a stale folder for the right one, would leave an
# owner's band reading from a wiki that is no longer there.
mods_marketplace_known() {
  local vault="$1" out
  out="$("$MODS_ENGINE" plugin marketplace list 2>/dev/null < /dev/null || true)"
  printf '%s' "$out" | grep -qF -- "$vault/$MODS_IN_VAULT"
}

# mods_install_plugin : add the marketplace from the wiki's folder and install
# the band at user scope. --yes is needed because nothing here runs on a
# terminal; an engine that does not know the option is asked again without it.
mods_install_plugin() {
  local vault="$1"
  mods_engine_run plugin marketplace add "$vault/$MODS_IN_VAULT"
  if [[ $MODS_CODE -ne 0 ]]; then
    MODS_STATE=failed
    return 1
  fi
  mods_engine_run plugin install --scope user --yes "$MODS_PLUGIN"
  if [[ $MODS_CODE -ne 0 ]] && printf '%s' "$MODS_OUT" | grep -qi "unknown option"; then
    mods_engine_run plugin install --scope user "$MODS_PLUGIN"
  fi
  if [[ $MODS_CODE -eq 0 ]]; then
    MODS_STATE=installed
    return 0
  fi
  MODS_STATE=failed
  return 1
}

# mods_update_plugin : bring the marketplace and the band up to date.
mods_update_plugin() {
  local vault="$1"
  if ! mods_marketplace_known "$vault"; then
    # the wiki has moved since, or the source was never added on this Mac
    mods_engine_run plugin marketplace add "$vault/$MODS_IN_VAULT"
  fi
  mods_engine_run plugin marketplace update "$MODS_MARKETPLACE"
  if [[ $MODS_CODE -ne 0 ]]; then
    mods_engine_run plugin marketplace add "$vault/$MODS_IN_VAULT"
    if [[ $MODS_CODE -ne 0 ]]; then
      MODS_STATE=failed
      return 1
    fi
  fi
  mods_engine_run plugin update --scope user "$MODS_PLUGIN"
  if [[ $MODS_CODE -ne 0 ]] && printf '%s' "$MODS_OUT" | grep -qi "unknown option"; then
    mods_engine_run plugin update "$MODS_PLUGIN"
  fi
  if [[ $MODS_CODE -eq 0 ]]; then
    MODS_STATE=updated
    return 0
  fi
  MODS_STATE=failed
  return 1
}

# ----- the whole thing, as the installer and the updater call it --------------
#
# mods_do <package root> <vault> <assistant> <install|update> [indent]
#
# Lays the mods into the wiki, finds an engine, registers them, and prints the
# plain lines the owner reads. Sets MODS_STATE. Never returns non-zero: the
# caller reads MODS_STATE and decides whether anything is outstanding.
mods_do() {
  local pack="$1" vault="$2" who="$3" mode="$4" pad="${5:-}"
  MODS_STATE=""; MODS_COPIED=none
  if [[ "$who" == "chatgpt" ]]; then
    MODS_STATE=chatgpt
    echo "${pad}$MODS_CHATGPT_SENTENCE"
    mods_diary "mods: $MODS_CHATGPT_SENTENCE"
    return 0
  fi
  if [[ ! -d "$pack/mods" ]]; then
    MODS_STATE=no-mods
    mods_diary "mods: this copy of Moblee ships no mods folder; nothing to install"
    return 0
  fi
  mods_copy "$pack" "$vault"
  case "$MODS_COPIED" in
    added)     echo "${pad}added $MODS_IN_VAULT (Claude's own additions, kept in your wiki)" ;;
    refreshed) echo "${pad}refreshed $MODS_IN_VAULT (Claude's own additions, kept in your wiki)" ;;
  esac
  mods_diary "mods: $MODS_IN_VAULT $MODS_COPIED"

  if ! mods_find_engine; then
    MODS_STATE=old-claude
    echo "${pad}$MODS_NO_ENGINE_SENTENCE"
    mods_diary "mods: $MODS_NO_ENGINE_SENTENCE"
    mods_diary "    the newest Claude found was ${MODS_ENGINE_BEST:-none at all}; mods need $MODS_MIN_ENGINE or later"
    return 0
  fi
  mods_diary "mods: using the Claude $MODS_ENGINE_WHERE, version $MODS_ENGINE_VERSION"

  # Asked once: each engine call takes a moment, and an install that asks the
  # same question twice is an install that takes twice as long to say nothing.
  local have=0
  if mods_plugin_installed; then have=1; fi
  if [[ $have -eq 1 && "$mode" == "update" ]]; then
    mods_update_plugin "$vault" || true
  elif [[ $have -eq 1 ]]; then
    MODS_STATE=already
    if ! mods_marketplace_known "$vault"; then
      # The band is installed, and Claude reads it from some other folder: an
      # earlier wiki on this Mac, or this wiki before it was moved. Point Claude
      # at this wiki's own copy, so that an update to the wiki reaches the band.
      mods_engine_run plugin marketplace add "$vault/$MODS_IN_VAULT"
    fi
  else
    mods_install_plugin "$vault" || true
  fi

  case "$MODS_STATE" in
    installed) echo "${pad}$MODS_YES_SENTENCE" ;;
    updated)   echo "${pad}$MODS_YES_SENTENCE" ;;
    already)   echo "${pad}$MODS_YES_SENTENCE" ;;
    failed)    echo "${pad}Claude's band above the prompt could not be registered, so it will not appear; nothing else is affected, and the install diary says what Claude replied." ;;
  esac
  mods_diary "mods: $MODS_STATE"
  return 0
}
