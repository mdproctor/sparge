"""
HTML Archive Scanner
====================
Scans a single archived HTML post for all known issue categories.
Returns a list of Issue dicts with CSS selectors for in-browser highlighting.

Issue types (mirrors the detection work done in App 1):

  data_placeholder      — <img src="data:..."> still present (lazy-load not recovered)
  noscript_remnant      — <noscript> with an http image URL (lazy-load sibling not cleaned up)
  external_image        — <img> pointing at an http/https URL (not yet localised locally)
  tracking_pixel        — 1×1 transparent image from a known tracking domain
  missing_local_image   — <img src="../../assets/..."> where the file doesn't exist on disk
  empty_embed           — <iframe> with no src or empty src (embed not recovered)
  unreplaced_gist       — <script src="gist.github.com/..."> not replaced with inline code
  wordpress_chrome      — WordPress metadata visible in the article (bylines, share widgets, etc.)
  missing_image_signal  — Paragraph whose text signals an image should follow but none does
                          ("as shown below", "the following screenshot", etc.)

Each issue has the keys:
  type      str   — one of the types above
  level     str   — 'ERROR' or 'WARN'
  detail    str   — human-readable description
  selector  str|None — CSS selector targeting the element (for highlighting)
"""

import re
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, Tag, NavigableString

try:
    from .constants import TRACKING_DOMAINS, is_tracking_pixel as _is_tracking_pixel
except ImportError:
    from constants import TRACKING_DOMAINS, is_tracking_pixel as _is_tracking_pixel

# ── WordPress chrome patterns ─────────────────────────────────────────────────
CHROME_SELECTORS = [
    '.entry-header', '.entry-meta', '.author-box', '.author-description',
    '.author-info', '.addtoany_share_save_container', '.sharedaddy',
    '#comments', '.comments-area', '.jp-relatedposts', '.post-navigation',
    '.wpdiscuz-form-container', '[class*="wpDiscuz"]', '[class*="addtoany"]',
]

CHROME_TEXT_PATTERNS = [
    re.compile(r'^by\s+[A-Z]', re.I),          # "by Mark Proctor"
    re.compile(r'View all posts by', re.I),     # author link
    re.compile(r'Post Comment', re.I),          # Blogger
    re.compile(r'Leave a Reply', re.I),         # WordPress comment form
    re.compile(r'You might also like', re.I),   # Related posts widget
    re.compile(r'Share this:', re.I),           # Share widget header
]

# ── Missing-image text signals ────────────────────────────────────────────────
MISSING_IMG_SIGNALS = [
    re.compile(r'as shown (below|above|here)', re.I),
    re.compile(r'(see|view) (the )?(image|screenshot|figure|diagram|chart|graph|photo) (below|above)', re.I),
    re.compile(r'(the )?(following|below) (image|screenshot|figure|diagram|chart|graph) shows?', re.I),
    re.compile(r'(image|screenshot|figure|diagram|chart|graph|photo):?\s*$', re.I),
    re.compile(r'click (to )?(enlarge|zoom|view)', re.I),
]


# ── CSS selector generation ────────────────────────────────────────────────────

def _selector(tag: Tag) -> Optional[str]:
    """Generate a reasonably unique CSS selector for a BeautifulSoup Tag."""
    if not isinstance(tag, Tag):
        return None
    if tag.get('id'):
        return f'#{tag["id"]}'
    parts = []
    el = tag
    for _ in range(6):  # max depth
        if not isinstance(el, Tag) or el.name in ('html', 'body', 'article', '[document]'):
            break
        parent = el.parent
        if not isinstance(parent, Tag):
            break
        siblings = [s for s in parent.children if isinstance(s, Tag) and s.name == el.name]
        if len(siblings) > 1:
            idx = siblings.index(el) + 1
            parts.append(f'{el.name}:nth-of-type({idx})')
        else:
            parts.append(el.name)
        el = parent
    if not parts:
        return tag.name
    parts.reverse()
    return ' > '.join(parts)


def _issue(itype: str, level: str, detail: str, tag: Optional[Tag] = None) -> dict:
    return {
        'type':     itype,
        'level':    level,
        'detail':   detail,
        'selector': _selector(tag) if tag is not None else None,
    }


# ── Individual checks ─────────────────────────────────────────────────────────

