"""
Pipeline invariant tests — four guarantees that must hold across all operations:

1. Original HTML is immutable — save-html, scan, and generate-md never touch it.
2. Edits write to the enriched copy — save-html writes to ENRICHED_DIR, not POSTS_DIR.
3. Scan respects the enriched copy — scan works on the current enriched HTML (including
   user edits) and does NOT re-enrich from the original (which would overwrite edits).
4. MD generator works from the enriched copy — generate-md reflects the current state
   of the enriched HTML (including user edits), not the raw original.

Root-cause history:
  - _api_scan_html() called _enrich_post() unconditionally before scanning, overwriting
    any manual edits to the enriched copy with a fresh copy from the original.
  - Fix: only enrich when enriched_path does not yet exist.

Requires server running on localhost:9000.
Tests are automatically skipped if server is not reachable.
"""
import json
import time
from pathlib import Path
import sys

import pytest
import requests

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

SERVER  = 'http://localhost:9000'
API     = SERVER + '/api'
SESSION = requests.Session()
SESSION.headers['Content-Type'] = 'application/json'

MARKER = '<!-- pipeline-invariant-test -->'

# Use a stable, well-known post that always has HTML
TEST_SLUG = '2006-05-31-what-is-a-rule-engine'


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_project_paths():
    """Return (original_path, enriched_path) for TEST_SLUG, or skip if unavailable."""
    try:
        import sparge_home as sh
        proj_dir = sh.get_projects_dir() / 'kie-mark-proctor'
    except Exception:
        pytest.skip('Cannot locate project directory via sparge_home')

    cfg_path = proj_dir / 'config.json'
    if not cfg_path.exists():
        pytest.skip('config.json not found')

    cfg = json.loads(cfg_path.read_text())
    serve_root  = Path(cfg['serve_root'])
    posts_dir   = serve_root / cfg['source']['posts_dir']
    enriched_dir = proj_dir / 'enriched'

    original_path = posts_dir / (TEST_SLUG + '.html')
    enriched_path = enriched_dir / (TEST_SLUG + '.html')

    if not original_path.exists():
        pytest.skip(f'Original HTML not found: {original_path}')

    return original_path, enriched_path


def _save_marker(enriched_current: str) -> str:
    """Append MARKER to enriched HTML and POST it. Returns the marked content."""
    marked = enriched_current + f'\n{MARKER}'
    r = SESSION.post(
        f'{API}/posts/{TEST_SLUG}/save-html',
        data=marked.encode('utf-8'),
        headers={'Content-Type': 'text/html; charset=utf-8'},
    )
    assert r.status_code == 200, f'save-html failed: {r.status_code}'
    return marked


def _restore(original_content: str):
    """Remove MARKER from enriched copy to restore clean state."""
    clean = original_content.replace(f'\n{MARKER}', '').replace(MARKER, '')
    SESSION.post(
        f'{API}/posts/{TEST_SLUG}/save-html',
        data=clean.encode('utf-8'),
        headers={'Content-Type': 'text/html; charset=utf-8'},
    )


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def server():
    """Skip all tests in this module if server is not running."""
    try:
        requests.get(f'{API}/projects', timeout=3).raise_for_status()
    except Exception:
        pytest.skip('Server not running on localhost:9000')


@pytest.fixture(scope='module')
def project_paths(server):
    return _get_project_paths()


# ── 1. Original is immutable ───────────────────────────────────────────────────

