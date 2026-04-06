"""
Comprehensive integration tests for the edit mode flow.

Tests the complete lifecycle:
  - Edit HTML → cancel (verify unchanged)
  - Edit HTML → save (verify saved)
  - Edit MD → cancel (verify unchanged)
  - Edit MD → save (verify saved)
  - Multiple edits in sequence
  - Author-filtered edit flows
  - Edit with the mock blog's 20 posts

Requires server running on localhost:9000 AND a project set up with mock blog posts.
Tests skip automatically if server not reachable.
"""
import json
import time
import uuid
import sys
from pathlib import Path

import pytest
import requests

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

SERVER  = 'http://localhost:9000'
API     = SERVER + '/api'
SESSION = requests.Session()
SESSION.headers['Content-Type'] = 'application/json'

# Test markers — unique enough to not appear in real content
HTML_MARKER  = '<!-- EDIT-TEST-{uid} -->'
MD_MARKER    = '\n\n> EDIT-TEST-{uid}\n\n'


@pytest.fixture(scope='module')
def server():
    try:
        requests.get(f'{API}/projects', timeout=3).raise_for_status()
    except Exception:
        pytest.skip('Server not running on localhost:9000')


@pytest.fixture(scope='module')
def ingested_project(server, mock_blog_server, tmp_path_factory):
    """
    Create a fresh project, ingest all 20 mock blog posts, and return the
    project id and list of slugs. Cleaned up after the module.
    """
    tmp = tmp_path_factory.mktemp('edit-test')
    proj_name = f'edit-test-{uuid.uuid4().hex[:6]}'
    r = SESSION.post(f'{API}/projects', json={
        'name': proj_name,
        'serve_root': str(tmp),
        'posts_dir': 'posts',
        'assets_dir': 'assets',
        'md_dir': 'md',
    })
    assert r.status_code == 200, f'Project create failed: {r.text}'
    proj_id = r.json()['id']

    # Activate the project
    SESSION.post(f'{API}/projects/{proj_id}/activate')

    # Discover posts from mock blog
    disc = SESSION.post(f'{API}/ingest/discover', json={'url': mock_blog_server})
    if disc.status_code == 503:
        SESSION.delete(f'{API}/projects/{proj_id}')
        pytest.skip('Ingest not available')
    assert disc.status_code == 200
    urls = disc.json()['urls']
    assert len(urls) == 20, f'Expected 20 URLs, got {len(urls)}'

    # Ingest all 20 posts
    r = SESSION.post(f'{API}/ingest/run', json={'urls': urls})
    assert r.status_code == 200

    # Wait for ingest to complete (max 30s)
    for _ in range(60):
        status = SESSION.get(f'{API}/ingest/status').json()
        if not status['running']:
            break
        time.sleep(0.5)
    else:
        pytest.fail('Ingest timed out after 30s')

    # Verify all 20 posts ingested
    posts = SESSION.get(f'{API}/posts').json()
    assert len(posts) == 20, f'Expected 20 posts after ingest, got {len(posts)}'

    yield {'project_id': proj_id, 'posts': posts, 'tmp': tmp}

    # Cleanup
    SESSION.delete(f'{API}/projects/{proj_id}')
    import shutil as _shutil
    _shutil.rmtree(str(tmp), ignore_errors=True)


def _slug(posts, n=0):
    """Return the nth post slug."""
    return posts[n]['slug']


class TestHtmlEditCancel:
    """Edit HTML → cancel → content unchanged."""

    def test_cancel_leaves_html_unchanged(self, server, ingested_project):
        """Fetching HTML, then NOT saving is equivalent to cancel."""
        posts = ingested_project['posts']
        slug = _slug(posts, 0)

        # Step 1: GET original HTML
        r = SESSION.get(f'{API}/posts/{slug}/html')
        assert r.status_code == 200
        original = r.text
        assert len(original) > 100

        # Step 2: Simulate "user opens editor but cancels" — do NOT POST save-html
        # (cancel = no API call)

        # Step 3: GET HTML again — must be identical to original
        r2 = SESSION.get(f'{API}/posts/{slug}/html')
        assert r2.status_code == 200
        assert r2.text == original, 'Cancel should leave content unchanged'

    def test_cancel_after_multiple_fetches_unchanged(self, server, ingested_project):
        """Multiple fetches without save still return the same content."""
        slug = _slug(ingested_project['posts'], 1)
        original = SESSION.get(f'{API}/posts/{slug}/html').text
        # Simulate user opening editor, scrolling around, then cancelling (multiple GETs)
        for _ in range(3):
            fetched = SESSION.get(f'{API}/posts/{slug}/html').text
            assert fetched == original


