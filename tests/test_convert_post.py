"""
Tests for scripts/convert_post.py — HTML-to-Markdown conversion.

Regression guards for:
  1. lxml double-encoding — non-ASCII characters must survive conversion
     (em dashes, curly quotes, en dashes are common in blog posts)
  2. json_path parameter — sidecar can live separately from the HTML file
     (needed when converting enriched copies outside the original posts tree)
  3. Front matter fields sourced from JSON sidecar

Known garbling signatures — any of these in the output is a bug:

  Pattern A: 'ÃÂÃÂ' — lxml double-encoding.
    Origin: BeautifulSoup(html, 'lxml') sees <meta charset="utf-8">, re-encodes
    the Python str to UTF-8 bytes internally, then serialises as Latin-1.
    U+201C (") → UTF-8 E2 80 9C → Latin-1 chars â + ctrl → re-encoded Ã¢ÂÂ

  Pattern B: 'Ã¢Â' — triple-encoding (old server writing lxml output to disk).
    Produced when Pattern A output is itself treated as a byte sequence and
    encoded again. Seen when the old convert_post.py (lxml) wrote a garbled
    MD file, then something re-encoded those bytes as UTF-8 again.
    E.g. U+201C → lxml → Ã¢ÂÂ bytes → re-read as Latin-1 → re-encoded → Ã¢Â…

  Pattern C: 'â€' — single Windows-1252 mismatch.
    Produced when UTF-8 bytes are decoded as Windows-1252 and displayed as-is.

  Any of these means a parser or encoding step is wrong somewhere in the pipeline.

Run: python3 -m pytest tests/test_convert_post.py -v
"""
import json
import sys
from pathlib import Path

import pytest

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

# ── Garbling signatures ───────────────────────────────────────────────────────

# All known garbling patterns. Any match = encoding bug.
GARBLING_SIGNATURES = [
    'ÃÂÃÂ',   # Pattern A: lxml double-encoding via <meta charset> sniffing
    'Ã¢Â',    # Pattern B: triple-encoding (lxml output re-encoded)
    'â€',      # Pattern C: UTF-8 decoded as Windows-1252
    'Ã¢ÂÂ',   # Pattern B variant — the exact triple-encode of left double quote
]


def assert_not_garbled(text: str, label: str = ''):
    """Assert none of the known garbling signatures appear in text."""
    prefix = f'{label}: ' if label else ''
    for sig in GARBLING_SIGNATURES:
        assert sig not in text, (
            f'{prefix}Garbling pattern {repr(sig)} found in output. '
            f'This means a parser is double-encoding non-ASCII characters. '
            f'Ensure html.parser (not lxml) is used in convert_post.py.'
        )


# ── Minimal valid sidecar — fields convert_post actually reads
MINIMAL_SIDECAR = {
    'title': 'Test Post',
    'date': '2006-05-31',
    'author': 'Mark Proctor',
    'categories': ['Rules'],
    'tags': ['drools'],
    'original_url': 'https://blog.kie.org/2006/05/test.html',
}

# HTML that exercises non-ASCII (em dashes, curly quotes, en dash, apostrophe)
NON_ASCII_HTML = '''\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><title>Test</title></head>
<body>
<article>
  <h1>What is a Rule Engine</h1>
  <p>The term \u201cProduction Rule\u201d \u2013 an abstract structure.</p>
  <p>It\u2019s considered \u201capplied artificial intelligence\u201d.</p>
  <p>Forward Chaining is \u201cdata-driven\u201d \u2014 facts are asserted.</p>
</article>
</body>
</html>'''


def _write_post(tmp_path, html_content=None, sidecar=None, slug='test-post'):
    """Write an HTML post and JSON sidecar to tmp_path. Returns (html_path, json_path)."""
    html = html_content or NON_ASCII_HTML
    meta = sidecar or MINIMAL_SIDECAR
    html_path = tmp_path / f'{slug}.html'
    json_path = tmp_path / f'{slug}.json'
    html_path.write_text(html, encoding='utf-8')
    json_path.write_text(json.dumps(meta), encoding='utf-8')
    return html_path, json_path


# ── Unit tests — lxml garbling regression ─────────────────────────────────────