def check_data_placeholders(article: Tag) -> list[dict]:
    """
    Images still carrying a data: src were not recovered from lazy-loading.
    These render as broken/blank without JS.
    LESSON: data: placeholders = unrecovered lazy-loaded images. Each one
    needs Wayback/mirror recovery or an explicit missing-image placeholder.
    """
    issues = []
    for img in article.find_all('img'):
        if not isinstance(img, Tag):
            continue
        src = img.get('src', '') or ''
        if src.startswith('data:'):
            alt = img.get('alt', '') or ''
            issues.append(_issue(
                'data_placeholder', 'ERROR',
                f'Unrecovered lazy-load placeholder — alt="{alt[:60]}"', img
            ))
    return issues


def check_noscript_remnants(article: Tag) -> list[dict]:
    """
    <noscript> tags containing http image URLs are lazy-load siblings that
    were not cleaned up after the main <img> was replaced.
    LESSON: After replacing a data: img with a recovered image, the sibling
    <noscript> must also be removed.
    """
    issues = []
    for ns in article.find_all('noscript'):
        if not isinstance(ns, Tag):
            continue
        text = str(ns)
        urls = re.findall(r'src=["\']?(https?://[^"\'>\s]+)', text)
        if urls:
            issues.append(_issue(
                'noscript_remnant', 'WARN',
                f'Orphaned <noscript> with image URL: {urls[0][:80]}', ns
            ))
    return issues


def check_external_images(article: Tag, assets_dir: Optional[Path] = None) -> list[dict]:
    """
    Images with http/https src have not been localised.
    Without localisation they break if the external host goes down.
    LESSON: All content images must be downloaded locally. External URLs
    are a single point of failure for long-term archival.
    """
    issues = []
    for img in article.find_all('img'):
        if not isinstance(img, Tag):
            continue
        src = img.get('src', '') or ''
        if not src.startswith('http'):
            continue
        # Skip 0-size tracking pixels (caught by separate check)
        w = img.get('width', '') or ''
        h = img.get('height', '') or ''
        if w in ('1', '0') and h in ('1', '0'):
            continue
        issues.append(_issue(
            'external_image', 'WARN',
            f'Image not localised: {src[:80]}', img
        ))
    return issues


def check_tracking_pixels(article: Tag) -> list[dict]:
    """
    1×1 images from known tracking domains must be removed entirely.
    They serve no archival purpose and fire requests to analytics servers.
    LESSON: WordPress themes embed tracking pixels from multiple vendors.
    Match on both domain and dimensions — some pixels use CSS not attributes.
    """
    issues = []
    for img in article.find_all('img'):
        if not isinstance(img, Tag):
            continue
        src = img.get('src', '') or ''
        w   = str(img.get('width',  '') or '')
        h   = str(img.get('height', '') or '')
        if _is_tracking_pixel(src, w, h):
            from urllib.parse import urlparse
            domain = urlparse(src).netloc.lower().lstrip('www.')
            issues.append(_issue(
                'tracking_pixel', 'WARN',
                f'Tracking pixel from {domain or "unknown"}: {src[:60]}', img
            ))
    return issues


def check_missing_local_images(article: Tag, post_path: Path,
                               posts_dir: Path | None = None) -> list[dict]:
    """
    Images using ../../assets/ relative paths where the file doesn't exist.
    LESSON: After extraction, some images may have been referenced but never
    actually downloaded to the assets directory.

    posts_dir: the canonical posts directory from the project config
      (e.g. legacy/posts/mark-proctor/). When provided, resolves assets
      relative to posts_dir/../.. — i.e. the project's serve_root/legacy/
      directory — regardless of where the HTML file being scanned is
      physically located (original or enriched copy).
      When None, falls back to navigating 3 levels up from post_path
      (legacy behaviour, only correct when scanning the original file).
    """
    issues = []
    if posts_dir is not None:
        # Generic: resolve from the canonical posts location in the project
        # ../../assets/ from posts_dir means posts_dir.parent.parent / assets/
        base_dir = posts_dir.parent.parent
    else:
        # Legacy fallback: 3 levels up from the scanned file
        # Only correct when post_path IS the original post at posts_dir/{slug}.html
        base_dir = post_path.parent.parent.parent
    for img in article.find_all('img'):
        if not isinstance(img, Tag):
            continue
        src = img.get('src', '') or ''
        if not src.startswith('../../assets/'):
            continue
        rel = src.replace('../../', '')
        abs_path = base_dir / rel
        if not abs_path.exists():
            issues.append(_issue(
                'missing_local_image', 'ERROR',
                f'Local image file missing: {rel}', img
            ))
    return issues


