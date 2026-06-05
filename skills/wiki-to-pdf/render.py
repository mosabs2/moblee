#!/usr/bin/env python3
"""
render.py: wiki-to-pdf
Renders a wiki page (and optionally its cluster notes) as a branded PDF
using your configured brand assets.

Usage:
    python3 render.py --page "[Your Domain]" \
        --vault "[Your Vault]" \
        --output-dir "[Your Vault]/outputs"

Vault detection:
    If --vault is omitted, the script walks upward from the current
    working directory looking for a `.obsidian/` folder, then falls
    back to the `WIKI_TO_PDF_VAULT` environment variable.

Optional flags:
    --with-cluster-notes   Bundle synthesis page with its cluster-note subfolder.
    --archetype            briefing | reference | default | no-cover  (override)
    --variant              filename (override; skips rotation log update)
    --prepared-for         "Recipient Name"   (briefing covers)
    --report-id            "Some ID"          (briefing meta block)
    --brand-mark-name      "Your Brand"       (eyebrow line label; defaults to "")
    --skip-log             Skip appending to wiki/log.md

Render styles:
    --style brand | cv     'brand' (default) is the cover/gradient template.
                           'cv' is the minimalist EB Garamond statement layout
                           with a faint centred monogram watermark and no cover.
    --subtitle "..."       (cv) override the masthead subtitle line; "" suppresses.
    --watermark <file>     (cv) monogram filename for the watermark; defaults to
                           your configured brand mark. Omitted if none is found.
    --footer-label "..."   (cv) running-footer label; defaults to the page title.
    --no-charts            Skip the vega-lite / mermaid fenced-block pre-render
                           (both styles); leave them as plain code blocks.

Charts (optional, both styles):
    Fenced ```vega-lite (JSON) and ```mermaid blocks are pre-rendered to inline
    SVG / PNG. vega-lite needs `pip install vl-convert-python`; mermaid needs the
    global `mmdc` binary (`npm i -g @mermaid-js/mermaid-cli`). If a dependency is
    missing or a block fails, that block degrades to a styled error box and the
    rest of the document still renders.
"""

import argparse
import base64
import datetime
import html as html_lib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

try:
    import vl_convert as vlc          # optional: vega-lite chart rendering
except ImportError:
    vlc = None

# ── Constants ────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).parent

# Default variant pools. Users populate these with their own brand-mark
# variant filenames after running `design-your-brand`. Empty pools fall
# back to the canonical brand mark named in the user's brand.css.
VARIANT_POOLS = {
    "Briefings":   [],
    "Family":      [],
    "Technology":  [],
    "Health":      [],
    "Reference":   [],
    "General":     [],
}

CATEGORY_LABELS = {
    "Briefings":   "Briefings & Advisory",
    "Family":      "Family & Heritage",
    "Technology":  "Technology & Projects",
    "Health":      "Health & Medical",
    "Reference":   "Reference",
    "General":     "",
}

REFERENCE_TITLES = {
    "brand reference",
    "how to use this wiki",
    "karpathy llm wiki pattern",
}

DEFAULT_BRAND_MARK_FILENAME = "monogram.png"

# ── Vault detection ──────────────────────────────────────────────────

def detect_vault(explicit: str | None) -> Path:
    """Resolve the vault path.

    1. Explicit --vault argument wins.
    2. WIKI_TO_PDF_VAULT environment variable.
    3. Walk upward from cwd looking for a `.obsidian/` folder.
    """
    if explicit:
        return Path(explicit).expanduser().resolve()

    env_path = os.environ.get("WIKI_TO_PDF_VAULT")
    if env_path:
        return Path(env_path).expanduser().resolve()

    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".obsidian").is_dir():
            return candidate

    sys.exit(json.dumps({
        "error": "Vault not found. Pass --vault, set WIKI_TO_PDF_VAULT, "
                 "or run from within a vault containing an .obsidian/ folder."
    }))


# ── Page resolution ──────────────────────────────────────────────────

def find_wiki_page(page_name: str, vault: Path) -> Path | None:
    """Find a wiki page by title. Exact stem match first, then case-insensitive."""
    wiki_dir = vault / "wiki"
    if not wiki_dir.exists():
        return None

    # Exact
    exact = wiki_dir / f"{page_name}.md"
    if exact.exists():
        return exact

    # Case-insensitive recursive
    name_lower = page_name.lower()
    for md_file in wiki_dir.rglob("*.md"):
        if md_file.stem.lower() == name_lower:
            return md_file

    return None