class TestNonAsciiPreservation:
    """Non-ASCII characters must survive HTML→Markdown conversion without garbling.

    Regression: convert_post.py was using lxml as the BeautifulSoup parser.
    When the HTML contains <meta charset="utf-8">, lxml re-encodes the Python
    str to UTF-8 bytes internally then serialises as Latin-1, producing
    double-encoded garbage like ÃÂÃÂ¢ÃÂÃÂÃÂÃÂ for every non-ASCII character.
    Fix: use html.parser which treats str input as-is (no charset sniffing).
    """

    def test_em_dash_not_garbled(self, tmp_path):
        """Em dash U+2014 must survive, not become ÃÂÃÂ¢... or Ã¢Â..."""
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path)
        result = convert_post(html_path)
        assert_not_garbled(result, 'em_dash_test')
        assert '\u2014' in result or '—' in result, \
            'Em dash should appear in output in some form'

    def test_curly_quotes_not_garbled(self, tmp_path):
        """Curly quotes U+201C/U+201D — content must be readable, not garbled."""
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path)
        result = convert_post(html_path)
        assert_not_garbled(result, 'curly_quotes_test')
        assert 'Production Rule' in result

    def test_en_dash_not_garbled(self, tmp_path):
        """En dash U+2013 must survive."""
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path)
        result = convert_post(html_path)
        assert_not_garbled(result, 'en_dash_test')

    def test_right_single_quote_not_garbled(self, tmp_path):
        """Apostrophe/right single quote U+2019 in contractions must survive."""
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path)
        result = convert_post(html_path)
        assert_not_garbled(result, 'apostrophe_test')
        assert 'considered' in result

    def test_meta_charset_does_not_trigger_garbling(self, tmp_path):
        """<meta charset="utf-8"> in head must not cause garbling.

        This is the specific trigger for the lxml bug — without the meta tag,
        lxml doesn't do charset sniffing. The test must include the meta tag.
        """
        from convert_post import convert_post
        html_with_charset = NON_ASCII_HTML  # already contains <meta charset="utf-8"/>
        assert '<meta charset' in html_with_charset, 'Test requires meta charset in HTML'
        html_path, _ = _write_post(tmp_path, html_content=html_with_charset)
        result = convert_post(html_path)
        assert_not_garbled(result, 'meta_charset_test')

    def test_all_garbling_signatures_absent(self, tmp_path):
        """None of the known garbling patterns must appear.

        Covers Pattern A (lxml double-encode), Pattern B (triple-encode from
        old server), and Pattern C (Windows-1252 mismatch).
        """
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path)
        result = convert_post(html_path)
        assert_not_garbled(result, 'all_signatures_test')

    def test_triple_encoding_pattern_absent(self, tmp_path):
        """Pattern B (Ã¢Â) — the triple-encoding signature — must not appear.

        This was seen when the old lxml-based server wrote garbled MD to disk.
        The garbled content (pattern A) was then re-read as bytes and re-encoded,
        producing pattern B. Testing explicitly guards this second-order regression.
        """
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path)
        result = convert_post(html_path)
        assert 'Ã¢Â' not in result, \
            'Triple-encoding (pattern B) detected — old lxml garbling may have returned'

    def test_real_post_not_garbled(self):
        """Convert an actual KIE archive post and verify no garbling.

        Uses the canonical regression post 'What is a Rule Engine' (2006)
        which has curly quotes, em dashes, and en dashes throughout.
        Skips if the legacy posts directory is not available.
        """
        from convert_post import convert_post
        posts_dir = Path('/Users/mdproctor/mdproctor.github.io/legacy/posts/mark-proctor')
        slug = '2006-05-31-what-is-a-rule-engine'
        html_path = posts_dir / f'{slug}.html'
        json_path = posts_dir / f'{slug}.json'
        if not html_path.exists():
            import pytest; pytest.skip('Legacy posts directory not available')
        result = convert_post(html_path, json_path=json_path if json_path.exists() else None)
        assert_not_garbled(result, 'real_post_what_is_a_rule_engine')
        assert 'Drools' in result, 'Real post content must appear in output'
        assert 'Rule Engine' in result or 'rule engine' in result.lower()


# ── Unit tests — json_path parameter ──────────────────────────────────────────

