#!/usr/bin/env python3
"""md2post.py — Convert a Markdown file into an FTU Labs blog post.

Usage
-----
    python3 scripts/md2post.py <markdown-file>
    python3 scripts/md2post.py blog/my-draft.md
    python3 scripts/md2post.py content/post.md --number 5 --slug my-post

The Markdown file must start with an HTML-comment front matter block:

    <!-- #!ftulabs-scripts
    title: My Post Title
    description: A short summary shown in the blog listing.
    date: 2026-04-01
    authors: Alice, Bob
    readtime: 8 min
    lang: en
    -->

    Body content in Markdown …

What it does
------------
1. Parses the front matter for metadata.
2. Converts the Markdown body to HTML matching the site template.
3. Writes  blog/{N}.{slug}.html  (or  vi/blog/…  when lang=vi).
4. Inserts a listing entry into  blog.html  (or  vi/blog.html).
"""

from __future__ import annotations

import argparse
import glob
import html as html_mod
import os
import re
import sys
import textwrap

# ── repo root (two levels up from scripts/) ──────────────────────────────────

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

# ── HTML fragments ────────────────────────────────────────────────────────────

NAV_LABELS = {
    "en": {
        "projects": "projects",
        "team": "team",
        "research": "research",
        "blog": "blog",
        "lang_aria": "Language",
        "theme_aria": "Toggle theme",
        "menu_aria": "Toggle menu",
        "back": "&larr; back to blog",
    },
    "vi": {
        "projects": "dự án",
        "team": "đội ngũ",
        "research": "nghiên cứu",
        "blog": "blog",
        "lang_aria": "Ngôn ngữ",
        "theme_aria": "Đổi giao diện",
        "menu_aria": "Toggle menu",
        "back": "&larr; quay lại blog",
    },
}

PAGE_TEMPLATE = """\
<!doctype html>
<html lang="{lang}">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>{title} &mdash; FTU Labs</title>
        <meta name="description" content="{description}" />
        <link rel="icon" href="/img/logo.png" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
        <link
            href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,100..800;1,100..800&display=swap"
            rel="stylesheet"
        />
{head_extras}\
        <link rel="stylesheet" href="/css/style.css" />
    </head>
    <body>
        <nav class="nav">
            <div class="nav-inner">
                <a href="../index.html" class="nav-logo"
                    ><img src="/img/logo.png" alt="FTU" />FTU Labs</a
                >
                <div class="nav-actions">
                    <div class="nav-links">
                        <a href="../projects.html">{nav_projects}</a>
                        <a href="../team.html">{nav_team}</a>
                        <a href="../research.html">{nav_research}</a>
                        <a href="../blog.html">{nav_blog}</a>
                    </div>
                    <div class="lang-switch" aria-label="{lang_aria}"></div>
                    <button class="theme-toggle" aria-label="{theme_aria}">
                        <svg class="icon-moon" viewBox="0 0 24 24">
                            <path
                                d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"
                            />
                        </svg>
                        <svg class="icon-sun" viewBox="0 0 24 24">
                            <circle cx="12" cy="12" r="5" />
                            <line x1="12" y1="1" x2="12" y2="3" />
                            <line x1="12" y1="21" x2="12" y2="23" />
                            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                            <line x1="1" y1="12" x2="3" y2="12" />
                            <line x1="21" y1="12" x2="23" y2="12" />
                            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                        </svg>
                    </button>
                    <button class="nav-toggle" aria-label="{menu_aria}">
                        <span></span><span></span><span></span>
                    </button>
                </div>
            </div>
        </nav>
        <div class="nav-mobile">
            <a href="../projects.html">{nav_projects}</a>
            <a href="../team.html">{nav_team}</a>
            <a href="../research.html">{nav_research}</a>
            <a href="../blog.html">{nav_blog}</a>
        </div>

        <main class="page">
            <div class="container">
                <a href="../blog.html" class="post-back animate"
                    >{back_label}</a
                >

                <header class="post-header animate animate-d1">
                    <h1 class="post-title">{title}</h1>
                    <div class="post-meta">
                        {date} &middot; {authors} &middot; {readtime} read
                    </div>
                </header>

                <article class="post-content animate animate-d2">
{article_body}
                </article>
            </div>
        </main>

        <footer class="footer">
            <div class="footer-inner">
                <span class="footer-copy">&copy; 2026 FTU Labs</span>
                <div class="footer-links">
                    <a href="https://github.com/ftulabs">GitHub</a>
                    <a href="https://twitter.com/ftulabs">Twitter</a>
                </div>
            </div>
        </footer>

        <script src="/js/main.js" defer></script>
{foot_extras}\
        <script src="/js/l10n.js"></script>
    </body>
</html>
"""

