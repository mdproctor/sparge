"""
Sparge HTML enrichment — Stage 2 fixes applied before Markdown conversion.

All functions take a BeautifulSoup Tag (the article element) and mutate it
in-place, returning a stats dict. They never touch the original HTML file.

Public API
----------
replace_youtube_embeds(article, assets_dir, session) -> dict
replace_gist_embeds(article, github_token, session)  -> dict
normalise_code_classes(article)                       -> dict
detect_code_languages(article)                        -> dict
replace_embed_fallbacks(article)                      -> dict
enrich_post(html_path, enriched_path, assets_dir, github_token) -> dict
"""
from __future__ import annotations

import html as html_module
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup, Tag


# ── YouTube ────────────────────────────────────────────────────────────────────

def _youtube_video_id(url: str) -> str | None:
    """Extract YouTube video ID from embed, watch, or nocookie URLs."""
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace('www.', '')
    if host == 'youtu.be':
        return parsed.path.lstrip('/').split('/')[0] or None
    if host in ('youtube.com', 'youtube-nocookie.com'):
        if '/embed/' in parsed.path:
            return parsed.path.split('/embed/')[-1].split('/')[0].split('?')[0] or None
        qs = parse_qs(parsed.query)
        if 'v' in qs:
            return qs['v'][0]
    return None


def _download_thumbnail(video_id: str, assets_dir: Path, session) -> str | None:
    """
    Download YouTube thumbnail to assets_dir/yt_{video_id}.jpg.
    Tries maxresdefault then hqdefault. Returns filename or None.
    """
    dest = assets_dir / f'yt_{video_id}.jpg'
    if dest.exists():
        return dest.name
    for quality in ('maxresdefault', 'hqdefault'):
        url = f'https://img.youtube.com/vi/{video_id}/{quality}.jpg'
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 200 and resp.content:
                dest.write_bytes(resp.content)
                return dest.name
        except Exception:
            continue
    return None


def replace_youtube_embeds(article: Tag, assets_dir: Path, session) -> dict:
    """
    Replace YouTube iframes with a thumbnail figure.
    Returns {'youtube_replaced': int}.
    """
    replaced = 0
    for iframe in list(article.find_all('iframe')):
        src = iframe.get('src', '')
        video_id = _youtube_video_id(src)
        if not video_id:
            continue
        thumb_name = _download_thumbnail(video_id, assets_dir, session)
        thumb_src  = thumb_name if thumb_name else ''
        safe_id    = html_module.escape(video_id)
        safe_thumb = html_module.escape(thumb_src)
        watch_url  = f'https://www.youtube.com/watch?v={safe_id}'
        fig_html = (
            f'<figure class="video-embed">'
            f'<a href="{watch_url}" target="_blank" rel="noopener">'
            f'<img src="{safe_thumb}" alt="YouTube video" style="max-width:100%">'
            f'<figcaption>&#9654; Watch on YouTube</figcaption>'
            f'</a></figure>'
        )
        iframe.replace_with(BeautifulSoup(fig_html, 'lxml').find('figure'))
        replaced += 1
    return {'youtube_replaced': replaced}


# ── Gists ─────────────────────────────────────────────────────────────────────

def _gist_id_from_src(src: str) -> tuple[str | None, str | None]:
    """Parse gist.github.com script src → (user, gist_id) or (None, None)."""
    parsed = urlparse(src)
    if 'gist.github.com' not in parsed.netloc:
        return None, None
    parts = parsed.path.strip('/').split('/')
    if len(parts) >= 2:
        return parts[0], parts[1].removesuffix('.js') or None
    if len(parts) == 1:
        gid = parts[0].removesuffix('.js')
        return None, gid or None
    return None, None