# ── Frontmatter ──────────────────────────────────────────────────────

def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Split YAML frontmatter from body. Returns (fm_dict, body_str)."""
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            fm_str = content[3:end].strip()
            body = content[end + 4:].strip()
            try:
                fm = yaml.safe_load(fm_str) or {}
            except yaml.YAMLError:
                fm = {}
            return fm, body
    return {}, content


# ── Category detection ───────────────────────────────────────────────

def determine_category(fm: dict, page_path: Path, title: str, prepared_for: str | None) -> str:
    title_lower = title.lower()
    path_str    = str(page_path).lower()

    # Briefings: explicit prepared_for or title keywords
    if prepared_for:
        return "Briefings"
    briefing_kw = ["briefing", "review for", "prepared for", "session review for"]
    if any(kw in title_lower for kw in briefing_kw):
        return "Briefings"

    # Frontmatter parent
    parent = str(fm.get("parent", "")).lower()
    if "health" in parent or "medical" in parent:
        return "Health"
    if "family" in parent or "heritage" in parent:
        return "Family"
    if "technolog" in parent or "project" in parent:
        return "Technology"
    if "index" in parent and title_lower in REFERENCE_TITLES:
        return "Reference"

    # Frontmatter status
    if fm.get("status") == "reference":
        return "Reference"

    # Path
    if "health" in path_str or "medical" in path_str:
        return "Health"
    if "family" in path_str:
        return "Family"
    if "technolog" in path_str:
        return "Technology"

    # Title keywords
    if title_lower in REFERENCE_TITLES:
        return "Reference"

    return "General"


# ── Archetype detection ──────────────────────────────────────────────

def determine_archetype(category: str, word_count: int, prepared_for: str | None, fm: dict) -> str:
    if word_count < 500:
        return "no-cover"
    if prepared_for or category == "Briefings":
        return "briefing"
    if category == "Reference" or fm.get("status") == "reference":
        return "reference"
    return "default"


# ── Word count ───────────────────────────────────────────────────────

def count_words(text: str) -> int:
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`[^`]+`", " ", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"[#*_\[\]()!|>~]", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    return len(text.split())


# ── Wikilink italicisation ───────────────────────────────────────────

def italicise_wikilinks(text: str) -> str:
    """[[Page]] → *Page*, [[Page|Display]] → *Display*, [[Page#H]] → *Page*."""
    def _repl(m):
        inner = m.group(1)
        if "|" in inner:
            return f"*{inner.split('|', 1)[1]}*"
        if "#" in inner:
            return f"*{inner.split('#', 1)[0]}*"
        return f"*{inner}*"
    return re.sub(r"\[\[([^\]]+)\]\]", _repl, text)


# ── H1 extraction ────────────────────────────────────────────────────

def get_h1(body: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    return m.group(1).strip() if m else fallback


# ── Slug ─────────────────────────────────────────────────────────────

def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# ── TOC ──────────────────────────────────────────────────────────────

def build_toc(html_body: str) -> str:
    h2_re = re.compile(r"<h2[^>]*>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
    entries = [re.sub(r"<[^>]+>", "", m.group(1)).strip() for m in h2_re.finditer(html_body)]
    if not entries:
        return ""
    lines = ['<div class="toc"><h2>Contents</h2>']
    for e in entries:
        lines.append(f'<div class="toc-entry"><span class="toc-title">{e}</span></div>')
    lines.append("</div>")
    return "\n".join(lines)


# ── Asset resolution ─────────────────────────────────────────────────

def find_monogram(vault: Path, variant_filename: str) -> Path | None:
    """Look for the cover monogram variant.

    Searches:
      vault/wiki/Brand Reference/assets/monogram/variations/<name>
      vault/wiki/Brand Reference/assets/monogram/<name>
      vault/wiki/Brand Reference/assets/<name>
    """
    if not variant_filename:
        variant_filename = DEFAULT_BRAND_MARK_FILENAME

    monogram_dir = vault / "wiki" / "Brand Reference" / "assets" / "monogram"
    candidates = [
        monogram_dir / "variations" / variant_filename,
        monogram_dir / variant_filename,
        vault / "wiki" / "Brand Reference" / "assets" / variant_filename,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def find_inline_monogram(vault: Path) -> Path | None:
    """Look for the inline page-header monogram (small, top-right)."""
    candidates = [
        vault / "outputs" / "inline-monogram.png",
        vault / "wiki" / "Brand Reference" / "assets" / "monogram" / DEFAULT_BRAND_MARK_FILENAME,
        vault / "wiki" / "Brand Reference" / "assets" / DEFAULT_BRAND_MARK_FILENAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ── Rotation log ─────────────────────────────────────────────────────

def load_log(output_dir: Path) -> dict:
    path = output_dir / ".wiki-to-pdf-history.json"
    default = {cat: [] for cat in VARIANT_POOLS}
    if path.exists():
        try:
            data = json.loads(path.read_text())
            for cat in default:
                data.setdefault(cat, [])
            return data
        except Exception:
            pass
    return default


def save_log(output_dir: Path, log: dict) -> None:
    path = output_dir / ".wiki-to-pdf-history.json"
    path.write_text(json.dumps(log, indent=2))


def pick_variant(category: str, log: dict, override: str | None) -> str:
    if override:
        return override
    pool   = VARIANT_POOLS.get(category, VARIANT_POOLS["General"])
    if not pool:
        # No pool configured; fall back to the canonical brand mark.
        return DEFAULT_BRAND_MARK_FILENAME
    recent = log.get(category, [])[:2]
    for v in pool:
        if v not in recent:
            return v
    # All in recent (small pool): pick least-recent
    return recent[-1] if recent else pool[0]


def update_log(log: dict, category: str, variant: str) -> dict:
    recent = [variant] + [v for v in log.get(category, []) if v != variant]
    log[category] = recent[:2]
    return log


# ── Summary extraction ───────────────────────────────────────────────

def extract_summary(fm: dict, body: str) -> str:
    if fm.get("summary"):
        return str(fm["summary"])
    plain = re.sub(r"#{1,6}\s+.+", "", body)        # strip headings
    plain = re.sub(r"\[\[([^\]|#]+)[^\]]*\]\]", r"\1", plain)  # wikilinks
    plain = re.sub(r"[*_`#\[\]()!|>~]", " ", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    m = re.search(r"([A-Z][^.!?]{15,}[.!?])", plain)
    return m.group(1).strip() if m else ""


# ── Chart pre-rendering: vega-lite + mermaid fenced blocks ───────────
# A4 body width (210mm − margins) ≈ 680px at 96dpi; mermaid rendered at 2×
# for retina sharpness, scaled back to body width via CSS max-width: 100%.
MERMAID_WIDTH_PX = 1360

CHART_BLOCK_RE = re.compile(
    r'<pre><code class="language-(vega-lite|mermaid)">(.*?)</code></pre>',
    re.DOTALL,
)


def _unescape_code(text: str) -> str:
    return (
        text.replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
            .replace("&amp;", "&")
    )


def _chart_error_block(kind: str, source: str, message: str) -> str:
    return (
        f'<pre class="chart-error" data-chart="{kind}">'
        f'<strong>{kind} render failed:</strong> {html_lib.escape(message)}\n\n'
        f'{html_lib.escape(source)}'
        '</pre>'
    )


def pre_render_charts(html_text: str) -> str:
    """Replace fenced ```vega-lite and ```mermaid blocks with inline SVG / PNG.

    A block that fails to render (or whose optional dependency is missing)
    becomes a styled <pre class="chart-error"> rather than failing the whole
    document. v1 inlines JSON only (no external chart-ref indirection).
    """
    def repl(match: re.Match) -> str:
        kind = match.group(1)
        source = _unescape_code(match.group(2))
        try:
            if kind == "vega-lite":
                if vlc is None:
                    raise RuntimeError(
                        "vl_convert not installed (pip install vl-convert-python)"
                    )
                spec = json.loads(source)
                svg = vlc.vegalite_to_svg(spec)
                return f'<div class="chart vega-lite-chart">{svg}</div>'
            # mermaid: shell out to mmdc, embed PNG (WeasyPrint strips the
            # <foreignObject> HTML labels mermaid 11 emits as SVG, so PNG via
            # Puppeteer is the durable path).
            in_path = out_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".mmd", delete=False, encoding="utf-8"
                ) as in_f:
                    in_f.write(source)
                    in_path = in_f.name
                out_path = tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False
                ).name
                result = subprocess.run(
                    ["mmdc", "-i", in_path, "-o", out_path,
                     "-w", str(MERMAID_WIDTH_PX), "-b", "transparent"],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        (result.stderr or result.stdout or "mmdc failed").strip()
                        or "mmdc not installed (npm i -g @mermaid-js/mermaid-cli)"
                    )
                b64 = base64.b64encode(Path(out_path).read_bytes()).decode("ascii")
                return (
                    '<div class="chart mermaid-chart">'
                    f'<img src="data:image/png;base64,{b64}" alt="Mermaid diagram"/>'
                    '</div>'
                )
            except FileNotFoundError:
                raise RuntimeError("mmdc not installed (npm i -g @mermaid-js/mermaid-cli)")
            finally:
                for p in (in_path, out_path):
                    if p:
                        Path(p).unlink(missing_ok=True)
        except Exception as exc:                       # noqa: BLE001
            return _chart_error_block(kind, source, str(exc))

    return CHART_BLOCK_RE.sub(repl, html_text)


# ── CV / statement style helpers ─────────────────────────────────────

def _cv_postprocess(html_text: str) -> str:
    """Map generic markdown HTML onto the CV stylesheet's classes.

    H2 headings become brand-colour section labels; the opening paragraph,
    if the body starts with one, becomes the EB Garamond lede.
    """
    html_text = html_text.replace("<h2>", '<h2 class="section">')
    if html_text.lstrip().startswith("<p>"):
        html_text = re.sub(r"<p>", '<p class="lede">', html_text, count=1)
    return html_text


def _css_string_escape(s: str) -> str:
    """Escape a string for use inside a CSS content: "..." literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _extract_root_block(brand_css: str) -> str:
    """Pull the :root {...} variable block out of brand.css so cv.css can
    reference the same brand variables (one design-your-brand run drives both
    render styles). Returns "" if no :root block is found."""
    m = re.search(r":root\s*\{[^}]*\}", brand_css, re.DOTALL)
    return m.group(0) if m else ""


def find_watermark(vault: Path, override: str | None) -> Path | None:
    """Resolve the CV-style watermark monogram. An explicit --watermark
    filename wins; otherwise fall back to the configured brand mark. Returns
    None if nothing is found (the CV style then renders with no watermark)."""
    if override:
        found = find_monogram(vault, override)
        if found:
            return found
    return find_inline_monogram(vault)


def render_cv(args: argparse.Namespace) -> None:
    """Minimalist CV / statement render: no cover, no variant rotation,
    EB Garamond masthead, brand-colour section labels, faint monogram
    watermark (only if configured). Self-contained path."""
    vault      = detect_vault(args.vault)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir \
                 else vault / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    page_file = find_wiki_page(args.page, vault)
    if not page_file:
        sys.exit(json.dumps({"error": f"Page not found: {args.page}"}))

    raw = page_file.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)
    title = get_h1(body, page_file.stem)
    summary = extract_summary(fm, body)

    # Strip the leading H1 (rendered as the masthead) to avoid duplication.
    body_md = re.sub(r"^#\s+.+?\n+", "", body, count=1)
    body_md = italicise_wikilinks(body_md)

    md_renderer = markdown.Markdown(extensions=["tables", "fenced_code"])
    body_html = md_renderer.convert(body_md)
    if not args.no_charts:
        body_html = pre_render_charts(body_html)
    body_html = _cv_postprocess(body_html)

    subtitle = args.subtitle if args.subtitle is not None else summary
    footer_label = args.footer_label or title

    watermark_path = find_watermark(vault, args.watermark)
    watermark_src = watermark_path.as_uri() if watermark_path else ""

    brand_css = (SKILL_DIR / "brand.css").read_text(encoding="utf-8")
    cv_css = (SKILL_DIR / "cv.css").read_text(encoding="utf-8")
    combined_css = _extract_root_block(brand_css) + "\n" + cv_css

    env      = Environment(loader=FileSystemLoader(str(SKILL_DIR)), autoescape=False)
    template = env.get_template("template-cv.html")
    full_html = template.render(
        title            = title,
        subtitle         = subtitle,
        body_html        = body_html,
        watermark_src    = watermark_src,
        footer_label_css = _css_string_escape(footer_label),
        cv_css           = combined_css,
    )

    slug = slugify(title)
    date_slug = datetime.date.today().strftime("%Y-%m-%d")
    html_out = output_dir / f"{slug}-{date_slug}.html"
    pdf_out  = output_dir / f"{slug}-{date_slug}.pdf"
    html_out.write_text(full_html, encoding="utf-8")

    try:
        HTML(filename=str(html_out)).write_pdf(str(pdf_out))
    except Exception as exc:
        print(json.dumps({"error": f"WeasyPrint failed: {exc}"}))
        sys.exit(1)

    page_count = -1
    try:
        from pypdf import PdfReader
        page_count = len(PdfReader(str(pdf_out)).pages)
    except Exception:
        pass

    if not args.skip_log:
        log_md = vault / "wiki" / "log.md"
        today  = datetime.date.today().strftime("%Y-%m-%d")
        entry  = f"\n## [{today}] render | {title}, wiki-to-pdf, cv, {page_count} pp\n"
        try:
            with open(log_md, "a", encoding="utf-8") as fh:
                fh.write(entry)
        except FileNotFoundError:
            pass

    print(json.dumps({
        "status":      "ok",
        "page_title":  title,
        "style":       "cv",
        "watermark":   watermark_path.name if watermark_path else "(none)",
        "page_count":  page_count,
        "output_pdf":  str(pdf_out),
        "output_html": str(html_out),
    }, indent=2))


# ── Main render ──────────────────────────────────────────────────────

def render(args: argparse.Namespace) -> None:
    vault      = detect_vault(args.vault)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir \
                 else vault / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Resolve page
    page_file = find_wiki_page(args.page, vault)
    if not page_file:
        sys.exit(json.dumps({"error": f"Page not found: {args.page}"}))

    # 2. Read source
    raw = page_file.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)

    # 3. Bundle?
    pages = [(page_file, body)]
    if args.with_cluster_notes:
        cluster_dir = vault / "wiki" / f"{page_file.stem} Cluster Notes"
        if cluster_dir.exists():
            for cf in sorted(cluster_dir.glob("*.md")):
                _, cb = parse_frontmatter(cf.read_text(encoding="utf-8"))
                pages.append((cf, cb))

    # 4. Title
    title = get_h1(body, page_file.stem)

    # 5. Metrics
    word_count = count_words(body)

    # 6. Category + archetype
    category = determine_category(fm, page_file, title, args.prepared_for)
    archetype = args.archetype or determine_archetype(category, word_count, args.prepared_for, fm)

    # 7. Variant
    log     = load_log(output_dir)
    variant = pick_variant(category, log, args.variant)

    # 8. Assets
    monogram_path        = find_monogram(vault, variant)
    inline_monogram_path = find_inline_monogram(vault)
    monogram_uri         = monogram_path.as_uri()        if monogram_path        else ""
    inline_monogram_uri  = inline_monogram_path.as_uri() if inline_monogram_path else ""

    # 9. Markdown rendering
    md_renderer = markdown.Markdown(extensions=["tables", "fenced_code"])
    body_parts  = []
    for i, (pf, pb) in enumerate(pages):
        converted = italicise_wikilinks(pb)
        md_renderer.reset()
        html_part = md_renderer.convert(converted)
        if not getattr(args, "no_charts", False):
            html_part = pre_render_charts(html_part)
        if i > 0:
            html_part = (
                '<div class="cluster-divider">'
                '<div class="cluster-eyebrow">Cluster Note</div>'
                '</div>\n' + html_part
            )
        body_parts.append(html_part)
    body_html = "\n".join(body_parts)

    # 10. TOC (reference + >2000 words)
    toc_html = build_toc(body_html) if (archetype == "reference" and word_count > 2000) else ""

    # 11. Summary
    summary = extract_summary(fm, body)

    # 12. Date
    date_str = datetime.date.today().strftime("%-d %B %Y")

    # 13. Brand CSS
    brand_css = (SKILL_DIR / "brand.css").read_text(encoding="utf-8")

    # 14. Template
    env      = Environment(loader=FileSystemLoader(str(SKILL_DIR)), autoescape=False)
    template = env.get_template("template.html")

    full_html = template.render(
        page_title          = title,
        cover_archetype     = archetype,
        monogram_uri        = monogram_uri,
        inline_monogram_uri = inline_monogram_uri,
        body_html           = body_html,
        prepared_for        = args.prepared_for or "",
        report_id           = args.report_id    or "",
        date_str            = date_str,
        category_label      = CATEGORY_LABELS.get(category, ""),
        summary             = summary,
        toc_html            = toc_html,
        brand_css           = brand_css,
        brand_mark_name     = args.brand_mark_name or "",
    )

    # 15. Output paths
    slug = slugify(title)
    if args.with_cluster_notes and len(pages) > 1:
        slug += "-bundle"
    date_slug   = datetime.date.today().strftime("%Y-%m-%d")
    output_stem = f"{slug}-{date_slug}"

    html_out = output_dir / f"{output_stem}.html"
    pdf_out  = output_dir / f"{output_stem}.pdf"

    html_out.write_text(full_html, encoding="utf-8")

    # 16. Render PDF
    try:
        HTML(filename=str(html_out)).write_pdf(str(pdf_out))
    except Exception as exc:
        print(json.dumps({"error": f"WeasyPrint failed: {exc}"}))
        sys.exit(1)

    # 17. Page count
    page_count = -1
    try:
        from pypdf import PdfReader
        page_count = len(PdfReader(str(pdf_out)).pages)
    except Exception:
        pass

    # 18. Update rotation log (skip if variant was overridden)
    if not args.variant:
        log = update_log(log, category, variant)
        save_log(output_dir, log)

    # 19. Append to wiki/log.md
    if not args.skip_log:
        log_md = vault / "wiki" / "log.md"
        today  = datetime.date.today().strftime("%Y-%m-%d")
        entry  = (
            f"\n## [{today}] render | {title}, "
            f"wiki-to-pdf, {variant}, {archetype}, {page_count} pp\n"
        )
        try:
            with open(log_md, "a", encoding="utf-8") as fh:
                fh.write(entry)
        except FileNotFoundError:
            pass

    # 20. Report
    result = {
        "status":      "ok",
        "page_title":  title,
        "category":    category,
        "archetype":   archetype,
        "variant":     variant,
        "page_count":  page_count,
        "output_pdf":  str(pdf_out),
        "output_html": str(html_out),
    }
    print(json.dumps(result, indent=2))


# ── Entry point ──────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Render a wiki page as a branded PDF.")
    p.add_argument("--page",               required=True, help="Page title")
    p.add_argument("--vault",              help="Vault root path (overrides auto-detect)")
    p.add_argument("--output-dir",         help="Output directory (defaults to <vault>/outputs)")
    p.add_argument("--with-cluster-notes", action="store_true")
    p.add_argument("--archetype",          choices=["briefing", "reference", "default", "no-cover"])
    p.add_argument("--variant",            help="Override variant filename")
    p.add_argument("--prepared-for",       help="Name for briefing covers")
    p.add_argument("--report-id",          help="Report ID for briefing meta")
    p.add_argument("--brand-mark-name",    help="Brand label for the eyebrow line")
    p.add_argument("--skip-log",           action="store_true", help="Skip wiki/log.md entry")
    p.add_argument("--style",              choices=["brand", "cv"], default="brand",
                   help="Render style: 'brand' (cover/gradient, default) or 'cv' "
                        "(minimalist EB Garamond statement layout, no cover).")
    p.add_argument("--subtitle",           help="CV style: override masthead subtitle ('' suppresses).")
    p.add_argument("--watermark",          help="CV style: monogram filename for the watermark.")
    p.add_argument("--footer-label",       help="CV style: running-footer label (defaults to title).")
    p.add_argument("--no-charts",          action="store_true",
                   help="Skip vega-lite / mermaid fenced-block pre-render (both styles).")
    args = p.parse_args()
    if args.style == "cv":
        render_cv(args)
    else:
        render(args)


if __name__ == "__main__":
    main()
