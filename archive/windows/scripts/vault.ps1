# ──────────────────────────────────────────────────────────────────────────────
# vault — session-start ritual for your Moblee wiki on Windows.
#
# This file is the PowerShell companion to scripts\vault.sh (which is the Mac
# version installed into ~/.zshrc). On Windows it is appended to your
# PowerShell profile by the Moblee installer ($PROFILE.CurrentUserCurrentHost),
# OR you can copy the function body into your own profile by hand.
#
# To use the function once installed: open PowerShell, type `vault`, press
# Enter. Run this at the start of any session that will touch the vault.
#
# Configuration:
#   The function reads the vault path from $env:USERPROFILE\.config\moblee\vault-path.
#   If that file is missing, it falls back to $env:USERPROFILE\Wiki\MyWiki.
#   Override by editing the path file or by setting $env:MOBLEE_VAULT_DIR.
#
# What it does, in order:
#   1. cd into the vault.
#   2. Show what changed since the last commit (`git status --short`).
#   3. If the working tree is dirty, auto-commit with a stamped message.
#   4. Print the last 5 commits so recent history is visible.
#   5. Confirm you're ready to start your Claude session.
#
# Windows note: there is no Cowork bindfs / FUSE problem on Windows, so the
# stale-index-lock cleanup the Mac version does is not needed here. Otherwise
# the function mirrors the Mac version step for step.
# ──────────────────────────────────────────────────────────────────────────────

function vault {
    $vaultDir = $null

    # --- Resolve the vault path -----------------------------------------------
    if ($env:MOBLEE_VAULT_DIR -and (Test-Path $env:MOBLEE_VAULT_DIR)) {
        $vaultDir = $env:MOBLEE_VAULT_DIR
    } else {
        $pathFile = Join-Path $env:USERPROFILE '.config\moblee\vault-path'
        if (Test-Path $pathFile) {
            $vaultDir = (Get-Content -Path $pathFile -Raw).Trim()
        } else {
            $vaultDir = Join-Path $env:USERPROFILE 'Wiki\MyWiki'
        }
    }

    # --- Step 1: cd into the vault --------------------------------------------
    if (-not (Test-Path $vaultDir)) {
        Write-Error "vault: could not find $vaultDir"
        Write-Host "       (configure the path in `$env:USERPROFILE\.config\moblee\vault-path"
        Write-Host "        or set `$env:MOBLEE_VAULT_DIR in your shell)"
        return
    }
    Set-Location -Path $vaultDir

    Write-Host ""
    Write-Host "── Vault ──"
    Write-Host (Get-Location).Path

    # --- Step 2: verify we are inside a git repo -----------------------------
    & git rev-parse --is-inside-work-tree 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "vault: $vaultDir is not a git repository."
        return
    }

    # --- Step 3: git author identity hint (non-fatal) ------------------------
    $userName = & git config user.name 2>$null
    $userEmail = & git config user.email 2>$null
    if ([string]::IsNullOrEmpty($userName) -or [string]::IsNullOrEmpty($userEmail)) {
        Write-Host ""
        Write-Host "Note: git user.name / user.email not configured." -ForegroundColor Yellow
        Write-Host "      Set with: git config --global user.name  `"Your Name`""
        Write-Host "                git config --global user.email `"you@example.com`""
    }

    # --- Step 4: show what's changed since the last commit -------------------
    Write-Host ""
    Write-Host "── Git status ──"
    & git status --short

    # --- Step 5: auto-commit if dirty ----------------------------------------
    $porcelain = & git status --porcelain
    if ($porcelain) {
        $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm zzz'

        Write-Host ""
        Write-Host "── Auto-commit ──"
        Write-Host "Staging all changes..."
        & git add .
        if ($LASTEXITCODE -ne 0) {
            Write-Error "vault: git add failed."
            return
        }

        & git commit -m "session start $stamp: commit pending changes"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Pending changes committed."
        } else {
            Write-Error "vault: git commit failed. Inspect manually."
            return
        }
    } else {
        Write-Host ""
        Write-Host "Working tree clean — nothing to commit."
    }

    # --- Step 6: show recent history -----------------------------------------
    Write-Host ""
    Write-Host "── Last 5 commits ──"
    & git log --oneline -5

    # --- Step 7: ready signal ------------------------------------------------
    Write-Host ""
    Write-Host "Ready. Open Claude.ai in your browser, or run 'claude' if you have Claude Code installed."
    Write-Host ""
}
