"""
Shared constants used across multiple Sparge scripts.

Centralised here to prevent the silent drift that occurs when the same
constant is defined independently in several files (scan_html.py,
scan_assets.py, ingest.py previously all defined TRACKING_DOMAINS
and _is_tracking_pixel identically — any update to one missed the others).

MIGRATION NOTE (Quarkus/Java):
  All constants in this file map directly to Java static final fields or
  enum sets.  TRACKING_DOMAINS → Set<String>, CSS_JUNK_SELECTORS →
  List<String>, etc.  The is_tracking_pixel() helper maps to a static
  boolean method.  No Python-specific behaviour is used here.
"""
from pathlib import Path
from urllib.parse import urlparse


# ── Tracking / analytics domains ──────────────────────────────────────────────
# Images from these domains are tracking pixels with no archival value.
# Used by: scan_html.py, scan_assets.py, ingest.py
TRACKING_DOMAINS: frozenset = frozenset({
    'stats.wordpress.com', 'pixel.wp.com', 'pixel.quantserve.com',
    'b.scorecardresearch.com', 'beacon.krxd.net', 'ad.doubleclick.net',
    'googleads.g.doubleclick.net', 'www.google-analytics.com',
    'connect.facebook.net', 'platform.twitter.com', 'bat.bing.com',
    'ct.pinterest.com', 'analytics.twitter.com', 'px.ads.linkedin.com',
    'mc.yandex.ru', 'counter.yadro.ru',
})


def is_tracking_pixel(src: str, width: str = '', height: str = '') -> bool:
    """Return True if this image is a tracking pixel that should be removed.

    Matches on domain membership in TRACKING_DOMAINS OR on dimensions (1×1 or 0×0)
    combined with an http/https src, which catches pixels from domains not yet
    in the list.

    MIGRATION NOTE (Quarkus/Java): implement as a static method.
      - urlparse → java.net.URI.getHost()
      - width/height comparison should use .strip() / trim() before parsing int
    """
    domain = urlparse(src).netloc.lower().lstrip('www.')
    is_tiny = width.strip() in ('1', '0') and height.strip() in ('1', '0')
    return domain in TRACKING_DOMAINS or (is_tiny and src.startswith('http'))


# ── WordPress / CMS chrome CSS selectors ──────────────────────────────────────
# These selectors identify blog-template chrome that is not article content.
# Used by: convert_post.py (JUNK_SELECTORS), scan_html.py (CHROME_SELECTORS).
#
# NOTE: convert_post.py and ingest.py use OVERLAPPING but not identical sets.
# ingest.py adds nav/header/footer (needed for full-page scraping of live URLs);
# convert_post.py omits these (pre-extracted article HTML won't have them).
# Both sets are kept separate below; import the right one for each context.
#
# MIGRATION NOTE (Quarkus/Java): these become Jsoup Element.select() calls.
# Jsoup CSS selectors are compatible with BS4's soup.select() syntax.

JUNK_SELECTORS_CONVERTER = [
    # Selectors used in convert_post.py when processing already-extracted article HTML.
    '.entry-header', 'header', '.entry-meta', '.author-box', '.author-description',
    '.author-info', '.addtoany_share_save_container', '.addtoany_share_save',
    '.sharedaddy', '#comments', '.comments-area', '.jp-relatedposts',
    '.post-navigation', '.wpdiscuz-form-container',
    '[class*="wpDiscuz"]', '[class*="addtoany"]',
    'script', 'style',
]

JUNK_SELECTORS_INGEST = [
    # Selectors used in ingest.py when scraping full live pages.
    # Superset of JUNK_SELECTORS_CONVERTER; includes page-level chrome not
    # present in pre-extracted article HTML.
    'nav', 'header', 'footer', '.sidebar', 'main',
    '.entry-header', '.entry-meta', '.author-box', '.author-description',
    '.author-info', '.addtoany_share_save_container', '.addtoany_share_save',
    '.sharedaddy', '#comments', '.comments-area', '.jp-relatedposts',
    '.post-navigation', '.wpdiscuz-form-container',
    '[class*="wpDiscuz"]', '[class*="addtoany"]',
    'script', 'style', 'noscript',
]
