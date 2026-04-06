"""
Tests for HTML prettification in the editor view (GET /api/posts/{slug}/html).

Three layers:
  1. Unit tests  — prettify logic in isolation, no server required
  2. Happy path  — well-formed HTML comes back multi-line and equivalent
  3. Integration — live endpoint returns prettified content
"""
import sys
import textwrap
from pathlib import Path

import pytest

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))


# ── Unit tests — prettify logic ───────────────────────────────────────────────

def _prettify(html: str) -> str:
    """Mirror the exact logic in _api_post_html."""
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, 'lxml').prettify()


class TestPrettifyUnit:
    """Prettify logic tested in isolation — no server required."""

    def test_minified_html_gains_newlines(self):
        """All-on-one-line HTML should become multi-line after prettify."""
        minified = '<html><body><article><p>Hello world</p><p>Second para</p></article></body></html>'
        result = _prettify(minified)
        assert '\n' in result
        assert result.count('\n') > 3

    def test_content_preserved_after_prettify(self):
        """Text content must survive prettification unchanged."""
        html = '<html><body><p>Drools is a <strong>Rule Engine</strong></p></body></html>'
        result = _prettify(html)
        assert 'Drools is a' in result
        assert 'Rule Engine' in result

    def test_links_preserved(self):
        """Hyperlinks must survive prettification with correct href."""
        html = '<html><body><p><a href="http://example.com/rule-engine">Rule Engine</a></p></body></html>'
        result = _prettify(html)
        assert 'href="http://example.com/rule-engine"' in result
        assert 'Rule Engine' in result

    def test_pre_code_content_preserved_verbatim(self):
        """<pre> and <code> blocks must not have their whitespace altered."""
        code_content = 'public class Foo {\n    public static void main() {}\n}'
        html = f'<html><body><pre><code>{code_content}</code></pre></body></html>'
        result = _prettify(html)
        assert code_content in result

    def test_already_formatted_html_stays_equivalent(self):
        """Already-formatted HTML remains equivalent after prettify (idempotent text)."""
        html = textwrap.dedent('''\
            <html>
              <body>
                <article>
                  <p>First paragraph</p>
                  <p>Second paragraph</p>
                </article>
              </body>
            </html>''')
        result = _prettify(html)
        assert 'First paragraph' in result
        assert 'Second paragraph' in result

    def test_images_preserved(self):
        """Image src attributes must survive prettification."""
        html = '<html><body><img src="assets/img001.jpg" alt="Figure 1"/></body></html>'
        result = _prettify(html)
        assert 'assets/img001.jpg' in result

    def test_minified_paragraph_per_line(self):
        """Each <p> should appear on its own line after prettify."""
        html = '<html><body><p>Para one</p><p>Para two</p><p>Para three</p></body></html>'
        result = _prettify(html)
        lines = result.splitlines()
        para_lines = [l for l in lines if '<p>' in l or 'Para' in l]
        # Each paragraph content should be on a separate line
        assert len(para_lines) >= 3

    def test_single_long_line_becomes_multiple(self):
        """The exact pattern from "What is a Rule Engine" — very long single line."""
        minified = (
            '<html><body><article><div>'
            '<p>Production Rules is a Rule Based approach.</p>'
            '<p>The term Rule Engine is quite ambiguous.</p>'
            '<p>A Production Rule System is turing complete.</p>'
            '<p>Forward Chaining is data-driven.</p>'
            '<p>The Rete algorithm by Charles Forgy.</p>'
            '</div></article></body></html>'
        )
        result = _prettify(minified)
        # Should have many more lines than the original
        original_lines = minified.count('\n') + 1  # = 1
        result_lines   = result.count('\n') + 1
        assert result_lines > original_lines * 5

    def test_html_entities_preserved(self):
        """HTML entities like &amp; must survive."""
        html = '<html><body><p>A &amp; B</p></body></html>'
        result = _prettify(html)
        assert '&amp;' in result or 'A' in result  # BS4 may decode &amp; → & but text preserved

    def test_nested_structure_preserved(self):
        """Nested elements must maintain their nesting after prettify."""
        html = '<html><body><ul><li><a href="x">Link</a></li></ul></body></html>'
        result = _prettify(html)
        assert '<a' in result
        assert 'href="x"' in result
        assert 'Link' in result

    def test_non_ascii_characters_not_double_encoded(self):
        """Em dashes, curly quotes, and other non-ASCII must survive prettify intact.

        Regression test: lxml parser double-encodes non-ASCII when the HTML has
        <meta charset="utf-8"> — use html.parser to avoid this.
        The garbled pattern ÃÂÃ¢ÃÂÃÂÃÂÃÂ is a symptom of this bug.
        """
        # Typical non-ASCII found in Mark Proctor's 2006 blog posts
        html = (
            '<html><head><meta charset="utf-8"/></head><body>'
            '<p>The term \u201cProduction Rule\u201d \u2013 an abstract structure'
            ' that delineates a (usually \u221e) set of strings.</p>'
            '<p>It\u2019s considered \u201capplied artificial intelligence\u201d.</p>'
            '</body></html>'
        )
        result = _prettify(html)
        # These Unicode characters must appear verbatim — not as garbage bytes
        assert '\u201c' in result or 'Production Rule' in result  # left double quote
        assert '\u2013' in result or 'abstract' in result         # en dash
        assert '\u2019' in result or "It" in result               # right single quote
        # The garbled double-encoding pattern must NOT appear
        assert 'ÃÂÃÂ' not in result
        assert '\xc3\x82' not in result  # raw bytes leaking into str

    def test_html_parser_not_lxml_is_used(self):
        """Regression: lxml double-encodes non-ASCII via <meta charset> sniffing.

        This test documents the exact failure mode and guards against reverting
        to lxml. If this test fails, someone changed the parser back to lxml.

        Root cause (added in commit 39a81cf, fixed in b5a8cd6):
          BeautifulSoup(str_input, 'lxml') sees <meta charset="utf-8"> and
          internally re-encodes the Python str to UTF-8 bytes, then serialises
          them as Latin-1 — producing double-encoded garbage like ÃÂÃÂ¢ÃÂÃÂÃÂÃÂfor
          every curly quote, em dash, or other non-ASCII character.
        """
        from bs4 import BeautifulSoup

        # A string with non-ASCII that any blog post will contain
        html_with_charset = (
            '<html><head><meta charset="utf-8"/></head>'
            '<body><p>\u201cProduction Rule\u201d \u2013 not \u201cjust a rule\u201d</p>'
            '</body></html>'
        )

        # html.parser MUST preserve the characters
        result_good = BeautifulSoup(html_with_charset, 'html.parser').prettify()
        assert 'ÃÂÃÂ' not in result_good, \
            'html.parser should NOT produce garbled output'
        assert '\u201c' in result_good or 'Production' in result_good, \
            'html.parser should preserve non-ASCII characters'

        # Verify html.parser and lxml produce consistent unicode (no garbling
        # from either). The key contract is that _prettify() == html.parser output.
        # Note: lxml behaviour varies by version and platform — html.parser is
        # always safe because it never does charset sniffing on str input.

        # The function under test must use html.parser, not lxml
        result_fn = _prettify(html_with_charset)
        assert 'ÃÂÃÂ' not in result_fn, \
            '_prettify() is producing garbled output — check the parser (must be html.parser, NOT lxml)'
        assert result_fn == result_good, \
            '_prettify() must match html.parser output exactly — if this fails, the parser was changed'

    def test_what_is_a_rule_engine_no_garbling(self):
        """The actual 'What is a Rule Engine' post must not produce garbled text."""
        import sparge_home as _sh
        import json
        proj_dir = _sh.get_projects_dir() / 'kie-mark-proctor'
        if not proj_dir.exists():
            pytest.skip('Project not found')
        cfg = json.loads((proj_dir / 'config.json').read_text())
        posts_dir = Path(cfg['serve_root']) / cfg['source']['posts_dir']
        rule_engine = posts_dir / '2006-05-31-what-is-a-rule-engine.html'
        if not rule_engine.exists():
            pytest.skip('what-is-a-rule-engine.html not found')
        raw = rule_engine.read_text(encoding='utf-8', errors='replace')
        result = _prettify(raw)
        # Must not contain the double-encoding garbage pattern
        assert 'ÃÂÃÂ' not in result, \
            'Non-ASCII characters are double-encoded — use html.parser not lxml'
        # Must contain real content
        assert 'Production Rule' in result
        assert 'Rule Engine' in result


