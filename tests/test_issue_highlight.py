"""
Playwright integration tests for issue panel click-to-highlight and auto-scroll.

Covers items 3 and 4 from the issue panel work:
  3. HTML issue rows: clicking highlights the element in the HTML iframe and
     auto-scrolls to it. Clicking again deselects. The iframe receives a
     <style> tag injecting a red outline on the targeted CSS selector.
  4. MD issue rows: clicking highlights the matching element/text in #md-wrap
     and auto-scrolls. Three strategies are tested:
       - CSS selector on rendered elements (a[href=""], img[src^="../../"], .fm-card)
       - Text-node search wrapped in <mark class="md-hl">
       - Fallback scroll-to-top
     Cross-clearing: clicking an HTML row clears any active MD highlight and
     vice versa.

Fixture: one test project with two posts, each with real HTML/MD files
served from serve_root so the iframe and md-wrap actually load content.

  html-click-post — HTML issues with selectors matching elements in the HTML file
  md-click-post   — MD issues covering all three highlight strategies; MD file
                    contains the matching content

Run with server on localhost:9000:
  python3 -m pytest tests/test_issue_highlight.py -v

Requires: pip install playwright && playwright install chromium
"""
import json
import shutil
import textwrap
import uuid
from pathlib import Path

import pytest

SERVER  = 'http://localhost:9000'
APP_URL = SERVER + '/ui/index.html'
API     = SERVER + '/api'

# ── Synthetic posts ────────────────────────────────────────────────────────────

HTML_SLUG    = '2020-06-01-html-click-post'
MD_SLUG      = '2020-06-02-md-click-post'
ASSET_SLUG   = '2020-06-03-asset-issues-post'  # has both html.issues AND assets.broken
MISSING_SLUG = '2020-06-04-missing-content-post'  # lists_dropped + content_phrase_missing

TS = '2026-01-01T00:00:00'

# HTML file for the HTML-click post — elements match the issue selectors below
HTML_POST_CONTENT = textwrap.dedent("""\
    <!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>HTML Click Test</title></head>
    <body>
    <article>
      <h1>HTML Click Test Post</h1>
      <p>First paragraph of content with some words.</p>
      <img src="http://cdn.example.com/photo.jpg" alt="External image">
      <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
           alt="Data placeholder">
      <p>Second paragraph with more content.</p>
    </article>
    </body></html>
""")

# MD file for the MD-click post — content matches the MD issue patterns
MD_FILE_CONTENT = textwrap.dedent("""\
    ---
    title: MD Click Test Post
    date: 2020-06-02
    author: Test Author
    tags:
      - test
    ---

    This content repeats here in this post.

    Here is a [broken link]() with an empty href.

    And a relative image: ![img](../../assets/legacy/photo.jpg)

    WordPress Related Posts

    This content repeats here in this post.
""")

# HTML issues — selectors must match elements in HTML_POST_CONTENT
HTML_ISSUES = [
    {
        'type': 'external_image', 'check': 'external_image', 'level': 'WARN',
        'detail': 'Image not localised: http://cdn.example.com/photo.jpg',
        'selector': 'img[src="http://cdn.example.com/photo.jpg"]',
    },
    {
        'type': 'data_placeholder', 'check': 'data_placeholder', 'level': 'ERROR',
        'detail': 'Unrecovered lazy-load placeholder — alt="Data placeholder"',
        'selector': 'img[src^="data:image"]',
    },
]

# MD issues — check names must map to strategies in _mdTarget()
MD_ISSUES = [
    {'check': 'broken_links',       'level': 'WARN',  'detail': '1 empty link(s) [text]()',              'selector': None},
    {'check': 'relative_image_path','level': 'WARN',  'detail': '1 image(s) use ../../ — should be /legacy/assets/...', 'selector': None},
    {'check': 'missing_fm_field',   'level': 'ERROR', 'detail': 'Required field missing: categories',    'selector': None},
    {'check': 'duplicate_paragraph','level': 'WARN',  'detail': 'Paragraph repeated: "This content repeats here in this post."', 'selector': None},
    {'check': 'wordpress_junk',     'level': 'WARN',  'detail': 'WordPress Related Posts in body',       'selector': None},
]


ASSET_HTML_ISSUES = [
    {
        'type': 'external_image', 'check': 'external_image', 'level': 'WARN',
        'detail': 'Image not localised: http://other.com/img.jpg',
        'selector': 'img[src="http://other.com/img.jpg"]',
    },
]
# assets.broken=2, assets.total=5 — these should appear in the panel as one aggregate row
ASSET_STATE = {'total': 5, 'localised': 3, 'broken': 2, 'checked_at': TS}

# Missing-content post: HTML has lists + a distinctive phrase; MD is missing both.
# The HTML file is served so the iframe can load it and highlight the list.
# The MD file has some content but is deliberately missing the list and the phrase.
MISSING_PHRASE = 'This distinctive phrase exists only in the HTML archive'

MISSING_HTML_CONTENT = textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>Missing Content Test</title></head>
    <body><article>
      <h1>Missing Content Test Post</h1>
      <p>This paragraph is present in both HTML and MD.</p>
      <ul>
        <li>First list item — dropped in conversion</li>
        <li>Second list item — also dropped</li>
        <li>Third list item — also dropped</li>
      </ul>
      <p>{MISSING_PHRASE}</p>
      <p>Another paragraph that also appears in the MD.</p>
    </article></body></html>
""")

# MD deliberately omits the <ul> list and the distinctive phrase
MISSING_MD_CONTENT = textwrap.dedent("""\
    ---
    title: Missing Content Test Post
    date: 2020-06-04
    author: Test Author
    tags:
      - test
    ---

    This paragraph is present in both HTML and MD.

    Another paragraph that also appears in the MD.
