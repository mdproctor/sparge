# Content Fidelity (Sub-project 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce an `enriched/` stage between Ingest and Generate MD where all HTML fixes are applied — YouTube thumbnail replacement, Gist inlining, code class normalisation, language detection, and embed fallbacks — without ever mutating the original HTML.

**Architecture:** A new `enrich.py` module applies all fixes to a BeautifulSoup article tree and writes the result to `projects/{id}/enriched/{slug}.html`. The Scan endpoint orchestrates enrichment after checking. Generate MD prefers the enriched file over the original. State tracks enrichment stats per post.

**Tech Stack:** Python 3.11+, BeautifulSoup4/lxml, requests (already in use), pytest

**Spec:** `blog-migrator/docs/pipeline.md` — read it before starting.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `blog-migrator/scripts/enrich.py` | **CREATE** | All HTML fix functions + `enrich_post()` orchestrator |
| `blog-migrator/tests/test_enrich.py` | **CREATE** | TDD tests for every function in `enrich.py` |
| `blog-migrator/scripts/config.py` | **MODIFY** | Add `github_token` field; resolve `_enriched_dir` |
| `blog-migrator/scripts/state.py` | **MODIFY** | Add `mark_enriched()` function |
| `blog-migrator/server.py` | **MODIFY** | Set `ENRICHED_DIR`; wire Scan → enrich; wire Generate MD → prefer enriched |

---

## Task 1: Config — add `github_token` and `_enriched_dir`

**Files:**
- Modify: `blog-migrator/scripts/config.py`

### Context
`config.py` loads `config.json` and resolves paths via `_resolve()`. We need:
1. `github_token` surfaced from config (empty string if absent)
2. `_enriched_dir` resolved — but enriched lives in the *project* dir, not serve_root. We'll expose a setter called from `server.py`'s `_activate_project()`.

- [ ] **Step 1: Write failing test**

Create `blog-migrator/tests/test_config.py`:

```python
"""Tests for config.py additions."""
import json
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from config import _resolve


def _make_cfg(extra=None):
    import tempfile
    tmp = tempfile.mkdtemp()
    d = {
        'project_name': 'Test',
        'serve_root': tmp,
        'source': {'posts_dir': 'posts', 'assets_dir': 'assets'},
        'output': {'md_dir': 'md'},
        'server': {'port': 9000},
    }
    if extra:
        d.update(extra)
    return d


def test_github_token_defaults_to_empty():
    cfg = _resolve(_make_cfg())
    assert cfg.get('github_token', '') == ''


def test_github_token_preserved():
    cfg = _resolve(_make_cfg({'github_token': 'ghp_abc123'}))
    assert cfg['github_token'] == 'ghp_abc123'
```