class TestOriginalIsImmutable:
    """The original HTML file (in POSTS_DIR) must never be modified by any
    pipeline operation — save-html, scan, or generate-md all work on the
    enriched copy only."""

    def test_save_html_does_not_touch_original(self, server, project_paths):
        original_path, _ = project_paths
        mtime_before = original_path.stat().st_mtime

        current = SESSION.get(f'{API}/posts/{TEST_SLUG}/html').text
        _save_marker(current)
        try:
            mtime_after = original_path.stat().st_mtime
        finally:
            _restore(current)

        assert mtime_after == mtime_before, (
            f'save-html modified the original HTML file at {original_path}. '
            f'Saves must only write to the enriched copy in ENRICHED_DIR. '
            f'mtime before={mtime_before}, after={mtime_after}'
        )

    def test_scan_does_not_touch_original(self, server, project_paths):
        original_path, _ = project_paths
        mtime_before = original_path.stat().st_mtime

        SESSION.post(f'{API}/posts/{TEST_SLUG}/scan')
        mtime_after = original_path.stat().st_mtime

        assert mtime_after == mtime_before, (
            f'scan modified the original HTML file at {original_path}. '
            f'Scan must only read, never write, the original file. '
            f'mtime before={mtime_before}, after={mtime_after}'
        )

    def test_generate_md_does_not_touch_original(self, server, project_paths):
        original_path, _ = project_paths
        mtime_before = original_path.stat().st_mtime

        SESSION.post(f'{API}/posts/{TEST_SLUG}/generate-md')
        mtime_after = original_path.stat().st_mtime

        assert mtime_after == mtime_before, (
            f'generate-md modified the original HTML file at {original_path}. '
            f'generate-md must derive from the enriched copy, never modify the original. '
            f'mtime before={mtime_before}, after={mtime_after}'
        )


# ── 2. Edits write to the enriched copy ───────────────────────────────────────

class TestEditsWriteToEnrichedCopy:
    """save-html must write to ENRICHED_DIR, not to POSTS_DIR.

    After a save, the enriched file must contain the edit and the original
    must not.
    """

    def test_save_writes_to_enriched_not_original(self, server, project_paths):
        original_path, enriched_path = project_paths
        original_content_before = original_path.read_text()
        current_enriched = SESSION.get(f'{API}/posts/{TEST_SLUG}/html').text

        _save_marker(current_enriched)
        try:
            original_content_after = original_path.read_text()
            enriched_content_after = enriched_path.read_text() if enriched_path.exists() else ''
        finally:
            _restore(current_enriched)

        assert MARKER not in original_content_after, (
            f'MARKER appeared in the original HTML file after save-html. '
            f'save-html must write only to the enriched copy in ENRICHED_DIR, '
            f'never to the original in POSTS_DIR.'
        )
        assert MARKER in enriched_content_after, (
            f'MARKER not found in enriched copy after save-html. '
            f'save-html must write to {enriched_path}. '
            f'Enriched file exists: {enriched_path.exists()}'
        )


# ── 3. Scan respects the enriched copy ────────────────────────────────────────

class TestScanRespectsEnrichedCopy:
    """Scan must work on the current enriched HTML — including user edits —
    without re-enriching from the original.

    Bug: _api_scan_html() called _enrich_post() unconditionally, overwriting
    any manual edits to the enriched copy with a fresh copy from the original.

    Fix: only call _enrich_post() when the enriched copy does not yet exist.
    """

    def test_scan_preserves_user_edits_in_enriched_copy(self, server, project_paths):
        """After saving an edit, scanning must not overwrite it."""
        original_path, enriched_path = project_paths
        current_enriched = SESSION.get(f'{API}/posts/{TEST_SLUG}/html').text

        # Save a marker into the enriched copy
        _save_marker(current_enriched)
        try:
            # Scan — this must NOT re-enrich from the original (which lacks the marker)
            SESSION.post(f'{API}/posts/{TEST_SLUG}/scan')

            # The enriched copy must still contain the marker after scanning
            enriched_after_scan = enriched_path.read_text() if enriched_path.exists() else ''
        finally:
            _restore(current_enriched)

        assert MARKER in enriched_after_scan, (
            f'Scan overwrote user edits in the enriched copy. '
            f'MARKER was saved to the enriched HTML, then scan was called — '
            f'but the marker is gone afterwards. '
            f'Root cause: _api_scan_html() called _enrich_post() unconditionally, '
            f'regenerating the enriched copy from the original (which lacks the marker). '
            f'Fix: only call _enrich_post() when enriched_path does not yet exist.'
        )

    def test_scan_does_not_re_enrich_existing_enriched_copy(self, server, project_paths):
        """Scan must not update the enriched file's mtime when it already exists."""
        _, enriched_path = project_paths
        if not enriched_path.exists():
            pytest.skip('No enriched copy exists yet for this post')

        mtime_before = enriched_path.stat().st_mtime
        time.sleep(0.05)  # ensure mtime would differ if file was written

        SESSION.post(f'{API}/posts/{TEST_SLUG}/scan')

        mtime_after = enriched_path.stat().st_mtime

        assert mtime_after == mtime_before, (
            f'Scan re-wrote the enriched copy even though it already existed. '
            f'This overwrites user edits. '
            f'Fix: guard _enrich_post() with `if not enriched_path.exists()` in '
            f'_api_scan_html(). '
            f'mtime before={mtime_before}, after={mtime_after}'
        )


