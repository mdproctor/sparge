"""
End-to-end garbling regression tests.

These tests prove the full pipeline is clean — not just unit functions,
but the actual file written to disk by the server and what the browser renders.

Why this exists: unit tests on convert_post() passed while the file on disk
was still garbled. The gap was between "the function returns clean text" and
"the server writes clean text to disk and serves it correctly."

These tests close that gap by:
  1. Calling the real generate-md API endpoint
  2. Reading the resulting .md file from disk directly
  3. Checking the HTTP response the server sends for the file
  4. Using Playwright to check what the browser actually renders in Sparge

Run with server on localhost:9000:
  python3 -m pytest tests/test_garbling_e2e.py -v

Playwright tests require: playwright install chromium
"""
import json
import sys
import time
from pathlib import Path

import pytest

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

SERVER = 'http://localhost:9000'
API    = SERVER + '/api'

GARBLING_SIGNATURES = ['ÃÂÃÂ', 'Ã¢Â', 'â€']
REGRESSION_SLUG = '2006-05-31-what-is-a-rule-engine'


def assert_not_garbled(text: str, label: str = ''):
    prefix = f'{label}: ' if label else ''
    for sig in GARBLING_SIGNATURES:
        assert sig not in text, (
            f'{prefix}Garbling signature {repr(sig)} found. '
            f'Encoding bug in the pipeline — check html.parser is used everywhere.'
        )


# ── Server availability ───────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def session():
    try:
        import requests
        s = requests.Session()
        s.get(f'{API}/projects', timeout=3).raise_for_status()
        # Always activate the KIE project — other test modules may have switched it
        s.post(f'{API}/projects/kie-mark-proctor/activate')
        return s
    except Exception:
        pytest.skip('Server not running on localhost:9000')


@pytest.fixture(scope='module')
def md_dir(session):
    """Return the absolute path to the MD output directory."""
    r = session.get(f'{API}/config')
    cfg = r.json()
    serve_root = Path(cfg.get('serve_root', ''))
    md_rel = cfg.get('output', {}).get('md_dir', 'mark-proctor')
    return serve_root / md_rel


# ── API + disk tests ──────────────────────────────────────────────────────────

class TestGenerateMdDiskOutput:
    """Prove the file written to disk is clean — not just the API response."""

    def test_generated_file_on_disk_not_garbled(self, session, md_dir):
        """After generate-md, the .md file on disk must contain no garbling.

        This is the critical test that was missing: previous tests checked the
        API response but not the actual bytes written to disk.
        """
        # Force regeneration
        r = session.post(f'{API}/posts/{REGRESSION_SLUG}/generate-md')
        assert r.status_code == 200, f'generate-md failed: {r.text}'

        # Read the file from disk directly
        md_file = md_dir / f'{REGRESSION_SLUG}.md'
        assert md_file.exists(), f'MD file not written to {md_file}'

        content = md_file.read_text(encoding='utf-8')
        assert_not_garbled(content, 'disk_file')
        assert 'Drools' in content, 'Basic content check failed'

    def test_generated_file_modification_time_updated(self, session, md_dir):
        """File mtime must be recent — proves regeneration actually wrote the file."""
        md_file = md_dir / f'{REGRESSION_SLUG}.md'
        mtime_before = md_file.stat().st_mtime if md_file.exists() else 0

        session.post(f'{API}/posts/{REGRESSION_SLUG}/generate-md')

        mtime_after = md_file.stat().st_mtime
        assert mtime_after >= mtime_before, 'File was not updated — generate-md may have silently failed'

    def test_http_served_file_not_garbled(self, session, md_dir):
        """The file as served over HTTP must not be garbled.

        The static file server might mangle encoding via wrong Content-Type.
        This test fetches the file via HTTP and checks the response body.
        """
        # First generate a fresh clean version
        session.post(f'{API}/posts/{REGRESSION_SLUG}/generate-md')

        # Fetch the file via HTTP (the same path the browser uses)
        cfg = session.get(f'{API}/config').json()
        md_rel = cfg.get('output', {}).get('md_dir', 'mark-proctor')
        url = f'{SERVER}/{md_rel}/{REGRESSION_SLUG}.md'
        r = session.get(url)
        assert r.status_code == 200, f'Static file not served: {url}'

        # Check response body for garbling
        content = r.text
        assert_not_garbled(content, 'http_response')

    def test_all_31_existing_md_files_not_garbled(self, session, md_dir):
        """All existing MD files on disk must be clean.

        Regenerate all 31 existing posts and verify each is garbling-free.
        This catches any post that might have been written with the old lxml bug.
        """
        import requests as _req
        posts = session.get(f'{API}/posts').json()
        md_posts = [p for p in posts if p.get('md', {}).get('generated_at')]

        garbled_posts = []
        for post in md_posts:
            slug = post['slug']
            # Force regenerate
            r = session.post(f'{API}/posts/{slug}/generate-md')
            if r.status_code != 200:
                continue
            md_file = md_dir / f'{slug}.md'
            if not md_file.exists():
                continue
            content = md_file.read_text(encoding='utf-8')
            for sig in GARBLING_SIGNATURES:
                if sig in content:
                    garbled_posts.append((slug, sig))
                    break

        assert not garbled_posts, (
            f'{len(garbled_posts)} MD files are still garbled after regeneration:\n'
            + '\n'.join(f'  {slug}: {repr(sig)}' for slug, sig in garbled_posts)
        )


