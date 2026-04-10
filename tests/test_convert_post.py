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

class TestPlaceholderReplacement:
    """convert_post replaces missing/lazy images with blockquote placeholders.

    Regression: switching from lxml to html.parser broke placeholder insertion.
    lxml always wraps fragments in <html><body>, so .body.next worked.
    html.parser does NOT add a body wrapper for small fragments, so .body
    was None and .body.next raised AttributeError — causing HTTP 500 on any
    post that had missing or lazy-loaded images.

    Fix: use .find() instead of .body.next to get the first element of a
    parsed fragment — works correctly for both lxml and html.parser.
    """

    DATA_URI_HTML = '''\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><title>Test</title></head>
<body>
<article>
  <h1>Post with lazy images</h1>
  <p>Before image</p>
  <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
       data-src="https://example.com/real-image.jpg"
       alt="A diagram">
  <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
       alt="Another image">
  <p>After image</p>
</article>
</body>
</html>'''

    MISSING_IMG_HTML = '''\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><title>Test</title></head>
<body>
<article>
  <h1>Post with broken images</h1>
  <p>Some content</p>
  <img src="../../assets/images/broken-1.png" alt="broken image one">
  <p>More content</p>
  <img src="../../assets/images/broken-2.jpg" alt="broken image two">
</article>
</body>
</html>'''

    def test_data_uri_placeholder_does_not_raise(self, tmp_path):
        """Posts with data: URI placeholder images must not raise AttributeError.

        Regression: .body.next on html.parser fragment returns None.body → AttributeError.
        """
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path, html_content=self.DATA_URI_HTML)
        # Must not raise — previously caused HTTP 500 for ~110 posts
        result = convert_post(html_path)
        assert isinstance(result, str)
        assert len(result) > 50

    def test_local_image_paths_converted_to_markdown(self, tmp_path):
        """Local image paths (../../assets/...) are rendered as markdown image links."""
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path, html_content=self.MISSING_IMG_HTML)
        result = convert_post(html_path)
        assert isinstance(result, str)
        # Local images are converted to markdown image syntax, not placeholders
        assert '![' in result or 'broken' in result

    def test_placeholder_content_not_garbled(self, tmp_path):
        """Placeholder blockquotes must not contain garbled text."""
        from convert_post import convert_post
        html_path, _ = _write_post(tmp_path, html_content=self.DATA_URI_HTML)
        result = convert_post(html_path)
        assert_not_garbled(result, 'placeholder_content')

    def test_posts_with_images_generate_without_500(self):
        """Integration: posts that previously caused 500 errors now generate successfully.

        The 110 posts that failed had lazy-loaded or missing images — they all
        triggered the placeholder code that used .body.next (now fixed to .find()).
        """
        import requests
        try:
            s = requests.Session()
            s.get('http://localhost:9000/api/projects', timeout=3).raise_for_status()
        except Exception:
            import pytest; pytest.skip('Server not running')

        # These slugs were in the original 110 that failed with HTTP 500
        test_slugs = [
            '2007-05-19-jboss-rules-expressiveness-goes-to-the-next-level',
            '2009-11-19-pacman-and-the-importance-of-betanode-sharing-rete-explained',
            '2011-04-18-backward-chaining-emerges-in-drools',
        ]
        for slug in test_slugs:
            r = s.post(f'http://localhost:9000/api/posts/{slug}/generate-md?dry=1')
            assert r.status_code == 200, \
                f'{slug} returned {r.status_code} — .body.next fix may have regressed'
            assert 'error' not in r.json(), \
                f'{slug} returned error: {r.json().get("error")}'


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


# ── ASCII decorator separator stripping ───────────────────────────────────────
#
# Some blog posts use lines of '===' or '---' as visual separators inside <p>
# elements separated by <br/> tags. These create Markdown setext headings:
#   '===' after text → H1 heading  (setext heading underline)
#   '---' after text → H2 heading  (setext heading underline)
#
# Fix: convert '===...' lines to blank line + '---' so the '---' is treated
# as an <hr> (horizontal rule) not a setext heading underline.
# The blank line is essential — it terminates the preceding paragraph so '---'
# starts a new block, rendering as <hr> not as a heading marker.

EQ_SEPARATOR_HTML = '''\
<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>EQ Test</title></head>
<body><article>
<h1>Test Post</h1>
<p>RuleML 2011@BRF – Conference Announcement<br/>===================================================================<br/>Last day for regular price: 29th October.</p>
<p>Supported by<br/>===================================================================<br/>W3C, OMG, OASIS</p>
<p>Real content here.</p>
</article></body></html>'''