# ── 4. MD generator works from the enriched copy ──────────────────────────────

class TestMdGeneratorUsesEnrichedCopy:
    """generate-md must derive Markdown from the current enriched HTML,
    not from the original.

    If the user edits the enriched HTML (to fix a table, add a code block, etc.),
    generate-md must reflect those edits in the resulting MD.
    """

    def test_generate_md_reflects_edit_in_enriched_copy(self, server, project_paths):
        """Edit enriched HTML → generate MD → MD must contain the edit."""
        _, enriched_path = project_paths
        cfg_r = SESSION.get(f'{API}/config').json()
        md_dir = cfg_r.get('output', {}).get('md_dir', 'mark-proctor')

        current_enriched = SESSION.get(f'{API}/posts/{TEST_SLUG}/html').text

        # Insert a distinctive paragraph into the enriched copy
        unique_text = 'pipeline-invariant-unique-content-xyzzy'
        marked = current_enriched.replace(
            '</article>', f'<p>{unique_text}</p>\n</article>', 1
        )
        SESSION.post(
            f'{API}/posts/{TEST_SLUG}/save-html',
            data=marked.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )

        try:
            # Generate MD from the (now-edited) enriched copy
            r = SESSION.post(f'{API}/posts/{TEST_SLUG}/generate-md')
            assert r.status_code == 200, f'generate-md failed: {r.status_code}'

            # The generated MD must contain our unique text
            md_content = requests.get(f'{SERVER}/{md_dir}/{TEST_SLUG}.md?v={time.time()}').text
        finally:
            # Restore the enriched copy and regenerate clean MD
            _restore(current_enriched)
            SESSION.post(f'{API}/posts/{TEST_SLUG}/save-html',
                         data=current_enriched.encode('utf-8'),
                         headers={'Content-Type': 'text/html; charset=utf-8'})
            SESSION.post(f'{API}/posts/{TEST_SLUG}/generate-md')

        assert unique_text in md_content, (
            f'generate-md did not include content from the enriched HTML edit. '
            f'The unique marker "{unique_text}" was saved to the enriched copy '
            f'but does not appear in the generated MD. '
            f'generate-md must derive from the enriched copy (which reflects user '
            f'edits), not from the raw original HTML.'
        )

    def test_generate_md_does_not_use_original_when_enriched_exists(self, server, project_paths):
        """generate-md output must differ from what the original alone would produce
        when the enriched copy contains additional content not in the original."""
        original_path, enriched_path = project_paths
        if not enriched_path.exists():
            pytest.skip('No enriched copy exists — cannot compare')

        cfg_r = SESSION.get(f'{API}/config').json()
        md_dir = cfg_r.get('output', {}).get('md_dir', 'mark-proctor')

        # The enriched copy contains processed content (local image paths, YouTube
        # embeds, etc.) that the original does not. If generate-md were reading
        # from the original, the MD would reference external URLs instead.
        enriched_content = enriched_path.read_text()

        # Generate MD and check it reflects enriched-only content
        SESSION.post(f'{API}/posts/{TEST_SLUG}/generate-md')
        md_content = requests.get(f'{SERVER}/{md_dir}/{TEST_SLUG}.md?v={time.time()}').text

        # The enriched copy uses /legacy/assets/ paths; the original uses blogspot URLs.
        # If generate-md is correctly using the enriched copy, the MD must not contain
        # raw blogspot image URLs that were replaced during enrichment.
        has_local_assets = '/legacy/assets/' in enriched_content
        if has_local_assets:
            assert '/legacy/assets/' in md_content, (
                f'generate-md produced MD with no /legacy/assets/ paths even though '
                f'the enriched copy contains them. This suggests generate-md is '
                f'reading from the original HTML (which has blogspot URLs) rather '
                f'than the enriched copy (which has localised asset paths).'
            )