Run: `python3 -m pytest blog-migrator/tests/test_config.py -v`
Expected: PASS (both tests should already pass — `_resolve` doesn't strip unknown keys)

- [ ] **Step 2: Verify token is accessible from server**

Open `blog-migrator/scripts/config.py`. Confirm `github_token` survives `_resolve()` (it does — `_resolve` only adds keys, doesn't strip). No code change needed for `github_token` itself.

- [ ] **Step 3: Commit**

```bash
git add blog-migrator/tests/test_config.py
git commit -m "test(config): verify github_token round-trips through _resolve"
```

---

## Task 2: State — add `mark_enriched()`

**Files:**
- Modify: `blog-migrator/scripts/state.py`

### Context
After enrichment, we store stats in `state.json` under `entry['enriched']`. The `_enrich()` helper (which adds computed fields) must not conflict with the `enriched` data key — rename the helper to `_computed()`.

- [ ] **Step 1: Write failing test**

Add to `blog-migrator/tests/test_enrich.py` (create the file now, we'll add more later):

```python
"""Tests for enrich.py and enrichment state tracking."""
import json
import tempfile
from pathlib import Path
import sys

MIGRATOR = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR / 'scripts'))

import state as State


def _tmp_state(tmp_dir):
    p = Path(tmp_dir) / 'state.json'
    p.write_text('{}')
    State.set_state_file(p)
    return p


def test_mark_enriched_stores_stats(tmp_path):
    _tmp_state(tmp_path)
    State.update('my-post', {'slug': 'my-post', 'ingested_at': '2026-01-01'})
    State.mark_enriched('my-post', {
        'youtube_replaced': 2,
        'gists_replaced': 1,
        'gists_failed': 0,
        'classes_normalised': 5,
        'languages_detected': 3,
        'embeds_wrapped': 1,
    })
    entry = State.get('my-post')
    assert entry['enriched']['youtube_replaced'] == 2
    assert entry['enriched']['gists_replaced'] == 1
    assert 'generated_at' in entry['enriched']
```

Run: `python3 -m pytest blog-migrator/tests/test_enrich.py::test_mark_enriched_stores_stats -v`
Expected: FAIL — `AttributeError: module 'state' has no attribute 'mark_enriched'`

- [ ] **Step 2: Rename `_enrich()` → `_computed()` in state.py to avoid collision**

In `blog-migrator/scripts/state.py`, rename the internal helper at line 72 and its two call sites (lines 83, 87):

```python
# line 72 — rename
def _computed(entry: dict) -> dict:
    """Add computed fields before returning to callers."""
    entry = dict(entry)
    entry['md'] = dict(entry.get('md', {}))
    entry['md']['stale'] = _is_stale(entry)
    return entry

# line 83
def get_all() -> list[dict]:
    return [_computed(e) for e in _load().values()]

# line 87
def get(slug: str) -> dict | None:
    entry = _load().get(slug)
    return _computed(entry) if entry else None
```

- [ ] **Step 3: Add `mark_enriched()` to state.py**

After the `mark_md_generated()` function (~line 135), add:

```python
def mark_enriched(slug: str, stats: dict):
    """Record enrichment stats for a post."""
    update(slug, {'enriched': {
        'generated_at': _now(),
        'youtube_replaced':   stats.get('youtube_replaced', 0),
        'gists_replaced':     stats.get('gists_replaced', 0),
        'gists_failed':       stats.get('gists_failed', 0),
        'classes_normalised': stats.get('classes_normalised', 0),
        'languages_detected': stats.get('languages_detected', 0),
        'embeds_wrapped':     stats.get('embeds_wrapped', 0),
    }})
```

- [ ] **Step 4: Run test**

Run: `python3 -m pytest blog-migrator/tests/test_enrich.py::test_mark_enriched_stores_stats -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add blog-migrator/scripts/state.py blog-migrator/tests/test_enrich.py
git commit -m "feat(state): add mark_enriched() for enrichment stats tracking"
```

---

## Task 3: `enrich.py` — YouTube embed replacement

**Files:**
- Create: `blog-migrator/scripts/enrich.py`
- Modify: `blog-migrator/tests/test_enrich.py`

### Context
YouTube iframes appear as `<iframe src="https://www.youtube.com/embed/{id}...">` or `youtube-nocookie.com`. We download the thumbnail to `assets_dir/yt_{video_id}.jpg` (maxresdefault, fallback hqdefault), then replace the iframe with a `<figure class="video-embed">`.

- [ ] **Step 1: Write failing tests**

Append to `blog-migrator/tests/test_enrich.py`:

```python
from bs4 import BeautifulSoup
from unittest.mock import MagicMock, patch


def parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(f'<article>{html}</article>', 'lxml').find('article')


# ── YouTube ───────────────────────────────────────────────────────────────────

def test_youtube_iframe_replaced(tmp_path):
    from enrich import replace_youtube_embeds
    article = parse('<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" width="560"></iframe>')
    assets_dir = tmp_path / 'assets'
    assets_dir.mkdir()

    with patch('enrich.requests') as mock_req:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'FAKEJPEG'
        mock_req.get.return_value = mock_resp

        stats = replace_youtube_embeds(article, assets_dir, mock_req)

    assert article.find('iframe') is None
    fig = article.find('figure', class_='video-embed')
    assert fig is not None
    img = fig.find('img')
    assert img is not None
    assert 'dQw4w9WgXcQ' in img['src']
    assert stats['youtube_replaced'] == 1
    assert (assets_dir / 'yt_dQw4w9WgXcQ.jpg').exists()


def test_youtube_nocookie_replaced(tmp_path):
    from enrich import replace_youtube_embeds
    article = parse('<iframe src="https://www.youtube-nocookie.com/embed/abc123"></iframe>')
    assets_dir = tmp_path / 'assets'
    assets_dir.mkdir()

    with patch('enrich.requests') as mock_req:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'FAKEJPEG'
        mock_req.get.return_value = mock_resp
        stats = replace_youtube_embeds(article, assets_dir, mock_req)

    assert stats['youtube_replaced'] == 1


def test_non_youtube_iframe_untouched(tmp_path):
    from enrich import replace_youtube_embeds
    article = parse('<iframe src="https://example.com/embed"></iframe>')
    assets_dir = tmp_path / 'assets'
    assets_dir.mkdir()

    with patch('enrich.requests') as mock_req:
        stats = replace_youtube_embeds(article, assets_dir, mock_req)

    assert article.find('iframe') is not None
    assert stats['youtube_replaced'] == 0


def test_youtube_thumbnail_fallback(tmp_path):
    """If maxresdefault 404s, fall back to hqdefault."""
    from enrich import replace_youtube_embeds
    article = parse('<iframe src="https://www.youtube.com/embed/abc123"></iframe>')
    assets_dir = tmp_path / 'assets'
    assets_dir.mkdir()

    with patch('enrich.requests') as mock_req:
        not_found = MagicMock()
        not_found.status_code = 404
        ok = MagicMock()
        ok.status_code = 200
        ok.content = b'FAKEJPEG'
        mock_req.get.side_effect = [not_found, ok]
        stats = replace_youtube_embeds(article, assets_dir, mock_req)

    assert stats['youtube_replaced'] == 1
```

Run: `python3 -m pytest blog-migrator/tests/test_enrich.py -k youtube -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'enrich'`

- [ ] **Step 2: Create `blog-migrator/scripts/enrich.py` with YouTube support**

```python
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
    Tries maxresdefault then hqdefault. Returns relative path or None.
    """
    dest = assets_dir / f'yt_{video_id}.jpg'
    if dest.exists():
        return str(dest.name)
    for quality in ('maxresdefault', 'hqdefault'):
        url = f'https://img.youtube.com/vi/{video_id}/{quality}.jpg'
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 200 and resp.content:
                dest.write_bytes(resp.content)
                return str(dest.name)
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
```

- [ ] **Step 3: Run YouTube tests**

Run: `python3 -m pytest blog-migrator/tests/test_enrich.py -k youtube -v`
Expected: All 4 PASS

- [ ] **Step 4: Commit**

```bash
git add blog-migrator/scripts/enrich.py blog-migrator/tests/test_enrich.py
git commit -m "feat(enrich): YouTube iframe → thumbnail figure replacement"
```

---

## Task 4: `enrich.py` — Gist inlining

**Files:**
- Modify: `blog-migrator/scripts/enrich.py`
- Modify: `blog-migrator/tests/test_enrich.py`

### Context
Gists embed as `<script src="https://gist.github.com/{user}/{id}.js">`. We call the GitHub API (`/gists/{id}`) and replace the script tag with a `<figure class="gist-embed">` containing `<pre><code>` for each file. If the API fails, we emit a fallback note with a link to the Gist.

- [ ] **Step 1: Write failing tests**

Append to `blog-migrator/tests/test_enrich.py`:

```python
# ── Gists ─────────────────────────────────────────────────────────────────────

GIST_API_RESPONSE = {
    'files': {
        'example.java': {
            'filename': 'example.java',
            'language': 'Java',
            'content': 'public class Foo {}',
        }
    }
}


def test_gist_script_replaced_with_code(tmp_path):
    from enrich import replace_gist_embeds
    article = parse('<script src="https://gist.github.com/mproctor/abc123.js"></script>')

    with patch('enrich.requests') as mock_req:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = GIST_API_RESPONSE
        mock_req.get.return_value = resp
        stats = replace_gist_embeds(article, '', mock_req)

    assert article.find('script') is None
    fig = article.find('figure', class_='gist-embed')
    assert fig is not None
    code = fig.find('code')
    assert code is not None
    assert 'public class Foo' in code.get_text()
    assert stats['gists_replaced'] == 1
    assert stats['gists_failed'] == 0


def test_gist_api_failure_produces_fallback(tmp_path):
    from enrich import replace_gist_embeds
    article = parse('<script src="https://gist.github.com/mproctor/abc123.js"></script>')

    with patch('enrich.requests') as mock_req:
        resp = MagicMock()
        resp.status_code = 404
        mock_req.get.return_value = resp
        stats = replace_gist_embeds(article, '', mock_req)

    assert article.find('script') is None
    fig = article.find('figure', class_='gist-embed')
    assert fig is not None
    assert 'gist.github.com' in str(fig)
    assert stats['gists_failed'] == 1


def test_gist_uses_github_token(tmp_path):
    from enrich import replace_gist_embeds
    article = parse('<script src="https://gist.github.com/abc123.js"></script>')

    with patch('enrich.requests') as mock_req:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = GIST_API_RESPONSE
        mock_req.get.return_value = resp
        replace_gist_embeds(article, 'ghp_mytoken', mock_req)

    call_kwargs = mock_req.get.call_args[1]
    assert 'Authorization' in call_kwargs.get('headers', {})
    assert 'ghp_mytoken' in call_kwargs['headers']['Authorization']


def test_non_gist_script_untouched():
    from enrich import replace_gist_embeds
    article = parse('<script src="https://example.com/analytics.js"></script>')

    with patch('enrich.requests') as mock_req:
        stats = replace_gist_embeds(article, '', mock_req)

    assert article.find('script') is not None
    assert stats['gists_replaced'] == 0
```

Run: `python3 -m pytest blog-migrator/tests/test_enrich.py -k gist -v`
Expected: FAIL — `AttributeError: module 'enrich' has no attribute 'replace_gist_embeds'`

- [ ] **Step 2: Add `replace_gist_embeds()` to `enrich.py`**

Append to `blog-migrator/scripts/enrich.py`:

```python
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
```

- [ ] **Step 3: Run Gist tests**

Run: `python3 -m pytest blog-migrator/tests/test_enrich.py -k gist -v`
Expected: All 4 PASS

- [ ] **Step 4: Commit**

```bash
git add blog-migrator/scripts/enrich.py blog-migrator/tests/test_enrich.py
git commit -m "feat(enrich): Gist script tag → inlined code figure"
```

---

## Task 5: `enrich.py` — code class normalisation + language detection

**Files:**
- Modify: `blog-migrator/scripts/enrich.py`
- Modify: `blog-migrator/tests/test_enrich.py`

### Context
WordPress SyntaxHighlighter used `brush:java` or `brush: java` on `<pre>` elements. These must become `language-java` before Markdown conversion. Separately, `<pre><code>` blocks with no language class should get a language guessed from content.

- [ ] **Step 1: Write failing tests**

Append to `blog-migrator/tests/test_enrich.py`:

```python
# ── Code class normalisation ──────────────────────────────────────────────────

def test_brush_class_normalised():
    from enrich import normalise_code_classes
    article = parse('<pre class="brush: java">public class Foo {}</pre>')
    stats = normalise_code_classes(article)
    pre = article.find('pre')
    assert 'language-java' in pre.get('class', [])
    assert stats['classes_normalised'] == 1


def test_brush_class_no_space_normalised():
    from enrich import normalise_code_classes
    article = parse('<pre class="brush:sql">SELECT 1</pre>')
    stats = normalise_code_classes(article)
    pre = article.find('pre')
    assert 'language-sql' in pre.get('class', [])


def test_non_brush_class_untouched():
    from enrich import normalise_code_classes
    article = parse('<pre class="language-python">print()</pre>')
    stats = normalise_code_classes(article)
    assert stats['classes_normalised'] == 0


# ── Language detection ────────────────────────────────────────────────────────

def test_java_detected_from_content():
    from enrich import detect_code_languages
    article = parse('<pre><code>public class Foo { public static void main(String[] args) {} }</code></pre>')
    stats = detect_code_languages(article)
    code = article.find('code')
    assert 'language-java' in code.get('class', [])
    assert stats['languages_detected'] == 1


def test_xml_detected_from_content():
    from enrich import detect_code_languages
    article = parse('<pre><code><?xml version="1.0"?><root><child/></root></code></pre>')
    stats = detect_code_languages(article)
    code = article.find('code')
    assert 'language-xml' in code.get('class', [])


def test_already_labelled_code_not_redetected():
    from enrich import detect_code_languages
    article = parse('<pre><code class="language-python">print()</code></pre>')
    stats = detect_code_languages(article)
    assert stats['languages_detected'] == 0
```

Run: `python3 -m pytest blog-migrator/tests/test_enrich.py -k "normalise or detect" -v`
Expected: FAIL

- [ ] **Step 2: Add `normalise_code_classes()` and `detect_code_languages()` to `enrich.py`**

Append to `blog-migrator/scripts/enrich.py`:

```python
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
        new_classes = [c for c in pre.get('class', []) if not _BRUSH_RE.search(c)]
        new_classes.append(f'language-{lang}')
        pre['class'] = new_classes
        # Also tag inner <code> if present
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
    ('plaintext',  []),   # fallback — never matched by pattern
]


def detect_code_languages(article: Tag) -> dict:
    """
    Detect language of unlabelled <pre><code> blocks from content heuristics.
    Adds language-X class to the <code> element.
    Returns {'languages_detected': int}.
    """
    count = 0
    for pre in article.find_all('pre'):
        code = pre.find('code')
        if not code:
            continue
        existing = code.get('class', []) + pre.get('class', [])
        if any(c.startswith('language-') for c in existing):
            continue  # already labelled
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
```

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest blog-migrator/tests/test_enrich.py -k "normalise or detect" -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add blog-migrator/scripts/enrich.py blog-migrator/tests/test_enrich.py
git commit -m "feat(enrich): brush:X class normalisation + language detection heuristics"
```

---

## Task 6: `enrich.py` — embed fallbacks

**Files:**
- Modify: `blog-migrator/scripts/enrich.py`
- Modify: `blog-migrator/tests/test_enrich.py`

### Context
Any `<iframe>` not matched as YouTube, and any `<object>` or `<embed>`, should be wrapped in a `<figure class="live-embed">` with an archive note and a link to the original src — rather than being silently stripped.

- [ ] **Step 1: Write failing tests**

Append to `blog-migrator/tests/test_enrich.py`:

```python
# ── Embed fallbacks ───────────────────────────────────────────────────────────

def test_unknown_iframe_wrapped():
    from enrich import replace_embed_fallbacks
    article = parse('<iframe src="https://slides.com/foo/embed"></iframe>')
    stats = replace_embed_fallbacks(article)
    assert article.find('iframe') is None
    fig = article.find('figure', class_='live-embed')
    assert fig is not None
    assert 'slides.com' in str(fig)
    assert stats['embeds_wrapped'] == 1


def test_empty_iframe_wrapped():
    from enrich import replace_embed_fallbacks
    article = parse('<iframe src=""></iframe>')
    stats = replace_embed_fallbacks(article)
    fig = article.find('figure', class_='live-embed')
    assert fig is not None


def test_already_replaced_figure_untouched():
    from enrich import replace_embed_fallbacks
    article = parse('<figure class="video-embed"><img src="x.jpg"></figure>')
    stats = replace_embed_fallbacks(article)
    assert stats['embeds_wrapped'] == 0
```

Run: `python3 -m pytest blog-migrator/tests/test_enrich.py -k fallback -v`
Expected: FAIL

- [ ] **Step 2: Add `replace_embed_fallbacks()` to `enrich.py`**

Append to `blog-migrator/scripts/enrich.py`:

```python
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
```

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest blog-migrator/tests/test_enrich.py -k fallback -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add blog-migrator/scripts/enrich.py blog-migrator/tests/test_enrich.py
git commit -m "feat(enrich): unknown iframe/object/embed → live-embed fallback figure"
```

---

## Task 7: `enrich.py` — `enrich_post()` orchestrator

**Files:**
- Modify: `blog-migrator/scripts/enrich.py`
- Modify: `blog-migrator/tests/test_enrich.py`

### Context
`enrich_post()` reads the original HTML, runs all fix functions in order, writes the enriched copy to `enriched_path`, and returns combined stats. This is the only function called from `server.py`.

Fix order matters:
1. `replace_youtube_embeds` — before fallbacks (so YouTube iframes don't get wrapped)
2. `replace_gist_embeds` — before fallbacks (so Gist scripts don't get wrapped)
3. `normalise_code_classes` — before language detection (sets language- classes)
4. `detect_code_languages` — after normalisation
5. `replace_embed_fallbacks` — last (catches anything YouTube/Gist missed)

- [ ] **Step 1: Write failing test**

Append to `blog-migrator/tests/test_enrich.py`:

```python
# ── Orchestrator ──────────────────────────────────────────────────────────────

def test_enrich_post_writes_enriched_file(tmp_path):
    from enrich import enrich_post

    html = '''<html><body><article>
        <p>Hello</p>
        <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>
        <script src="https://gist.github.com/user/abc123.js"></script>
    </article></body></html>'''

    html_path     = tmp_path / 'my-post.html'
    enriched_path = tmp_path / 'enriched' / 'my-post.html'
    assets_dir    = tmp_path / 'assets'
    html_path.write_text(html)
    assets_dir.mkdir()
    enriched_path.parent.mkdir(parents=True)

    with patch('enrich.requests') as mock_req:
        yt_resp = MagicMock()
        yt_resp.status_code = 200
        yt_resp.content = b'JPEG'
        api_resp = MagicMock()
        api_resp.status_code = 404   # Gist fetch fails → fallback
        mock_req.get.side_effect = [yt_resp, api_resp]

        stats = enrich_post(html_path, enriched_path, assets_dir, '')

    assert enriched_path.exists()
    content = enriched_path.read_text()
    assert 'video-embed' in content       # YouTube replaced
    assert 'gist-embed' in content        # Gist fallback present
    assert '<iframe' not in content       # No raw iframes
    assert '<script' not in content       # No raw scripts
    assert stats['youtube_replaced'] == 1
    assert stats['gists_failed'] == 1
```

Run: `python3 -m pytest blog-migrator/tests/test_enrich.py::test_enrich_post_writes_enriched_file -v`
Expected: FAIL

- [ ] **Step 2: Add `enrich_post()` to `enrich.py`**

Append to `blog-migrator/scripts/enrich.py`:

```python
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
```

- [ ] **Step 3: Run all enrich tests**

Run: `python3 -m pytest blog-migrator/tests/test_enrich.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add blog-migrator/scripts/enrich.py blog-migrator/tests/test_enrich.py
git commit -m "feat(enrich): enrich_post() orchestrator — full pipeline"
```

---

## Task 8: Wire `server.py` — Scan triggers enrichment

**Files:**
- Modify: `blog-migrator/server.py`

### Context
`_activate_project()` sets `POSTS_DIR`, `MD_DIR`, etc. We add `ENRICHED_DIR`. The `_api_scan_html()` endpoint now calls `enrich_post()` after scanning and calls `State.mark_enriched()`. A warning is printed if Gists are detected but no `github_token` is set.

- [ ] **Step 1: Add `ENRICHED_DIR` global and set it in `_activate_project()`**

In `server.py`, find the globals block near line 55 where `POSTS_DIR`, `MD_DIR`, `SERVE_ROOT` are declared. Add:

```python
ENRICHED_DIR: Path = ROOT / 'projects' / 'kie-mark-proctor' / 'enriched'
```

In `_activate_project()`, add after the existing path assignments:

```python
global ENRICHED_DIR
ENRICHED_DIR = proj_dir / 'enriched'
ENRICHED_DIR.mkdir(exist_ok=True)
```

- [ ] **Step 2: Import `enrich_post` and `mark_enriched` at top of `server.py`**

Find the `try/except` import block for `_can_scan` (~line 135). Add a new block after it:

```python
try:
    from enrich import enrich_post as _enrich_post
    _can_enrich = True
except ImportError:
    _can_enrich = False
```

- [ ] **Step 3: Call `enrich_post` inside `_api_scan_html()`**

At the end of the `try` block in `_api_scan_html()`, before `self._json(200, ...)`, add:

```python
            # ── Enrichment ────────────────────────────────────────────────────
            if _can_enrich:
                github_token = cfg.get('github_token', '')
                # Warn if post has Gists but no token
                has_gists = any(
                    i.get('check') == 'unreplaced_gists' for i in issues
                )
                if has_gists and not github_token:
                    print(
                        f'WARNING: {slug} has Gist embeds but github_token is not set. '
                        f'Gists will be replaced with fallback links. '
                        f'Add github_token to config.json for full inlining.'
                    )
                enriched_path = ENRICHED_DIR / (slug + '.html')
                enrich_stats  = _enrich_post(
                    html_path, enriched_path,
                    cfg['_assets_dir'],
                    github_token,
                )
                State.mark_enriched(slug, enrich_stats)
                print(
                    f'Enriched: {slug} — '
                    f'{enrich_stats["youtube_replaced"]}yt '
                    f'{enrich_stats["gists_replaced"]}gist '
                    f'{enrich_stats["gists_failed"]}gist-fail '
                    f'{enrich_stats["classes_normalised"]}cls '
                    f'{enrich_stats["embeds_wrapped"]}wrap'
                )
```

- [ ] **Step 4: Manual smoke test**

With Sparge running (`python3 blog-migrator/server.py`), pick a post with a YouTube embed or Gist and hit Scan. Check:
- Console shows enrichment stats line
- `blog-migrator/projects/kie-mark-proctor/enriched/{slug}.html` exists
- `state.json` has `enriched` block for that slug

- [ ] **Step 5: Commit**

```bash
git add blog-migrator/server.py
git commit -m "feat(server): Scan now enriches HTML and writes enriched/ copy"
```

---

## Task 9: Wire `server.py` — Generate MD prefers enriched HTML

**Files:**
- Modify: `blog-migrator/server.py`

### Context
`_api_generate_md()` currently reads from `POSTS_DIR/{slug}.html`. It should prefer `ENRICHED_DIR/{slug}.html` if it exists, falling back to the original. This is the only change needed — the MD converter doesn't care which HTML it reads.

- [ ] **Step 1: Update `_api_generate_md()` to prefer enriched**

In `_api_generate_md()` (~line 404), replace:

```python
html_path = POSTS_DIR / (slug + '.html')
```

with:

```python
enriched_path = ENRICHED_DIR / (slug + '.html')
html_path = enriched_path if enriched_path.exists() else POSTS_DIR / (slug + '.html')
```

- [ ] **Step 2: Validate MD also uses enriched HTML for cross-checks**

In `_api_generate_md()`, the `validate_md` call already passes `html_path` for cross-checks. With the change above it will now use the enriched HTML — which is correct, since that's what we converted from.

No additional changes needed.

- [ ] **Step 3: Manual smoke test**

With a post that has been scanned (enriched file exists):
1. Click Generate MD
2. Check the output: YouTube embeds should appear as links, Gist content should be present as code blocks (not missing)

- [ ] **Step 4: Commit**

```bash
git add blog-migrator/server.py
git commit -m "feat(server): Generate MD prefers enriched HTML over original"
```

---

## Task 10: Update `scan_html.py` — suppress Gist warning after enrichment

**Files:**
- Modify: `blog-migrator/scripts/scan_html.py`

### Context
`check_unreplaced_gists` flags `<script src="gist.github.com...">` as an issue. After enrichment, these will be gone from the enriched HTML. But Scan currently runs on the **original** HTML for issue detection. We should move HTML scanning to run on the enriched HTML after it's produced. This is a small ordering fix in `server.py`.

- [ ] **Step 1: Reorder scan flow in `_api_scan_html()`**

The current flow in `_api_scan_html()`:
1. `_scan_post(html_path)` — scans original
2. `State.set_html_issues()`
3. `_scan_assets(html_path)` — scans original
4. `_enrich_post()` — enriches

Change to:
1. `_enrich_post()` — enrich first
2. `_scan_post(enriched_path if enriched_path.exists() else html_path)` — scan enriched
3. `State.set_html_issues()`
4. `_scan_assets(enriched_path if enriched_path.exists() else html_path)` — scan enriched

Update `_api_scan_html()` so enrichment runs before the scan checks:

```python
    def _api_scan_html(self, slug: str):
        html_path = POSTS_DIR / (slug + '.html')
        if not html_path.exists():
            self._json(404, {'error': f'HTML not found: {slug}'})
            return
        if not _can_scan:
            self._json(503, {'error': 'scan_html not available'})
            return
        try:
            enriched_path = ENRICHED_DIR / (slug + '.html')

            # ── Step 1: Enrich first ──────────────────────────────────────────
            if _can_enrich:
                github_token = cfg.get('github_token', '')
                enrich_stats = _enrich_post(
                    html_path, enriched_path,
                    cfg['_assets_dir'], github_token,
                )
                State.mark_enriched(slug, enrich_stats)
                # Warn if Gists present but no token
                if enrich_stats.get('gists_failed', 0) and not github_token:
                    print(
                        f'WARNING: {slug} has Gist embeds but github_token is not set. '
                        f'Add github_token to config.json for full inlining.'
                    )
                print(
                    f'Enriched: {slug} — '
                    f'{enrich_stats["youtube_replaced"]}yt '
                    f'{enrich_stats["gists_replaced"]}gist '
                    f'{enrich_stats["gists_failed"]}gist-fail '
                    f'{enrich_stats["classes_normalised"]}cls '
                    f'{enrich_stats["embeds_wrapped"]}wrap'
                )

            # ── Step 2: Scan the enriched HTML (or original if no enrich) ────
            scan_path = enriched_path if enriched_path.exists() else html_path
            raw_issues = _scan_post(scan_path)
            issues = [
                {'type': i['type'], 'level': i['level'],
                 'check': i['type'],
                 'detail': i['detail'], 'selector': i.get('selector')}
                for i in raw_issues
            ]
            State.set_html_issues(slug, issues)

            # ── Step 3: Asset scan ────────────────────────────────────────────
            if _can_scan_assets:
                from datetime import datetime, timezone
                asset_result = _scan_assets(scan_path)
                State.update(slug, {'assets': {
                    'total':      asset_result['total'],
                    'localised':  asset_result['localised'],
                    'broken':     asset_result['broken'],
                    'checked_at': datetime.now(timezone.utc).isoformat(),
                }})

            errors = sum(1 for i in issues if i['level'] == 'ERROR')
            warns  = sum(1 for i in issues if i['level'] == 'WARN')
            print(f'Scanned: {slug} — {errors}E {warns}W html')
            self._json(200, State.get(slug))
        except Exception as e:
            self._json(500, {'error': str(e)})
```

- [ ] **Step 2: Run existing scan tests to confirm nothing broke**

Run: `python3 -m pytest blog-migrator/tests/test_scan_html.py blog-migrator/tests/test_server_api.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add blog-migrator/server.py
git commit -m "fix(server): scan runs on enriched HTML so fixed embeds don't appear as issues"
```

---

## Task 11: Add `github_token` documentation to pipeline.md

The pipeline spec already has the GitHub token setup section. Verify it's accurate after implementation — no changes expected, but confirm token field name matches `config.json` exactly.

- [ ] **Step 1: Check pipeline.md setup section**

Open `blog-migrator/docs/pipeline.md` and verify:
- Field name is `github_token` (matches `cfg.get('github_token', '')` in server.py) ✓
- Instructions reference Settings → Developer settings → Tokens (classic) ✓

- [ ] **Step 2: Commit docs**

```bash
git add blog-migrator/docs/pipeline.md
git commit -m "docs: pipeline spec — content fidelity stage documented"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by task |
|---|---|
| Enriched HTML stage (`enriched/` folder) | Tasks 7, 8, 10 |
| YouTube thumbnail → figure replacement | Task 3 |
| Gist API inlining with fallback | Task 4 |
| Optional `github_token` with warning | Tasks 4, 8 |
| `brush:X` → `language-X` normalisation | Task 5 |
| Language heuristics for unlabelled code | Task 5 |
| Non-YouTube/Gist embed fallback | Task 6 |
| Generate MD prefers enriched HTML | Task 9 |
| Scan runs on enriched (not original) | Task 10 |
| State tracks enrichment stats | Task 2 |
| GitHub token setup documented | Task 11 |

**Placeholder scan:** None found — every step has concrete code or commands.

**Type consistency:** `enrich_post()` returns `dict` with keys `youtube_replaced`, `gists_replaced`, `gists_failed`, `classes_normalised`, `languages_detected`, `embeds_wrapped` — used consistently in Tasks 7, 8, and 2 (`mark_enriched`).

**Note:** SlideShare generalisation from the spec is not a separate task here because `replace_embed_fallbacks()` (Task 6) already handles any unknown iframe by wrapping it with a link — this covers the SlideShare case generically. A specific SlideShare thumbnail-fetching path can be added in a later iteration if desired.