def check_empty_embeds(article: Tag) -> list[dict]:
    """
    <iframe> elements with no src or empty src — the embed was not recovered.
    LESSON: WordPress lazy-loads iframes just like images. The src is often
    in data-src or injected by JS. Without JS, these render as empty boxes.
    Recovery requires Playwright or manual URL lookup.
    """
    issues = []
    for iframe in article.find_all('iframe'):
        if not isinstance(iframe, Tag):
            continue
        src = (iframe.get('src', '') or '').strip()
        data_src = (iframe.get('data-src', '') or '').strip()
        if not src and not data_src:
            title = (iframe.get('title', '') or iframe.get('class', ['iframe']) or ['iframe'])[0]
            issues.append(_issue(
                'empty_embed', 'ERROR',
                f'Empty iframe (no src recovered) — title="{str(title)[:40]}"', iframe
            ))
        elif not src and data_src:
            # Has data-src but not wired to src
            issues.append(_issue(
                'empty_embed', 'WARN',
                f'iframe has data-src but no src — needs wiring: {data_src[:60]}', iframe
            ))
    return issues


def check_unreplaced_gists(article: Tag) -> list[dict]:
    """
    <script src="gist.github.com/..."> tags not replaced with inline code.
    LESSON: Gist embeds require JS to render. They must be replaced with the
    raw code content fetched from the GitHub API during archival.
    """
    issues = []
    for script in article.find_all('script', src=True):
        if not isinstance(script, Tag):
            continue
        src = script.get('src', '') or ''
        if 'gist.github.com' in src:
            issues.append(_issue(
                'unreplaced_gist', 'ERROR',
                f'Gist not inlined: {src[:80]}', script
            ))
    return issues


def check_wordpress_chrome(article: Tag) -> list[dict]:
    """
    WordPress UI elements that leaked into the archived article body.
    LESSON: The extractor strips known selectors, but theme variations mean
    some chrome slips through — share buttons, bylines, author sections,
    comment forms. These should not appear in the cleaned archive.
    """
    issues = []
    for sel in CHROME_SELECTORS:
        for el in article.select(sel):
            if not isinstance(el, Tag):
                continue
            text = el.get_text(strip=True)
            if len(text) < 3:
                continue
            issues.append(_issue(
                'wordpress_chrome', 'WARN',
                f'WordPress UI element in article ({sel}): "{text[:50]}"', el
            ))
    # Text-pattern based detection on short paragraphs
    for tag in article.find_all(['p', 'div', 'span']):
        if not isinstance(tag, Tag):
            continue
        text = tag.get_text(separator=' ', strip=True)
        if len(text) > 200:
            continue
        for pattern in CHROME_TEXT_PATTERNS:
            if pattern.search(text):
                issues.append(_issue(
                    'wordpress_chrome', 'WARN',
                    f'Metadata text in article: "{text[:60]}"', tag
                ))
                break
    return issues


def check_layout_spacer_images(article: Tag) -> list[dict]:
    """
    Detect layout-spacer images — transparent 1×N GIFs used as invisible
    column/row separators in old HTML table-based layouts.

    Two detection signals (either is sufficient):
      1. The image filename contains "spacer" (case-insensitive) — the canonical
         name for these layout aids (spacer.gif, Spacer.GIF, etc.)
      2. The image has height="1" (or "0") AND an empty/absent alt attribute —
         a 1px-tall image with no description is almost certainly a spacer.

    Images that already match check_tracking_pixels are not double-reported.

    LESSON: HTML table layouts from the early 2000s routinely used hundreds of
    these invisible spacer GIFs.  In an archived blog post they produce either
    broken-image warnings or requests to defunct servers.  They carry no content.
    Detecting them lets the human decide to strip them — and allows convert_post
    to remove them automatically via a follow-up pipeline rule.
    """
    from urllib.parse import urlparse
    spacers = []
    for img in article.find_all('img'):
        if not isinstance(img, Tag):
            continue
        src  = img.get('src', '') or ''
        alt  = (img.get('alt', '') or '').strip()
        h    = str(img.get('height', '') or '').strip()
        w    = str(img.get('width',  '') or '').strip()

        # Skip tracking pixels — already handled by check_tracking_pixels
        if _is_tracking_pixel(src, w, h):
            continue

        fname = urlparse(src).path.split('/')[-1].lower()
        is_spacer_name = 'spacer' in fname
        is_spacer_dims = h in ('0', '1') and not alt

        if is_spacer_name or is_spacer_dims:
            spacers.append(img)

    if not spacers:
        return []
    return [_issue(
        'layout_spacer_image', 'WARN',
        f'{len(spacers)} layout spacer image(s) (e.g. spacer.gif {spacers[0].get("width","?")}×'
        f'{spacers[0].get("height","?")}px) — no content value, safe to remove',
        spacers[0]  # selector points to the first instance
    )]