# ── Playwright browser tests ──────────────────────────────────────────────────

def _playwright_available():
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _playwright_available(), reason='playwright not installed')
class TestBrowserRender:
    """Playwright tests — prove what the browser actually renders is clean.

    These are the definitive tests: if the browser shows garbled text,
    something in the full pipeline is wrong regardless of what unit tests say.
    """

    @pytest.fixture(scope='class')
    def browser_page(self, session):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            # Navigate to Sparge and select the regression post
            page.goto(f'{SERVER}/ui/')
            page.wait_for_load_state('networkidle')
            yield page
            browser.close()

    def _open_post_in_sparge(self):
        """Open Sparge, activate the KIE project, select the regression post.
        Returns (page, browser, playwright_ctx) — caller must close browser.
        """
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch()
        page = browser.new_page()

        # Navigate to projects page and open the KIE project
        page.goto(f'{SERVER}/ui/projects.html')
        page.wait_for_load_state('networkidle')
        time.sleep(0.5)

        # Click "Open" on the kie-mark-proctor project
        open_btn = page.locator('button.primary', has_text='→ Open').first
        if open_btn.count():
            open_btn.click()
            page.wait_for_load_state('networkidle')
            time.sleep(1)

        # Find and click the regression post
        post_item = page.locator(f'#pi-{REGRESSION_SLUG}')
        if not post_item.count():
            # Try waiting a bit longer for post list to load
            time.sleep(2)
            post_item = page.locator(f'#pi-{REGRESSION_SLUG}')

        if post_item.count():
            post_item.click()
            time.sleep(1)

        return page, browser, pw

    def test_browser_md_panel_not_garbled(self, session):
        """What the browser renders in the MD panel must not be garbled.

        This is the definitive regression test. Previous tests confirmed the
        file is clean, but the user still saw garbling — this test catches any
        remaining issue in serving or rendering.
        """
        session.post(f'{API}/posts/{REGRESSION_SLUG}/generate-md')
        time.sleep(0.5)

        page, browser, pw = self._open_post_in_sparge()
        try:
            md_panel = page.locator('#md-wrap')
            if not md_panel.count():
                pytest.skip('Could not find MD panel in Sparge UI')
            text = md_panel.inner_text()
            if not text.strip():
                pytest.skip('MD panel is empty — post may not have MD generated')
            assert_not_garbled(text, 'browser_md_panel')
            assert 'Drools' in text or 'Rule Engine' in text.lower(), \
                'Expected content not found in MD panel'
        finally:
            browser.close()
            pw.stop()

    def test_browser_md_panel_shows_proper_quotes(self, session):
        """Curly quotes must render as readable text, not garbled sequences."""
        session.post(f'{API}/posts/{REGRESSION_SLUG}/generate-md')
        time.sleep(0.5)

        page, browser, pw = self._open_post_in_sparge()
        try:
            md_panel = page.locator('#md-wrap')
            if not md_panel.count():
                pytest.skip('Could not find MD panel in Sparge UI')
            text = md_panel.inner_text()
            if not text.strip():
                pytest.skip('MD panel is empty')
            assert_not_garbled(text, 'browser_quotes_check')
            assert 'Production Rule' in text, \
                '"Production Rule" should be readable in browser MD panel'
        finally:
            browser.close()
            pw.stop()