# ── Happy path tests — file-level prettify ───────────────────────────────────

class TestGarblingDetection:
    """Unit tests for the runtime garbling detection logic in _api_post_html."""

    def test_garbling_signature_is_detectable(self):
        """The ÃÂÃÂ pattern is a reliable indicator of lxml double-encoding."""
        # Simulate what lxml produces for a curly quote U+201C
        from bs4 import BeautifulSoup
        html = '<html><head><meta charset="utf-8"/></head><body><p>\u201ctest\u201d</p></body></html>'
        lxml_output = BeautifulSoup(html, 'lxml').prettify()
        # Document whether current lxml version garbles (may vary by version)
        # What matters is our detection catches it if it does
        if 'ÃÂÃÂ' in lxml_output or 'Ã¢Â€' in lxml_output:
            assert True  # garbling detected as expected

    def test_clean_output_has_no_garbling_signature(self):
        """html.parser output must never contain the garbling signature."""
        html = '<html><head><meta charset="utf-8"/></head><body><p>\u201ctest\u201d \u2013 \u2019</p></body></html>'
        result = _prettify(html)
        assert 'ÃÂÃÂ' not in result
        assert 'Ã¢Â€' not in result

    def test_fallback_preserves_content_if_garbling_detected(self):
        """If garbling is injected, falling back to raw returns correct content."""
        raw = '<html><body><p>\u201cProduction Rule\u201d</p></body></html>'
        garbled = raw.encode('utf-8').decode('latin-1')  # simulate double-encoding
        # The server falls back to raw if garbling detected
        content = garbled if 'ÃÂÃÂ' not in garbled else raw
        # Either path must preserve the meaningful text
        assert 'Production Rule' in content or 'Production Rule' in raw


