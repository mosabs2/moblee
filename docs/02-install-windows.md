# Install — Windows

This is the Windows companion to `02-install.md` (which covers macOS). You should already have everything in `01-prerequisites-windows.md` installed before starting here. Total install time once you have the prerequisites in place: 10 to 15 minutes.

## The one-line install

Open PowerShell in the folder where you cloned or downloaded Moblee. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

PowerShell asks for execution-policy permission because Moblee scripts are not signed by Microsoft. The `-ExecutionPolicy Bypass` flag passes that gate for this one invocation without changing your system-wide setting. If you prefer to change your policy permanently to allow local scripts, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` and confirm Yes.

## What the installer asks

Three questions, with sensible defaults you can accept by pressing Enter.

**Your name.** Used to personalise placeholders in the seeded vault pages (your CLAUDE.md, your Welcome.md, your house-style notes). Defaults to `[Your Name]` if you leave it blank, which you can search and replace later.

**Vault name.** The folder name for your vault. Defaults to `MyWiki`. Pick something you will recognise; this is the name Obsidian will show when you open the vault. Examples: `MoSabsWiki`, `MyBrain`, `KhanWiki`. Avoid spaces and special characters for cleaner paths.

**Vault location.** Where on disk to put the vault folder. Defaults to `C:\Users\You\Wiki\<vault name>`. Accepting the default is fine; if you want the vault elsewhere (e.g. on a different drive or under a OneDrive-synced folder), type the full path here.

## What the installer does

In order:

1. Verifies it is being run from inside the Moblee package (sees `vault-template\` in the parent directory).
2. Refuses to overwrite any existing folder at your chosen vault location. If you re-run after a previous install, pick a different location or delete the previous folder by hand first.
3. Copies the entire `vault-template\` tree to your chosen location.
4. Walks every text file (`.md`, `.css`, `.html`, `.py`, `.txt`, `.yml`, `.yaml`, `.json`) inside the new vault and substitutes the placeholders `[Your Name]`, `[Your Vault Name]`, `[Your Vault]` with the values you supplied.
5. Initialises a git repository inside the vault (`git init`), stages every file (`git add .`), and creates an initial commit (`git commit -m "initial vault from Moblee starter pack"`). If your `git config --global user.name` and `user.email` are not set yet, the commit is skipped with a note; configure them and re-run `git commit -m "initial vault"` manually.
6. Asks whether you want the `vault` PowerShell function added to your profile. Answering Yes appends the function from `scripts\vault.ps1` to `$PROFILE.CurrentUserCurrentHost` (typically at `C:\Users\You\Documents\PowerShell\Microsoft.PowerShell_profile.ps1` for PowerShell 7, or the equivalent for Windows PowerShell 5.1). The function reads the vault path from `$env:USERPROFILE\.config\moblee\vault-path`, which the installer also writes.
7. Prints next-step instructions.

## After the installer finishes

Three things to do, in this order.

### 1. Open the vault in Obsidian

Open Obsidian. From the welcome screen, choose **"Open folder as vault"**. Navigate to your vault location and select the vault folder. Obsidian indexes the contents (a few seconds for a fresh vault) and shows you `Welcome.md` as the first page. Read it; it is your orientation to what is in the vault and how to use it.

### 2. Open a fresh PowerShell window (if you installed the vault function)

The `vault` function gets added to your PowerShell profile, but profiles only load when PowerShell starts. Close any existing PowerShell windows and open a fresh one. Type `vault` and press Enter. You should see:

```
── Vault ──
C:\Users\You\Wiki\MyWiki

── Git status ──
(no output means clean)

Working tree clean — nothing to commit.

── Last 5 commits ──
abc1234 initial vault from Moblee starter pack

Ready. Open Claude.ai in your browser, or run 'claude' if you have Claude Code installed.
```

The function does three things on every invocation: cd into the vault, auto-commit any pending changes from earlier sessions, and show recent history. Run it at the start of every session where you intend to touch the vault.

### 3. Start your first Claude conversation

Open [claude.ai](https://claude.ai) in your browser. Start a new conversation. Paste the contents of `START_HERE.md` (from the Moblee package, not from your new vault) as your first message. Claude reads the briefing and guides you through the first conversation: what to ingest first, how the workflow runs, and how the Windows track differs from the documented Mac path. Follow the guide.

## Windows-specific things to know

A short list of things that are different from the Mac path:

- **No Cowork.** Cowork is a Mac-only desktop application as of Moblee v0.2. Your Claude interface on Windows is web chat at claude.ai. The functional difference is that you copy-paste sources into chat by hand (and copy Claude's responses out by hand into your vault), rather than the Mac flow where Cowork can write files into the vault directly.
- **Claude Code is not the default Windows interface.** Claude Code runs on Windows but is documented as an advanced setup in v0.2. The skills bundled in the Moblee package (`brain`, `wiki-capture`, `wiki-to-pdf`) target Claude Code on macOS and are not installed by the Windows install script. See `docs/07-windows-workflow.md` for the workflow you use in their place.
- **Git is manual via the `vault` function.** The Mac path is fully automatic in Claude Code; the Windows path uses the `vault` function to auto-commit on every session start, plus manual `git add . && git commit -m "..."` inside PowerShell at the close of a substantive session. There is no in-Claude commit step on the Windows track.
- **Paths use backslashes.** Wiki content inside your vault should still use forward slashes (`wiki/Geopolitics.md`) because the wiki is markdown, but Windows PowerShell paths to the vault use backslashes (`C:\Users\You\Wiki\MyWiki`).
- **File watchers.** Obsidian watches the vault for changes; if you edit files outside Obsidian (e.g. in VS Code or Notepad), the changes appear in Obsidian's left sidebar within seconds. The audit trail (git commits via the `vault` function) is the same on both platforms.

## Troubleshooting

**The install script fails with "execution policy".** Either run with `-ExecutionPolicy Bypass` as shown above, or change your policy: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` and confirm Yes when prompted.

**The vault function does not run after install.** Open a fresh PowerShell window. Run `$PROFILE` to see the path of your profile file; open it in any editor and confirm the `# >>> moblee vault function >>>` block is at the bottom. If it is missing, re-run the installer.

**`git commit` failed during install with a user.name / user.email warning.** Run `git config --global user.name "Your Name"` and `git config --global user.email "your@email"`, then in PowerShell `cd` to the vault and run `git commit -m "initial vault from Moblee starter pack"` to create the missing initial commit.

**Obsidian shows my vault as empty or with strange characters.** If you used non-ASCII characters in `[Your Name]`, ensure your PowerShell session is using UTF-8: `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` before running the installer. The installer reads and writes files as UTF-8 throughout, but the interactive `Read-Host` prompt depends on the console encoding.

**Claude.ai limits my message volume.** The free tier of Claude has daily message limits; if you hit them mid-session, take a break or upgrade to Claude Pro. The Karpathy pattern works at any rhythm; you do not have to ingest sources the moment you find them.

## Next

Read `docs/07-windows-workflow.md` for the day-to-day Windows-track workflow (claude.ai web chat as the Claude interface, manual ingest workflow, the `vault` function as your session-start ritual, where the skills are missing and what to do instead).
