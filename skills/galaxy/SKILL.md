---
name: galaxy
description: Rebuild and open the Wiki Galaxy, the offline 3D knowledge-graph view of the user's wiki vault (detect the vault at runtime; the MOBLEE_VAULT environment variable, then ~/.config/moblee/vault-path, then walking up from the working directory for a folder containing wiki/Index.md). Trigger when the user says "galaxy", "/galaxy", "open the galaxy", "show me the galaxy", "wiki galaxy", "show me my brain in 3D", or any clear variant. Rebuilds the graph data fresh from the wiki with scripts/wiki-galaxy/build.py so the view always reflects current state, then opens the viewer in the user's default browser. Read-only on wiki/; writes only outputs/galaxy/. Do not trigger on lint requests, vault-stats requests, or brain-pattern reflective queries.
---

# Wiki Galaxy launcher (/galaxy)

Open the 3D knowledge-graph view of the wiki, always freshly built. Every wiki page is a node, every wikilink is an edge, and the folders become colour groups automatically, so the picture is the vault as it stands at the moment of the build.

## Finding the vault

Detect the vault root at runtime, in this order: the `MOBLEE_VAULT` environment variable; the path recorded in `~/.config/moblee/vault-path` (the Moblee installer writes it); otherwise walk up from the current working directory looking for a folder containing `wiki/Index.md`. If none of those finds a vault, say so plainly and stop; do not guess a path. The build script performs the same detection itself and exits with a plain-English message if it cannot find the vault, so the two agree.

## Steps

1. **Rebuild** (fast, a few seconds; keeps the view current with the wiki). The script lives in the vault at `scripts/wiki-galaxy/build.py`, put there by the Moblee installer:

   ```bash
   python3 "<vault>/scripts/wiki-galaxy/build.py"
   ```

   It writes `outputs/galaxy/index.html`, `outputs/galaxy/graph-data.js` and `outputs/galaxy/galaxy-libs.min.js` under the vault, and prints two lines: the counts (pages, links, orphans, restricted pages excluded) and the output folder. Needs only the Python 3 that macOS ships; no packages, no network.

2. **Open in the default browser** (fully offline; a `file://` URL is fine, there is no server and no keys):

   ```bash
   open "<vault>/outputs/galaxy/index.html"
   ```

3. **Report** the build line back in one sentence (pages, links, orphans). If the orphan count has moved notably since the last run, say so: orphans are lint fodder. If the build line reports unreadable files dropped, say that too, since the graph is then partial.

## Notes

- **Read-only on `wiki/`.** The only thing written is `outputs/galaxy/`, which is regenerated on every run and can be discarded freely; the wiki is the source, the galaxy is a render of it.
- **Exclusions are enforced inside `build.py` at build time**, not here: `wiki/log.md` is left out so chronology does not distort the knowledge structure, and any page carrying a `restricted:` frontmatter marker is skipped (no node, no title, no preview), as is any folder the vault's `CLAUDE.md` marks restricted and the script knows about. Nothing to do at launch, but never "fix" a missing private page by editing the script's exclusions without the user's explicit say-so.
- **Groups need no configuration.** `Index.md` is the sun, top-level wiki pages are the core, `Wiki Operations/` and `_context.md` are operations, `Daily Notes/` are dust, and every other `wiki/` subfolder gets its own colour from a fixed palette automatically. A new subfolder shows up as a new colour on the next rebuild.
- **The viewer source** lives at `scripts/wiki-galaxy/viewer/galaxy.html`, with the vendored libraries at `scripts/wiki-galaxy/vendor/galaxy-libs.min.js` (three.js, 3d-force-graph and three-spritetext in a single bundle). If the bundle ever needs regenerating, keep all three libraries on one three.js version; mixed versions render a silent black canvas.
- **In-viewer help:** click a node to focus it, shift-click two nodes for the link path between them, right-click for the page card, Recent mode shows where the wiki grew lately, and every node has an Open in Obsidian action.
- If the dashboard is installed, its Galaxy button runs this same build and serves the result at `/galaxy/`; this skill is the terminal-side equivalent.
