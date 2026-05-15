# ──────────────────────────────────────────────────────────────────────────────
# vault — session-start ritual for your Moblee wiki.
#
# Append this whole block to ~/.zshrc (the Moblee installer offers to do this
# for you), then open a new Terminal or run `source ~/.zshrc`. At the start of
# any session, type `vault` and press Enter before doing anything else.
#
# Configuration:
#   The function reads the vault path from ~/.config/moblee/vault-path first.
#   If that file is missing, it falls back to $HOME/Wiki/MyWiki. Override by
#   editing the path file or by setting $MOBLEE_VAULT_DIR in your shell.
#
# What it does, in order:
#   1. cd into the vault.
#   2. Show what changed since the last commit (`git status --short`).
#   3. If the working tree is dirty, clear any stale .git/index.lock left
#      behind by Cowork's bindfs sandbox, then auto-commit with a
#      "session start <timestamp>: commit pending Cowork changes" message.
#   4. Print the last 5 commits so recent history is visible.
#   5. Confirm you're ready to start Claude Code.
#
# You do not need to remember individual pending-commit scripts; git itself
# tracks every change and `vault` commits whatever has accumulated.
# ──────────────────────────────────────────────────────────────────────────────

vault() {
  local vault_dir

  # --- Resolve the vault path ---------------------------------------------------
  if [[ -n "${MOBLEE_VAULT_DIR:-}" ]]; then
    vault_dir="$MOBLEE_VAULT_DIR"
  elif [[ -f "$HOME/.config/moblee/vault-path" ]]; then
    vault_dir="$(cat "$HOME/.config/moblee/vault-path")"
  else
    vault_dir="$HOME/Wiki/MyWiki"
  fi

  # --- Step 1: cd into the vault ------------------------------------------------
  if ! cd "$vault_dir" 2>/dev/null; then
    print -u2 "vault: could not cd into $vault_dir"
    print -u2 "       (configure the path in ~/.config/moblee/vault-path or"
    print -u2 "        set \$MOBLEE_VAULT_DIR in your shell)"
    return 1
  fi

  printf '\n── Vault ──\n'
  printf '%s\n' "$PWD"

  # --- Step 2: verify we are inside a git repo ---------------------------------
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    print -u2 "vault: $vault_dir is not a git repository."
    return 1
  fi

  # --- Step 3: surface git author identity hint (non-fatal) --------------------
  if [[ -z "$(git config user.name 2>/dev/null)" || -z "$(git config user.email 2>/dev/null)" ]]; then
    printf '\nNote: git user.name / user.email not configured.\n'
    printf '      Set with: git config --global user.name  "Your Name"\n'
    printf '               git config --global user.email "you@example.com"\n'
  fi

  # --- Step 4: show what's changed since the last commit -----------------------
  printf '\n── Git status ──\n'
  git status --short

  # --- Step 5: auto-commit if dirty -------------------------------------------
  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    # Clear any stale Cowork-bindfs index.lock(s) before staging.
    rm -f .git/index.lock .git/index.lock.stale 2>/dev/null

    local stamp
    stamp="$(date '+%Y-%m-%d %H:%M %Z')"

    printf '\n── Auto-commit ──\n'
    printf 'Staging all changes…\n'
    if ! git add .; then
      print -u2 "vault: git add failed."
      return 1
    fi

    if git commit -m "session start ${stamp}: commit pending Cowork changes"; then
      printf 'Pending changes committed.\n'
    else
      print -u2 "vault: git commit failed. Inspect manually."
      return 1
    fi
  else
    printf '\nWorking tree clean — nothing to commit.\n'
  fi

  # --- Step 6: show recent history --------------------------------------------
  printf '\n── Last 5 commits ──\n'
  git log --oneline -5

  # --- Step 7: ready signal ----------------------------------------------------
  printf '\nReady. Run `claude` to start Claude Code.\n\n'
}
