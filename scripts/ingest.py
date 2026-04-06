"""
Ingest Engine
=============
Fetches blog posts from any URL, detects the platform, discovers all post
URLs, extracts and cleans the article HTML, localises assets, and writes
posts to disk.

Public API
----------
  detect_platform(base_url, session) -> dict
  discover_urls(base_url, platform, session, author_filter=None) -> list[str]
  preview_post(url, session) -> dict
  ingest_post(url, session, posts_dir, serve_root) -> dict
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

# ── Constants ─────────────────────────────────────────────────────────────────

USER_AGENT = (
    'Mozilla/5.0 (compatible; BlogMigrator/1.0; '
    '+https://github.com/mdproctor/mdproctor.github.io)'
)

TIMEOUT = 20

# Junk selectors to strip from article content (mirrors scan_html.py)
JUNK_SELECTORS = [
    'script', 'style', 'nav', 'header', 'footer',
    '.sidebar', '#comments', '.comments-area',
    '.author-box', '.author-description', '.author-info',
    '.sharedaddy', '.addtoany_share_save_container',
    '[class*="wpDiscuz"]', '[class*="addtoany"]',
    '.jp-relatedposts', '.post-navigation',
    '.wpdiscuz-form-container', '.entry-header', '.entry-meta',
]

# Known tracking / analytics domains (mirrors scan_html.py and scan_assets.py)
TRACKING_DOMAINS = {
    'stats.wordpress.com', 'pixel.wp.com', 'pixel.quantserve.com',
    'b.scorecardresearch.com', 'beacon.krxd.net', 'ad.doubleclick.net',
    'googleads.g.doubleclick.net', 'www.google-analytics.com',
    'connect.facebook.net', 'platform.twitter.com', 'bat.bing.com',
    'ct.pinterest.com', 'analytics.twitter.com', 'px.ads.linkedin.com',
    'mc.yandex.ru', 'counter.yadro.ru',
}

# Candidate RSS/feed paths for generic blogs
GENERIC_FEED_PATHS = ['/feed/', '/rss.xml', '/atom.xml', '/feed.xml']


# ── URL normalisation ─────────────────────────────────────────────────────────

def _normalise_url(url: str) -> str:
    """Strip trailing slash. Preserve http:// (local/test servers); upgrade bare domains to https."""
    url = url.strip().rstrip('/')
    if url.startswith('http://'):
        pass  # keep as-is — caller chose http explicitly (localhost, mirrors, etc.)
    elif not url.startswith('https://'):
        url = 'https://' + url
    return url


def _session_get(url: str, session, stream: bool = False):
    """Perform a GET with standard headers and timeout. Returns response or None."""
    try:
        resp = session.get(
            url,
            headers={'User-Agent': USER_AGENT},
            timeout=TIMEOUT,
            allow_redirects=True,
            stream=stream,
        )
        return resp
    except Exception:
        return None


# ── Platform detection ────────────────────────────────────────────────────────