class TestHtmlEditSave:
    """Edit HTML → save → content changed."""

    def test_save_persists_html_change(self, server, ingested_project):
        """Saving modified HTML is retrievable on subsequent fetch."""
        slug = _slug(ingested_project['posts'], 2)
        uid  = uuid.uuid4().hex[:8]
        marker = HTML_MARKER.format(uid=uid)

        original = SESSION.get(f'{API}/posts/{slug}/html').text
        assert marker not in original

        # Save modified content
        modified = original + marker
        r = SESSION.post(f'{API}/posts/{slug}/save-html',
                         data=modified.encode('utf-8'),
                         headers={'Content-Type': 'text/html; charset=utf-8'})
        assert r.status_code == 200

        # Verify change persisted
        retrieved = SESSION.get(f'{API}/posts/{slug}/html').text
        assert marker in retrieved, 'Saved content should be retrievable'
        assert retrieved == modified

        # Restore original
        SESSION.post(f'{API}/posts/{slug}/save-html',
                     data=original.encode('utf-8'),
                     headers={'Content-Type': 'text/html; charset=utf-8'})

    def test_save_then_cancel_keeps_saved_version(self, server, ingested_project):
        """After saving, a subsequent 'cancel' (no POST) keeps the saved version."""
        slug = _slug(ingested_project['posts'], 3)
        uid  = uuid.uuid4().hex[:8]
        marker = HTML_MARKER.format(uid=uid)

        original = SESSION.get(f'{API}/posts/{slug}/html').text

        # First edit: save with marker
        SESSION.post(f'{API}/posts/{slug}/save-html',
                     data=(original + marker).encode('utf-8'),
                     headers={'Content-Type': 'text/html; charset=utf-8'})

        # Second edit: cancel (no POST)
        after_cancel = SESSION.get(f'{API}/posts/{slug}/html').text
        assert marker in after_cancel, 'Saved content should persist after cancel'

        # Restore
        SESSION.post(f'{API}/posts/{slug}/save-html',
                     data=original.encode('utf-8'),
                     headers={'Content-Type': 'text/html; charset=utf-8'})

    def test_sequential_edits_each_overwrite_previous(self, server, ingested_project):
        """Each save overwrites the previous — last write wins."""
        slug = _slug(ingested_project['posts'], 4)
        original = SESSION.get(f'{API}/posts/{slug}/html').text

        for i in range(3):
            uid    = uuid.uuid4().hex[:8]
            marker = HTML_MARKER.format(uid=uid)
            SESSION.post(f'{API}/posts/{slug}/save-html',
                         data=(original + marker).encode('utf-8'),
                         headers={'Content-Type': 'text/html; charset=utf-8'})
            retrieved = SESSION.get(f'{API}/posts/{slug}/html').text
            assert marker in retrieved, f'Edit {i+1} should be retrievable'

        # Restore
        SESSION.post(f'{API}/posts/{slug}/save-html',
                     data=original.encode('utf-8'),
                     headers={'Content-Type': 'text/html; charset=utf-8'})

    def test_save_returns_post_state_with_correct_slug(self, server, ingested_project):
        """save-html response includes the post state with matching slug."""
        slug = _slug(ingested_project['posts'], 5)
        original = SESSION.get(f'{API}/posts/{slug}/html').text
        r = SESSION.post(f'{API}/posts/{slug}/save-html',
                         data=original.encode('utf-8'),
                         headers={'Content-Type': 'text/html; charset=utf-8'})
        assert r.status_code == 200
        state = r.json()
        assert state['slug'] == slug

    def test_original_html_never_modified(self, server, ingested_project):
        """The original ingested HTML file on disk must never change."""
        import sparge_home as _sh
        slug     = _slug(ingested_project['posts'], 6)
        proj_dir = _sh.get_projects_dir() / ingested_project['project_id']
        cfg      = json.loads((proj_dir / 'config.json').read_text())
        serve    = Path(cfg['serve_root'])
        orig_path = serve / cfg['source']['posts_dir'] / (slug + '.html')
        if not orig_path.exists():
            pytest.skip('Original file not accessible')

        mtime_before = orig_path.stat().st_mtime

        original = SESSION.get(f'{API}/posts/{slug}/html').text
        SESSION.post(f'{API}/posts/{slug}/save-html',
                     data=(original + '<!-- mtime-test -->').encode('utf-8'),
                     headers={'Content-Type': 'text/html; charset=utf-8'})

        assert orig_path.stat().st_mtime == mtime_before, \
            'Original HTML file must never be written to'

        # Restore
        SESSION.post(f'{API}/posts/{slug}/save-html',
                     data=original.encode('utf-8'),
                     headers={'Content-Type': 'text/html; charset=utf-8'})


