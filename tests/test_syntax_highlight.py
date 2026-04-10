"""
Playwright tests: syntax highlighting in the MD panel.

Code blocks rendered by marked.js in #md-wrap must have highlight.js applied:
  - <code> elements must have the 'hljs' class
  - <span> elements must exist inside (token colouring)
  - Coloured tokens must use non-default text colour

Tests written FIRST (fail before fix), then fix applied, then verify passing.

Run with server on localhost:9000:
  python3 -m pytest tests/test_syntax_highlight.py -v
"""
import pytest

SERVER  = 'http://localhost:9000'
APP_URL = SERVER + '/ui/index.html'
API     = SERVER + '/api'

TARGET_SLUG = '2013-10-31-configuration-and-convention-based-building-and-utilization'


@pytest.fixture(scope='module')
def session():
    try:
        import requests
        s = requests.Session()
        s.get(f'{API}/projects', timeout=3).raise_for_status()
        s.post(f'{API}/projects/kie-mark-proctor/activate')
        # Regenerate to get latest conversion
        s.post(f'{API}/posts/{TARGET_SLUG}/generate-md')
        return s
    except Exception:
        pytest.skip('Server not running on localhost:9000')


@pytest.fixture(scope='module')
def page(session):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip('playwright not installed')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page(viewport={'width': 1400, 'height': 900})
        pg.goto(APP_URL, wait_until='networkidle')
        pg.wait_for_selector('.pi', timeout=15000)

        # Select the post and wait for md-wrap
        pg.locator(f'[data-slug="{TARGET_SLUG}"]').click()
        pg.wait_for_function(
            "() => document.getElementById('md-wrap')?.querySelectorAll('pre code').length > 0",
            timeout=10000,
        )
        pg.wait_for_timeout(500)
        yield pg
        browser.close()


def code_block_info(page):
    """Return info about all code blocks in #md-wrap."""
    return page.evaluate("""() => {
        const blocks = [...document.querySelectorAll('#md-wrap pre code')];
        return blocks.map(b => ({
            classes:      b.className,
            has_hljs:     b.classList.contains('hljs'),
            span_count:   b.querySelectorAll('span').length,
            text_preview: b.textContent.slice(0, 60),
            has_nbsp:     b.textContent.includes('\\u00a0'),
        }));
    }""")


# ── Failing tests (written before the fix) ────────────────────────────────────

class TestSyntaxHighlighting:

    def test_code_blocks_exist(self, page):
        """Sanity: the post must have at least one code block in md-wrap."""
        blocks = code_block_info(page)
        assert len(blocks) > 0, 'No <pre><code> blocks found in #md-wrap'

    def test_code_blocks_have_hljs_class(self, page):
        """Every code block must have the 'hljs' class — proof hljs was applied.

        FAILS before fix: marked.use({ extensions:[{name:'code',...}] }) does not
        override the built-in code renderer; blocks get class='language-xml' only.
        PASSES after fix: use marked.use({ renderer: { code(...) {...} } }) instead.
        """
        blocks = code_block_info(page)
        without_hljs = [b for b in blocks if not b['has_hljs']]
        assert not without_hljs, (
            f'{len(without_hljs)}/{len(blocks)} code blocks lack the "hljs" class.\n'
            f'This means highlight.js was NOT applied — the marked.use() extension '
            f'approach does not override built-in code rendering in marked.js v9.\n'
            f'First offender: class={without_hljs[0]["classes"]!r}, '
            f'text={without_hljs[0]["text_preview"]!r}')

    def test_code_blocks_have_coloured_spans(self, page):
        """Highlighted blocks must contain <span> elements for token colouring.

        FAILS before fix: no hljs applied → no spans → plain monochrome text.
        PASSES after fix: hljs highlights tokens → multiple <span class="hljs-*">.
        """
        blocks = code_block_info(page)
        # Blocks with a language tag should have spans; unlabelled blocks may not
        labelled = [b for b in blocks if 'language-' in b['classes']]
        without_spans = [b for b in labelled if b['span_count'] == 0]
        assert not without_spans, (
            f'{len(without_spans)} language-tagged code blocks have zero <span> '
            f'elements — no syntax colouring applied.\n'
            f'First offender: {without_spans[0]["text_preview"]!r}')

    def test_no_nbsp_in_rendered_code(self, page):
        """Code block text must not contain \\u00a0 (non-breaking space).

        FAILS before fix: convert_post.py did not normalise \\xa0 → space, so the
        MD file has nbsp chars that render literally, breaking tokenisation.
        PASSES after fix: \\xa0 replaced with space during code block extraction.
        """
        blocks = code_block_info(page)
        with_nbsp = [b for b in blocks if b['has_nbsp']]
        assert not with_nbsp, (
            f'{len(with_nbsp)} code blocks contain \\u00a0 (non-breaking space).\n'
            f'This breaks hljs tokenisation and means the MD was generated by old '
            f'convert_post.py or the server was not restarted after the fix.\n'
            f'First offender: {with_nbsp[0]["text_preview"]!r}')

    def test_xml_blocks_have_coloured_tags(self, page):
        """XML code blocks must have <span class="hljs-tag"> or similar hljs spans.

        FAILS before fix: no highlighting → plain text.
        PASSES after fix: hljs XML tokeniser produces coloured tag spans.
        """
        xml_spans = page.evaluate("""() => {
            const blocks = [...document.querySelectorAll('#md-wrap pre code.language-xml')];
            return blocks.map(b => ({
                hljs_spans: b.querySelectorAll('[class*="hljs-"]').length,
                text: b.textContent.slice(0, 40),
            }));
        }""")
        assert xml_spans, 'No language-xml code blocks found'
        without_colour = [b for b in xml_spans if b['hljs_spans'] == 0]
        assert not without_colour, (
            f'{len(without_colour)} XML blocks have no hljs-* colour spans.\n'
            f'First: {without_colour[0]["text"]!r}')
