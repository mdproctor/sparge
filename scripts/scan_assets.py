"""
Asset Localisation Scanner
==========================
Scans a single archived HTML post for image/asset references and checks each
against the local filesystem.

Returns a summary dict:
  total          int  — total images found (excluding data: src and tracking pixels)
  localised      int  — local images that exist on disk
  broken         int  — images that are broken (local+missing or external)
  missing_local  list — relative paths of local images not found on disk
  external       list — external http/https URLs not yet localised
"""

from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

try:
    from .config import cfg   # imported as scripts.scan_assets (package)
except ImportError:
    from config import cfg    # imported as top-level module by server

# ── Known tracking domains (mirrors scan_html.py) ─────────────────────────────
TRACKING_DOMAINS = {
    'stats.wordpress.com', 'pixel.wp.com', 'pixel.quantserve.com',
    'b.scorecardresearch.com', 'beacon.krxd.net', 'ad.doubleclick.net',
    'googleads.g.doubleclick.net', 'www.google-analytics.com',
    'connect.facebook.net', 'platform.twitter.com', 'bat.bing.com',
    'ct.pinterest.com', 'analytics.twitter.com', 'px.ads.linkedin.com',
    'mc.yandex.ru', 'counter.yadro.ru',
}


def _is_tracking_pixel(img: Tag) -> bool:
    """Return True if this image is a 1×1 tracking pixel from a known domain."""
    src = img.get('src', '') or ''
    w   = str(img.get('width',  '') or '')
    h   = str(img.get('height', '') or '')
    is_tiny = (w in ('1', '0') and h in ('1', '0'))
    domain = urlparse(src).netloc.lower().lstrip('www.')
    return domain in TRACKING_DOMAINS or (is_tiny and src.startswith('http'))


def scan_assets(html_path: Path) -> dict:
    """
    Scan a single archived HTML post for image/asset references.

    Parameters
    ----------
    html_path : Path
        Absolute path to the HTML post file.

    Returns
    -------
    dict with keys:
      total         — images considered (excludes data: and tracking pixels)
      localised     — local images that exist on disk
      broken        — local-missing + external images
      missing_local — list of relative paths that don't exist
      external      — list of external URLs not yet localised
    """
    serve_root: Path = cfg['_root']

    try:
        soup = BeautifulSoup(html_path.read_text(errors='replace'), 'lxml')
    except Exception:
        return {'total': 0, 'localised': 0, 'broken': 0,
                'missing_local': [], 'external': []}

    article = soup.find('article')
    if not article or not isinstance(article, Tag):
        article = soup.find('body')
    if not article or not isinstance(article, Tag):
        return {'total': 0, 'localised': 0, 'broken': 0,
                'missing_local': [], 'external': []}

    missing_local: list[str] = []
    external: list[str] = []

    for img in article.find_all('img'):
        if not isinstance(img, Tag):
            continue
        src = img.get('src', '') or ''

        # Skip data: URIs — handled separately by the HTML scanner
        if src.startswith('data:'):
            continue

        # Skip tracking pixels — not content images
        if _is_tracking_pixel(img):
            continue

        if src.startswith('http://') or src.startswith('https://'):
            # External URL — not yet localised
            external.append(src)
        elif src.startswith('/'):
            # Absolute path relative to serve_root (e.g. /legacy/assets/...)
            abs_path = serve_root / src.lstrip('/')
            if not abs_path.exists():
                missing_local.append(src)
        elif src:
            # Relative path (e.g. ../../assets/...) — resolve from post directory
            abs_path = (html_path.parent / src).resolve()
            if not abs_path.exists():
                missing_local.append(src)

    total = len(missing_local) + len(external)
    # Count local images that exist: we need to tally all local imgs seen
    # Re-derive: walk again to count existing locals
    localised = 0
    for img in article.find_all('img'):
        if not isinstance(img, Tag):
            continue
        src = img.get('src', '') or ''
        if src.startswith('data:') or not src:
            continue
        if _is_tracking_pixel(img):
            continue
        if src.startswith('http://') or src.startswith('https://'):
            continue  # external — not localised
        # It's a local reference
        if src.startswith('/'):
            abs_path = serve_root / src.lstrip('/')
        else:
            abs_path = (html_path.parent / src).resolve()
        if abs_path.exists():
            localised += 1

    total = localised + len(missing_local) + len(external)
    broken = len(missing_local) + len(external)

    return {
        'total':         total,
        'localised':     localised,
        'broken':        broken,
        'missing_local': missing_local,
        'external':      external,
    }