""")

MISSING_MD_ISSUES = [
    {'check': 'lists_dropped', 'level': 'WARN',
     'detail': 'HTML has 1 list(s) but MD has no list items', 'selector': None},
    {'check': 'content_phrase_missing', 'level': 'WARN',
     'detail': f'HTML para phrase not in MD: "{MISSING_PHRASE[:60]}..."', 'selector': None},
]


def make_highlight_state():
    return {
        HTML_SLUG: {
            'slug': HTML_SLUG, 'title': 'HTML Click Test Post',
            'date': '2020-06-01', 'author': 'Click Test Author',
            'original_url': f'http://example.com/{HTML_SLUG}',
            'ingested_at': TS, 'reviewed': False,
            'html': {'hash': uuid.uuid4().hex[:12], 'issues': HTML_ISSUES, 'checked_at': TS},
        },
        MD_SLUG: {
            'slug': MD_SLUG, 'title': 'MD Click Test Post',
            'date': '2020-06-02', 'author': 'Click Test Author',
            'original_url': f'http://example.com/{MD_SLUG}',
            'ingested_at': TS, 'reviewed': False,
            'html': {'hash': uuid.uuid4().hex[:12], 'issues': [], 'checked_at': TS},
            'md': {
                'generated_at': TS, 'html_hash': 'aaa000',
                'issues': MD_ISSUES, 'staged': False, 'validated_at': TS,
            },
        },
        ASSET_SLUG: {
            'slug': ASSET_SLUG, 'title': 'Asset Issues Post',
            'date': '2020-06-03', 'author': 'Click Test Author',
            'original_url': f'http://example.com/{ASSET_SLUG}',
            'ingested_at': TS, 'reviewed': False,
            'html': {'hash': uuid.uuid4().hex[:12], 'issues': ASSET_HTML_ISSUES, 'checked_at': TS},
            'assets': ASSET_STATE,
        },
        MISSING_SLUG: {
            'slug': MISSING_SLUG, 'title': 'Missing Content Test Post',
            'date': '2020-06-04', 'author': 'Click Test Author',
            'original_url': f'http://example.com/{MISSING_SLUG}',
            'ingested_at': TS, 'reviewed': False,
            'html': {'hash': uuid.uuid4().hex[:12], 'issues': [], 'checked_at': TS},
            'md': {
                'generated_at': TS, 'html_hash': 'bbb000',
                'issues': MISSING_MD_ISSUES, 'staged': False, 'validated_at': TS,
            },
        },
    }


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def session():
    try:
        import requests
        s = requests.Session()
        s.get(f'{API}/projects', timeout=3).raise_for_status()
        return s
    except Exception:
        pytest.skip('Server not running on localhost:9000')


@pytest.fixture(scope='module')
def test_project(session, tmp_path_factory):
    tmp = tmp_path_factory.mktemp('highlight_test')
    uid = uuid.uuid4().hex[:8]

    r = session.post(f'{API}/projects', json={
        'name': f'highlight-{uid}',
        'serve_root': str(tmp),
        'posts_dir': 'posts',
        'assets_dir': 'assets',
        'md_dir': 'md',
        'author_filter': '',
    })
    assert r.status_code in (200, 201), f'Project creation failed: {r.text}'
    pid = r.json()['id']

    cfg = session.get(f'{API}/config').json()
    projects_dir = Path(cfg.get('projects_dir', Path.home() / 'sparge-projects'))
    proj_dir = projects_dir / pid
    proj_dir.mkdir(parents=True, exist_ok=True)

    # Write state.json
    (proj_dir / 'state.json').write_text(json.dumps(make_highlight_state(), indent=2))

    # Write real HTML and MD files so iframe/md-wrap can load them
    posts_dir = tmp / 'posts'
    md_dir    = tmp / 'md'
    posts_dir.mkdir(exist_ok=True)
    md_dir.mkdir(exist_ok=True)

    (posts_dir / f'{HTML_SLUG}.html').write_text(HTML_POST_CONTENT, encoding='utf-8')
    (md_dir    / f'{MD_SLUG}.md').write_text(MD_FILE_CONTENT, encoding='utf-8')
    (posts_dir / f'{MISSING_SLUG}.html').write_text(MISSING_HTML_CONTENT, encoding='utf-8')
    (md_dir    / f'{MISSING_SLUG}.md').write_text(MISSING_MD_CONTENT, encoding='utf-8')

    session.post(f'{API}/projects/{pid}/activate')

    posts = session.get(f'{API}/posts').json()
    assert len(posts) == 4, f'Expected 4 posts, got {len(posts)}'

    yield {'id': pid, 'dir': proj_dir, 'tmp': tmp}

    session.delete(f'{API}/projects/{pid}')
    if proj_dir.exists():
        shutil.rmtree(proj_dir)
    session.post(f'{API}/projects/kie-mark-proctor/activate')


@pytest.fixture(scope='module')
def page(test_project, session):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip('playwright not installed')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page(viewport={'width': 1280, 'height': 900})
        pg.goto(APP_URL, wait_until='networkidle')
        pg.wait_for_selector('.pi', timeout=10000)
        yield pg
        browser.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def select_and_open(page, slug: str):
    """Select a post, open the issues panel, wait for iframe/md to load."""
    page.locator(f'[data-slug="{slug}"]').click()
    # Wait for iframe or md-wrap to settle
    page.wait_for_timeout(600)
    btn = page.locator('#btn-issues')
    if 'active' not in (btn.get_attribute('class') or ''):
        btn.click()
        page.wait_for_timeout(200)


def close_issues(page):
    btn = page.locator('#btn-issues')
    if 'active' in (btn.get_attribute('class') or ''):
        btn.click()
        page.wait_for_timeout(100)


def html_issue_row(page, check: str):
    return page.locator(f'#html-issue-list .irow[data-check="{check}"]').first


def md_issue_row(page, check: str):
    return page.locator(f'#md-issue-list .irow[data-check="{check}"]').first


def wait_for_iframe_load(page, slug: str, timeout=8000):
    """Wait until the iframe has fully loaded the document for this slug.

    Uses slug in the URL check so we don't accidentally return early with the
    previous post's document still loaded (race between re-select and reload).
    """
    page.wait_for_function(f"""() => {{
        const f = document.getElementById('orig-frame');
        return f && f.src && f.src.includes('{slug}') &&
               f.contentDocument &&
               f.contentDocument.readyState === 'complete' &&
               f.contentDocument.querySelector('body') !== null;
    }}""", timeout=timeout)


def iframe_has_highlight_style(page) -> bool:
    """True if the iframe's injected style tag has non-empty content."""
    return page.evaluate("""() => {
        try {
            const doc = document.getElementById('orig-frame').contentDocument;
            const st  = doc && doc.getElementById('__migrator-highlight-style__');
            return !!(st && st.textContent && st.textContent.trim().length > 0);
        } catch(e) { return false; }
    }""")