class TestMdEditCancel:
    """Generate MD, then edit → cancel → MD unchanged."""

    @pytest.fixture(scope='class')
    def post_with_md(self, server, ingested_project):
        """Generate MD for one post and return its slug."""
        slug = _slug(ingested_project['posts'], 7)
        r = SESSION.post(f'{API}/posts/{slug}/generate-md')
        if r.status_code not in (200, 201):
            pytest.skip(f'Could not generate MD: {r.status_code} {r.text[:200]}')
        return slug

    def test_cancel_leaves_md_unchanged(self, server, ingested_project, post_with_md):
        slug = post_with_md
        cfg  = SESSION.get(f'{API}/config').json()
        md_dir = cfg.get('output', {}).get('md_dir', 'md')

        original = requests.get(f'{SERVER}/{md_dir}/{slug}.md').text

        # Simulate cancel — no POST to save-md
        retrieved = requests.get(f'{SERVER}/{md_dir}/{slug}.md?v=1').text
        assert retrieved == original

    def test_cancel_after_md_edit_unchanged(self, server, ingested_project, post_with_md):
        """Reading MD multiple times without saving returns same content."""
        slug   = post_with_md
        cfg    = SESSION.get(f'{API}/config').json()
        md_dir = cfg.get('output', {}).get('md_dir', 'md')
        original = requests.get(f'{SERVER}/{md_dir}/{slug}.md').text
        for _ in range(3):
            assert requests.get(f'{SERVER}/{md_dir}/{slug}.md').text == original


class TestMdEditSave:
    """Generate MD, then edit → save → MD changed."""

    @pytest.fixture(scope='class')
    def post_with_md(self, server, ingested_project):
        slug = _slug(ingested_project['posts'], 8)
        r = SESSION.post(f'{API}/posts/{slug}/generate-md')
        if r.status_code not in (200, 201):
            pytest.skip(f'Could not generate MD: {r.status_code} {r.text[:200]}')
        return slug

    def test_save_persists_md_change(self, server, ingested_project, post_with_md):
        slug   = post_with_md
        uid    = uuid.uuid4().hex[:8]
        marker = MD_MARKER.format(uid=uid)
        cfg    = SESSION.get(f'{API}/config').json()
        md_dir = cfg.get('output', {}).get('md_dir', 'md')

        original = requests.get(f'{SERVER}/{md_dir}/{slug}.md').text
        assert marker not in original

        r = SESSION.post(f'{API}/posts/{slug}/save-md',
                         data=(original + marker).encode('utf-8'),
                         headers={'Content-Type': 'text/plain; charset=utf-8'})
        assert r.status_code == 200

        retrieved = requests.get(f'{SERVER}/{md_dir}/{slug}.md?v=2').text
        assert marker in retrieved

        # Restore
        SESSION.post(f'{API}/posts/{slug}/save-md',
                     data=original.encode('utf-8'),
                     headers={'Content-Type': 'text/plain; charset=utf-8'})

    def test_save_md_response_includes_slug(self, server, ingested_project, post_with_md):
        slug = post_with_md
        cfg  = SESSION.get(f'{API}/config').json()
        md_dir = cfg.get('output', {}).get('md_dir', 'md')
        original = requests.get(f'{SERVER}/{md_dir}/{slug}.md').text
        r = SESSION.post(f'{API}/posts/{slug}/save-md',
                         data=original.encode('utf-8'),
                         headers={'Content-Type': 'text/plain; charset=utf-8'})
        assert r.json()['slug'] == slug

    def test_sequential_md_edits(self, server, ingested_project, post_with_md):
        """Multiple sequential MD edits — each save overwrites."""
        slug = post_with_md
        cfg  = SESSION.get(f'{API}/config').json()
        md_dir = cfg.get('output', {}).get('md_dir', 'md')
        original = requests.get(f'{SERVER}/{md_dir}/{slug}.md').text

        markers = []
        for i in range(3):
            uid    = uuid.uuid4().hex[:8]
            marker = MD_MARKER.format(uid=uid)
            markers.append(marker)
            SESSION.post(f'{API}/posts/{slug}/save-md',
                         data=(original + marker).encode('utf-8'),
                         headers={'Content-Type': 'text/plain; charset=utf-8'})
            retrieved = requests.get(f'{SERVER}/{md_dir}/{slug}.md?v={i}').text
            # Only latest marker should be present
            assert marker in retrieved
            for prev in markers[:-1]:
                assert prev not in retrieved

        # Restore
        SESSION.post(f'{API}/posts/{slug}/save-md',
                     data=original.encode('utf-8'),
                     headers={'Content-Type': 'text/plain; charset=utf-8'})