class TestJsonPathParameter:
    """json_path lets callers supply the sidecar from a different directory.

    Regression: when converting enriched HTML copies (which live in
    sparge-projects/{id}/enriched/), the JSON sidecar lives in the original
    posts directory. Without json_path, convert_post looks in enriched/ and
    raises FileNotFoundError.
    """

    def test_json_path_none_reads_from_same_dir(self, tmp_path):
        """Default (json_path=None) reads sidecar from html_path's directory."""
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path)
        # Should work fine — sidecar is alongside the HTML
        result = convert_post(html_path, json_path=None)
        assert 'Test Post' in result  # title from sidecar

    def test_json_path_reads_from_different_directory(self, tmp_path):
        """json_path can point to a sidecar in a completely different directory."""
        from convert_post import convert_post

        # Simulate enriched/ layout:
        #   posts_dir/slug.html + posts_dir/slug.json  (originals)
        #   enriched_dir/slug.html  (enriched copy — no sidecar here)
        posts_dir   = tmp_path / 'posts'
        enriched_dir = tmp_path / 'enriched'
        posts_dir.mkdir(); enriched_dir.mkdir()

        # Write original with sidecar
        orig_html = posts_dir / 'test-post.html'
        orig_json = posts_dir / 'test-post.json'
        orig_html.write_text(NON_ASCII_HTML, encoding='utf-8')
        orig_json.write_text(json.dumps({**MINIMAL_SIDECAR, 'title': 'From Sidecar'}))

        # Write enriched copy — NO sidecar in enriched/
        enriched_html = enriched_dir / 'test-post.html'
        enriched_html.write_text(NON_ASCII_HTML, encoding='utf-8')

        # Without json_path — should raise FileNotFoundError (sidecar missing)
        with pytest.raises(FileNotFoundError):
            convert_post(enriched_html, json_path=None)

        # With json_path pointing to original sidecar — should succeed
        result = convert_post(enriched_html, json_path=orig_json)
        assert 'From Sidecar' in result, \
            'Title from json_path sidecar should appear in front matter'
        assert 'ÃÂÃÂ' not in result

    def test_json_path_overrides_same_dir_sidecar(self, tmp_path):
        """json_path is used even when a same-dir sidecar exists."""
        from convert_post import convert_post

        # Two sidecars — one alongside HTML, one elsewhere
        html_path = tmp_path / 'post.html'
        same_dir_json = tmp_path / 'post.json'
        other_json = tmp_path / 'other.json'

        html_path.write_text(NON_ASCII_HTML, encoding='utf-8')
        same_dir_json.write_text(json.dumps({**MINIMAL_SIDECAR, 'title': 'Same Dir'}))
        other_json.write_text(json.dumps({**MINIMAL_SIDECAR, 'title': 'Other Dir'}))

        result_same = convert_post(html_path, json_path=None)
        result_other = convert_post(html_path, json_path=other_json)

        assert 'Same Dir' in result_same
        assert 'Other Dir' in result_other

    def test_json_path_none_missing_sidecar_raises(self, tmp_path):
        """Without json_path, missing sidecar raises FileNotFoundError (not silent)."""
        from convert_post import convert_post
        html_path = tmp_path / 'post.html'
        html_path.write_text(NON_ASCII_HTML, encoding='utf-8')
        # No sidecar written
        with pytest.raises(FileNotFoundError):
            convert_post(html_path, json_path=None)


# ── Unit tests — front matter from sidecar ────────────────────────────────────

class TestFrontMatter:
    """Front matter fields are populated from the JSON sidecar."""

    def test_title_in_front_matter(self, tmp_path):
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path, sidecar={
            **MINIMAL_SIDECAR, 'title': 'My Special Post'
        })
        result = convert_post(html_path)
        assert 'My Special Post' in result

    def test_date_in_front_matter(self, tmp_path):
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path, sidecar={
            **MINIMAL_SIDECAR, 'date': '2011-04-18'
        })
        result = convert_post(html_path)
        assert '2011-04-18' in result

    def test_author_in_front_matter(self, tmp_path):
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path)
        result = convert_post(html_path)
        assert 'Mark Proctor' in result

    def test_output_starts_with_front_matter(self, tmp_path):
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path)
        result = convert_post(html_path)
        assert result.startswith('---\n'), \
            'Output must start with YAML front matter delimiter'


# ── Integration tests — live server ───────────────────────────────────────────

try:
    import requests as _requests
    SERVER  = 'http://localhost:9000'
    API     = SERVER + '/api'
    SESSION = _requests.Session()
    SESSION.headers['Content-Type'] = 'application/json'
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