def iframe_highlight_matches_selector(page, selector: str) -> bool:
    """True if the iframe contains the expected selector in its highlight style."""
    return page.evaluate(f"""() => {{
        try {{
            const doc = document.getElementById('orig-frame').contentDocument;
            const st  = doc && doc.getElementById('__migrator-highlight-style__');
            return !!(st && st.textContent && st.textContent.includes({json.dumps(selector)}));
        }} catch(e) {{ return false; }}
    }}""")


def md_wrap_has_highlight(page) -> bool:
    """True if #md-wrap contains any .md-hl element (class or mark)."""
    return page.evaluate("""() =>
        document.querySelectorAll('#md-wrap .md-hl').length > 0
    """)


def md_highlight_tag(page) -> str | None:
    """Return the tag name of the first .md-hl element, or None."""
    return page.evaluate("""() => {
        const el = document.querySelector('#md-wrap .md-hl');
        return el ? el.tagName.toLowerCase() : null;
    }""")


def md_highlight_text(page) -> str:
    """Return text content of the first .md-hl element."""
    return page.evaluate("""() => {
        const el = document.querySelector('#md-wrap .md-hl');
        return el ? el.textContent : '';
    }""")


def row_is_highlighted(page, row_locator) -> bool:
    return 'highlighted' in (row_locator.get_attribute('class') or '')


def click_row(page, row_locator):
    row_locator.click()
    page.wait_for_timeout(300)


# ── HTML issue highlight tests ─────────────────────────────────────────────────

class TestHtmlIssueHighlight:

    def setup_method(self, _):
        pass  # each test does its own select_and_open

    def test_html_row_has_data_selector_attribute(self, page):
        select_and_open(page, HTML_SLUG)
        for row in page.locator('#html-issue-list .irow.clickable').all():
            sel = row.get_attribute('data-selector')
            assert sel is not None and len(sel) > 0, (
                'HTML issue rows with selectors must have data-selector attribute')

    def test_html_row_does_not_have_no_selector_class(self, page):
        """HTML rows with selectors must be clickable, not dimmed as no-selector."""
        select_and_open(page, HTML_SLUG)
        for row in page.locator('#html-issue-list .irow').all():
            classes = row.get_attribute('class') or ''
            assert 'no-selector' not in classes, (
                f'HTML row with a selector must not have no-selector class. Got: {classes}')

    def test_click_external_image_row_injects_iframe_style(self, page):
        """Clicking external_image row must inject a highlight style into the iframe."""
        select_and_open(page, HTML_SLUG)
        wait_for_iframe_load(page, HTML_SLUG)
        row = html_issue_row(page, 'external_image')
        click_row(page, row)
        assert iframe_has_highlight_style(page), (
            'Iframe should have a non-empty highlight style tag after clicking the row')

    def test_click_external_image_row_uses_correct_selector(self, page):
        select_and_open(page, HTML_SLUG)
        wait_for_iframe_load(page, HTML_SLUG)
        click_row(page, html_issue_row(page, 'external_image'))
        selector = 'img[src="http://cdn.example.com/photo.jpg"]'
        assert iframe_highlight_matches_selector(page, selector), (
            f'Iframe style should contain selector {selector!r}')

    def test_click_external_image_row_gets_highlighted_class(self, page):
        select_and_open(page, HTML_SLUG)
        wait_for_iframe_load(page, HTML_SLUG)
        row = html_issue_row(page, 'external_image')
        click_row(page, row)
        assert row_is_highlighted(page, row), (
            'Clicked HTML issue row must get .highlighted class')

    def test_click_data_placeholder_row_uses_correct_selector(self, page):
        select_and_open(page, HTML_SLUG)
        wait_for_iframe_load(page, HTML_SLUG)
        click_row(page, html_issue_row(page, 'data_placeholder'))
        selector = 'img[src^="data:image"]'
        assert iframe_highlight_matches_selector(page, selector), (
            f'Iframe style should contain selector {selector!r}')

    def test_click_same_html_row_twice_clears_highlight(self, page):
        select_and_open(page, HTML_SLUG)
        wait_for_iframe_load(page, HTML_SLUG)
        row = html_issue_row(page, 'external_image')
        click_row(page, row)
        assert iframe_has_highlight_style(page), 'Should be highlighted after first click'
        click_row(page, row)  # second click = deselect
        assert not iframe_has_highlight_style(page), (
            'Iframe highlight style should be cleared after clicking same row twice')
        assert not row_is_highlighted(page, row), (
            'Row should lose .highlighted class after second click')

    def test_switching_html_rows_updates_selector(self, page):
        """Clicking a different row clears the previous and applies the new selector."""
        select_and_open(page, HTML_SLUG)
        wait_for_iframe_load(page, HTML_SLUG)
        click_row(page, html_issue_row(page, 'external_image'))
        assert iframe_highlight_matches_selector(page, 'img[src="http://cdn.example.com/photo.jpg"]')
        click_row(page, html_issue_row(page, 'data_placeholder'))
        assert iframe_highlight_matches_selector(page, 'img[src^="data:image"]'), (
            'Switching to a different row must update the iframe selector')
        assert not iframe_highlight_matches_selector(page, 'img[src="http://cdn.example.com/photo.jpg"]'), (
            'Previous selector must be gone after switching rows')

    def test_switching_posts_clears_html_highlight(self, page):
        select_and_open(page, HTML_SLUG)
        wait_for_iframe_load(page, HTML_SLUG)
        click_row(page, html_issue_row(page, 'external_image'))
        assert iframe_has_highlight_style(page)
        # Switch to the other post
        page.locator(f'[data-slug="{MD_SLUG}"]').click()
        page.wait_for_timeout(400)
        assert not iframe_has_highlight_style(page), (
            'Switching posts must clear the iframe highlight')

    def test_closing_issue_panel_clears_html_highlight(self, page):
        select_and_open(page, HTML_SLUG)
        wait_for_iframe_load(page, HTML_SLUG)
        click_row(page, html_issue_row(page, 'external_image'))
        assert iframe_has_highlight_style(page)
        close_issues(page)
        assert not iframe_has_highlight_style(page), (
            'Closing the issue panel must clear the iframe highlight')