class TestAuthorFilteredEditFlow:
    """Edit flow works correctly with author-filtered views."""

    def test_edit_alice_post_does_not_affect_bob_post(self, server, ingested_project):
        """Saving one author's post does not change another author's post."""
        posts = ingested_project['posts']
        alice_posts = [p for p in posts if p.get('author') == 'Alice Smith']
        bob_posts   = [p for p in posts if p.get('author') == 'Bob Jones']
        if not alice_posts or not bob_posts:
            pytest.skip('Need posts from both Alice and Bob')

        alice_slug = alice_posts[0]['slug']
        bob_slug   = bob_posts[0]['slug']

        alice_orig = SESSION.get(f'{API}/posts/{alice_slug}/html').text
        bob_orig   = SESSION.get(f'{API}/posts/{bob_slug}/html').text

        uid    = uuid.uuid4().hex[:8]
        marker = HTML_MARKER.format(uid=uid)

        # Edit Alice's post
        SESSION.post(f'{API}/posts/{alice_slug}/save-html',
                     data=(alice_orig + marker).encode('utf-8'),
                     headers={'Content-Type': 'text/html; charset=utf-8'})

        # Bob's post must be unchanged
        bob_after = SESSION.get(f'{API}/posts/{bob_slug}/html').text
        assert bob_after == bob_orig, "Alice's edit should not affect Bob's post"
        assert marker not in bob_after

        # Restore Alice
        SESSION.post(f'{API}/posts/{alice_slug}/save-html',
                     data=alice_orig.encode('utf-8'),
                     headers={'Content-Type': 'text/html; charset=utf-8'})

    def test_all_20_posts_have_fetchable_html(self, server, ingested_project):
        """Every ingested post must return valid HTML from GET /html."""
        for post in ingested_project['posts']:
            r = SESSION.get(f'{API}/posts/{post["slug"]}/html')
            assert r.status_code == 200, f'POST {post["slug"]} returned {r.status_code}'
            assert '<' in r.text, f'POST {post["slug"]} returned non-HTML'

    def test_edit_each_author_independently(self, server, ingested_project):
        """Edit one post per author, verify each saved independently."""
        posts   = ingested_project['posts']
        authors = ['Alice Smith', 'Bob Jones', 'Carol White']
        by_author = {a: next((p for p in posts if p.get('author') == a), None)
                     for a in authors}

        originals = {}
        markers   = {}
        for author, post in by_author.items():
            if post is None:
                continue
            slug = post['slug']
            originals[slug] = SESSION.get(f'{API}/posts/{slug}/html').text
            uid  = uuid.uuid4().hex[:8]
            markers[slug]   = HTML_MARKER.format(uid=uid)

        # Save all three
        for author, post in by_author.items():
            if post is None:
                continue
            slug = post['slug']
            SESSION.post(f'{API}/posts/{slug}/save-html',
                         data=(originals[slug] + markers[slug]).encode('utf-8'),
                         headers={'Content-Type': 'text/html; charset=utf-8'})

        # Verify each independently
        for author, post in by_author.items():
            if post is None:
                continue
            slug = post['slug']
            retrieved = SESSION.get(f'{API}/posts/{slug}/html').text
            assert markers[slug] in retrieved, f'{author} post should have its own marker'
            for other_slug, other_marker in markers.items():
                if other_slug != slug:
                    assert other_marker not in retrieved, \
                        f'{author} post should not contain {other_slug} marker'

        # Restore all
        for author, post in by_author.items():
            if post is None:
                continue
            slug = post['slug']
            SESSION.post(f'{API}/posts/{slug}/save-html',
                         data=originals[slug].encode('utf-8'),
                         headers={'Content-Type': 'text/html; charset=utf-8'})