def detect_platform(base_url: str, session) -> dict:
    """
    Detect the blog platform and extract the blog name.

    Returns
    -------
    dict with keys:
      platform  — 'wordpress' | 'blogger' | 'ghost' | 'generic'
      base_url  — normalised base URL (no trailing slash, https)
      name      — blog title string
    """
    base_url = _normalise_url(base_url)

    # 1. WordPress: check wp-json REST API endpoint
    try:
        resp = session.get(
            f'{base_url}/wp-json/',
            headers={'User-Agent': USER_AGENT},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            try:
                data = resp.json()
                name = data.get('name', '')
                if not name:
                    name = _extract_site_name(base_url, session)
                return {'platform': 'wordpress', 'base_url': base_url, 'name': name}
            except Exception:
                pass
    except Exception:
        pass

    # 2. Blogger: check domain
    parsed = urlparse(base_url)
    host = parsed.netloc.lower()
    if 'blogger.com' in host or 'blogspot.com' in host:
        name = _extract_site_name(base_url, session)
        return {'platform': 'blogger', 'base_url': base_url, 'name': name}

    # 3. Ghost: check <meta name="generator"> on homepage
    resp = _session_get(base_url, session)
    if resp is not None and resp.status_code == 200:
        try:
            soup = BeautifulSoup(resp.text, 'lxml')
            gen = soup.find('meta', attrs={'name': 'generator'})
            if gen and isinstance(gen, Tag):
                content = gen.get('content', '') or ''
                if 'ghost' in content.lower():
                    name = _extract_name_from_soup(soup, base_url)
                    return {'platform': 'ghost', 'base_url': base_url, 'name': name}
            name = _extract_name_from_soup(soup, base_url)
        except Exception:
            name = ''
    else:
        name = ''

    return {'platform': 'generic', 'base_url': base_url, 'name': name}


def _extract_site_name(base_url: str, session) -> str:
    resp = _session_get(base_url, session)
    if resp is None or resp.status_code != 200:
        return ''
    try:
        soup = BeautifulSoup(resp.text, 'lxml')
        return _extract_name_from_soup(soup, base_url)
    except Exception:
        return ''


def _extract_name_from_soup(soup: BeautifulSoup, base_url: str) -> str:
    """Extract blog/site name from OG meta or <title>."""
    og = soup.find('meta', property='og:site_name')
    if og and isinstance(og, Tag):
        val = og.get('content', '') or ''
        if val.strip():
            return val.strip()
    title_tag = soup.find('title')
    if title_tag:
        return title_tag.get_text(strip=True)
    return urlparse(base_url).netloc


# ── URL discovery ─────────────────────────────────────────────────────────────

def discover_urls(
    base_url: str,
    platform: str,
    session,
    author_filter: Optional[str] = None,
) -> list[str]:
    """
    Discover all post URLs for a blog, ordered chronologically (oldest first).

    Discovery order (attempted in sequence, stopping at first success):
      1. sitemap.xml (or sitemap index → post-sitemap.xml)
      2. WordPress REST API (wp-json/wp/v2/posts)
      3. Platform-specific RSS (Blogger) or generic RSS feeds

    author_filter
        If set, filters to posts where the extracted author matches
        (case-insensitive). Only applied when the URL count ≤ 50 to avoid
        making an extra fetch per post at scale. For larger sets, caller
        should filter after ingestion via the sidecar metadata.
    """
    base_url = _normalise_url(base_url)
    urls: list[str] = []

    # ── 1. Sitemap ────────────────────────────────────────────────────────────
    urls = _try_sitemap(base_url, session)

    # ── 2. WordPress REST API ─────────────────────────────────────────────────
    if not urls and platform == 'wordpress':
        urls = _try_wp_rest(base_url, session)

    # ── 3. RSS / Atom feeds ───────────────────────────────────────────────────
    if not urls:
        if platform == 'blogger':
            urls = _try_blogger_feed(base_url, session)
        if not urls:
            urls = _try_generic_feeds(base_url, session)

    # Deduplicate preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    urls = deduped

    # Author filter (only when count is small enough to be practical)
    if author_filter and urls and len(urls) <= 50:
        filtered: list[str] = []
        for u in urls:
            try:
                meta = _fetch_post_meta(u, session)
                author = meta.get('author', '') or ''
                if author_filter.lower() in author.lower():
                    filtered.append(u)
            except Exception:
                filtered.append(u)  # keep on error
        urls = filtered

    return urls


def _is_post_url(url: str) -> bool:
    """
    Heuristic: a URL looks like a blog post if it has a date component
    or doesn't match known taxonomy/system paths.
    Security: non-http/https schemes are always rejected.
    """
    # Security: only http and https URLs are valid post URLs
    if not url.startswith(('http://', 'https://')):
        return False
    parsed = urlparse(url)
    path = parsed.path.lower()
    # Security: reject path traversal attempts
    if '..' in path:
        return False
    # Exclude taxonomy and system paths
    exclude_segments = {
        'category', 'tag', 'author', 'page', 'feed',
        'wp-content', 'wp-includes', 'wp-admin',
        'comment-page', 'attachment',
    }
    parts = [p for p in path.split('/') if p]
    if any(seg in exclude_segments for seg in parts):
        return False
    # Prefer URLs with a date-like segment (YYYY or YYYY/MM or YYYY/MM/DD)
    if re.search(r'/\d{4}/', path):
        return True
    # Accept any path with at least one meaningful slug segment
    return len(parts) >= 1


def _try_sitemap(base_url: str, session) -> list[str]:
    """Fetch sitemap.xml and extract post URLs. Follows sitemap indexes."""
    resp = _session_get(f'{base_url}/sitemap.xml', session)
    if resp is None or resp.status_code != 200:
        return []
    content = resp.text
    if not content.strip().startswith('<'):
        return []

    try:
        soup = BeautifulSoup(content, 'xml')
    except Exception:
        return []

    # Sitemap index: contains <sitemap> entries — look for post-sitemap
    sitemaps = soup.find_all('sitemap')
    if sitemaps:
        urls: list[str] = []
        for sm in sitemaps:
            loc = sm.find('loc')
            if not loc:
                continue
            sm_url = loc.get_text(strip=True)
            if 'post' in sm_url.lower():
                child_urls = _fetch_sitemap_locs(sm_url, session)
                urls.extend(child_urls)
        if not urls:
            # Fall back: fetch all child sitemaps
            for sm in sitemaps:
                loc = sm.find('loc')
                if not loc:
                    continue
                sm_url = loc.get_text(strip=True)
                child_urls = _fetch_sitemap_locs(sm_url, session)
                urls.extend(child_urls)
        return [u for u in urls if _is_post_url(u)]

    # Regular sitemap: contains <url><loc>…</loc></url>
    locs = [tag.get_text(strip=True) for tag in soup.find_all('loc')]
    return [u for u in locs if _is_post_url(u)]


def _fetch_sitemap_locs(url: str, session) -> list[str]:
    """Fetch a child sitemap and return all <loc> values."""
    resp = _session_get(url, session)
    if resp is None or resp.status_code != 200:
        return []
    try:
        soup = BeautifulSoup(resp.text, 'xml')
        return [tag.get_text(strip=True) for tag in soup.find_all('loc')]
    except Exception:
        return []


def _try_wp_rest(base_url: str, session) -> list[str]:
    """Paginate through WordPress REST API /wp/v2/posts to collect all URLs."""
    urls: list[str] = []
    page = 1
    while True:
        api_url = f'{base_url}/wp-json/wp/v2/posts?per_page=100&page={page}&_fields=link'
        resp = _session_get(api_url, session)
        if resp is None or resp.status_code != 200:
            break
        try:
            data = resp.json()
        except Exception:
            break
        if not data:
            break
        for item in data:
            link = item.get('link', '')
            if link:
                urls.append(link)
        if len(data) < 100:
            break
        page += 1
    return urls


def _try_blogger_feed(base_url: str, session) -> list[str]:
    """Fetch Blogger Atom/RSS feed and extract post links."""
    feed_url = f'{base_url}/feeds/posts/default?max-results=500&alt=rss'
    resp = _session_get(feed_url, session)
    if resp is None or resp.status_code != 200:
        return []
    try:
        soup = BeautifulSoup(resp.text, 'xml')
        links: list[str] = []
        for item in soup.find_all('item'):
            link_tag = item.find('link')
            if link_tag:
                links.append(link_tag.get_text(strip=True))
        return links
    except Exception:
        return []


def _try_generic_feeds(base_url: str, session) -> list[str]:
    """Try standard RSS/Atom feed paths and extract post links."""
    for path in GENERIC_FEED_PATHS:
        resp = _session_get(f'{base_url}{path}', session)
        if resp is None or resp.status_code != 200:
            continue
        content = resp.text
        if not content.strip().startswith('<'):
            continue
        try:
            soup = BeautifulSoup(content, 'xml')
            links: list[str] = []
            # RSS: <link> inside <item>
            for item in soup.find_all('item'):
                link_tag = item.find('link')
                if link_tag:
                    links.append(link_tag.get_text(strip=True))
            # Atom: <entry><link href="..."/>
            for entry in soup.find_all('entry'):
                link_tag = entry.find('link', href=True)
                if link_tag and isinstance(link_tag, Tag):
                    href = link_tag.get('href', '')
                    if href:
                        links.append(href)
            if links:
                return links
        except Exception:
            continue
    return []


# ── Metadata extraction helpers ───────────────────────────────────────────────

def _fetch_post_meta(url: str, session) -> dict:
    """Lightweight fetch of just the metadata fields from a post URL."""
    resp = _session_get(url, session)
    if resp is None or resp.status_code != 200:
        return {}
    try:
        soup = BeautifulSoup(resp.text, 'lxml')
        return _extract_metadata(soup, url)
    except Exception:
        return {}


def _extract_metadata(soup: BeautifulSoup, url: str) -> dict:
    """
    Extract title, date, author, categories and tags from a parsed page.

    Tries in order:
      1. JSON-LD structured data
      2. OpenGraph / standard meta tags
      3. Common WordPress HTML patterns
    """
    meta: dict = {
        'title': '',
        'date': '',
        'author': '',
        'categories': [],
        'tags': [],
    }

    # ── JSON-LD ───────────────────────────────────────────────────────────────
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.get_text())
            if isinstance(data, list):
                data = data[0]
            if not isinstance(data, dict):
                continue
            if not meta['title']:
                meta['title'] = data.get('headline', '') or data.get('name', '')
            if not meta['date']:
                meta['date'] = data.get('datePublished', '') or data.get('dateCreated', '')
            if not meta['author']:
                author_field = data.get('author', {})
                if isinstance(author_field, dict):
                    meta['author'] = author_field.get('name', '')
                elif isinstance(author_field, str):
                    meta['author'] = author_field
            if not meta['categories']:
                kws = data.get('keywords', '')
                if isinstance(kws, str) and kws:
                    meta['categories'] = [k.strip() for k in kws.split(',') if k.strip()]
        except Exception:
            pass

    # ── OpenGraph / article meta ──────────────────────────────────────────────
    if not meta['title']:
        og_title = soup.find('meta', property='og:title')
        if og_title and isinstance(og_title, Tag):
            meta['title'] = og_title.get('content', '') or ''

    if not meta['date']:
        for attr in ('article:published_time', 'article:modified_time'):
            tag = soup.find('meta', property=attr)
            if tag and isinstance(tag, Tag):
                val = tag.get('content', '') or ''
                if val:
                    meta['date'] = val
                    break

    if not meta['author']:
        author_meta = soup.find('meta', attrs={'name': 'author'})
        if author_meta and isinstance(author_meta, Tag):
            meta['author'] = author_meta.get('content', '') or ''

    # ── WordPress HTML patterns ───────────────────────────────────────────────
    if not meta['title']:
        h1 = soup.find('h1', class_='entry-title')
        if h1 and isinstance(h1, Tag):
            meta['title'] = h1.get_text(strip=True)

    if not meta['title']:
        title_tag = soup.find('title')
        if title_tag:
            raw = title_tag.get_text(strip=True)
            # Strip site name suffix ("Post Title - Site Name" or "Post Title | Site")
            for sep in (' - ', ' | ', ' — ', ' – '):
                if sep in raw:
                    raw = raw.split(sep)[0].strip()
                    break
            meta['title'] = raw

    if not meta['date']:
        time_tag = soup.find('time', datetime=True)
        if time_tag and isinstance(time_tag, Tag):
            meta['date'] = time_tag.get('datetime', '') or ''

    if not meta['author']:
        author_tag = soup.find('a', class_='author')
        if not author_tag:
            author_tag = soup.find(class_=re.compile(r'\bauthor\b'))
        if author_tag and isinstance(author_tag, Tag):
            meta['author'] = author_tag.get_text(strip=True)

    # Categories and tags from rel="category tag"
    if not meta['categories']:
        cats: list[str] = []
        tags: list[str] = []
        for a in soup.find_all('a', rel=True):
            if not isinstance(a, Tag):
                continue
            rels = a.get('rel', [])
            if isinstance(rels, str):
                rels = rels.split()
            if 'category' in rels:
                cats.append(a.get_text(strip=True))
            elif 'tag' in rels:
                tags.append(a.get_text(strip=True))
        meta['categories'] = cats
        meta['tags'] = tags

    # Normalise date to ISO format (YYYY-MM-DD)
    if meta['date']:
        meta['date'] = _normalise_date(meta['date'])

    return meta