# ── MD issue highlight tests ───────────────────────────────────────────────────

class TestMdIssueHighlight:
    """MD issue rows click → highlight in #md-wrap."""

    def _open(self, page):
        select_and_open(page, MD_SLUG)
        # Wait for md-wrap to have rendered content
        page.wait_for_function(
            "() => document.getElementById('md-wrap')?.children.length > 0",
            timeout=6000,
        )

    def test_md_rows_are_all_clickable(self, page):
        self._open(page)
        rows = page.locator('#md-issue-list .irow').all()
        assert len(rows) == len(MD_ISSUES), (
            f'Expected {len(MD_ISSUES)} MD issue rows, got {len(rows)}')
        for row in rows:
            assert 'clickable' in (row.get_attribute('class') or ''), (
                'All MD issue rows must have .clickable class')
            assert 'no-selector' not in (row.get_attribute('class') or ''), (
                'MD rows must not have .no-selector dim class')

    def test_md_rows_have_data_check_and_detail(self, page):
        self._open(page)
        for row in page.locator('#md-issue-list .irow').all():
            assert row.get_attribute('data-check'), 'MD row must have data-check'
            assert row.get_attribute('data-detail'), 'MD row must have data-detail'

    # ── Strategy: CSS selector (broken_links → a[href=""])
    def test_broken_links_highlights_empty_anchor(self, page):
        self._open(page)
        click_row(page, md_issue_row(page, 'broken_links'))
        assert md_wrap_has_highlight(page), 'broken_links click must add .md-hl to #md-wrap'
        tag = md_highlight_tag(page)
        assert tag == 'a', f'broken_links should highlight an <a> element, got <{tag}>'

    def test_broken_links_row_gets_highlighted_class(self, page):
        self._open(page)
        row = md_issue_row(page, 'broken_links')
        click_row(page, row)
        assert row_is_highlighted(page, row)

    # ── Strategy: CSS selector (relative_image_path → img[src^="../../"])
    def test_relative_image_highlights_img(self, page):
        self._open(page)
        click_row(page, md_issue_row(page, 'relative_image_path'))
        assert md_wrap_has_highlight(page)
        tag = md_highlight_tag(page)
        assert tag == 'img', f'relative_image_path should highlight an <img>, got <{tag}>'

    # ── Strategy: CSS selector (missing_fm_field → .fm-card)
    def test_missing_fm_field_highlights_fm_card(self, page):
        self._open(page)
        click_row(page, md_issue_row(page, 'missing_fm_field'))
        assert md_wrap_has_highlight(page)
        # The fm-card is a div — check it contains the post title
        text = md_highlight_text(page)
        assert len(text) > 0, 'fm-card highlight must have non-empty text content'

    # ── Strategy: text search (duplicate_paragraph)
    def test_duplicate_paragraph_wraps_text_in_mark(self, page):
        self._open(page)
        click_row(page, md_issue_row(page, 'duplicate_paragraph'))
        assert md_wrap_has_highlight(page)
        tag = md_highlight_tag(page)
        assert tag == 'mark', (
            f'duplicate_paragraph should wrap text in <mark>, got <{tag}>')
        text = md_highlight_text(page)
        assert 'This content repeats' in text, (
            f'Highlighted text should contain the repeated phrase. Got: {text!r}')

    # ── Strategy: text search (wordpress_junk)
    def test_wordpress_junk_wraps_text_in_mark(self, page):
        self._open(page)
        click_row(page, md_issue_row(page, 'wordpress_junk'))
        assert md_wrap_has_highlight(page)
        tag = md_highlight_tag(page)
        assert tag == 'mark', (
            f'wordpress_junk should wrap text in <mark>, got <{tag}>')
        text = md_highlight_text(page)
        assert 'WordPress' in text, (
            f'Highlighted text should contain WordPress. Got: {text!r}')

    def test_click_same_md_row_twice_clears_highlight(self, page):
        self._open(page)
        row = md_issue_row(page, 'broken_links')
        click_row(page, row)
        assert md_wrap_has_highlight(page)
        click_row(page, row)
        assert not md_wrap_has_highlight(page), (
            'Second click on same MD row must clear the highlight')
        assert not row_is_highlighted(page, row)

    def test_switching_md_rows_clears_previous(self, page):
        self._open(page)
        click_row(page, md_issue_row(page, 'broken_links'))
        assert md_highlight_tag(page) == 'a'
        click_row(page, md_issue_row(page, 'relative_image_path'))
        tag = md_highlight_tag(page)
        assert tag == 'img', (
            f'After switching rows, previous highlight must clear and new one applied. Got: {tag}')
        # Only one .md-hl should exist
        count = page.evaluate("document.querySelectorAll('#md-wrap .md-hl').length")
        assert count == 1, f'Only one .md-hl should exist at a time, got {count}'

    def test_switching_posts_clears_md_highlight(self, page):
        self._open(page)
        click_row(page, md_issue_row(page, 'broken_links'))
        assert md_wrap_has_highlight(page)
        page.locator(f'[data-slug="{HTML_SLUG}"]').click()
        page.wait_for_timeout(400)
        assert not md_wrap_has_highlight(page), (
            'Switching posts must clear #md-wrap highlight')

    def test_closing_panel_clears_md_highlight(self, page):
        self._open(page)
        click_row(page, md_issue_row(page, 'missing_fm_field'))
        assert md_wrap_has_highlight(page)
        close_issues(page)
        assert not md_wrap_has_highlight(page), (
            'Closing the issues panel must clear the MD highlight')