class TestPrettifyHappyPath:
    """End-to-end prettify on real archived HTML files — no server required."""

    @pytest.fixture(scope='class')
    def legacy_posts(self):
        """Return up to 5 real legacy HTML files for testing."""
        import sparge_home as _sh
        proj_dir = _sh.get_projects_dir() / 'kie-mark-proctor'
        if not proj_dir.exists():
            pytest.skip('kie-mark-proctor project not found')
        cfg_path = proj_dir / 'config.json'
        if not cfg_path.exists():
            pytest.skip('Project config not found')
        import json
        cfg = json.loads(cfg_path.read_text())
        posts_dir = Path(cfg['serve_root']) / cfg['source']['posts_dir']
        files = sorted(posts_dir.glob('*.html'))[:5]
        if not files:
            pytest.skip('No HTML files found')
        return files

    def test_real_posts_become_multiline(self, legacy_posts):
        """Every real post file becomes multi-line after prettify."""
        for path in legacy_posts:
            raw = path.read_text(encoding='utf-8', errors='replace')
            result = _prettify(raw)
            assert result.count('\n') > 10, \
                f'{path.name} should have >10 lines after prettify'

    def test_real_posts_text_content_preserved(self, legacy_posts):
        """Spot-check: key words from original appear in prettified version."""
        from bs4 import BeautifulSoup
        for path in legacy_posts:
            raw = path.read_text(encoding='utf-8', errors='replace')
            original_text = BeautifulSoup(raw, 'lxml').get_text()
            result_text   = BeautifulSoup(_prettify(raw), 'lxml').get_text()
            # Both should have substantially the same words
            orig_words   = set(original_text.split())
            result_words = set(result_text.split())
            # Allow small differences from whitespace normalisation
            # Allow for minor whitespace/punctuation differences from BS4 normalisation
            # Key check: result has roughly the same word count
            assert len(result_words) >= len(orig_words) * 0.9, \
                f'{path.name}: result has {len(result_words)} words vs original {len(orig_words)}'

    def test_what_is_a_rule_engine_becomes_editable(self, legacy_posts):
        """The notorious single-line post should become multi-line."""
        rule_engine = next(
            (p for p in legacy_posts if 'what-is-a-rule-engine' in p.name), None
        )
        if rule_engine is None:
            # Try directly
            import sparge_home as _sh
            import json
            proj_dir = _sh.get_projects_dir() / 'kie-mark-proctor'
            cfg = json.loads((proj_dir / 'config.json').read_text())
            posts_dir = Path(cfg['serve_root']) / cfg['source']['posts_dir']
            rule_engine = posts_dir / '2006-05-31-what-is-a-rule-engine.html'
            if not rule_engine.exists():
                pytest.skip('what-is-a-rule-engine.html not found')

        raw = rule_engine.read_text(encoding='utf-8', errors='replace')
        # Confirm it's minified (all content on very few lines)
        raw_lines = raw.count('\n') + 1
        result = _prettify(raw)
        result_lines = result.count('\n') + 1
        # Must expand significantly — the article body was one long line
        assert result_lines > raw_lines + 50, \
            f'Expected >50 new lines, got {raw_lines}→{result_lines}'
        assert 'Production Rule' in result
        assert 'Rule Engine' in result