def _fetch_gist(gist_id: str, github_token: str, session) -> list[dict] | None:
    """Fetch gist files via GitHub API. Returns list of file dicts or None on failure."""
    headers = {'Accept': 'application/vnd.github+json'}
    if github_token:
        headers['Authorization'] = f'Bearer {github_token}'
    try:
        resp = session.get(
            f'https://api.github.com/gists/{gist_id}',
            headers=headers,
            timeout=30,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return [
            {
                'filename': fname,
                'content':  fdata.get('content', ''),
                'language': (fdata.get('language') or 'text').lower(),
            }
            for fname, fdata in data.get('files', {}).items()
        ]
    except Exception:
        return None


def _gist_figure(user: str | None, gist_id: str, files: list[dict] | None) -> str:
    safe_user = html_module.escape(user) if user else None
    safe_id   = html_module.escape(gist_id)
    gist_url  = (
        f'https://gist.github.com/{safe_user}/{safe_id}'
        if safe_user else
        f'https://gist.github.com/{safe_id}'
    )
    if not files:
        return (
            f'<figure class="gist-embed">'
            f'<p class="archive-note">Gist embed could not be retrieved. '
            f'<a href="{gist_url}" target="_blank" rel="noopener">View original on GitHub Gist</a>.</p>'
            f'</figure>'
        )
    parts = []
    for f in files:
        escaped = html_module.escape(f['content'])
        parts.append(
            f'<figure class="gist-embed">'
            f'<figcaption><a href="{gist_url}" target="_blank" rel="noopener">'
            f'View on GitHub Gist: {html_module.escape(f["filename"])}</a></figcaption>'
            f'<pre><code class="language-{f["language"]}">{escaped}</code></pre>'
            f'</figure>'
        )
    return '\n'.join(parts)


def replace_gist_embeds(article: Tag, github_token: str, session) -> dict:
    """
    Replace Gist <script> tags with inlined code figures.
    Returns {'gists_replaced': int, 'gists_failed': int}.
    """
    replaced = failed = 0
    for script in list(article.find_all('script')):
        src = script.get('src', '')
        user, gist_id = _gist_id_from_src(src)
        if not gist_id:
            continue
        files = _fetch_gist(gist_id, github_token, session)
        success = bool(files)
        fig_html = _gist_figure(user, gist_id, files)
        script.replace_with(BeautifulSoup(fig_html, 'lxml').find('figure'))
        if success:
            replaced += 1
        else:
            failed += 1
    return {'gists_replaced': replaced, 'gists_failed': failed}


# ── Code class normalisation ──────────────────────────────────────────────────

_BRUSH_RE = re.compile(r'\bbrush\s*:\s*(\w+)\b', re.IGNORECASE)

_BRUSH_MAP = {
    'jscript': 'javascript', 'js': 'javascript',
    'csharp': 'csharp', 'c#': 'csharp',
    'c++': 'cpp', 'cplusplus': 'cpp',
    'plain': 'plaintext', 'text': 'plaintext',
    'shell': 'bash', 'sh': 'bash',
    'drl': 'drl',
}


def normalise_code_classes(article: Tag) -> dict:
    """
    Convert SyntaxHighlighter brush:X classes to language-X on <pre> elements.
    Returns {'classes_normalised': int}.
    """
    count = 0
    for pre in article.find_all('pre'):
        classes = ' '.join(pre.get('class', []))
        m = _BRUSH_RE.search(classes)
        if not m:
            continue
        lang = _BRUSH_MAP.get(m.group(1).lower(), m.group(1).lower())
        # Remove ALL brush-related tokens (brush:, the language word, etc.) and add language-X
        lang_token = m.group(1).lower()
        new_classes = [c for c in pre.get('class', [])
                       if not _BRUSH_RE.search(c)
                       and not re.match(r'^brush', c, re.IGNORECASE)
                       and c.lower() not in _BRUSH_MAP
                       and c.lower() != lang_token]
        new_classes.append(f'language-{lang}')
        pre['class'] = new_classes
        code = pre.find('code')
        if code:
            code_classes = [c for c in code.get('class', []) if not c.startswith('language-')]
            code_classes.append(f'language-{lang}')
            code['class'] = code_classes
        count += 1
    return {'classes_normalised': count}


# ── Language detection ────────────────────────────────────────────────────────

_LANG_PATTERNS: list[tuple[str, list[str]]] = [
    ('java',       [r'\bpublic\s+class\b', r'\bpublic\s+static\s+void\s+main\b', r'\bimport\s+java\.']),
    ('xml',        [r'<\?xml\s', r'xmlns=']),
    ('html',       [r'<!DOCTYPE\s+html', r'<html[\s>]']),
    ('sql',        [r'\bSELECT\b.+\bFROM\b', r'\bCREATE\s+TABLE\b', r'\bINSERT\s+INTO\b']),
    ('python',     [r'\bdef\s+\w+\s*\(', r'\bimport\s+\w+', r'\bprint\s*\(']),
    ('javascript', [r'\bfunction\s+\w+\s*\(', r'\bconst\s+\w+\s*=', r'=>']),
    ('bash',       [r'^#!.*\bsh\b', r'\$\{?\w+\}?']),
    ('drl',        [r'\brule\s+"', r'\bwhen\b.*\bthen\b', r'\bend\b']),
]


def detect_code_languages(article: Tag) -> dict:
    """
    Detect language of unlabelled <pre><code> blocks from content heuristics.
    Returns {'languages_detected': int}.
    """
    count = 0
    for pre in article.find_all('pre'):
        code = pre.find('code')
        if not code:
            continue
        existing = code.get('class', []) + pre.get('class', [])
        if any(c.startswith('language-') for c in existing):
            continue
        text = code.get_text()
        detected = None
        for lang, patterns in _LANG_PATTERNS:
            if any(re.search(p, text, re.MULTILINE | re.IGNORECASE) for p in patterns):
                detected = lang
                break
        if detected:
            classes = list(code.get('class', []))
            classes.append(f'language-{detected}')
            code['class'] = classes
            count += 1
    return {'languages_detected': count}


# ── Embed fallbacks ────────────────────────────────────────────────────────────

def replace_embed_fallbacks(article: Tag) -> dict:
    """
    Wrap any remaining <iframe>/<object>/<embed> elements with a live-embed figure.
    Should be called AFTER replace_youtube_embeds() so YouTube iframes are already gone.
    Returns {'embeds_wrapped': int}.
    """
    count = 0
    for tag in list(article.find_all(['iframe', 'object', 'embed'])):
        src = tag.get('src', '') or tag.get('data', '') or ''
        safe_src = html_module.escape(src)
        link = f'<a href="{safe_src}" target="_blank" rel="noopener">{safe_src}</a>' if src else 'unknown source'
        fig_html = (
            f'<figure class="live-embed">'
            f'<p class="archive-note">This embed could not be captured in the archive. '
            f'Original source: {link}</p>'
            f'</figure>'
        )
        tag.replace_with(BeautifulSoup(fig_html, 'lxml').find('figure'))
        count += 1
    return {'embeds_wrapped': count}


# ── Orchestrator ───────────────────────────────────────────────────────────────

def enrich_post(
    html_path: Path,
    enriched_path: Path,
    assets_dir: Path,
    github_token: str,
) -> dict:
    """
    Read original HTML, apply all fixes, write enriched copy.
    Returns combined stats dict.

    Fix order:
      1. replace_youtube_embeds   — before fallbacks
      2. replace_gist_embeds      — before fallbacks
      3. normalise_code_classes   — before language detection
      4. detect_code_languages    — after normalisation
      5. replace_embed_fallbacks  — last: catches remaining iframes
    """
    soup    = BeautifulSoup(html_path.read_text(encoding='utf-8', errors='replace'), 'lxml')
    article = soup.find('article') or soup.find('body') or soup

    session = requests.Session()
    stats: dict = {}

    stats.update(replace_youtube_embeds(article, assets_dir, session))
    stats.update(replace_gist_embeds(article, github_token, session))
    stats.update(normalise_code_classes(article))
    stats.update(detect_code_languages(article))
    stats.update(replace_embed_fallbacks(article))

    enriched_path.parent.mkdir(parents=True, exist_ok=True)
    enriched_path.write_text(str(soup), encoding='utf-8')

    return stats