def _normalise_date(raw: str) -> str:
    """Try to extract YYYY-MM-DD from a date string."""
    if not raw:
        return ''
    # Already ISO: 2006-01-15 or 2006-01-15T10:30:00Z
    m = re.match(r'(\d{4}-\d{2}-\d{2})', raw)
    if m:
        return m.group(1)
    return raw[:10] if len(raw) >= 10 else raw


def _make_slug(date_str: str, url: str) -> str:
    """
    Generate a slug in the form YYYY-MM-DD-{url-path-last-segment}.
    Strips .html extension, lowercases, limits to 80 chars total.
    """
    # Extract last meaningful path segment from URL
    path = urlparse(url).path.rstrip('/')
    segment = path.split('/')[-1] if path else 'post'
    segment = re.sub(r'\.html?$', '', segment, flags=re.I)
    segment = re.sub(r'[^\w-]', '-', segment.lower())
    segment = re.sub(r'-+', '-', segment).strip('-')

    prefix = date_str if date_str else 'undated'
    slug = f'{prefix}-{segment}'
    return slug[:80]


# ── Article extraction ────────────────────────────────────────────────────────

def _find_article(soup: BeautifulSoup) -> Optional[Tag]:
    """
    Find the main article element in order of preference.
    Returns None if nothing usable is found.
    """
    for selector in (
        'article',
        'div.entry-content',
        'div#content',
        'main',
        'body',
    ):
        el = soup.select_one(selector)
        if el and isinstance(el, Tag):
            return el
    return None