def check_suspicious_encoded_html(article: Tag) -> list[dict]:
    """
    Detect <pre><code> elements whose content is HTML-encoded HTML markup.

    Blogger and some CMS platforms HTML-encode table/div content when pasted
    into the rich-text editor: <table> becomes &lt;table&gt; inside a <pre><code>
    block.  When archived and converted by html2text, this produces a massive
    code fence (e.g. 21k chars for a conference schedule) instead of a rendered
    table.

    LESSON: This cannot be auto-fixed — a human must decide whether the code
    block is intentional (e.g. an HTML tutorial showing markup) or an archiving
    artefact (e.g. a conference schedule that should render as a table).
    The check surfaces these as WARN issues so a human can review and dismiss
    if the encoded HTML is intentional.
    """
    issues = []
    # HTML tag names and XML declarations that are suspicious when HTML-encoded
    # inside a code block.  Structural layout tags and XML declarations indicate
    # Blogger/CMS artefacts where a rendered table/config was pasted as raw markup.
    _ENCODED_TAG_RE = re.compile(r'&lt;(?:\?xml|table|div|p|span|ul|ol|li|section|article|h[1-6]|tr|td|th)\b', re.I)
    for pre in article.find_all('pre'):
        if not isinstance(pre, Tag):
            continue
        code = pre.find('code')
        if not isinstance(code, Tag):
            continue
        raw = str(code)  # includes the HTML-encoded entities as-is
        if _ENCODED_TAG_RE.search(raw):
            issues.append(_issue(
                'suspicious_code_content', 'WARN',
                f'<pre><code> contains HTML-encoded markup — may be a conversion '
                f'artefact rather than intentional code (e.g. &lt;table&gt;). '
                f'Check original page and dismiss if intentional.',
                pre
            ))
    return issues


def check_md_notation_in_text(article: Tag) -> list[dict]:
    """
    Inline formatting elements immediately adjacent to a non-space character
    cause html2text to emit **text**(more — with no space before the punctuation.
    The MD validator then compares "name (org" (from HTML plain text) against
    "name(org" (from MD after stripping ** markers), and the phrase check fails.

    LESSON: When <b>Name</b>(Org) appears in HTML, html2text discards the
    trailing whitespace inside the ** wrapper and produces **Name**(Org). The
    plain-text extraction of the same HTML gives "Name (Org". This mismatch
    is a structural artefact of the formatting, not a real content loss.
    Detecting it early lets users dismiss MD phrase-check WARNings on these posts
    as expected false-positives rather than hunting for missing content.
    """
    issues = []
    for tag in article.find_all(['strong', 'b', 'em', 'i']):
        if not isinstance(tag, Tag):
            continue
        # Skip formatting inside code blocks — adjacent punctuation is expected there
        if tag.find_parent(['pre', 'code']):
            continue
        sib = tag.next_sibling
        if isinstance(sib, NavigableString) and sib and not sib[0].isspace():
            adjacent_char = sib[0]
            issues.append(_issue(
                'md_notation_in_text', 'WARN',
                f'<{tag.name}> immediately followed by {adjacent_char!r} — '
                f'html2text produces **{tag.get_text()[:20]}**{adjacent_char} '
                f'(no space), mismatching the HTML plain text which has a space',
                tag
            ))
    return issues


