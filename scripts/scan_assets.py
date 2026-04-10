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
    from .config import cfg       # imported as scripts.scan_assets (package)
    from .constants import is_tracking_pixel as _is_pixel
except ImportError:
    from config import cfg        # imported as top-level module by server
    from constants import is_tracking_pixel as _is_pixel


def _is_tracking_pixel(img: Tag) -> bool:
    """Return True if this image is a 1×1 tracking pixel from a known domain."""
    src = img.get('src', '') or ''
    w   = str(img.get('width',  '') or '')
    h   = str(img.get('height', '') or '')
    return _is_pixel(src, w, h)


def scan_assets(html_path: Path, original_path: Path | None = None) -> dict:
    """
    Scan a single archived HTML post for image/asset references.

    Parameters
    ----------
    html_path : Path
        Absolute path to the HTML file to scan (may be the enriched copy).
    original_path : Path | None
        Absolute path to the ORIGINAL source HTML in the posts directory.
        When html_path is an enriched copy outside the original posts tree,
        relative image paths like '../../assets/...' must be resolved from
        original_path.parent (not html_path.parent) to find the actual files.
        If None, falls back to html_path.parent for relative path resolution.

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
    # Base directory for resolving relative paths (e.g. ../../assets/...)
    relative_base: Path = (original_path or html_path).parent

    try:
        soup = BeautifulSoup(html_path.read_text(errors='replace'), 'html.parser')
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
            # Relative path (e.g. ../../assets/...) — resolve from the ORIGINAL
            # post directory, not from html_path.parent.  When scanning an enriched
            # copy outside the posts tree, relative_base ensures the path resolves
            # to where the assets actually live.
            abs_path = (relative_base / src).resolve()
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
            abs_path = (relative_base / src).resolve()
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