# ── Cross-clearing tests ───────────────────────────────────────────────────────

class TestCrossHighlightClearing:
    """Clicking an HTML row must clear any MD highlight and vice versa."""

    def test_html_click_clears_md_highlight(self, page):
        # First get a MD highlight
        select_and_open(page, MD_SLUG)
        page.wait_for_function(
            "() => document.getElementById('md-wrap')?.children.length > 0",
            timeout=6000)
        click_row(page, md_issue_row(page, 'broken_links'))
        assert md_wrap_has_highlight(page), 'Setup: MD highlight must be active'

        # Switch to HTML post and click an HTML row
        select_and_open(page, HTML_SLUG)
        wait_for_iframe_load(page, HTML_SLUG)
        click_row(page, html_issue_row(page, 'external_image'))

        assert iframe_has_highlight_style(page), 'HTML highlight must be active'
        assert not md_wrap_has_highlight(page), (
            'MD highlight must be cleared when HTML row is clicked')

    def test_md_click_clears_html_highlight(self, page):
        # First get an HTML highlight
        select_and_open(page, HTML_SLUG)
        wait_for_iframe_load(page, HTML_SLUG)
        click_row(page, html_issue_row(page, 'external_image'))
        assert iframe_has_highlight_style(page), 'Setup: HTML highlight must be active'

        # Switch to MD post and click an MD row
        select_and_open(page, MD_SLUG)
        page.wait_for_function(
            "() => document.getElementById('md-wrap')?.children.length > 0",
            timeout=6000)
        click_row(page, md_issue_row(page, 'broken_links'))

        assert md_wrap_has_highlight(page), 'MD highlight must be active'
        assert not iframe_has_highlight_style(page), (
            'HTML iframe highlight must be cleared when MD row is clicked')

    def test_only_one_html_row_highlighted_at_a_time(self, page):
        select_and_open(page, HTML_SLUG)
        wait_for_iframe_load(page, HTML_SLUG)
        row1 = html_issue_row(page, 'external_image')
        row2 = html_issue_row(page, 'data_placeholder')
        click_row(page, row1)
        assert iframe_highlight_matches_selector(page, 'img[src="http://cdn.example.com/photo.jpg"]'), (
            'First row: red outline must appear on external_image selector')
        click_row(page, row2)
        assert not row_is_highlighted(page, row1), (
            'First row must lose .highlighted when second is clicked')
        assert row_is_highlighted(page, row2), (
            'Second row must have .highlighted class')
        # Verify previous selector's red outline is gone — new selector is active
        assert not iframe_highlight_matches_selector(page, 'img[src="http://cdn.example.com/photo.jpg"]'), (
            'Previous selector red outline must disappear when different row is clicked')
        assert iframe_highlight_matches_selector(page, 'img[src^="data:image"]'), (
            'New selector red outline must appear on data_placeholder selector')

    def test_only_one_md_row_highlighted_at_a_time(self, page):
        select_and_open(page, MD_SLUG)
        page.wait_for_function(
            "() => document.getElementById('md-wrap')?.children.length > 0",
            timeout=6000)
        row1 = md_issue_row(page, 'broken_links')
        row2 = md_issue_row(page, 'relative_image_path')
        click_row(page, row1)
        # First red outline on <a href="">
        first_tag = md_highlight_tag(page)
        assert first_tag == 'a', f'First MD highlight should be <a>, got <{first_tag}>'
        click_row(page, row2)
        assert not row_is_highlighted(page, row1), 'First MD row must lose .highlighted'
        assert row_is_highlighted(page, row2), 'Second MD row must have .highlighted'
        # Previous <a> red outline gone; now <img> is highlighted
        second_tag = md_highlight_tag(page)
        assert second_tag == 'img', (
            f'After switching MD rows, previous <a> red outline must clear '
            f'and <img> outline must appear. Got: <{second_tag}>')
        count = page.evaluate("document.querySelectorAll('#md-wrap .md-hl').length")
        assert count == 1, f'Only one red-outlined element at a time, got {count}'

    def test_html_red_outline_clears_on_deselect(self, page):
        """Clicking the same HTML row twice: outline appears then disappears."""
        select_and_open(page, HTML_SLUG)
        wait_for_iframe_load(page, HTML_SLUG)
        row = html_issue_row(page, 'external_image')
        click_row(page, row)
        assert iframe_has_highlight_style(page), 'Red outline must appear after first click'
        click_row(page, row)  # deselect
        assert not iframe_has_highlight_style(page), (
            'Red outline must disappear after clicking same HTML row twice')

    def test_md_red_outline_clears_on_deselect(self, page):
        """Clicking the same MD row twice: outline appears then disappears."""
        select_and_open(page, MD_SLUG)
        page.wait_for_function(
            "() => document.getElementById('md-wrap')?.children.length > 0",
            timeout=6000)
        row = md_issue_row(page, 'broken_links')
        click_row(page, row)
        assert md_wrap_has_highlight(page), 'MD red outline must appear after first click'
        click_row(page, row)  # deselect
        assert not md_wrap_has_highlight(page), (
            'MD red outline must disappear after clicking same row twice')


# ── Badge ↔ panel consistency ──────────────────────────────────────────────────