def check_missing_image_signals(article: Tag) -> list[dict]:
    """
    Paragraphs whose text signals that an image should follow, but no image does.
    LESSON: Authors write "as shown below" or "the following screenshot shows"
    before images. When the image was not recovered, this text becomes a
    dangling reference that confuses readers.
    """
    issues = []
    for p in article.find_all(['p', 'div']):
        if not isinstance(p, Tag):
            continue
        # Skip elements that are already missing-image placeholders we inserted
        if 'missing-image' in ' '.join(p.get('class', [])):
            continue
        text = p.get_text(strip=True)
        if not text or len(text) > 300:
            continue
        if not any(sig.search(text) for sig in MISSING_IMG_SIGNALS):
            continue
        # Skip if the element itself contains an image — text is a caption
        if p.find('img'):
            continue
        # Check whether the next sibling has an image or placeholder
        nxt = p.find_next_sibling()
        if nxt and isinstance(nxt, Tag):
            if nxt.name in ('img', 'figure'):
                continue
            if nxt.find('img'):
                continue
            if 'missing-image' in ' '.join(nxt.get('class', [])):
                continue
        issues.append(_issue(
            'missing_image_signal', 'WARN',
            f'Text signals missing image: "{text[:80]}"', p
        ))
    return issues


def check_imgur_images(article: Tag) -> list[dict]:
    """
    Images and links referencing i.imgur.com are geo-blocked in several regions
    (e.g. the UK). Imgur returns HTTP 200 with a stock "Content not viewable in
    your region" image, making the block undetectable via status code alone.
    Both <img src> and <a href> links to imgur must be replaced with Wayback
    Machine archived versions anchored near the post date.
    LESSON: imgur geo-blocking is silent — assume every imgur.com URL is broken
    for a significant portion of readers and replace proactively.
    """
    issues = []
    for img in article.find_all('img'):
        if not isinstance(img, Tag):
            continue
        src = img.get('src', '') or ''
        if 'imgur.com' in src and 'web.archive.org' not in src:
            issues.append(_issue(
                'imgur_image', 'WARN',
                f'imgur img src — geo-blocked in some regions, replace with Wayback URL: {src[:100]}',
                img,
            ))
    for a in article.find_all('a'):
        if not isinstance(a, Tag):
            continue
        href = a.get('href', '') or ''
        if 'imgur.com' in href and 'web.archive.org' not in href:
            issues.append(_issue(
                'imgur_image', 'WARN',
                f'imgur link href — geo-blocked in some regions, replace with Wayback URL: {href[:100]}',
                a,
            ))
    return issues


def check_code_block_no_newlines(article: Tag) -> list[dict]:
    """
    Detect <pre><code> blocks whose content is all on one line (no newlines).

    Some CMS platforms store code without newlines and add <br/> tags at
    render time (WordPress wpautop, Blogger).  During ingest the <br/> tags
    are now converted to \n, but already-ingested posts may still have the
    raw one-line content.  These blocks render in the HTML viewer as a single
    unreadable run of code and produce unreadable MD.

    The fix is to re-fetch from the original URL and recover the proper line
    structure, or to hand-edit the enriched HTML.
    """
    issues = []
    for pre in article.find_all('pre'):
        if not isinstance(pre, Tag):
            continue
        # data-oneliner="true" marks blocks that are intentionally one line
        # (e.g. MVEL template expressions, short inline snippets).
        if pre.get('data-oneliner') == 'true':
            continue
        code = pre.find('code')
        target = code if code else pre

        # Case A: <br/> tags used as line separators (CMS render-time pattern).
        # get_text() collapses them to nothing, making multi-line code appear
        # as one line.  Flag any <pre> that has <br/> children — these should
        # have been converted to \n at ingest/enrich time.
        if target.find('br'):
            brs = target.find_all('br')
            if len(brs) >= 2:  # 1 <br/> could be intentional; 2+ = line-break pattern
                # Extract text treating <br/> as newlines to get a code snippet
                import copy as _copy
                t_copy = _copy.copy(target)
                for br in t_copy.find_all('br'):
                    br.replace_with('\n')
                snippet = t_copy.get_text()[:60].replace('\n', ' ')
                issues.append(_issue(
                    'code_no_newlines', 'WARN',
                    f'<pre><code> uses <br/> for line breaks — must be converted '
                    f'to \\n at ingest/enrich time: "{snippet}"',
                    pre,
                ))
                continue

        # Case B: content is already one long line (no <br/>, no \n).
        text = target.get_text()
        # Only flag if: no newlines, reasonably long (not a one-liner by design),
        # and looks like multi-statement code (has ; or { or keywords implying lines)
        if '\n' in text:
            continue
        if len(text) < 40:
            continue
        if not re.search(r'[;{}]|when\s+\w|\bthen\b|\bend\b', text):
            continue
        snippet = text[:60]
        issues.append(_issue(
            'code_no_newlines', 'WARN',
            f'<pre><code> content has no line breaks — likely lost during ingest '
            f'(CMS adds <br/> at render time): "{snippet}"',
            pre,
        ))
    return issues