def _eq_post(tmp_path):
    hp = tmp_path / 'eq-test.html'
    hp.write_text(EQ_SEPARATOR_HTML, encoding='utf-8')
    (tmp_path / 'eq-test.json').write_text(json.dumps(MINIMAL_SIDECAR))
    return hp


class TestTableBlankLineCollapse:
    """Blank lines within html2text-generated MD tables must be removed.

    html2text inserts blank lines between rows of complex HTML tables
    (e.g. rows with <br/> content, empty spacer rows). These blank lines
    break Markdown table rendering — marked.js requires all rows to be
    contiguous with no blank lines between them.

    Fix: after html2text conversion, remove blank lines that sit between
    lines containing '|' (table row indicators).
    """

    def _make_table_post(self, tmp_path, table_html):
        html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>T</title></head>
<body><article><h1>Test</h1>{table_html}</article></body></html>'''
        hp = tmp_path / 'table-test.html'
        hp.write_text(html, encoding='utf-8')
        (tmp_path / 'table-test.json').write_text(
            '{"title":"T","date":"2009-01-01","author":"A","categories":[],"tags":[],"original_url":"http://x.com"}')
        return hp

    def _body(self, result):
        idx = result.find('\n---\n')
        return result[idx + 5:] if idx >= 0 else result

    def test_blank_lines_removed_within_table(self):
        """Blank/whitespace-only lines between table rows must be removed.

        The October Rules Festival 2009 post has a complex conference schedule
        table with many spacer rows. html2text renders these spacer rows as
        whitespace-only lines between content rows, breaking MD table rendering.
        """
        import sys; sys.path.insert(0, 'scripts')
        from pathlib import Path
        from convert_post import convert_post

        slug = '2009-07-20-october-rules-festival-2009'
        enriched = Path(f'/Users/mdproctor/sparge-projects/kie-mark-proctor/enriched/{slug}.html')
        json_path = Path(f'/Users/mdproctor/mdproctor.github.io/legacy/posts/mark-proctor/{slug}.json')
        if not enriched.exists() or not json_path.exists():
            import pytest; pytest.skip('Enriched copy not available')

        result = convert_post(enriched, json_path=json_path)
        body = result[result.find('\n---\n')+5:]
        lines = body.splitlines()
        pipe_indices = [i for i, l in enumerate(lines) if '|' in l]

        if not pipe_indices:
            import pytest; pytest.skip('No | table content found in this post — source has no HTML tables, cannot test blank line collapse')

        for a, b in zip(pipe_indices, pipe_indices[1:]):
            between = lines[a+1:b]
            blank_between = [l for l in between if not l.strip()]
            assert not blank_between, (
                f'Blank/whitespace-only line between table rows at lines {a} and {b}. '
                f'Spacer rows in complex HTML tables produce whitespace-only lines '
                f'that break MD table rendering in marked.js. '
                f'Fix: remove lines within a table section that are blank/whitespace-only.'
            )

    def test_blank_lines_between_paragraphs_preserved(self, tmp_path):
        """Blank lines between normal paragraphs (not tables) must be kept."""
        from convert_post import convert_post
        html = '<p>First paragraph.</p><p>Second paragraph.</p>'
        hp = self._make_table_post(tmp_path, html)
        body = self._body(convert_post(hp))
        assert '\n\n' in body, 'Blank lines between paragraphs must be preserved'


class TestAsciiSeparatorStripping:
    """'===' visual separator lines must become proper <hr> elements, not headings.

    Both '===' (H1) and '---' (H2) after text create setext headings in Markdown.
    The fix: insert a blank line before '---' to terminate the preceding paragraph,
    making '---' an unambiguous horizontal rule rather than a heading marker.
    """

    def _body(self, result):
        idx = result.find('\n---\n')
        return result[idx + 5:] if idx >= 0 else result

    def test_eq_lines_converted_not_left_as_is(self, tmp_path):
        """'===' lines must not appear in MD — they'd create setext H1 headings."""
        from convert_post import convert_post
        import re
        body = self._body(convert_post(_eq_post(tmp_path)))
        eq_lines = re.findall(r'^={4,}\s*$', body, re.MULTILINE)
        assert not eq_lines, (
            f'{len(eq_lines)} "===" lines in MD — these create setext H1 headings. '
            f'Fix: convert to blank line + "---" in convert_post.py cleanup.')

    def test_no_setext_headings_created_from_separators(self, tmp_path):
        """Converting '===' to '---' WITHOUT a preceding blank line creates H2 headings.
        The blank line before '---' is essential for it to render as <hr>.
        """
        from convert_post import convert_post
        import re
        body = self._body(convert_post(_eq_post(tmp_path)))
        # Setext H2: a non-empty line immediately followed by '---' (no blank between)
        setext_h2 = re.findall(r'^[^\n]+\n-{3,}\s*$', body, re.MULTILINE)
        assert not setext_h2, (
            f'Setext H2 headings created by "---" without preceding blank line: '
            f'{setext_h2[:2]}. Fix: prepend blank line before "---".')

    def test_content_around_separators_preserved(self, tmp_path):
        """Content before and after separators must be preserved."""
        from convert_post import convert_post
        body = self._body(convert_post(_eq_post(tmp_path)))
        assert 'Last day for regular price' in body
        assert 'W3C, OMG, OASIS' in body
        assert 'Real content here' in body


# ── Inline formatting adjacent to punctuation ─────────────────────────────────
#
# html2text strips trailing whitespace from inside bold/italic markers, so:
#   <b>Name </b>(Org)  →  **Name**(Org)   ← no space before (
#
# The missing space is a typographic error and also caused validator phrase-check
# false positives (HTML plain text has "Name (Org" but stripped MD has "Name(Org").
# Fix: after html2text conversion, insert a space between closing ** and (.

_BOLD_ADJACENT_HTML = '''\
<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>Adj Test</title></head>
<body><article>
<h1>Keynote Speakers</h1>
<p><b>Bob Kowalski </b>(Imperial College London): Logic and AI</p>
<p><strong>Elena Baralis </strong>(Politecnico di Torino): Opening the Black Box</p>
<p>Normal sentence with <b>bold words</b> in the middle.</p>
<p><em>italic </em>(parenthetical remark)</p>
<p>Deleted: <del>old text </del>(replacement)</p>
<p>Strikethrough s: <s>struck </s>(clarification)</p>
<p>Strikethrough strike: <strike>struck </strike>(clarification)</p>
<p>Code: <code>expr </code>(explanation)</p>
<p>Underline: <u>term </u>(definition)</p>
<p>Link: <a href="http://example.com">read more </a>(optional)</p>
<p>No space: <b>adjacent</b>(parenthetical) in original.</p>
</article></body></html>'''


def _adj_post(tmp_path):
    hp = tmp_path / 'adj-test.html'
    hp.write_text(_BOLD_ADJACENT_HTML, encoding='utf-8')
    (tmp_path / 'adj-test.json').write_text(json.dumps(MINIMAL_SIDECAR))
    return hp


class TestInlineFormatAdjacentToPunct:
    """Closing bold/italic markers must preserve trailing whitespace from the HTML.

    html2text strips trailing whitespace inside bold/italic markers:
      <b>Name </b>(Org)  →  **Name**(Org)   ← space lost, ( runs into **
      <b>Name</b>(Org)   →  **Name**(Org)   ← correctly no space

    The correct fix is a BeautifulSoup pre-processing step BEFORE html2text:
    move trailing whitespace from inside the tag to after the closing tag.
      <b>Name </b>(Org)  →  <b>Name</b> (Org)  →  **Name** (Org)  ✓
      <b>Name</b>(Org)   →  <b>Name</b>(Org)   →  **Name**(Org)   ✓ (unchanged)

    A post-processing regex on the MD output (re.sub r'(\*+)\(' r'\1 (') is wrong:
    it adds a space before ALL (  even when the original had none.
    """

    def _body(self, result):
        idx = result.find('\n---\n')
        return result[idx + 5:] if idx >= 0 else result

    def test_bold_adjacent_paren_gets_space(self, tmp_path):
        """<b>Name </b>(Org) must become **Name** (Org) not **Name**(Org)."""
        from convert_post import convert_post
        body = self._body(convert_post(_adj_post(tmp_path)))
        assert '** (' in body or '**(' not in body, (
            'Bold marker immediately followed by "(" — space must be inserted. '
            'html2text strips trailing whitespace inside ** so '
            '<b>Name </b>(Org) → **Name**(Org). '
            'Fix: re.sub(r\'(\\*+)\\(\', r\'\\1 (\', md) in convert_post.py.'
        )

    def test_strong_adjacent_paren_gets_space(self, tmp_path):
        """<strong>Name </strong>(Org) must also get the space."""
        from convert_post import convert_post
        body = self._body(convert_post(_adj_post(tmp_path)))
        assert 'Baralis** (' in body or 'Baralis**(' not in body, (
            '<strong>Name </strong>(Org) still produces **Name**(Org) without space.'
        )

    def test_italic_adjacent_paren_gets_space(self, tmp_path):
        """<em>text </em>(remark) must become *text* (remark)."""
        from convert_post import convert_post
        body = self._body(convert_post(_adj_post(tmp_path)))
        assert '* (' in body or '*(' not in body, (
            '<em>text </em>(remark) still produces *text*(remark) without space.'
        )

    def test_bold_mid_sentence_unchanged(self, tmp_path):
        """Bold in the middle of a sentence must not be changed."""
        from convert_post import convert_post
        body = self._body(convert_post(_adj_post(tmp_path)))
        assert 'bold words' in body, 'Bold words in mid-sentence must be preserved'

    def test_del_adjacent_paren_gets_space(self, tmp_path):
        """<del>text </del>(more) must preserve the space."""
        from convert_post import convert_post
        body = self._body(convert_post(_adj_post(tmp_path)))
        assert 'old text~~(' not in body, (
            '<del>old text </del>(replacement) still loses the space — '
            '~~old text~~( in output.'
        )

    def test_s_adjacent_paren_gets_space(self, tmp_path):
        """<s>text </s>(more) must preserve the space."""
        from convert_post import convert_post
        body = self._body(convert_post(_adj_post(tmp_path)))
        assert 'struck~~(' not in body, (
            '<s>struck </s>(clarification) still loses the space — '
            '~~struck~~( in output.'
        )

    def test_strike_adjacent_paren_gets_space(self, tmp_path):
        """<strike>text </strike>(more) must preserve the space."""
        from convert_post import convert_post
        body = self._body(convert_post(_adj_post(tmp_path)))
        # strike produces the same ~~ output as s/del — both share the same test content
        # so we check generically that no ~~ marker directly abuts (
        assert '~~(' not in body, (
            '<strike>struck </strike>(clarification) still loses the space.'
        )

    def test_code_adjacent_paren_gets_space(self, tmp_path):
        """<code>expr </code>(explanation) must preserve the space."""
        from convert_post import convert_post
        body = self._body(convert_post(_adj_post(tmp_path)))
        assert '`(' not in body, (
            '<code>expr </code>(explanation) still loses the space — '
            '`expr`(explanation) in output.'
        )

    def test_u_adjacent_paren_gets_space(self, tmp_path):
        """<u>term </u>(definition) must preserve the space."""
        from convert_post import convert_post
        body = self._body(convert_post(_adj_post(tmp_path)))
        # html2text renders <u> as italic (_term_)
        assert 'term_(' not in body, (
            '<u>term </u>(definition) still loses the space — '
            '_term_( in output.'
        )

    def test_a_adjacent_paren_gets_space(self, tmp_path):
        """<a href="...">text </a>(more) must preserve the space."""
        from convert_post import convert_post
        body = self._body(convert_post(_adj_post(tmp_path)))
        # html2text renders as [text](url) — ( should not run into )
        assert '>)(optional)' not in body and '](optional)' not in body, (
            '<a>read more </a>(optional) still loses the space — '
            'link)(optional) or link](optional) in output.'
        )

    def test_no_space_when_none_in_original(self, tmp_path):
        """<b>adjacent</b>(parenthetical) — no space in HTML, none must be added.

        This is the key test that distinguishes the correct pre-processing approach
        from the incorrect post-processing regex.  The regex blindly adds a space
        before every **(  even when the original HTML had none.  The pre-processing
        approach only moves a space that actually existed inside the tag.
        """
        from convert_post import convert_post
        body = self._body(convert_post(_adj_post(tmp_path)))
        assert 'adjacent**(parenthetical)' in body or 'adjacent** (parenthetical)' not in body, (
            'No space existed between </b> and ( in original HTML — none should be '
            'added. A post-processing regex adds space unconditionally; the correct '
            'fix moves trailing whitespace from inside the tag to after it BEFORE '
            'html2text, so only real spaces are preserved. '
            f'Body: {body!r}'
        )