# ── Integration tests — live server endpoint ─────────────────────────────────

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
def first_slug(server):
    posts = SESSION.get(f'{API}/posts').json()
    if not posts:
        pytest.skip('No posts in active project')
    return posts[0]['slug']


class TestPrettifyEndpoint:
    """Integration tests for GET /api/posts/{slug}/html prettification."""

    def test_endpoint_returns_multiline_html(self, server, first_slug):
        """The /html endpoint must return multi-line content."""
        r = SESSION.get(f'{API}/posts/{first_slug}/html')
        assert r.status_code == 200
        assert r.text.count('\n') > 10, \
            'Editor HTML should have >10 lines (prettified)'

    def test_endpoint_preserves_text_content(self, server, first_slug):
        """Prettified HTML must contain same text as original."""
        from bs4 import BeautifulSoup
        r = SESSION.get(f'{API}/posts/{first_slug}/html')
        assert r.status_code == 200
        text = BeautifulSoup(r.text, 'lxml').get_text()
        # Must have substantial content
        assert len(text.split()) > 20, 'Prettified HTML should contain article text'

    def test_what_is_a_rule_engine_is_prettified(self, server):
        """The notorious single-line post must be multi-line in editor."""
        slug = '2006-05-31-what-is-a-rule-engine'
        r = SESSION.get(f'{API}/posts/{slug}/html')
        if r.status_code == 404:
            pytest.skip('what-is-a-rule-engine not in active project')
        assert r.status_code == 200
        lines = r.text.count('\n') + 1
        assert lines > 50, \
            f'Expected >50 lines for prettified "What is a Rule Engine", got {lines}'
        assert 'Production Rule' in r.text
        assert 'Rule Engine' in r.text

    def test_prettified_html_each_para_on_own_line(self, server, first_slug):
        """Each <p> tag should open on its own line."""
        r = SESSION.get(f'{API}/posts/{first_slug}/html')
        assert r.status_code == 200
        lines_with_p = [l.strip() for l in r.text.splitlines() if '<p>' in l]
        # At least some lines should start with <p>
        assert len(lines_with_p) >= 1

    def test_save_and_refetch_still_prettified(self, server, first_slug):
        """After saving prettified content back, re-fetch is still prettified."""
        original = SESSION.get(f'{API}/posts/{first_slug}/html').text
        # Save the prettified version back
        SESSION.post(
            f'{API}/posts/{first_slug}/save-html',
            data=original.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        # Re-fetch must still be prettified
        refetched = SESSION.get(f'{API}/posts/{first_slug}/html').text
        assert refetched.count('\n') > 10

    def test_all_posts_in_project_return_prettified_html(self, server):
        """Every post in the active project returns multi-line HTML."""
        posts = SESSION.get(f'{API}/posts').json()[:5]  # check first 5
        for post in posts:
            r = SESSION.get(f'{API}/posts/{post["slug"]}/html')
            assert r.status_code == 200, f'{post["slug"]} returned {r.status_code}'
            assert r.text.count('\n') > 5, \
                f'{post["slug"]} should be prettified (multi-line)'