# Strong signals — one match alone is enough to flag as code.
# These are very specific patterns that essentially never appear in English prose.
_CODE_SIGNALS_STRONG: list[re.Pattern] = [
    re.compile(r'\brule[\s\xa0]*"', re.I),                    # DRL rule declaration (with or without space/nbsp)
    re.compile(r'^\s*when\s*$', re.M),                        # DRL when keyword alone
    re.compile(r'^\s*then\s*$', re.M),                        # DRL then keyword alone
    re.compile(r'\bpublic\s+(class|static\s+void|interface)\b'),  # Java class/method
    re.compile(r'\bimport\s+[\w.]+;'),                        # Java import
    re.compile(r'<\?xml\b'),                                   # XML declaration
]

# Weak signals — need 2+ to flag.  Each appears in English prose on its own.
_CODE_SIGNALS_WEAK: list[re.Pattern] = [
    re.compile(r'^\s*end\s*$', re.M),        # "end" alone on a line (also DRL, but common word)
    re.compile(r'\bnew\s+\w+\s*\('),         # Java constructor
    re.compile(r'<[a-zA-Z][a-zA-Z0-9]*\b[^>]*/?>'),  # XML/HTML tag in text
    re.compile(r'[;{}]\s*$', re.M),           # semicolons/braces at EOL
]

# For backwards compat — union used by fix_code_blocks.py _is_drl()
_CODE_SIGNALS = _CODE_SIGNALS_STRONG + _CODE_SIGNALS_WEAK


def check_linenumber_table_code(article: Tag) -> list[dict]:
    """
    Detect two-column tables used by old SyntaxHighlighter plugins to render
    code with line numbers: left column = line numbers, right column = code.

    Pattern A: <table><td><pre>1\\n2\\n</pre></td><td><pre>code</pre></td></table>
    Pattern B: <table><td><div>1</div><div>2</div></td>
                      <td><div><code>line</code></div>...</td></table>

    These must be converted to plain <pre><code> blocks — the table structure
    is a rendering artefact, not semantic content.
    LESSON: Old WordPress/Blogger SyntaxHighlighter plugin outputs code in
    two-column tables that look correct in HTML but are wrong for Markdown
    conversion and accessibility.
    """
    issues = []
    for table in article.find_all('table'):
        if not isinstance(table, Tag):
            continue
        tds = table.find_all('td')
        if len(tds) < 2:
            continue
        left_td, right_td = tds[0], tds[1]

        # Pattern A: left td has a <pre> with only digits/newlines
        left_pre = left_td.find('pre')
        is_a = (left_pre is not None and
                bool(left_pre.get_text().strip()) and
                all(c.isdigit() or c in '\n ' for c in left_pre.get_text().strip()))

        # Pattern B: left td has only <div> children, each a single digit
        if not is_a:
            children = [c for c in left_td.children if hasattr(c, 'name') and c.name]
            is_b = (bool(children) and
                    all(c.name == 'div' and c.get_text().strip().isdigit()
                        for c in children) and
                    bool(right_td.find(['code', 'pre'])))
        else:
            is_b = False

        if is_a or is_b:
            right_code = right_td.find(['pre', 'code'])
            snippet = right_code.get_text()[:50] if right_code else ''
            issues.append(_issue(
                'linenumber_table_code', 'WARN',
                f'Two-column line-number table — left column is line numbers, '
                f'right column is code. Convert to <pre><code>: "{snippet}"',
                table,
            ))
    return issues