def _strip_junk(article: Tag):
    """Remove junk/chrome elements from the article in-place."""
    for selector in JUNK_SELECTORS:
        for el in article.select(selector):
            el.decompose()

    # Also remove noscript tags
    for ns in article.find_all('noscript'):
        ns.decompose()

    # ── Security: sanitise all surviving tags ────────────────────────────────
    # Strip event handler attributes (on*) and javascript: href/src values.
    # This prevents XSS from blog content that survived junk stripping.
    for tag in article.find_all(True):
        if not isinstance(tag, Tag):
            continue
        # Remove all on* event handler attributes
        dangerous_attrs = [a for a in list(tag.attrs) if a.lower().startswith('on')]
        for attr in dangerous_attrs:
            del tag[attr]
        # Sanitise href and src: strip javascript: scheme
        for url_attr in ('href', 'src', 'action', 'formaction', 'data'):
            val = tag.get(url_attr, '')
            if val and val.strip().lower().lstrip('\x00\t\n\r ').startswith('javascript:'):
                del tag[url_attr]
        # Strip style attributes containing url() references to external hosts
        style = tag.get('style', '')
        if style and re.search(r'url\s*\(\s*["\']?https?://', style, re.I):
            del tag['style']

    # Remove tracking pixels
    for img in article.find_all('img'):
        if not isinstance(img, Tag):
            continue
        src = img.get('src', '') or ''
        w = str(img.get('width', '') or '')
        h = str(img.get('height', '') or '')
        is_tiny = w in ('1', '0') and h in ('1', '0')
        domain = urlparse(src).netloc.lower().lstrip('www.')
        if domain in TRACKING_DOMAINS or (is_tiny and src.startswith('http')):
            img.decompose()