@pytest.fixture(scope='module')
def server():
    if not _HAS_REQUESTS:
        pytest.skip('requests not installed')
    try:
        _requests.get(f'{API}/projects', timeout=3).raise_for_status()
    except Exception:
        pytest.skip('Server not running on localhost:9000')


@pytest.fixture(scope='module')
def post_with_non_ascii(server):
    """Return the slug of a post known to contain non-ASCII characters."""
    # The KIE archive has many posts with em dashes, curly quotes etc.
    # Use what-is-a-rule-engine as the canonical regression post.
    slug = '2006-05-31-what-is-a-rule-engine'
    r = SESSION.get(f'{API}/posts/{slug}')
    if r.status_code != 200:
        pytest.skip(f'Test post {slug} not in active project')
    return slug


class TestGenerateMdEndpoint:
    """Integration tests for POST /api/posts/{slug}/generate-md."""

    def test_generate_md_available(self, server):
        """generate-md endpoint is reachable and not returning 503."""
        posts = SESSION.get(f'{API}/posts').json()
        if not posts:
            pytest.skip('No posts in active project')
        slug = posts[0]['slug']
        r = SESSION.post(f'{API}/posts/{slug}/generate-md?dry=1')
        assert r.status_code != 503, \
            'convert_post not available — check scripts/convert_post.py is present'

    def test_dry_run_returns_content(self, server, post_with_non_ascii):
        """Dry run returns a content field without writing to disk."""
        r = SESSION.post(f'{API}/posts/{post_with_non_ascii}/generate-md?dry=1')
        assert r.status_code == 200
        data = r.json()
        assert 'content' in data, 'Dry run must return content field'
        assert len(data['content']) > 100, 'Content should be non-trivial'

    def test_dry_run_no_garbling(self, server, post_with_non_ascii):
        """Dry run output must not contain any known garbling signature.

        Regression A: lxml double-encoding via <meta charset> sniffing.
        Regression B: triple-encoding when garbled output written/read again.
        Regression C: Windows-1252 byte mismatch.
        """
        r = SESSION.post(f'{API}/posts/{post_with_non_ascii}/generate-md?dry=1')
        assert r.status_code == 200
        content = r.json().get('content', '')
        assert_not_garbled(content, 'generate_md_dry_run')

    def test_generate_md_produces_front_matter(self, server, post_with_non_ascii):
        """Generated MD must start with YAML front matter."""
        r = SESSION.post(f'{API}/posts/{post_with_non_ascii}/generate-md?dry=1')
        assert r.status_code == 200
        content = r.json().get('content', '')
        assert content.startswith('---\n'), 'MD must start with front matter'
        assert 'author: Mark Proctor' in content

    def test_generate_md_preserves_technical_terms(self, server, post_with_non_ascii):
        """Key technical terms from the post must appear in generated MD."""
        r = SESSION.post(f'{API}/posts/{post_with_non_ascii}/generate-md?dry=1')
        assert r.status_code == 200
        content = r.json().get('content', '')
        # These are the first words of the post — must not be garbled or dropped
        assert 'Drools' in content
        assert 'Rule Engine' in content or 'rule engine' in content.lower()

    def test_generate_md_writes_file(self, server, post_with_non_ascii):
        """Non-dry generate-md writes a clean file to disk."""
        r = SESSION.post(f'{API}/posts/{post_with_non_ascii}/generate-md')
        assert r.status_code == 200
        state = r.json()
        assert state.get('md', {}).get('generated_at'), \
            'state.md.generated_at should be set after generation'

        # Fetch the file directly to verify no garbling on disk
        import sparge_home as _sh
        proj_dir = _sh.get_projects_dir() / 'kie-mark-proctor'
        if not proj_dir.exists():
            return  # can't check file directly
        cfg_path = proj_dir / 'config.json'
        if not cfg_path.exists():
            return
        import json as _json
        cfg = _json.loads(cfg_path.read_text())
        md_dir = Path(cfg['serve_root']) / cfg['output']['md_dir']
        md_file = md_dir / f'{post_with_non_ascii}.md'
        if md_file.exists():
            content = md_file.read_text(encoding='utf-8')
            assert_not_garbled(content, 'md_file_on_disk')