BLOG_ENTRY = """\
          <div class="blog-item reveal">
            <div class="blog-date">{date}</div>
            <h2 class="blog-title"><a href="blog/{filename}">{title}</a></h2>
            <p class="blog-excerpt">{description}</p>
          </div>"""

# ── front matter ──────────────────────────────────────────────────────────────

REQUIRED_FIELDS = ("title", "description", "date", "authors", "readtime", "lang")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (metadata-dict, markdown-body) from the raw file text."""
    m = re.match(r"<!--\s*#!ftulabs-scripts\s*\n(.*?)\n\s*-->", text, re.DOTALL)
    if not m:
        die("no front matter found (expected <!-- #!ftulabs-scripts … -->)")
    meta: dict[str, str] = {}
    for line in m.group(1).strip().splitlines():
        key, _, val = line.partition(":")
        key = key.strip()
        if key:
            meta[key] = val.strip()
    for field in REQUIRED_FIELDS:
        if field not in meta:
            die(f"front matter is missing required field: {field}")
    body = text[m.end() :].strip()
    return meta, body


# ── slugify / numbering ──────────────────────────────────────────────────────


def slugify(title: str, max_words: int = 4) -> str:
    s = re.sub(r"[^a-z0-9\s-]", "", title.lower())
    words = s.split()[:max_words]
    return "-".join(w for w in words if w) or "post"


def next_number(blog_dir: str) -> int:
    nums = []
    for f in glob.glob(os.path.join(blog_dir, "[0-9]*.html")):
        m = re.match(r"(\d+)\.", os.path.basename(f))
        if m:
            nums.append(int(m.group(1)))
    return max(nums, default=0) + 1


# ── inline markdown ──────────────────────────────────────────────────────────


def _fmt(text: str) -> str:
    """Apply inline formatting (bold, italic, links, images, strikethrough)
    to a stretch of text that is NOT inside a code span."""
    # images  ![alt](src)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', text)
    # links  [text](url "title")  or  [text](url)
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+?)(?:\s+"([^"]*)")?\)',
        lambda m: (
            f'<a href="{m.group(2)}" title="{m.group(3)}">{m.group(1)}</a>'
            if m.group(3)
            else f'<a href="{m.group(2)}">{m.group(1)}</a>'
        ),
        text,
    )
    # bold-italic  ***text***
    text = re.sub(r"\*{3}(.+?)\*{3}", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"_{3}(.+?)_{3}", r"<strong><em>\1</em></strong>", text)
    # bold  **text**
    text = re.sub(r"\*{2}(.+?)\*{2}", r"<strong>\1</strong>", text)
    text = re.sub(r"_{2}(.+?)_{2}", r"<strong>\1</strong>", text)
    # italic  *text*  (not preceded/followed by *)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", text)
    # strikethrough  ~~text~~
    text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)
    return text


def inline(text: str) -> str:
    """Convert inline markdown, protecting code spans from inner parsing."""
    parts: list[str] = []
    last = 0
    # handle double-backtick code spans first: ``code with `backtick` ``
    for m in re.finditer(r"``(.+?)``|`([^`]+)`", text):
        parts.append(_fmt(text[last : m.start()]))
        code = m.group(1) if m.group(1) is not None else m.group(2)
        parts.append(f"<code>{html_mod.escape(code.strip())}</code>")
        last = m.end()
    parts.append(_fmt(text[last:]))
    return "".join(parts)


# ── block-level markdown ─────────────────────────────────────────────────────

_RE_HEADING = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$")
_RE_FENCE = re.compile(r"^(`{3,})(\w*)")
_RE_HR = re.compile(r"^(\*{3,}|-{3,}|_{3,})\s*$")
_RE_UL = re.compile(r"^([*\-+])\s+(.*)")
_RE_OL = re.compile(r"^(\d+)[.)]\s+(.*)")
_RE_BQ = re.compile(r"^>\s?(.*)")
_RE_IMG = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
_RE_TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")
_RE_TABLE_SEP = re.compile(r"^\|[\s:]*-+[\s:|-]*\|\s*$")


def _is_block_start(line: str) -> bool:
    """Return True if *line* would begin a new block element."""
    s = line.strip()
    if not s:
        return True
    if _RE_HEADING.match(s):
        return True
    if _RE_FENCE.match(s):
        return True
    if _RE_HR.match(s):
        return True
    if _RE_UL.match(s):
        return True
    if _RE_OL.match(s):
        return True
    if _RE_BQ.match(s):
        return True
    if _RE_IMG.match(s):
        return True
    if _RE_TABLE_ROW.match(s):
        return True
    if s.startswith("<") and not s.startswith("<a") and not s.startswith("<img"):
        return True
    return False


class Converter:
    """Stateful Markdown-to-HTML block converter."""

    def __init__(self) -> None:
        self.has_code: bool = False
        self.first_image: bool = True

    # ── public API ────────────────────────────────────────

    def convert(self, body: str) -> list[str]:
        lines = body.split("\n")
        blocks: list[str] = []
        i = 0
        while i < len(lines):
            i = self._dispatch(lines, i, blocks)
        return blocks

    # ── dispatcher ────────────────────────────────────────

    def _dispatch(self, lines: list[str], i: int, blocks: list[str]) -> int:
        line = lines[i]
        stripped = line.strip()

        # blank
        if not stripped:
            return i + 1

        # fenced code block
        m = _RE_FENCE.match(stripped)
        if m:
            return self._code_block(lines, i, blocks, m)

        # ATX heading
        m = _RE_HEADING.match(stripped)
        if m:
            return self._heading(m, blocks)

        # horizontal rule
        if _RE_HR.match(stripped):
            blocks.append("<hr>")
            return i + 1

        # standalone image
        m = _RE_IMG.match(stripped)
        if m:
            return self._image(m, blocks)

        # blockquote
        if _RE_BQ.match(stripped):
            return self._blockquote(lines, i, blocks)

        # unordered list
        if _RE_UL.match(stripped):
            return self._unordered_list(lines, i, blocks)

        # ordered list
        if _RE_OL.match(stripped):
            return self._ordered_list(lines, i, blocks)

        # table
        if _RE_TABLE_ROW.match(stripped):
            return self._table(lines, i, blocks)

        # raw HTML passthrough (block-level tags)
        if (
            stripped.startswith("<")
            and not stripped.startswith("<a")
            and not stripped.startswith("<img")
        ):
            return self._raw_html(lines, i, blocks)

        # paragraph (default)
        return self._paragraph(lines, i, blocks)

    # ── block parsers ─────────────────────────────────────

    def _code_block(
        self, lines: list[str], i: int, blocks: list[str], m: re.Match
    ) -> int:
        fence_char = m.group(1)
        lang = m.group(2) or "text"
        if lang == "text":
            lang = "plaintext"
        self.has_code = True
        code_lines: list[str] = []
        i += 1
        while i < len(lines):
            if lines[i].strip().startswith(fence_char[0] * len(fence_char)) and (
                lines[i].strip() == fence_char[0] * len(fence_char)
                or re.match(r"^`{3,}\s*$", lines[i].strip())
            ):
                i += 1
                break
            code_lines.append(lines[i])
            i += 1
        code = "\n".join(code_lines)
        escaped = html_mod.escape(code)
        blocks.append(f'<pre><code class="language-{lang}">{escaped}</code></pre>')
        return i

    def _heading(self, m: re.Match, blocks: list[str]) -> int:
        level = len(m.group(1))
        text = inline(m.group(2).strip())
        blocks.append(f"<h{level}>{text}</h{level}>")
        return m.end() if hasattr(m, "endpos") else 0  # unused; caller uses return

    def _image(self, m: re.Match, blocks: list[str]) -> int:
        alt = m.group(1)
        src = m.group(2)
        if self.first_image:
            blocks.append(
                f"<figure>\n"
                f'    <img src="{src}" alt="{alt or "Post image"}">\n'
                f"    <figcaption>{alt}</figcaption>\n"
                f"</figure>"
            )
            self.first_image = False
        else:
            blocks.append(f'<img src="{src}" alt="{alt}">')
        return 0  # unused

    def _blockquote(self, lines: list[str], i: int, blocks: list[str]) -> int:
        bq_lines: list[str] = []
        while i < len(lines):
            m = _RE_BQ.match(lines[i].strip())
            if m:
                bq_lines.append(m.group(1))
                i += 1
            elif not lines[i].strip():
                # peek: if next non-blank line is also a blockquote, continue
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines) and _RE_BQ.match(lines[j].strip()):
                    bq_lines.append("")
                    i += 1
                else:
                    break
            else:
                break
        # Convert blockquote content — may contain paragraphs
        inner_text = "\n".join(bq_lines).strip()
        paragraphs = re.split(r"\n{2,}", inner_text)
        if len(paragraphs) == 1:
            blocks.append(
                f"<blockquote>{inline(paragraphs[0].replace(chr(10), ' '))}</blockquote>"
            )
        else:
            inner = "\n".join(
                f"    <p>{inline(p.replace(chr(10), ' '))}</p>"
                for p in paragraphs
                if p.strip()
            )
            blocks.append(f"<blockquote>\n{inner}\n</blockquote>")
        return i

    def _collect_list_items(
        self, lines: list[str], i: int, pattern: re.Pattern
    ) -> tuple[list[str], int]:
        """Collect list items, handling continuation lines and blank separators."""
        items: list[str] = []
        current: list[str] | None = None

        while i < len(lines):
            stripped = lines[i].strip()
            m = pattern.match(stripped)

            if m:
                # New list item
                if current is not None:
                    items.append(" ".join(current))
                current = [m.group(2) if pattern.groups >= 2 else m.group(1)]
                i += 1
            elif not stripped:
                # Blank line — may separate loose list items
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines) and pattern.match(lines[j].strip()):
                    i = j  # skip blanks, continue list
                else:
                    i = j
                    break
            elif current is not None and (
                lines[i].startswith("  ") or lines[i].startswith("\t")
            ):
                # Continuation line (indented)
                current.append(stripped)
                i += 1
            else:
                break

        if current is not None:
            items.append(" ".join(current))
        return items, i

    def _unordered_list(self, lines: list[str], i: int, blocks: list[str]) -> int:
        items, i = self._collect_list_items(lines, i, _RE_UL)
        li = "\n".join(f"    <li>{inline(item)}</li>" for item in items)
        blocks.append(f"<ul>\n{li}\n</ul>")
        return i

    def _ordered_list(self, lines: list[str], i: int, blocks: list[str]) -> int:
        items, i = self._collect_list_items(lines, i, _RE_OL)
        li = "\n".join(f"    <li>{inline(item)}</li>" for item in items)
        blocks.append(f"<ol>\n{li}\n</ol>")
        return i

    def _table(self, lines: list[str], i: int, blocks: list[str]) -> int:
        rows: list[list[str]] = []
        aligns: list[str] = []

        while i < len(lines) and _RE_TABLE_ROW.match(lines[i].strip()):
            raw = lines[i].strip()
            cells = [c.strip() for c in raw.strip("|").split("|")]

            # separator row?
            if _RE_TABLE_SEP.match(raw):
                for cell in cells:
                    cell = cell.strip()
                    if cell.startswith(":") and cell.endswith(":"):
                        aligns.append("center")
                    elif cell.endswith(":"):
                        aligns.append("right")
                    else:
                        aligns.append("left")
                i += 1
                continue

            rows.append(cells)
            i += 1

        if not rows:
            return i

        out = ["<table>"]
        for ri, row in enumerate(rows):
            tag = "th" if ri == 0 and aligns else "td"
            section_open = "<thead>" if ri == 0 and aligns else ""
            section_close = "</thead>\n<tbody>" if ri == 0 and aligns else ""
            if section_open:
                out.append(f"    {section_open}")
            out.append("    <tr>")
            for ci, cell in enumerate(row):
                align = ""
                if aligns and ci < len(aligns) and aligns[ci] != "left":
                    align = f' style="text-align:{aligns[ci]}"'
                out.append(f"        <{tag}{align}>{inline(cell)}</{tag}>")
            out.append("    </tr>")
            if section_close:
                out.append(f"    {section_close}")
        if aligns:
            out.append("</tbody>")
        out.append("</table>")
        blocks.append("\n".join(out))
        return i

    def _raw_html(self, lines: list[str], i: int, blocks: list[str]) -> int:
        html_lines: list[str] = [lines[i]]
        i += 1
        while i < len(lines) and lines[i].strip():
            html_lines.append(lines[i])
            i += 1
        blocks.append("\n".join(html_lines))
        return i

    def _paragraph(self, lines: list[str], i: int, blocks: list[str]) -> int:
        para: list[str] = []
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped:
                break
            if _is_block_start(stripped) and para:
                break
            para.append(stripped)
            i += 1
        text = inline(" ".join(para))
        blocks.append(f"<p>{text}</p>")
        return i


# ── heading / image special returns ──────────────────────────────────────────
# The _heading and _image helpers are called via _dispatch which advances i,
# so we patch _dispatch to handle their return values properly.


def _convert_body(body: str) -> tuple[str, bool]:
    """Convert a markdown body to HTML content string + has_code flag."""
    conv = Converter()
    lines = body.split("\n")
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        if not stripped:
            i += 1
            continue

        # fenced code
        m = _RE_FENCE.match(stripped)
        if m:
            i = conv._code_block(lines, i, blocks, m)
            continue

        # heading
        m = _RE_HEADING.match(stripped)
        if m:
            level = len(m.group(1))
            text = inline(m.group(2).strip())
            blocks.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        # hr
        if _RE_HR.match(stripped):
            blocks.append("<hr>")
            i += 1
            continue

        # standalone image
        m = _RE_IMG.match(stripped)
        if m:
            alt_text = m.group(1)
            src = m.group(2)
            if conv.first_image:
                blocks.append(
                    "<figure>\n"
                    f'    <img src="{src}" alt="{alt_text or "Post image"}">\n'
                    f"    <figcaption>{alt_text}</figcaption>\n"
                    "</figure>"
                )
                conv.first_image = False
            else:
                blocks.append(f'<img src="{src}" alt="{alt_text}">')
            i += 1
            continue

        # blockquote
        if _RE_BQ.match(stripped):
            i = conv._blockquote(lines, i, blocks)
            continue

        # unordered list
        if _RE_UL.match(stripped):
            i = conv._unordered_list(lines, i, blocks)
            continue

        # ordered list
        if _RE_OL.match(stripped):
            i = conv._ordered_list(lines, i, blocks)
            continue

        # table
        if _RE_TABLE_ROW.match(stripped):
            i = conv._table(lines, i, blocks)
            continue

        # raw HTML passthrough
        if (
            stripped.startswith("<")
            and not stripped.startswith("<a")
            and not stripped.startswith("<img")
            and not stripped.startswith("<em")
            and not stripped.startswith("<strong")
            and not stripped.startswith("<code")
            and not stripped.startswith("<del")
        ):
            html_lines: list[str] = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].strip():
                html_lines.append(lines[i])
                i += 1
            blocks.append("\n".join(html_lines))
            continue

        # paragraph
        para: list[str] = []
        while i < len(lines):
            s = lines[i].strip()
            if not s:
                break
            if _is_block_start(s) and para:
                break
            para.append(s)
            i += 1
        text = inline(" ".join(para))
        blocks.append(f"<p>{text}</p>")

    return blocks, conv.has_code


# ── full-page generation ─────────────────────────────────────────────────────

I = "                    "  # 20-space indent (5 × 4) for article body


def generate_page(meta: dict[str, str], blocks: list[str], has_code: bool) -> str:
    lang = meta["lang"]
    nav = NAV_LABELS.get(lang, NAV_LABELS["en"])

    # indent each block inside the <article>
    body_lines: list[str] = []
    for block in blocks:
        for line in block.split("\n"):
            body_lines.append(f"{I}{line}" if line.strip() else "")
        body_lines.append("")  # blank line between blocks

    head_extras = ""
    foot_extras = ""
    if has_code:
        head_extras = '        <link rel="stylesheet" href="/vendor/hljs/atom-one-dark.min.css" />\n'
        foot_extras = '        <script src="/js/hljs.js" defer></script>\n'

    return PAGE_TEMPLATE.format(
        lang=lang,
        title=html_mod.escape(meta["title"], quote=True),
        description=html_mod.escape(meta["description"], quote=True),
        date=meta["date"],
        authors=meta["authors"],
        readtime=meta["readtime"],
        nav_projects=nav["projects"],
        nav_team=nav["team"],
        nav_research=nav["research"],
        nav_blog=nav["blog"],
        lang_aria=nav["lang_aria"],
        theme_aria=nav["theme_aria"],
        menu_aria=nav["menu_aria"],
        back_label=nav["back"],
        head_extras=head_extras,
        foot_extras=foot_extras,
        article_body="\n".join(body_lines).rstrip(),
    )


# ── blog listing update ──────────────────────────────────────────────────────


def add_listing_entry(meta: dict[str, str], filename: str, listing_path: str) -> None:
    """Insert a blog-item entry into the blog listing page (date-ordered)."""
    if not os.path.isfile(listing_path):
        warn(f"listing page not found: {listing_path} — skipping entry insertion")
        return

    entry = BLOG_ENTRY.format(
        date=meta["date"],
        title=html_mod.escape(meta["title"]),
        description=html_mod.escape(meta["description"]),
        filename=filename,
    )

    with open(listing_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the blog-list div
    marker = '<div class="blog-list">'
    idx = content.find(marker)
    if idx == -1:
        warn(f"could not find {marker} in {listing_path} — skipping entry insertion")
        return

    insert_at = idx + len(marker)

    # Try to insert in correct date order (newest first).
    # Find all existing blog-date values and their positions.
    date_pattern = re.compile(r'<div class="blog-date">(\d{4}-\d{2}-\d{2})</div>')
    new_date = meta["date"]
    best_pos = insert_at  # default: top of list

    for m in date_pattern.finditer(content, insert_at):
        if m.group(1) <= new_date:
            # Insert before this entry — find the start of its blog-item div
            search_start = max(insert_at, m.start() - 200)
            chunk = content[search_start : m.start()]
            item_offset = chunk.rfind('<div class="blog-item')
            if item_offset != -1:
                best_pos = search_start + item_offset
            break
    else:
        # New entry is older than all existing entries — insert at end
        section_end = content.find("</section>", insert_at)
        if section_end != -1:
            blog_list_close = content.rfind("</div>", insert_at, section_end)
            if blog_list_close != -1:
                best_pos = blog_list_close

    # Walk best_pos back to the line boundary so the next entry keeps its
    # leading whitespace intact (prevents broken indentation).
    if best_pos > insert_at:
        line_start = content.rfind("\n", insert_at, best_pos)
        if line_start != -1:
            best_pos = line_start + 1
        new_content = content[:best_pos] + entry + "\n" + content[best_pos:]
    else:
        # Inserting at top of list (right after <div class="blog-list">)
        new_content = content[:best_pos] + "\n" + entry + content[best_pos:]

    with open(listing_path, "w", encoding="utf-8") as f:
        f.write(new_content)


# ── helpers ───────────────────────────────────────────────────────────────────


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"  warning: {msg}", file=sys.stderr)


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Convert a Markdown file into an FTU Labs blog post.",
    )
    ap.add_argument("markdown", help="path to the Markdown source file")
    ap.add_argument(
        "--number", "-n", type=int, default=None, help="override auto-numbering"
    )
    ap.add_argument("--slug", "-s", default=None, help="override auto-slug")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be done without writing files",
    )
    args = ap.parse_args()

    md_path = args.markdown
    if not os.path.isfile(md_path):
        die(f"file not found: {md_path}")

    with open(md_path, "r", encoding="utf-8") as f:
        raw = f.read()

    meta, body = parse_frontmatter(raw)
    blocks, has_code = _convert_body(body)

    lang = meta["lang"]
    if lang == "en":
        blog_dir = os.path.join(ROOT, "blog")
        listing = os.path.join(ROOT, "blog.html")
    else:
        blog_dir = os.path.join(ROOT, lang, "blog")
        listing = os.path.join(ROOT, lang, "blog.html")

    os.makedirs(blog_dir, exist_ok=True)

    num = args.number if args.number is not None else next_number(blog_dir)
    slug = args.slug or slugify(meta["title"])
    filename = f"{num}.{slug}.html"
    out_path = os.path.join(blog_dir, filename)

    page_html = generate_page(meta, blocks, has_code)

    if args.dry_run:
        print(f"  would write  {os.path.relpath(out_path, ROOT)}")
        print(f"  would update {os.path.relpath(listing, ROOT)}")
        print(f"  title:       {meta['title']}")
        print(f"  slug:        {slug}")
        print(f"  number:      {num}")
        print(f"  has code:    {has_code}")
        return

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page_html)

    add_listing_entry(meta, filename, listing)

    rel_out = os.path.relpath(out_path, ROOT)
    rel_lst = os.path.relpath(listing, ROOT)
    print(f"  ✓ {rel_out}")
    print(f"  ✓ {rel_lst}  (entry added)")
    print(f"    title:    {meta['title']}")
    print(f"    date:     {meta['date']}")
    print(f"    authors:  {meta['authors']}")
    print(f"    has code: {has_code}")


if __name__ == "__main__":
    main()
