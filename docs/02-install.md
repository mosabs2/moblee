# 02. Installing Moblee

This document walks through the step-by-step install of the Moblee starter pack on a Mac. It assumes you have the prerequisites from [01-prerequisites.md](01-prerequisites.md) in place.

## Step 1: get the Moblee package

If Moblee is hosted on a git server, clone it:

```
git clone <repo-url> ~/moblee
cd ~/moblee
```

If you have it as a zip file, unzip it into your home directory and `cd` into the resulting folder. The exact location doesn't matter; the installer can be run from anywhere as long as you point it at the right folder.

To confirm you're in the right place:

```
ls
```

You should see `README.md`, `START_HERE.md`, `LICENSE`, and the `vault-template/`, `skills/`, `scripts/`, and `docs/` folders.

## Step 2: run the vault installer

From inside the Moblee folder:

```
bash scripts/install.sh
```

The script will ask you three questions:

1. **Your name**, used in the templates as the author of the vault. Default: `[Your Name]`.
2. **Vault name**, used as the folder name and substituted into template files. Default: `MyWiki`.
3. **Vault location**, where to put the vault. Default: `~/Wiki/<vault name>`.

You can press Enter at each prompt to accept the default.

After confirming, the script will:

- Copy the `vault-template/` to your chosen location.
- Substitute `[Your Name]`, `[Your Vault Name]`, and `[Your Vault]` placeholders inside all markdown, CSS, HTML, Python, and other text files.
- Initialise a git repository in the new vault and make the first commit.
- Offer to append the `vault` shell function to your `~/.zshrc`.

If you answer yes to the `vault` shell function prompt, the installer also writes the vault path to `~/.config/moblee/vault-path` so the function knows where to `cd` to.

## Step 3: install the skills

```
bash scripts/install-skills.sh
```

This copies the four bundled skills from `skills/<name>/` to `~/.claude/skills/<name>/`. If a skill is already present, the script skips it (use `-f` to force overwrite).

The script then prompts you to install the WeasyPrint dependencies that the `wiki-to-pdf` skill needs. Answer yes if you plan to use the PDF renderer; otherwise no.

## Step 4: configure the vault shell function

If you skipped step 2's `vault` shell function prompt, you can install it manually now. Open `~/.zshrc` in any editor and append the contents of `scripts/vault.sh`:

```
cat scripts/vault.sh >> ~/.zshrc
```

Then write the vault path to its config file:

```
mkdir -p ~/.config/moblee
echo "$HOME/Wiki/<your-vault-name>" > ~/.config/moblee/vault-path
```

Replace `<your-vault-name>` with whatever you chose in step 2.

Open a new Terminal window (or run `source ~/.zshrc`) and type:

```
vault
```

You should see the vault path printed, a brief git status, the message "Working tree clean — nothing to commit", and the ready signal. If you see an error about the path, re-check `~/.config/moblee/vault-path`.

## Step 5: open the vault in Obsidian

Launch Obsidian. On the welcome screen (or `File → Open vault`), choose **Open folder as vault**. Navigate to the location you chose in step 2 and select the vault folder. Obsidian will open it and you'll see `Welcome.md` in the file pane.

Click `Welcome.md` and read it.

## Step 6: verify the install

A quick checklist to confirm everything is in place:

- The vault folder exists at the location you chose.
- `~/.claude/skills/` contains four subfolders: `brain/`, `wiki-capture/`, `wiki-to-pdf/`, `design-your-brand/`.
- Typing `vault` in a new Terminal cds you into the vault and prints the ready signal.
- Obsidian opens the vault and displays `Welcome.md`.
- Running `claude` in the vault's Terminal session starts a Claude Code session that can see your vault.

If anything is missing, re-run the relevant installer; both scripts are idempotent and safe to run again.

## What's next

You have a working vault. Move on to [03-first-conversation.md](03-first-conversation.md) to learn how to work with Claude in this system, or jump to [04-first-ingest.md](04-first-ingest.md) to walk through ingesting your first piece of content.

The fastest path is to paste the contents of `../START_HERE.md` into a Claude session and let Claude walk you through the rest interactively.