# ── Asset helpers ─────────────────────────────────────────────────────────────

def _asset_local_path(
    url: str, serve_root: Path, subdir: str, date_str: str = ''
) -> tuple[Path, str]:
    """
    Compute the local filesystem path and web-relative URL for an asset.

    Assets are stored under:
      serve_root/assets/{subdir}/{YYYY}/{MM}/{hash12}-{filename}

    Returns (absolute_path_on_disk, relative_url_for_html).
    """
    parsed = urlparse(url)
    filename = parsed.path.split('/')[-1] or 'asset'
    # Sanitise filename
    filename = re.sub(r'[^\w.\-]', '_', filename)
    if not filename or filename == '_':
        filename = 'asset'
    # Limit filename length
    filename = filename[-60:] if len(filename) > 60 else filename

    # Hash the URL for deduplication
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]

    # Derive year/month from date_str if available
    if date_str and re.match(r'\d{4}-\d{2}', date_str):
        year = date_str[:4]
        month = date_str[5:7]
    else:
        year = 'undated'
        month = ''

    parts = ['assets', subdir, year]
    if month:
        parts.append(month)

    rel_dir = '/'.join(parts)
    rel_url = f'/{rel_dir}/{url_hash}-{filename}'
    abs_path = serve_root / rel_dir.lstrip('/') / f'{url_hash}-{filename}'
    return abs_path, rel_url