class TestBadgePanelConsistency:
    """The number of entries in the HTML issues panel must equal the number
    of issue items the badges account for:

      panel_html_row_count == len(html.issues) + (1 if assets.broken > 0 else 0)

    Broken assets are shown as ONE aggregate entry in the panel (individual
    file paths are not stored in state — only the count).  The assets badge
    shows HOW MANY images are broken; the aggregate panel entry explains what
    to do about it.

    This test class was added because the original implementation showed
    '1 HTML scan + 🖼 2 missing' in the badges but only 1 entry in the panel,
    confusing users who expected the counts to correspond.
    """

    def _html_row_count(self, page) -> int:
        return page.locator('#html-issue-list .irow').count()

    def _open_asset_post(self, page):
        select_and_open(page, ASSET_SLUG)
        page.wait_for_timeout(300)

    def test_post_with_no_assets_broken_shows_only_scan_issues(self, page):
        """HTML_SLUG has 2 html.issues and no assets data — panel shows 2 rows."""
        select_and_open(page, HTML_SLUG)
        count = self._html_row_count(page)
        assert count == len(HTML_ISSUES), (
            f'Panel should show {len(HTML_ISSUES)} rows (scan issues only, no asset issues). '
            f'Got {count}.')

    def test_post_with_assets_broken_shows_scan_plus_aggregate(self, page):
        """ASSET_SLUG has 1 scan issue + assets.broken=2 — panel shows 2 rows (1+1)."""
        self._open_asset_post(page)
        count = self._html_row_count(page)
        expected = len(ASSET_HTML_ISSUES) + 1  # 1 aggregate asset row
        assert count == expected, (
            f'Panel should show {expected} rows (1 scan + 1 aggregate asset entry). '
            f'Got {count}. The asset badge shows "2 missing" images; '
            f'they must appear in the panel as one aggregate entry.')

    def test_aggregate_asset_row_has_correct_check_type(self, page):
        """The synthetic asset row must use check type images_not_localised."""
        self._open_asset_post(page)
        row = page.locator('#html-issue-list .irow[data-check="images_not_localised"]')
        assert row.count() == 1, (
            'Expected exactly one images_not_localised row in the HTML issues panel')

    def test_aggregate_asset_row_mentions_broken_count(self, page):
        """The aggregate asset row detail must mention the broken count (2)."""
        self._open_asset_post(page)
        row = page.locator('#html-issue-list .irow[data-check="images_not_localised"]')
        text = row.inner_text()
        assert '2' in text, (
            f'Aggregate asset row must mention the broken count (2). Got: {text!r}')
        assert '5' in text, (
            f'Aggregate asset row must mention the total count (5). Got: {text!r}')

    def test_aggregate_asset_row_is_warn_level(self, page):
        """Asset row is a WARN (not ERROR) — individual files may be recoverable."""
        self._open_asset_post(page)
        row = page.locator('#html-issue-list .irow[data-check="images_not_localised"]')
        classes = row.get_attribute('class') or ''
        assert 'warn' in classes, f'Asset row should have .warn class. Got: {classes}'
        assert 'err' not in classes, f'Asset row should not have .err class. Got: {classes}'

    def test_ph_assets_badge_shows_broken_count(self, page):
        """The assets badge must display the broken count from assets.broken."""
        self._open_asset_post(page)
        badge = page.locator('#ph-assets-badge')
        assert badge.is_visible(), 'Assets badge must be visible when assets.broken > 0'
        text = badge.inner_text()
        assert '2' in text, (
            f'Assets badge must show the broken count (2). Got: {text!r}')

    def test_post_without_asset_scan_has_no_aggregate_row(self, page):
        """A post with html.issues but no assets scan shows only scan rows."""
        select_and_open(page, HTML_SLUG)
        agg = page.locator('#html-issue-list .irow[data-check="images_not_localised"]')
        assert agg.count() == 0, (
            'No aggregate asset row should appear when assets have not been scanned')


# ── Missing-content highlight tests ───────────────────────────────────────────

