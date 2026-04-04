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

# ── Known tracking domains ─────────────────────────────────────────────────────
TRACKING_DOMAINS = {
    'stats.wordpress.com', 'pixel.wp.com', 'pixel.quantserve.com',
    'b.scorecardresearch.com', 'beacon.krxd.net', 'ad.doubleclick.net',
    'googleads.g.doubleclick.net', 'www.google-analytics.com',
    'connect.facebook.net', 'platform.twitter.com', 'bat.bing.com',
    'ct.pinterest.com', 'analytics.twitter.com', 'px.ads.linkedin.com',
    'mc.yandex.ru', 'counter.yadro.ru',
}

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
        is_tiny = (w in ('1','0') and h in ('1','0'))
        from urllib.parse import urlparse
        domain = urlparse(src).netloc.lower().lstrip('www.')
        if domain in TRACKING_DOMAINS or (is_tiny and src.startswith('http')):
            issues.append(_issue(
                'tracking_pixel', 'WARN',
                f'Tracking pixel from {domain or "unknown"}: {src[:60]}', img
            ))
    return issues


def check_missing_local_images(article: Tag, post_path: Path) -> list[dict]:
    """
    Images using ../../assets/ relative paths where the file doesn't exist.
    LESSON: After extraction, some images may have been referenced but never
    actually downloaded to the assets directory.
    """
    issues = []
    legacy_dir = post_path.parent.parent.parent  # posts/author/ -> posts/ -> legacy/
    for img in article.find_all('img'):
        if not isinstance(img, Tag):
            continue
        src = img.get('src', '') or ''
        if not src.startswith('../../assets/'):
            continue
        rel = src.replace('../../', '')
        abs_path = legacy_dir / rel
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


# ── Main entry point ──────────────────────────────────────────────────────────

def scan_post(html_path: Path) -> list[dict]:
    """
    Scan a single archived HTML post and return all detected issues.
    Each issue is a dict with keys: type, level, detail, selector.
    """
    try:
        soup = BeautifulSoup(html_path.read_text(errors='replace'), 'lxml')
    except Exception as e:
        return [_issue('parse_error', 'ERROR', f'Could not parse HTML: {e}')]

    article = soup.find('article')
    if not article or not isinstance(article, Tag):
        # Fallback: try body
        article = soup.find('body')
    if not article or not isinstance(article, Tag):
        return [_issue('no_article', 'ERROR', 'No <article> or <body> element found')]

    # Strip scripts/noscripts from the clone we inspect — except we DO want to check them
    # so we work on the raw article, specific checks handle scripts/noscripts explicitly

    issues: list[dict] = []
    issues += check_data_placeholders(article)
    issues += check_noscript_remnants(article)
    issues += check_external_images(article)
    issues += check_tracking_pixels(article)
    issues += check_missing_local_images(article, html_path)
    issues += check_empty_embeds(article)
    issues += check_unreplaced_gists(article)
    issues += check_wordpress_chrome(article)
    issues += check_missing_image_signals(article)

    return issues


def scan_summary(issues: list[dict]) -> dict:
    """Return a count breakdown by issue type."""
    summary: dict[str, int] = {}
    for issue in issues:
        summary[issue['type']] = summary.get(issue['type'], 0) + 1
    return summary