def _download_asset(url: str, local_path: Path, session) -> bool:
    """
    Download url to local_path. Returns True on success.
    Skips download if local_path already exists (hash-named, so existence = match).
    """
    if local_path.exists():
        return True
    local_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        resp = session.get(
            url,
            headers={'User-Agent': USER_AGENT},
            timeout=TIMEOUT,
            stream=True,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return False
        with open(local_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        return True
    except Exception:
        if local_path.exists():
            local_path.unlink(missing_ok=True)
        return False


def _rewrite_css_urls(css_text: str, css_url: str, serve_root: Path, session) -> str:
    """
    Rewrite url(...) references inside a downloaded CSS file so they point
    to locally downloaded copies. Returns the rewritten CSS text.
    """
    def replace_url(match):
        raw = match.group(1).strip('"\'')
        if raw.startswith('data:') or raw.startswith('#') or not raw:
            return match.group(0)
        abs_url = urljoin(css_url, raw)
        local_path, rel_url = _asset_local_path(abs_url, serve_root, 'fonts')
        _download_asset(abs_url, local_path, session)
        return f'url("{rel_url}")'

    return re.sub(r'url\(\s*([^)]+)\s*\)', replace_url, css_text)


def _is_tracking_pixel(img: Tag) -> bool:
    src = img.get('src', '') or ''
    w = str(img.get('width', '') or '')
    h = str(img.get('height', '') or '')
    is_tiny = w in ('1', '0') and h in ('1', '0')
    domain = urlparse(src).netloc.lower().lstrip('www.')
    return domain in TRACKING_DOMAINS or (is_tiny and src.startswith('http'))


# ── Core fetch-and-extract ────────────────────────────────────────────────────

def _fetch_and_extract(url: str, session) -> dict:
    """
    Fetch a post URL and extract cleaned article HTML + metadata.

    Returns a dict with keys:
      slug, title, date, author, categories, tags, original_url,
      html (str), asset_count (int), error (str|None)
    """
    result: dict = {
        'slug': '',
        'title': '',
        'date': '',
        'author': '',
        'categories': [],
        'tags': [],
        'original_url': url,
        'html': '',
        'asset_count': 0,
        'error': None,
    }

    # Fetch
    try:
        resp = session.get(
            url,
            headers={'User-Agent': USER_AGENT},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
    except Exception as e:
        err = str(e)
        if 'timeout' in err.lower() or 'timed out' in err.lower():
            result['error'] = 'Connection timeout'
        else:
            result['error'] = f'Fetch error: {err}'
        return result

    if resp.status_code != 200:
        result['error'] = f'HTTP {resp.status_code}'
        return result

    # Parse
    try:
        soup = BeautifulSoup(resp.text, 'lxml')
    except Exception as e:
        result['error'] = f'Parse error: {e}'
        return result

    # Metadata
    meta = _extract_metadata(soup, url)
    result.update(meta)

    # Article element
    article = _find_article(soup)
    if article is None:
        result['error'] = 'No article content found'
        return result

    # Strip junk
    _strip_junk(article)

    # Count assets before any localisation
    asset_count = 0
    for img in article.find_all('img'):
        if not isinstance(img, Tag):
            continue
        src = img.get('src', '') or ''
        if src.startswith('data:') or not src:
            continue
        if _is_tracking_pixel(img):
            continue
        asset_count += 1
    for link in article.find_all('link', rel=True):
        if not isinstance(link, Tag):
            continue
        rels = link.get('rel', [])
        if isinstance(rels, str):
            rels = [rels]
        if 'stylesheet' in rels and link.get('href', ''):
            asset_count += 1
    result['asset_count'] = asset_count

    # Slug
    result['slug'] = _make_slug(result['date'], url)

    # Serialise cleaned HTML
    result['html'] = str(article)

    return result


# ── Public API ────────────────────────────────────────────────────────────────

def preview_post(url: str, session) -> dict:
    """
    Fetch and extract ONE post WITHOUT writing to disk.

    Returns
    -------
    dict with keys:
      slug, title, date, author, categories, tags, original_url,
      html (str — cleaned article HTML), asset_count (int), error (str|None)
    """
    return _fetch_and_extract(url, session)


def ingest_post(url: str, session, posts_dir: Path, serve_root: Path) -> dict:
    """
    Fetch, extract, localise assets, and WRITE post to disk.

    Writes
    ------
      posts_dir/{slug}.html  — cleaned article HTML with local asset paths
      posts_dir/{slug}.json  — metadata sidecar

    Returns
    -------
    dict with same keys as preview_post minus 'html', plus:
      asset_localised (int), asset_failed (int), wrote (bool)
    """
    data = _fetch_and_extract(url, session)

    result = {k: v for k, v in data.items() if k != 'html'}
    result['asset_localised'] = 0
    result['asset_failed'] = 0
    result['wrote'] = False

    if data.get('error'):
        return result

    # Re-parse the cleaned article HTML for asset localisation
    try:
        article_soup = BeautifulSoup(data['html'], 'lxml')
        # lxml wraps in html/body — find the top-level element
        body = article_soup.find('body')
        article = body.find() if body else article_soup.find()  # type: ignore[union-attr]
        if article is None or not isinstance(article, Tag):
            article = article_soup
    except Exception as e:
        result['error'] = f'Re-parse error: {e}'
        return result

    date_str = data.get('date', '')

    # ── Localise images ───────────────────────────────────────────────────────
    for img in article.find_all('img'):  # type: ignore[union-attr]
        if not isinstance(img, Tag):
            continue
        src = img.get('src', '') or ''
        if not src or src.startswith('data:'):
            continue
        if _is_tracking_pixel(img):
            img.decompose()
            continue
        if not src.startswith('http'):
            # Already relative/local — skip
            continue
        local_path, rel_url = _asset_local_path(src, serve_root, 'images', date_str)
        ok = _download_asset(src, local_path, session)
        if ok:
            img['src'] = rel_url
            result['asset_localised'] += 1
        else:
            result['asset_failed'] += 1

    # ── Localise stylesheets ──────────────────────────────────────────────────
    for link in article.find_all('link', rel=True):  # type: ignore[union-attr]
        if not isinstance(link, Tag):
            continue
        rels = link.get('rel', [])
        if isinstance(rels, str):
            rels = [rels]
        if 'stylesheet' not in rels:
            continue
        href = link.get('href', '') or ''
        if not href or not href.startswith('http'):
            continue
        local_path, rel_url = _asset_local_path(href, serve_root, 'css', date_str)
        if not local_path.exists():
            resp = _session_get(href, session)
            if resp is not None and resp.status_code == 200:
                css_text = _rewrite_css_urls(resp.text, href, serve_root, session)
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_text(css_text, encoding='utf-8')
                result['asset_localised'] += 1
            else:
                result['asset_failed'] += 1
                continue
        else:
            result['asset_localised'] += 1
        link['href'] = rel_url

    # ── Remove remaining script tags ──────────────────────────────────────────
    for script in article.find_all('script'):  # type: ignore[union-attr]
        script.decompose()

    # ── Write to disk ─────────────────────────────────────────────────────────
    slug = data['slug']
    posts_dir.mkdir(parents=True, exist_ok=True)

    html_path = posts_dir / f'{slug}.html'
    json_path = posts_dir / f'{slug}.json'

    try:
        html_path.write_text(str(article), encoding='utf-8')
    except Exception as e:
        result['error'] = f'Write error (html): {e}'
        return result

    sidecar = {
        'slug':         slug,
        'title':        data.get('title', ''),
        'date':         data.get('date', ''),
        'author':       data.get('author', ''),
        'categories':   data.get('categories', []),
        'tags':         data.get('tags', []),
        'original_url': url,
        'ingested_at':  datetime.now().isoformat(timespec='seconds'),
        'asset_localised': result['asset_localised'],
        'asset_failed':    result['asset_failed'],
    }

    try:
        json_path.write_text(
            json.dumps(sidecar, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
    except Exception as e:
        result['error'] = f'Write error (json): {e}'
        return result

    result['wrote'] = True
    return result