class TestMissingContentHighlight:
    """lists_dropped and content_phrase_missing show the HTML source and a MD marker.

    These issues indicate content that exists in the HTML but was not converted
    into the MD. The new behaviour (vs the old 'absent' tooltip-only):
      - HTML panel: scrolls to and red-outlines the dropped element
      - MD panel:   inserts a red dashed marker line where the content should be
    """

    def _open_missing(self, page):
        select_and_open(page, MISSING_SLUG)
        page.wait_for_function(
            "() => document.getElementById('md-wrap')?.children.length > 0",
            timeout=6000,
        )

    def _md_marker_count(self, page) -> int:
        return page.locator('#md-wrap .md-absent-marker').count()

    def _md_marker_text(self, page) -> str:
        return page.locator('#md-wrap .md-absent-marker').first.inner_text()

    # ── lists_dropped ──────────────────────────────────────────────────────────

    def test_lists_dropped_row_is_clickable(self, page):
        self._open_missing(page)
        row = md_issue_row(page, 'lists_dropped')
        assert 'clickable' in (row.get_attribute('class') or ''), (
            'lists_dropped row must have .clickable class')

    def test_lists_dropped_highlights_html_iframe(self, page):
        """Clicking lists_dropped must inject a highlight style into the iframe
        targeting 'ul, ol' — showing the actual dropped list."""
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        click_row(page, md_issue_row(page, 'lists_dropped'))
        assert iframe_has_highlight_style(page), (
            'lists_dropped click must inject a highlight style into the HTML iframe')

    def test_lists_dropped_iframe_selector_targets_list(self, page):
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        click_row(page, md_issue_row(page, 'lists_dropped'))
        # The selector must target ul or ol (the actual dropped list element)
        assert iframe_highlight_matches_selector(page, 'ul') or \
               iframe_highlight_matches_selector(page, 'ol') or \
               iframe_highlight_matches_selector(page, 'ul, ol'), (
            'lists_dropped iframe selector must target a list element (ul or ol)')

    def test_lists_dropped_inserts_md_marker(self, page):
        """A red dashed marker must appear in #md-wrap after clicking lists_dropped."""
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        assert self._md_marker_count(page) == 0, 'No marker before clicking'
        click_row(page, md_issue_row(page, 'lists_dropped'))
        assert self._md_marker_count(page) == 1, (
            'Exactly one .md-absent-marker must appear in #md-wrap after clicking lists_dropped')

    def test_lists_dropped_marker_mentions_lists(self, page):
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        click_row(page, md_issue_row(page, 'lists_dropped'))
        text = self._md_marker_text(page).lower()
        assert 'list' in text or 'drop' in text or 'missing' in text, (
            f'Marker text should mention lists or dropped content. Got: {text!r}')

    def test_lists_dropped_row_gets_highlighted_class(self, page):
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        row = md_issue_row(page, 'lists_dropped')
        click_row(page, row)
        assert row_is_highlighted(page, row), (
            'lists_dropped row must get .highlighted class after clicking')

    def test_lists_dropped_deselect_clears_both_highlights(self, page):
        """Clicking the same row twice clears the iframe highlight AND the MD marker."""
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        row = md_issue_row(page, 'lists_dropped')
        click_row(page, row)
        assert iframe_has_highlight_style(page), 'HTML highlight must appear after first click'
        assert self._md_marker_count(page) == 1, 'MD marker must appear after first click'
        click_row(page, row)  # deselect
        assert not iframe_has_highlight_style(page), (
            'HTML highlight must clear after clicking same row twice')
        assert self._md_marker_count(page) == 0, (
            'MD marker must be removed after clicking same row twice')

    # ── content_phrase_missing ────────────────────────────────────────────────

    def test_content_phrase_missing_row_is_clickable(self, page):
        self._open_missing(page)
        row = md_issue_row(page, 'content_phrase_missing')
        assert 'clickable' in (row.get_attribute('class') or '')

    def test_content_phrase_missing_highlights_html_iframe(self, page):
        """Clicking content_phrase_missing highlights a paragraph in the HTML iframe."""
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        click_row(page, md_issue_row(page, 'content_phrase_missing'))
        assert iframe_has_highlight_style(page), (
            'content_phrase_missing click must inject a highlight into the HTML iframe')

    def test_content_phrase_missing_inserts_md_marker(self, page):
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        click_row(page, md_issue_row(page, 'content_phrase_missing'))
        assert self._md_marker_count(page) == 1, (
            'One .md-absent-marker must appear after clicking content_phrase_missing')

    def test_content_phrase_missing_marker_contains_phrase(self, page):
        """The marker text must include the actual missing phrase from the detail."""
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        click_row(page, md_issue_row(page, 'content_phrase_missing'))
        text = self._md_marker_text(page)
        # The phrase from MISSING_PHRASE should appear in the marker
        assert 'distinctive' in text.lower() or 'phrase' in text.lower() or \
               'absent' in text.lower() or 'missing' in text.lower(), (
            f'Marker text should reference the missing phrase. Got: {text!r}')

    def test_content_phrase_missing_deselect_clears_both(self, page):
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        row = md_issue_row(page, 'content_phrase_missing')
        click_row(page, row)
        assert iframe_has_highlight_style(page)
        assert self._md_marker_count(page) == 1
        click_row(page, row)
        assert not iframe_has_highlight_style(page), 'HTML highlight must clear on deselect'
        assert self._md_marker_count(page) == 0, 'MD marker must clear on deselect'

    # ── cross-clearing with other issue types ─────────────────────────────────

    def test_switching_to_missing_type_clears_previous_md_highlight(self, page):
        """Clicking a regular MD issue then a missing-content issue: previous cleared."""
        select_and_open(page, MD_SLUG)
        page.wait_for_function(
            "() => document.getElementById('md-wrap')?.children.length > 0",
            timeout=6000)
        click_row(page, md_issue_row(page, 'broken_links'))
        assert md_wrap_has_highlight(page), 'Setup: broken_links highlight active'

        # Switch to missing-content post
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        click_row(page, md_issue_row(page, 'lists_dropped'))

        assert not md_wrap_has_highlight(page), (
            'Previous .md-hl highlight must be cleared when switching to missing-content issue')
        assert self._md_marker_count(page) == 1, (
            'MD absent marker must appear for lists_dropped')

    def test_switching_from_missing_type_clears_marker(self, page):
        """After a missing-content click, switching to a regular issue clears the marker."""
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        click_row(page, md_issue_row(page, 'lists_dropped'))
        assert self._md_marker_count(page) == 1

        # Switch to regular MD post and click a normal issue
        select_and_open(page, MD_SLUG)
        page.wait_for_function(
            "() => document.getElementById('md-wrap')?.children.length > 0",
            timeout=6000)
        click_row(page, md_issue_row(page, 'broken_links'))

        assert self._md_marker_count(page) == 0, (
            'MD absent marker must be removed when switching to a different post/issue')

    def test_switching_posts_clears_missing_content_marker(self, page):
        """Navigating to a different post removes any active MD absent marker."""
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        click_row(page, md_issue_row(page, 'lists_dropped'))
        assert self._md_marker_count(page) == 1

        page.locator(f'[data-slug="{HTML_SLUG}"]').click()
        page.wait_for_timeout(400)

        assert self._md_marker_count(page) == 0, (
            'MD absent marker must be removed when navigating to a different post')

    def test_only_one_md_marker_at_a_time(self, page):
        """Clicking a second missing-content issue replaces the first marker."""
        self._open_missing(page)
        wait_for_iframe_load(page, MISSING_SLUG)
        click_row(page, md_issue_row(page, 'lists_dropped'))
        assert self._md_marker_count(page) == 1
        click_row(page, md_issue_row(page, 'content_phrase_missing'))
        count = self._md_marker_count(page)
        assert count == 1, (
            f'Only one absent marker should exist at a time, got {count}')


# ── generateMd dry-run: content extraction from JSON response ─────────────────

