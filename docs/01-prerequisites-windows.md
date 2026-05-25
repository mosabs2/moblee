# Prerequisites — Windows

This is the Windows companion to `01-prerequisites.md` (which covers the macOS path). Moblee v0.2 supports Windows 10 and 11 with a slightly different toolchain to the Mac path and with reduced automation around Claude itself. Read the trade-offs in `docs/07-windows-workflow.md` before deciding whether the Windows track suits you.

If you have any access to a Mac, the macOS path is materially smoother and is still the default. The Windows track exists so that you can begin without one and migrate later without losing the vault you build.

## What you will install

A list, with the install steps below.

- **Windows 10 22H2 or Windows 11.** Earlier versions are not supported.
- **Obsidian for Windows**, free. The reading layer; works identically on Windows and Mac.
- **Git for Windows**, free. The audit trail. Bundles a small Bash shell which Moblee scripts can use as a fallback if you prefer Bash to PowerShell.
- **A Claude account on claude.ai**, free or paid. Web chat is your primary Claude interface on the Windows track. There is no Cowork desktop application on Windows in v0.2, and Claude Code on Windows runs but is documented as advanced rather than default.
- **Python 3 for Windows**, optional. Required only if you later want to render wiki pages to PDF via the bundled `wiki-to-pdf` skill; the skill is documented as Mac-targeted in v0.2 and is not part of the default Windows install path.
- **A modern PowerShell.** PowerShell 7 is recommended (download from [github.com/PowerShell/PowerShell](https://github.com/PowerShell/PowerShell)) but the Windows 11 built-in Windows PowerShell 5.1 also works for the install script.

## Step by step

### 1. Obsidian

Download the Windows installer from [obsidian.md](https://obsidian.md). Run it. Accept the defaults. Obsidian does not need an account; you can open any folder of markdown files as a vault. Skip the "Sign up for Obsidian Sync" prompt unless you specifically want sync across devices later (it is paid; not required for Moblee).

### 2. Git for Windows

Download from [git-scm.com/download/win](https://git-scm.com/download/win). Run the installer. The defaults are sensible; accept them through the wizard. The one option worth pausing on is the default editor; pick something you recognise (Notepad, VS Code if you have it installed) rather than Vim if you are new to git.

After installing, open PowerShell and verify:

```powershell
git --version
```

If you see a version string, you are set. The installer also bundles **Git Bash**, a small Bash shell environment, which Moblee scripts can use as a fallback if you prefer Bash to PowerShell.

### 3. Configure git identity

Tell git who you are. This information is recorded on every commit (the audit trail of changes to your vault).

```powershell
git config --global user.name "Your Name"
git config --global user.email "your@email"
```

### 4. Claude

Go to [claude.ai](https://claude.ai) and sign in or create an account. The free tier works for getting started; the Pro plan removes message-volume limits and is useful once your wiki is established. The Windows track does not use Cowork (Mac-only) or Claude Code by default; web chat at claude.ai is your Claude interface.

### 5. PowerShell 7 (recommended)

Windows 11 ships with Windows PowerShell 5.1 by default, which works for the Moblee install. PowerShell 7 is the modern cross-platform replacement and is generally smoother for everyday command-line work. Download the Windows installer from [github.com/PowerShell/PowerShell/releases](https://github.com/PowerShell/PowerShell/releases) (look for the `.msi` for x64) and run it. After install, open `pwsh` (the PowerShell 7 shell) instead of `powershell` (the legacy 5.1 shell) when running Moblee scripts.

### 6. Python 3 (optional, deferred)

You only need Python on the Windows track if you decide to author PDFs of wiki pages using the bundled `wiki-to-pdf` skill, and the skill is documented as Mac-targeted in v0.2. If you want to try it on Windows, install Python 3.11 or later from [python.org](https://www.python.org/downloads/) and add it to PATH during install. The `wiki-to-pdf` skill itself uses WeasyPrint, which on Windows requires GTK runtime libraries that are fiddlier to install than the Homebrew route on Mac; consider this an advanced setup rather than a default.

## Verification

After installing the above, open PowerShell and check each component:

```powershell
git --version            # Should print "git version 2.x.x..."
obsidian --version       # May or may not work from CLI depending on install path; if not, just check the Obsidian app opens
python --version         # Optional; expect "Python 3.11.x" or later if you installed Python
```

If git is the only one of the four that prints a version, you are ready for the install script. Obsidian and Claude do not need command-line verification.

## What about WSL (Windows Subsystem for Linux)?

WSL2 is an alternative path: it gives you a real Ubuntu shell inside Windows, where the original `scripts\install.sh` Bash script would run identically to the Mac version. The Moblee v0.2 release supports both approaches:

- **Native Windows (this document)**: use PowerShell; install via `scripts\install.ps1`; vault lives at a Windows path like `C:\Users\You\Wiki\MyWiki`.
- **WSL2**: install Ubuntu via the Microsoft Store, then run the original Bash install script from inside WSL; the vault lives at a Linux path like `/home/you/Wiki/MyWiki`. Obsidian on Windows can open WSL paths via `\\wsl.localhost\Ubuntu\home\you\Wiki\MyWiki`, but the cross-filesystem performance is a small cost.

For most Windows users new to the Karpathy pattern, native Windows is simpler. WSL2 is the right choice if you are already comfortable in a Linux shell and want the Bash automation that the Mac path gets.

## Next

Once everything in this list is installed, return to `docs/02-install-windows.md` for the Windows install walkthrough.
