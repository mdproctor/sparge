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