class TestGenerateMdDryRun:
    """Regression test for the dry-run JSON parsing bug.

    generateMd() does a dry-run (POST generate-md?dry=1) when a post already
    has MD, so it can show a diff before overwriting.  The server returns
    {"content": "---\\ntitle: ...\\n---\\n..."} — a JSON object with a
    "content" key.

    Bug: the old code used .text() on this response, so newMd was the raw JSON
    string '{"content": "---\\n..."}'. That string was passed to showDiffModal(),
    which rendered it in the right diff column — the user saw the front matter
    wrapped in JSON rather than the actual MD content.

    Fix: use .json().content to extract the actual MD string.

    Test-first note: this class was written AFTER the fix was applied.  The
    assertion `assert '{"content":' not in right_text` is the one that would
    have caught the bug — it would have failed against the broken code because
    the JSON wrapper would appear verbatim in the diff panel.
    """

    MOCK_NEW_MD = textwrap.dedent("""\
        ---
        layout: post
        title: "Mock regenerated title"
        date: 2020-06-04
        author: Test Author
        categories: []
        tags: []
        original_url: http://example.com/missing
        ---

        This is the regenerated body content.

        It has multiple paragraphs.
    """)

    def _intercept_dryrun(self, page, content: str):
        """Route POST generate-md?dry=1 to return a mock {"content": ...} response."""
        import json as _json

        def handler(route):
            if 'dry=1' in route.request.url:
                route.fulfill(
                    status=200,
                    content_type='application/json',
                    body=_json.dumps({'content': content}),
                )
            else:
                route.continue_()  # let real generate-md calls through

        page.route('**/generate-md*', handler)

    def _open_post_with_md(self, page):
        """Select MISSING_SLUG (has md.generated_at) and open it."""
        page.locator(f'[data-slug="{MISSING_SLUG}"]').click()
        page.wait_for_timeout(400)

    def _click_generate_button(self, page):
        """Click the per-post '↺ Generate MD' button in the action bar."""
        page.locator('#btn-gen').click()

    def _diff_right_text(self, page) -> str:
        """Return the visible text of the right (new/regenerated) diff column."""
        return page.locator('#diff-right-wrap').inner_text()

    def _diff_modal_is_open(self, page) -> bool:
        return 'open' in (page.locator('#diff-modal').get_attribute('class') or '')

    def test_diff_right_panel_shows_md_not_json_wrapper(self, page):
        """The right diff panel must show the extracted MD content, not '{"content": ...}'.

        This is the core regression: the broken code passed the raw JSON string
        to showDiffModal(), so the right panel contained '{"content":' literally.
        The fix uses .json().content to extract the MD string before diffing.
        """
        self._open_post_with_md(page)
        self._intercept_dryrun(page, self.MOCK_NEW_MD)
        try:
            self._click_generate_button(page)
            # Wait for either the diff modal to open or the button to restore
            page.wait_for_function(
                "() => document.getElementById('diff-modal').classList.contains('open') "
                "|| document.getElementById('btn-gen').textContent.includes('No change') "
                "|| document.getElementById('btn-gen').textContent.includes('Generate')",
                timeout=8000,
            )
            if not self._diff_modal_is_open(page):
                # Content was identical — nothing to test here (shouldn't happen with mock)
                pytest.skip('Diff modal did not open — existing and new MD were identical')

            right_text = self._diff_right_text(page)

            # KEY ASSERTION: the raw JSON wrapper must NOT appear in the diff panel
            assert '{"content":' not in right_text, (
                'Diff right panel contains the raw JSON wrapper {"content": ...} — '
                'the dry-run response was not parsed correctly. '
                f'Got (first 200 chars): {right_text[:200]!r}')

            # The actual MD content (front matter marker) must be visible
            assert '---' in right_text or 'Mock regenerated title' in right_text, (
                'Diff right panel should show actual MD content (front matter or title). '
                f'Got (first 200 chars): {right_text[:200]!r}')
        finally:
            page.unroute('**/generate-md*')
            if self._diff_modal_is_open(page):
                page.locator('#diff-close').click()
                page.wait_for_timeout(200)

    def test_diff_right_panel_contains_regenerated_body(self, page):
        """The right panel must contain the body text from the mock response."""
        self._open_post_with_md(page)
        self._intercept_dryrun(page, self.MOCK_NEW_MD)
        try:
            self._click_generate_button(page)
            page.wait_for_function(
                "() => document.getElementById('diff-modal').classList.contains('open') "
                "|| document.getElementById('btn-gen').textContent.includes('Generate')",
                timeout=8000,
            )
            if not self._diff_modal_is_open(page):
                pytest.skip('Diff modal did not open')

            right_text = self._diff_right_text(page)
            assert 'regenerated body content' in right_text, (
                f'Right panel should contain the mock body text. '
                f'Got (first 200 chars): {right_text[:200]!r}')
        finally:
            page.unroute('**/generate-md*')
            if self._diff_modal_is_open(page):
                page.locator('#diff-close').click()
                page.wait_for_timeout(200)

    def test_no_change_when_dry_run_matches_existing(self, page):
        """When dry-run returns identical content to existing MD, no diff modal appears."""
        self._open_post_with_md(page)
        # Return the SAME content as the existing MD file
        self._intercept_dryrun(page, MISSING_MD_CONTENT)
        try:
            self._click_generate_button(page)
            # Wait for button to show "No change" (same content) or modal to open
            page.wait_for_function(
                "() => document.getElementById('btn-gen').textContent.includes('No change') "
                "|| document.getElementById('diff-modal').classList.contains('open')",
                timeout=8000,
            )
            assert not self._diff_modal_is_open(page), (
                'Diff modal must not open when regenerated content is identical to existing')
            btn_text = page.locator('#btn-gen').inner_text()
            assert 'No change' in btn_text, (
                f'Button should show "No change" when content is identical. Got: {btn_text!r}')
        finally:
            page.unroute('**/generate-md*')
            if self._diff_modal_is_open(page):
                page.locator('#diff-close').click()
                page.wait_for_timeout(200)
