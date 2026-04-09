"""
Integration tests for the edit mode save/retrieve cycle.

Tests the complete flow:
  1. Fetch raw HTML/MD via API
  2. Save modified content
  3. Verify the modification is retrievable

Requires server running on localhost:9000.
Tests are automatically skipped if server is not reachable.
"""
import json
import sys
from pathlib import Path

import pytest
import requests

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

SERVER = 'http://localhost:9000'
API    = SERVER + '/api'
SESSION = requests.Session()
SESSION.headers['Content-Type'] = 'application/json'

MARKER_HTML = '<!-- edit-flow-integration-test -->'
MARKER_MD   = '\n\n<!-- edit-flow-integration-test -->'


@pytest.fixture(scope='module')
def server():
    """Skip all tests if server is not running."""
    try:
        requests.get(f'{API}/projects', timeout=3).raise_for_status()
    except Exception:
        pytest.skip('Server not running on localhost:9000')


@pytest.fixture(scope='module')
def test_slug(server):
    """Return the slug of the first available post."""
    posts = SESSION.get(f'{API}/posts').json()
    if not posts:
        pytest.skip('No posts in active project')
    return posts[0]['slug']


class TestHtmlEditCycle:
    """Complete HTML edit → save → retrieve cycle."""

    def test_fetch_html_returns_content(self, server, test_slug):
        r = SESSION.get(f'{API}/posts/{test_slug}/html')
        assert r.status_code == 200
        assert len(r.text) > 100
        assert '<' in r.text

    def test_save_and_retrieve_html(self, server, test_slug):
        original = SESSION.get(f'{API}/posts/{test_slug}/html').text
        assert MARKER_HTML not in original

        modified = original + MARKER_HTML
        r = SESSION.post(
            f'{API}/posts/{test_slug}/save-html',
            data=modified.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        assert r.status_code == 200

        retrieved = SESSION.get(f'{API}/posts/{test_slug}/html').text
        assert MARKER_HTML in retrieved

    def test_save_html_returns_post_state(self, server, test_slug):
        original = SESSION.get(f'{API}/posts/{test_slug}/html').text
        r = SESSION.post(
            f'{API}/posts/{test_slug}/save-html',
            data=original.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        data = r.json()
        assert 'slug' in data
        assert data['slug'] == test_slug

    def test_save_html_never_touches_original(self, server, test_slug):
        """Original HTML file must remain unchanged after saving enriched copy."""
        import sparge_home as _sh
        proj_dir = _sh.get_projects_dir() / 'kie-mark-proctor'
        cfg_path = proj_dir / 'config.json'
        if not cfg_path.exists():
            pytest.skip('Cannot locate project config')
        cfg = json.loads(cfg_path.read_text())
        serve_root = Path(cfg['serve_root'])
        posts_dir  = serve_root / cfg['source']['posts_dir']
        original_path = posts_dir / (test_slug + '.html')
        if not original_path.exists():
            pytest.skip('Original HTML file not accessible in test')
        original_mtime = original_path.stat().st_mtime

        current = SESSION.get(f'{API}/posts/{test_slug}/html').text
        SESSION.post(
            f'{API}/posts/{test_slug}/save-html',
            data=(current + '<!-- mtime-test -->').encode(),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )

        assert original_path.stat().st_mtime == original_mtime, \
            'Original HTML file was modified — it should never be touched'

    def test_restore_original_after_test(self, server, test_slug):
        """Cleanup: remove test markers from enriched copy."""
        current = SESSION.get(f'{API}/posts/{test_slug}/html').text
        clean = current.replace(MARKER_HTML, '').replace('<!-- mtime-test -->', '')
        SESSION.post(
            f'{API}/posts/{test_slug}/save-html',
            data=clean.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        retrieved = SESSION.get(f'{API}/posts/{test_slug}/html').text
        assert MARKER_HTML not in retrieved


class TestMdEditCycle:
    """Complete MD edit → save → retrieve cycle."""

    def test_save_and_retrieve_md(self, server, test_slug):
        posts = SESSION.get(f'{API}/posts').json()
        post = next((p for p in posts if p['slug'] == test_slug), None)
        if not post or not post.get('md', {}).get('generated_at'):
            pytest.skip('Test post has no MD generated')

        cfg_r = SESSION.get(f'{API}/config').json()
        md_dir = cfg_r.get('output', {}).get('md_dir', 'mark-proctor')
        r = requests.get(f'{SERVER}/{md_dir}/{test_slug}.md')
        if r.status_code != 200:
            pytest.skip('Cannot fetch MD file')
        original_md = r.text
        assert MARKER_MD not in original_md

        modified = original_md + MARKER_MD
        r = SESSION.post(
            f'{API}/posts/{test_slug}/save-md',
            data=modified.encode('utf-8'),
            headers={'Content-Type': 'text/plain'},
        )
        assert r.status_code == 200

        retrieved = requests.get(f'{SERVER}/{md_dir}/{test_slug}.md?v=1').text
        assert MARKER_MD in retrieved

        SESSION.post(
            f'{API}/posts/{test_slug}/save-md',
            data=original_md.encode('utf-8'),
            headers={'Content-Type': 'text/plain'},
        )

    def test_save_md_returns_post_state(self, server, test_slug):
        posts = SESSION.get(f'{API}/posts').json()
        post = next((p for p in posts if p['slug'] == test_slug), None)
        if not post or not post.get('md', {}).get('generated_at'):
            pytest.skip('Test post has no MD generated')

        cfg_r = SESSION.get(f'{API}/config').json()
        md_dir = cfg_r.get('output', {}).get('md_dir', 'mark-proctor')
        r = requests.get(f'{SERVER}/{md_dir}/{test_slug}.md')
        if r.status_code != 200:
            pytest.skip('Cannot fetch MD file')

        result = SESSION.post(
            f'{API}/posts/{test_slug}/save-md',
            data=r.text.encode('utf-8'),
            headers={'Content-Type': 'text/plain'},
        )
        data = result.json()
        assert 'slug' in data
        assert data['slug'] == test_slug


class TestUnsavedStateTracking:
    """Verify save/retrieve consistency."""

    def test_enriched_copy_reflects_save(self, server, test_slug):
        original = SESSION.get(f'{API}/posts/{test_slug}/html').text
        unique = f'<!-- unique-{id(original)} -->'
        SESSION.post(
            f'{API}/posts/{test_slug}/save-html',
            data=(original + unique).encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        assert unique in SESSION.get(f'{API}/posts/{test_slug}/html').text

        SESSION.post(
            f'{API}/posts/{test_slug}/save-html',
            data=original.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )


# ── Playwright: full edit → save → visible in viewer cycle ───────────────────

APP_URL = SERVER + '/ui/index.html'

# Use the empty-body Twitter post — its article is blank so edits are unambiguous
EDIT_SLUG   = '2008-10-15-drools-boot-camp-in-texas-is-now-being-twittered'
EDIT_MARKER = 'sparge-edit-flow-playwright-marker'
EDIT_HTML   = (
    f'<p>At the request of others I\'ve setup a twitter account. {EDIT_MARKER}</p>'
    f'<p><a href="http://twitter.com/markproctor">http://twitter.com/markproctor</a></p>'
)


@pytest.fixture(scope='module')
def edit_page(server):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip('playwright not installed')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page(viewport={'width': 1400, 'height': 900})
        pg.goto(APP_URL, wait_until='networkidle')
        pg.wait_for_selector('.pi', timeout=15000)
        pg.locator(f'[data-slug="{EDIT_SLUG}"]').click()
        pg.wait_for_function(
            f"() => document.getElementById('orig-frame')?.src?.includes('{EDIT_SLUG}')",
            timeout=8000)
        pg.wait_for_timeout(600)
        yield pg
        browser.close()


class TestEditSaveImmediatelyVisible:
    """After clicking Save in the HTML editor, the rendered iframe must update
    immediately — without the user having to click the post again or refresh.

    Bug: saveEditContent() calls exitEditModeImmediate() which makes the iframe
    visible again, but never updates iframe.src.  The iframe re-shows the same
    URL it had before edit mode was entered — the browser serves the cached
    response, so the edit is invisible until a hard refresh.

    Fix: after a successful HTML save, set iframe.src to the /view endpoint
    with a fresh cache-bust timestamp so the browser re-fetches the enriched copy.
    """

    def test_ui_save_updates_iframe_without_reclick(self, edit_page, server):
        """Save via the editor Save button — iframe must update with no re-click."""
        pg = edit_page
        ui_marker = 'sparge-ui-iframe-refresh-test'

        # Navigate to the Twitter post
        pg.locator(f'[data-slug="{EDIT_SLUG}"]').scroll_into_view_if_needed()
        pg.locator(f'[data-slug="{EDIT_SLUG}"]').click()
        pg.wait_for_function(
            f"() => document.getElementById('orig-frame')?.src?.includes('{EDIT_SLUG}')",
            timeout=8000)
        pg.wait_for_timeout(800)

        # Enter HTML edit mode
        pg.locator('#btn-edit-html').click()
        pg.wait_for_selector('#html-editor', state='visible', timeout=5000)
        pg.wait_for_timeout(500)

        # Inject test content via the CodeMirror API (faster than keyboard input)
        current = pg.evaluate("() => htmlEditor ? htmlEditor.getValue() : ''")
        insert_before = '</body>' if '</body>' in current else '</html>'
        new_content = current.replace(
            insert_before,
            f'<p>{ui_marker}</p>\n{insert_before}',
            1,
        )
        pg.evaluate("(c) => htmlEditor && htmlEditor.setValue(c)", new_content)
        pg.wait_for_timeout(200)

        # Capture the iframe src BEFORE saving (so we can detect whether it changes)
        src_before = pg.evaluate("() => document.getElementById('orig-frame').src")

        # Click Save — on success, exitEditModeImmediate() hides the editor
        pg.locator('#btn-edit-save').click()
        pg.wait_for_selector('#html-editor', state='hidden', timeout=10000)
        pg.wait_for_timeout(600)

        # The iframe src MUST change after a successful HTML save.
        # Without an updated src (new cache-bust timestamp), real browsers serve
        # the cached version of the old URL and the edit appears invisible.
        # Headless Playwright may re-fetch regardless, so checking the src change
        # is the reliable proxy for the real-browser behaviour.
        src_after = pg.evaluate("() => document.getElementById('orig-frame').src")

        assert src_after != src_before, (
            f'iframe.src was not updated after saving HTML. '
            f'saveEditContent() calls exitEditModeImmediate() which makes the iframe '
            f'visible again but never changes its src — real browsers serve the cached '
            f'response so the edit remains invisible until a hard refresh. '
            f'Fix: after exitEditModeImmediate() in saveEditContent(), set '
            f'$("orig-frame").src = `/api/posts/${{currentSlug}}/view?v=${{Date.now()}}`. '
            f'src before: {src_before!r}'
        )

        # Cleanup
        clean = new_content.replace(f'<p>{ui_marker}</p>\n', '')
        SESSION.post(
            f'{API}/posts/{EDIT_SLUG}/save-html',
            data=clean.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )


class TestEditSaveVisibleInViewer:
    """Saving edited HTML must be visible in the rendered iframe.

    Bug: after save, the iframe reloads with the static file URL
    (/{posts_dir}/{slug}.html) which points to the ORIGINAL file on disk.
    The enriched copy (containing the edit) lives at a different path and
    is never served at that URL — so the viewer never shows the saved change.

    Fix: serve a /api/posts/{slug}/view endpoint that prefers the enriched copy,
    and point the iframe src there instead of the static original path.
    """

    def test_edit_saved_html_visible_in_iframe(self, edit_page, server):
        """After saving HTML via the API, the rendered iframe must show the change."""
        pg = edit_page

        # Save the edit via API (same call the UI save button makes).
        # Insert before </body> — works whether the enriched copy has <article>
        # or not (user edits may strip the article wrapper).
        original_html = SESSION.get(f'{API}/posts/{EDIT_SLUG}/html').text
        insert_before = '</body>' if '</body>' in original_html else '</html>'
        new_html = original_html.replace(insert_before, f'{EDIT_HTML}\n{insert_before}', 1)
        assert EDIT_MARKER in new_html, 'Could not inject test marker into HTML'
        r = SESSION.post(
            f'{API}/posts/{EDIT_SLUG}/save-html',
            data=new_html.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        assert r.status_code == 200, f'Save failed: {r.status_code}'

        # Navigate to the post — simulates what happens after the UI save button
        # calls reloadPost(), which re-selects the post and reloads the iframe
        pg.locator(f'[data-slug="{EDIT_SLUG}"]').scroll_into_view_if_needed()
        pg.locator(f'[data-slug="{EDIT_SLUG}"]').click()
        pg.wait_for_function(
            f"() => document.getElementById('orig-frame')?.src?.includes('{EDIT_SLUG}')",
            timeout=8000)
        pg.wait_for_timeout(1000)  # let iframe load

        # The iframe must render the saved content
        iframe_text = pg.evaluate("""() => {
            try {
                return document.getElementById('orig-frame').contentDocument.body.innerText;
            } catch(e) { return ''; }
        }""")

        assert EDIT_MARKER in iframe_text, (
            f'Saved HTML edit not visible in the rendered iframe. '
            f'The iframe src points to the original file on disk '
            f'(/{{}}/posts_dir/{{}}/slug.html) which is never modified — '
            f'edits go to the enriched copy at a different path. '
            f'Fix: add GET /api/posts/{{slug}}/view endpoint that prefers the '
            f'enriched copy, and use that URL for the iframe src. '
            f'iframe body: {iframe_text[:300]!r}'
        )

    def test_cleanup_edit(self, edit_page, server):
        """Remove the test edit so it does not affect other tests."""
        current = SESSION.get(f'{API}/posts/{EDIT_SLUG}/html').text
        clean = current.replace(f'{EDIT_HTML}\n', '').replace(EDIT_HTML, '').replace(EDIT_MARKER, '')
        SESSION.post(
            f'{API}/posts/{EDIT_SLUG}/save-html',
            data=clean.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        assert EDIT_MARKER not in SESSION.get(f'{API}/posts/{EDIT_SLUG}/html').text


# ── Editor switch tests ───────────────────────────────────────────────────────
# Use a post that has MD already generated so both editors can be opened.

SWITCH_SLUG = '2006-05-31-what-is-a-rule-engine'


@pytest.fixture(scope='module')
def switch_page(edit_page, server):
    """Browser page for editor switch tests.

    Reuses the existing Playwright browser from edit_page to avoid creating a
    second sync_playwright() context in the same session (asyncio conflict).
    """
    ctx = edit_page.context.browser.new_context(viewport={'width': 1400, 'height': 900})
    pg = ctx.new_page()
    pg.goto(APP_URL, wait_until='networkidle')
    pg.wait_for_selector('.pi', timeout=15000)
    yield pg
    ctx.close()


def _current_edit_mode(pg):
    """Return the current editState from the page JS ('html', 'md', or None)."""
    return pg.evaluate("() => typeof editState !== 'undefined' ? editState : null")


def _sidebar_mode_text(pg):
    """Return the edit sidebar mode label text."""
    return pg.evaluate(
        "() => document.getElementById('edit-sidebar-mode')?.textContent || ''"
    )


def _first_visible_cm_mode(pg):
    """Return the CodeMirror mode name of the first VISIBLE editor in #html-editor.

    This is what the user actually sees — checks only editors not hidden by
    display:none (the fix hides the inactive editor with display:none).
    Returns 'htmlmixed', 'markdown', or 'none'.
    """
    return pg.evaluate("""() => {
        const editors = [...document.querySelectorAll('#html-editor .CodeMirror')]
            .filter(el => getComputedStyle(el).display !== 'none');
        if (!editors.length) return 'none';
        const cm = editors[0].CodeMirror;
        return cm ? cm.getMode().name : 'none';
    }""")


class TestEditorSwitch:
    """Opening one editor then clicking the other must switch — not stay on the first.

    Bug: toggleEditMode() only checks if editState === 'md' to exit, otherwise
    calls enterEditMode('md') directly without exiting the current HTML mode.
    enterEditMode() appends a second CodeMirror to the same #html-editor container;
    the original (HTML) editor stays on top and the user sees no change.

    Fix: in toggleEditMode() and toggleHtmlEditMode(), if already in the *other*
    mode, call exitEditModeImmediate() first before entering the new mode.
    """

    def _navigate_to_switch_slug(self, pg):
        """Navigate to SWITCH_SLUG with a full reload to reset JS editor state."""
        pg.goto(APP_URL, wait_until='networkidle')
        pg.wait_for_selector('.pi', timeout=15000)
        pg.locator(f'[data-slug="{SWITCH_SLUG}"]').scroll_into_view_if_needed()
        pg.locator(f'[data-slug="{SWITCH_SLUG}"]').click()
        pg.wait_for_function(
            f"() => document.getElementById('orig-frame')?.src?.includes('{SWITCH_SLUG}')",
            timeout=8000)
        pg.wait_for_timeout(600)

    def test_html_first_then_md_switches(self, switch_page, server):
        """Open HTML editor, then click MD editor — must switch to MD."""
        pg = switch_page
        self._navigate_to_switch_slug(pg)  # fresh JS state for each test

        # Open HTML editor
        pg.locator('#btn-edit-html').click()
        pg.wait_for_selector('#html-editor', state='visible', timeout=5000)
        pg.wait_for_timeout(300)
        assert _current_edit_mode(pg) == 'html', 'Expected HTML edit mode after clicking Edit HTML'

        # Now click MD editor — should switch to MD, not stay on HTML
        pg.locator('#btn-edit-md').click()
        pg.wait_for_timeout(600)

        mode = _current_edit_mode(pg)
        visible_cm = _first_visible_cm_mode(pg)
        sidebar = _sidebar_mode_text(pg)

        # Clean up before asserting
        if mode:
            pg.locator('#btn-edit-md').click()
            pg.wait_for_timeout(300)

        assert visible_cm == 'markdown', (
            f'After clicking MD editor while HTML editor was open, the visible '
            f'CodeMirror is still in HTML mode ({visible_cm!r}). '
            f'editState={mode!r}, sidebar={sidebar!r}. '
            f'Bug: toggleEditMode() calls enterEditMode("md") without first exiting '
            f'HTML mode — a second CodeMirror is appended to #html-editor, the HTML '
            f'one stays on top and the user sees no change. '
            f'Fix: in toggleEditMode(), if editState === "html", call '
            f'exitEditModeImmediate() before enterEditMode("md").'
        )

    def test_md_first_then_html_switches(self, switch_page, server):
        """Open MD editor, then click HTML editor — must switch to HTML."""
        pg = switch_page
        self._navigate_to_switch_slug(pg)  # fresh JS state so MD editor is created first

        # Open MD editor
        pg.locator('#btn-edit-md').click()
        pg.wait_for_selector('#html-editor', state='visible', timeout=5000)
        pg.wait_for_timeout(300)
        assert _current_edit_mode(pg) == 'md', 'Expected MD edit mode after clicking Edit MD'

        # Now click HTML editor — should switch to HTML, not stay on MD
        pg.locator('#btn-edit-html').click()
        pg.wait_for_timeout(600)

        mode = _current_edit_mode(pg)
        visible_cm = _first_visible_cm_mode(pg)
        sidebar = _sidebar_mode_text(pg)

        # Clean up
        if mode:
            pg.locator('#btn-edit-html').click()
            pg.wait_for_timeout(300)

        assert visible_cm == 'htmlmixed', (
            f'After clicking HTML editor while MD editor was open, the visible '
            f'CodeMirror is still in markdown mode ({visible_cm!r}). '
            f'editState={mode!r}, sidebar={sidebar!r}. '
            f'Bug: toggleHtmlEditMode() calls enterEditMode("html") without first '
            f'exiting MD mode — a second CodeMirror is appended to #html-editor, the '
            f'MD one stays on top and the user sees no change. '
            f'Fix: in toggleHtmlEditMode(), if editState === "md", call '
            f'exitEditModeImmediate() before enterEditMode("html").'
        )
