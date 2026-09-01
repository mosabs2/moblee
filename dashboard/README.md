# Moblee Dashboard

A local web dashboard for your Moblee wiki vault: see the vault's working
state at a glance, ask the wiki questions by voice or text (each ask runs
Claude Code inside the vault), browse past conversations, open the 3D
knowledge galaxy, and draw charts from any CSV you keep in the vault.

Everything runs on your machine. The server binds to 127.0.0.1 only, and the
page's voice features degrade gracefully: ElevenLabs if you have a key, the
macOS `say` command if not, silence otherwise.

## Run it

```
python3 dashboard/server.py
```

Then open http://127.0.0.1:7373 in your browser. That is the whole procedure.
The server finds your vault from `~/.config/moblee/vault-path` (the Moblee
installer writes that file), or from the `MOBLEE_VAULT` environment variable,
or by walking up from the folder you ran it in. Closing the dashboard tab
shuts the server down automatically — there is nothing to stop by hand.

Requirements: Python 3.8+ (standard library only, nothing to install) and the
`claude` CLI on your PATH for the Ask tab.

## The tabs

- **Ask the wiki** — type or speak a question; it runs `claude -p` inside the
  vault and streams the reply, with optional read-aloud. Follow-up messages
  continue the same conversation. You can attach images by drag, paste, or
  the paper-clip button. Everything an ask changes on disk is recorded to
  `outputs/dashboard-audit/` in the vault, and git is the undo path.
- **Orient** — the vault's working state, read live from `wiki/_context.md`:
  active threads, open decisions, the watch list, and today's plan if you
  keep daily notes. Click any item for quick actions (summarise, trace, ask).
- **Recent log** — the newest entries from `wiki/log.md` as a timeline,
  filterable by entry type.
- **Visuals** — every chart configured in `dashboard-charts.json` (see below).
- **History** — past Claude Code conversations in this vault on this machine,
  readable and resumable.

The hero strip above the tabs shows the clock, the wiki page count, the
inbox count (`raw/` plus `Clippings/` — click it to review and ingest), and
the last git commit. The Galaxy button in the header rebuilds and opens the
3D knowledge galaxy (`scripts/wiki-galaxy/`).

## Charts: dashboard-charts.json

The Visuals tab is driven entirely by `dashboard-charts.json`, which lives
next to `server.py`. It holds a list of chart definitions:

```json
{
  "charts": [
    {
      "id": "wiki-growth",
      "title": "Wiki growth",
      "why": "How the knowledge base is compounding — cumulative pages over time.",
      "builtin": "wiki-growth",
      "type": "cumulative",
      "date_x": true
    },
    {
      "id": "weight",
      "title": "Morning weight",
      "why": "The trend matters, not the daily wobble.",
      "csv": "wiki/data/weight.csv",
      "type": "line",
      "x": "date",
      "y": "kg",
      "date_x": true
    }
  ]
}
```

Fields per chart:

- `id` — unique name, used in the API (`/api/chart/custom?id=...`).
- `title` — the card heading.
- `why` — one line on why this chart matters; shown under the title.
- `csv` — path to a CSV file, **relative to the vault root**. The first row
  must be column headers.
- `builtin` — instead of `csv`, name a built-in series computed by the
  server. Currently one exists: `"wiki-growth"` (cumulative wiki page count
  by file date).
- `type` — `"line"`, `"bar"`, or `"cumulative"` (a running total, drawn as a
  stepped line; with no `y` column each row counts one).
- `x` — the column to plot along the x axis.
- `y` — the column to plot as the value, or a list of columns for a
  multi-series chart.
- `date_x` — `true` if the x column holds dates (ISO form `YYYY-MM-DD` works
  best).

Each card shows an "as of" stamp taken from the CSV file's modification
time, so you always know how fresh the data is. When the file lists no
charts, the tab says so and nothing breaks.

## Adding a chart the easy way

You do not need to edit any of this by hand. In the Ask tab (or any Claude
Code session in the vault), just say something like *"add a chart of my
weekly running distance to my dashboard"* — Claude can create or extend a
CSV in the vault, add the matching entry to `dashboard-charts.json`, and the
chart appears the next time you open the Visuals tab. The config file is
re-read on every request, so there is nothing to restart.
