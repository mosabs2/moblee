# install.ps1 — Lay down a Moblee wiki on this Windows machine.
#
# Run from the root of the Moblee package (the folder containing this script's
# parent `scripts/` directory, alongside `vault-template/` and `skills/`):
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
#
# What it does:
#   1. Asks for a vault name (default: "MyWiki").
#   2. Asks for a vault location (default: "$env:USERPROFILE\Wiki\<vault name>").
#   3. Refuses to overwrite an existing directory.
#   4. Copies vault-template\ to the destination.
#   5. Substitutes [Your Name] and [Your Vault Name] placeholders inside files.
#   6. Initialises a git repository and makes the first commit.
#   7. Optionally adds the `vault` function to your PowerShell profile.
#   8. Prints next-step instructions.
#
# This is the Windows companion to scripts\install.sh. It does the same job in
# PowerShell, using Windows-native paths and conventions.

$ErrorActionPreference = 'Stop'

# ----- locate the package root ------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PackageRoot = Split-Path -Parent $ScriptDir
$VaultTemplate = Join-Path $PackageRoot 'vault-template'

if (-not (Test-Path $VaultTemplate -PathType Container)) {
    Write-Host "Error: vault-template\ not found at $VaultTemplate" -ForegroundColor Red
    Write-Host "Are you running this script from inside the Moblee package?"
    exit 1
}

Write-Host ""
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "  Moblee installer (Windows)"
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script lays down a Karpathy-style Obsidian vault on your Windows machine."
Write-Host ""

# ----- collect user input -----------------------------------------------------
$UserName = Read-Host "Your name (used in templates) [Your Name]"
if ([string]::IsNullOrWhiteSpace($UserName)) { $UserName = '[Your Name]' }

$VaultName = Read-Host "Vault name [MyWiki]"
if ([string]::IsNullOrWhiteSpace($VaultName)) { $VaultName = 'MyWiki' }

$DefaultLocation = Join-Path (Join-Path $env:USERPROFILE 'Wiki') $VaultName
$VaultLocation = Read-Host "Vault location [$DefaultLocation]"
if ([string]::IsNullOrWhiteSpace($VaultLocation)) { $VaultLocation = $DefaultLocation }

# Expand any leading ~ to the user's profile directory.
if ($VaultLocation.StartsWith('~')) {
    $VaultLocation = $VaultLocation -replace '^~', $env:USERPROFILE
}

# ----- safety: refuse to overwrite --------------------------------------------
if (Test-Path $VaultLocation) {
    Write-Host ""
    Write-Host "Error: $VaultLocation already exists." -ForegroundColor Red
    Write-Host "Refusing to overwrite. Pick a different location, or delete the existing"
    Write-Host "directory first if you're sure you want to replace it."
    exit 1
}

# ----- copy the template ------------------------------------------------------
Write-Host ""
Write-Host "Creating vault at $VaultLocation..."
$ParentDir = Split-Path -Parent $VaultLocation
if (-not (Test-Path $ParentDir)) {
    New-Item -ItemType Directory -Path $ParentDir -Force | Out-Null
}
Copy-Item -Path $VaultTemplate -Destination $VaultLocation -Recurse

# ----- substitute placeholders ------------------------------------------------
Write-Host "Substituting placeholders..."

$TextExtensions = @('.md', '.css', '.html', '.py', '.txt', '.yml', '.yaml', '.json')

Get-ChildItem -Path $VaultLocation -Recurse -File | ForEach-Object {
    if ($TextExtensions -contains $_.Extension.ToLower()) {
        $content = Get-Content -Path $_.FullName -Raw -Encoding UTF8
        $content = $content -replace '\[Your Name\]', $UserName
        $content = $content -replace '\[Your Vault Name\]', $VaultName
        $content = $content -replace '\[Your Vault\]', $VaultName
        Set-Content -Path $_.FullName -Value $content -Encoding UTF8 -NoNewline
    }
}

# ----- git init ---------------------------------------------------------------
Write-Host "Initialising git repository..."
Push-Location $VaultLocation
try {
    & git init --quiet --initial-branch=main 2>$null
    if ($LASTEXITCODE -ne 0) {
        & git init --quiet
    }
    & git add . | Out-Null
    & git commit --quiet -m "initial vault from Moblee starter pack" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  (git commit skipped; configure user.name and user.email first via 'git config --global')"
    }
} finally {
    Pop-Location
}

# ----- optional: install the vault function to PowerShell profile -------------
Write-Host ""
$InstallVaultFn = Read-Host "Add the ``vault`` function to your PowerShell profile? [y/N]"
if ($InstallVaultFn -match '^[Yy]$') {
    $MobleeConfigDir = Join-Path $env:USERPROFILE '.config\moblee'
    if (-not (Test-Path $MobleeConfigDir)) {
        New-Item -ItemType Directory -Path $MobleeConfigDir -Force | Out-Null
    }
    Set-Content -Path (Join-Path $MobleeConfigDir 'vault-path') -Value $VaultLocation -Encoding UTF8

    $ProfilePath = $PROFILE.CurrentUserCurrentHost
    $ProfileDir = Split-Path -Parent $ProfilePath
    if (-not (Test-Path $ProfileDir)) {
        New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
    }
    if (-not (Test-Path $ProfilePath)) {
        New-Item -ItemType File -Path $ProfilePath -Force | Out-Null
    }

    $VaultPs1 = Join-Path $ScriptDir 'vault.ps1'
    $Marker = '# >>> moblee vault function >>>'
    $ProfileContent = Get-Content -Path $ProfilePath -Raw -ErrorAction SilentlyContinue
    if ($ProfileContent -and $ProfileContent.Contains($Marker)) {
        Write-Host "  Already present in $ProfilePath, skipped."
    } else {
        Add-Content -Path $ProfilePath -Value ""
        Add-Content -Path $ProfilePath -Value $Marker
        Add-Content -Path $ProfilePath -Value (Get-Content -Path $VaultPs1 -Raw)
        Add-Content -Path $ProfilePath -Value '# <<< moblee vault function <<<'
        Write-Host "  Appended to $ProfilePath."
        Write-Host "  Open a new PowerShell window or run: . `$PROFILE"
    }
}

# ----- done -------------------------------------------------------------------
Write-Host ""
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "  Done."
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your vault lives at:" -ForegroundColor Green
Write-Host "  $VaultLocation"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Open Obsidian, choose `"Open folder as vault`", and point it at:"
Write-Host "       $VaultLocation"
Write-Host ""
Write-Host "  2. Open the vault's Welcome.md and follow it from there. Or paste"
Write-Host "     START_HERE.md into Claude.ai web chat and let it walk you through."
Write-Host ""
Write-Host "  3. Read docs\07-windows-workflow.md for the Windows-specific workflow"
Write-Host "     (Claude.ai web chat in place of Cowork; manual git via vault function;"
Write-Host "     no Claude Code skills on the Windows track for v0.2)."
Write-Host ""