def check_potential_code_blocks(article: Tag) -> list[dict]:
    """
    Detect paragraphs whose content looks like code but is formatted as
    inline HTML (nested <span>/<b> elements with <br/> line breaks) rather
    than a proper <pre><code> block.

    Blogger and similar CMSes sometimes store syntax-highlighted code as
    coloured <span> elements, which loses the semantic structure.  html2text
    renders these as plain prose with no code fence — the content is present
    but not highlighted.

    LESSON: If a <p> contains <br/> line breaks AND matches code patterns
    (DRL keywords, Java imports, curly braces, semicolons) it is almost
    certainly a code block that should be wrapped in <pre><code>.
    """
    issues = []
    for p in article.find_all(['p', 'div']):
        if not isinstance(p, Tag):
            continue
        # Skip elements already inside a code block
        if p.find_parent(['pre', 'code']):
            continue
        # Skip <div> elements that are direct children of <article> — these are
        # post-content wrapper divs, not code blocks.  Their text matches code
        # signals because they contain the actual code paragraphs as descendants.
        if p.name == 'div' and isinstance(p.parent, Tag) and p.parent.name == 'article':
            continue
        # Skip elements that already contain a <pre> block — their text naturally
        # includes code keywords from the embedded block, not from inline formatting.
        if p.find('pre'):
            continue
        # Must have at least one <br/> — code blocks use these for line breaks
        if not p.find('br'):
            continue
        text = p.get_text(separator='\n')
        if len(text) < 20 or len(text) > 5000:
            continue
        # Must match a strong signal OR two or more weak signals.
        # Weak signals alone (e.g. a lone semicolon at EOL, or "end" on its own
        # line) appear regularly in English prose and generate false positives.
        strong_hit = any(sig.search(text) for sig in _CODE_SIGNALS_STRONG)
        weak_hits  = sum(1 for sig in _CODE_SIGNALS_WEAK if sig.search(text))
        if not strong_hit and weak_hits < 2:
            continue
        # Extra confidence: has multiple short lines (not prose)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if len(lines) < 2:
            continue
        avg_len = sum(len(l) for l in lines) / len(lines)
        if avg_len > 80:  # long lines = probably prose, not code
            # (120 was too permissive — prose paragraphs with semicolons avg ~100+ chars/line)
            continue
        snippet = text[:60].replace('\n', ' ')
        issues.append(_issue(
            'potential_code_block', 'WARN',
            f'<p> with <br/> line breaks looks like unformatted code — '
            f'consider wrapping in <pre><code>: "{snippet}"',
            p,
        ))
    return issues


# ── Main entry point ──────────────────────────────────────────────────────────

def scan_post(html_path: Path, posts_dir: Path | None = None) -> list[dict]:
    """
    Scan a single archived HTML post and return all detected issues.
    Each issue is a dict with keys: type, level, detail, selector.

    posts_dir: canonical posts directory from the project config.
      Pass this when scanning an enriched copy (which lives outside the
      original posts tree) so that relative asset paths resolve correctly.
      When None, falls back to deriving the base from html_path (only
      correct when scanning the original post file).
    """
    try:
        soup = BeautifulSoup(html_path.read_text(errors='replace'), 'html.parser')
    except Exception as e:
        return [_issue('parse_error', 'ERROR', f'Could not parse HTML: {e}')]

    article = soup.find('article')
    if not article or not isinstance(article, Tag):
        # Fallback: try body
        article = soup.find('body')
    if not article or not isinstance(article, Tag):
        return [_issue('no_article', 'ERROR', 'No <article> or <body> element found')]

    # Pre-strip systematic WordPress bylines before scanning.
    # Format: "by Author - Month Day, Year Category+ Article"
    # These appear in every KIE post as an unclassed <div> and are already
    # removed by convert_post.py — reporting 580 identical issues adds noise.
    # Genuine chrome (sidebars, related posts, comment forms) is still detected.
    for tag in list(article.find_all(['p', 'div', 'span'])):
        if not isinstance(tag, Tag): continue
        text = tag.get_text(separator=' ', strip=True)
        if len(text) < 200 and re.match(r'^by\s+[A-Z]', text, re.I):
            tag.decompose()

    issues: list[dict] = []
    issues += check_data_placeholders(article)
    issues += check_noscript_remnants(article)
    issues += check_external_images(article)
    issues += check_tracking_pixels(article)
    issues += check_missing_local_images(article, html_path, posts_dir=posts_dir)
    issues += check_empty_embeds(article)
    issues += check_unreplaced_gists(article)
    issues += check_wordpress_chrome(article)
    issues += check_missing_image_signals(article)
    issues += check_md_notation_in_text(article)
    issues += check_suspicious_encoded_html(article)
    issues += check_layout_spacer_images(article)
    issues += check_imgur_images(article)
    issues += check_linenumber_table_code(article)
    issues += check_potential_code_blocks(article)
    issues += check_code_block_no_newlines(article)

    return issues


def scan_summary(issues: list[dict]) -> dict:
    """Return a count breakdown by issue type."""
    summary: dict[str, int] = {}
    for issue in issues:
        summary[issue['type']] = summary.get(issue['type'], 0) + 1
    return summary
