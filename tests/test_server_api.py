"""
Server API tests — test /api/projects and /api/ingest/* endpoints
against the running Sparge server.

These tests require the server to be running on localhost:9000.
Run: python3 server.py &
Then: python3 -m pytest tests/test_server_api.py -v

Tests are automatically skipped if the server is not reachable.
"""
import json
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path

import pytest
import requests

MIGRATOR_ROOT = Path(__file__).parent.parent

SERVER = 'http://localhost:9000'
API = SERVER + '/api'


# ── Availability fixture ───────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def server():
    """Skip all tests in this module if server is not running."""
    try:
        r = requests.get(f'{API}/projects', timeout=3)
        r.raise_for_status()
    except Exception:
        pytest.skip('Sparge server not running on localhost:9000')
    return SESSION_HTTP


SESSION_HTTP = requests.Session()
SESSION_HTTP.headers['Content-Type'] = 'application/json'


# ── /api/projects ─────────────────────────────────────────────────────────────

class TestProjectsList:
    """GET /api/projects returns a well-formed list."""

    def test_returns_list(self, server):
        r = SESSION_HTTP.get(f'{API}/projects')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_each_project_has_required_fields(self, server):
        data = SESSION_HTTP.get(f'{API}/projects').json()
        assert len(data) >= 1, 'Expected at least one project (KIE blog)'
        for p in data:
            assert 'id' in p
            assert 'name' in p
            assert 'stats' in p
            stats = p['stats']
            for field in ('total', 'reviewed', 'staged', 'md_generated', 'html_issues'):
                assert field in stats, f'stats missing {field}'

    def test_stats_are_non_negative_ints(self, server):
        data = SESSION_HTTP.get(f'{API}/projects').json()
        for p in data:
            for v in p['stats'].values():
                assert isinstance(v, int) and v >= 0

    def test_active_field_present(self, server):
        data = SESSION_HTTP.get(f'{API}/projects').json()
        assert any(p.get('active') for p in data), 'Expected one active project'


class TestProjectCreate:
    """POST /api/projects creates a project and adds it to the index."""

    def test_creates_project_with_local_paths(self, server, tmp_path):
        name = f'Test Project {uuid.uuid4().hex[:6]}'
        payload = {
            'name':         name,
            'serve_root':   str(tmp_path),
            'posts_dir':    'posts',
            'assets_dir':   'assets',
            'md_dir':       'md',
            'author_filter': '',
        }
        r = SESSION_HTTP.post(f'{API}/projects', json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert 'id' in data
        assert data['name'] == name

        # Appears in list
        projects = SESSION_HTTP.get(f'{API}/projects').json()
        ids = [p['id'] for p in projects]
        assert data['id'] in ids

        # Clean up — delete from index AND remove project dir on disk
        SESSION_HTTP.delete(f"{API}/projects/{data['id']}")
        proj_dir = MIGRATOR_ROOT / 'projects' / data['id']
        if proj_dir.exists():
            shutil.rmtree(proj_dir)

    def test_rejects_missing_name(self, server):
        r = SESSION_HTTP.post(f'{API}/projects', json={'serve_root': '/tmp'})
        assert r.status_code == 400

    def test_id_derived_from_name(self, server, tmp_path):
        name = 'My Test Blog 99'
        r = SESSION_HTTP.post(f'{API}/projects',
                               json={'name': name, 'serve_root': str(tmp_path),
                                     'posts_dir': 'p', 'assets_dir': 'a', 'md_dir': 'm'})
        assert r.status_code == 200
        data = r.json()
        assert re.match(r'^[a-z0-9-]+$', data['id']), 'ID should be slug-safe'
        SESSION_HTTP.delete(f"{API}/projects/{data['id']}")
        proj_dir = MIGRATOR_ROOT / 'projects' / data['id']
        if proj_dir.exists():
            shutil.rmtree(proj_dir)


class TestProjectDelete:
    """DELETE /api/projects/{id} removes project from index."""

    def test_deletes_project(self, server, tmp_path):
        name = f'Delete Me {uuid.uuid4().hex[:6]}'
        created = SESSION_HTTP.post(f'{API}/projects',
                                     json={'name': name, 'serve_root': str(tmp_path),
                                           'posts_dir': 'p', 'assets_dir': 'a', 'md_dir': 'm'}).json()
        pid = created['id']

        r = SESSION_HTTP.delete(f'{API}/projects/{pid}')
        assert r.status_code == 200

        ids = [p['id'] for p in SESSION_HTTP.get(f'{API}/projects').json()]
        assert pid not in ids, 'Deleted project still in list'

        # Also remove project dir from disk
        proj_dir = MIGRATOR_ROOT / 'projects' / pid
        if proj_dir.exists():
            shutil.rmtree(proj_dir)

    def test_deleting_nonexistent_is_safe(self, server):
        r = SESSION_HTTP.delete(f'{API}/projects/does-not-exist-xyz')
        assert r.status_code == 200  # idempotent — no error


class TestProjectActivate:
    """POST /api/projects/{id}/activate switches the active project."""

    def test_activate_existing_project(self, server):
        projects = SESSION_HTTP.get(f'{API}/projects').json()
        assert projects, 'Need at least one project'
        pid = projects[0]['id']
        r = SESSION_HTTP.post(f'{API}/projects/{pid}/activate')
        assert r.status_code == 200
        data = r.json()
        assert data['active'] == pid
        assert 'name' in data

    def test_activate_nonexistent_returns_404(self, server):
        r = SESSION_HTTP.post(f'{API}/projects/nonexistent-xyz-abc/activate')
        assert r.status_code == 404

    def test_posts_reflect_active_project(self, server):
        projects = SESSION_HTTP.get(f'{API}/projects').json()
        pid = projects[0]['id']
        SESSION_HTTP.post(f'{API}/projects/{pid}/activate')
        r = SESSION_HTTP.get(f'{API}/posts')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)


# ── /api/ingest/* ─────────────────────────────────────────────────────────────

class TestIngestStatus:
    """GET /api/ingest/status returns job state."""

    def test_returns_status_object(self, server):
        r = SESSION_HTTP.get(f'{API}/ingest/status')
        assert r.status_code == 200
        d = r.json()
        for field in ('running', 'done', 'total', 'current', 'errors', 'cancelled'):
            assert field in d, f'status missing {field}'

    def test_not_running_initially(self, server):
        d = SESSION_HTTP.get(f'{API}/ingest/status').json()
        assert d['running'] is False


class TestIngestDetect:
    """POST /api/ingest/detect detects platform from a URL."""

    def test_detects_wordpress_org(self, server):
        # wordpress.org itself has /wp-json/ → wordpress
        r = SESSION_HTTP.post(f'{API}/ingest/detect',
                               json={'url': 'https://wordpress.org'})
        if r.status_code == 503:
            pytest.skip('ingest not available (requests not installed)')
        # May return 200 or 500 (network), just check shape if 200
        if r.status_code == 200:
            d = r.json()
            assert 'platform' in d
            assert 'base_url' in d

    def test_requires_url_field(self, server):
        r = SESSION_HTTP.post(f'{API}/ingest/detect', json={})
        assert r.status_code in (400, 503)

    def test_detect_with_mock_blog(self, server, mock_blog_server):
        r = SESSION_HTTP.post(f'{API}/ingest/detect',
                               json={'url': mock_blog_server})
        if r.status_code == 503:
            pytest.skip('ingest not available')
        assert r.status_code == 200
        d = r.json()
        assert d['platform'] in ('generic', 'wordpress', 'blogger', 'ghost')
        assert 'localhost' in d['base_url']


class TestIngestDiscover:
    """POST /api/ingest/discover discovers post URLs from a blog."""

    def test_discovers_mock_blog_posts(self, server, mock_blog_server):
        r = SESSION_HTTP.post(f'{API}/ingest/discover',
                               json={'url': mock_blog_server})
        if r.status_code == 503:
            pytest.skip('ingest not available')
        assert r.status_code == 200
        d = r.json()
        assert 'urls' in d
        assert 'count' in d
        assert d['count'] == len(d['urls'])
        assert d['count'] == 20, f'Expected 20 posts, got {d["count"]}'

    def test_requires_url(self, server):
        r = SESSION_HTTP.post(f'{API}/ingest/discover', json={})
        assert r.status_code in (400, 503)


class TestIngestPreview:
    """POST /api/ingest/preview extracts one post without writing."""

    def test_previews_mock_blog_post(self, server, mock_blog_server):
        # First discover to get a URL
        disc = SESSION_HTTP.post(f'{API}/ingest/discover',
                                  json={'url': mock_blog_server})
        if disc.status_code == 503:
            pytest.skip('ingest not available')
        urls = disc.json().get('urls', [])
        if not urls:
            pytest.skip('no URLs discovered')

        r = SESSION_HTTP.post(f'{API}/ingest/preview', json={'url': urls[0]})
        assert r.status_code == 200
        d = r.json()
        assert 'title' in d
        assert 'date' in d
        assert 'author' in d
        assert 'html' in d
        assert d.get('error') is None

    def test_requires_url(self, server):
        r = SESSION_HTTP.post(f'{API}/ingest/preview', json={})
        assert r.status_code in (400, 503)


# ── /api/posts (active project) ───────────────────────────────────────────────

class TestPostsEndpoints:
    """Basic posts endpoints work for the active project."""

    def test_get_posts_returns_list(self, server):
        r = SESSION_HTTP.get(f'{API}/posts')
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_single_post(self, server):
        posts = SESSION_HTTP.get(f'{API}/posts').json()
        if not posts:
            pytest.skip('No posts in active project')
        slug = posts[0]['slug']
        r = SESSION_HTTP.get(f'{API}/posts/{slug}')
        assert r.status_code == 200
        d = r.json()
        assert d['slug'] == slug

    def test_get_nonexistent_post_returns_404(self, server):
        r = SESSION_HTTP.get(f'{API}/posts/this-post-does-not-exist-xyz')
        assert r.status_code == 404


# mock_blog_server fixture is provided by conftest.py


class TestProjectNewestDate:
    """GET /api/projects/{id}/newest-date returns the most recent post date."""

    def test_returns_newest_date_for_project_with_posts(self, server):
        projects = SESSION_HTTP.get(f'{API}/projects').json()
        # Find a project with posts
        with_posts = [p for p in projects if p['stats']['total'] > 0]
        if not with_posts:
            pytest.skip('No projects with posts')
        pid = with_posts[0]['id']
        r = SESSION_HTTP.get(f'{API}/projects/{pid}/newest-date')
        assert r.status_code == 200
        d = r.json()
        assert 'date' in d
        assert 'count' in d
        assert d['count'] > 0
        if d['date']:
            # Date should match YYYY-MM-DD
            import re
            assert re.match(r'^\d{4}-\d{2}-\d{2}$', d['date']), f"Bad date format: {d['date']}"

    def test_returns_null_date_for_empty_project(self, server):
        # Create a temporary empty project
        name = f'Empty Test {uuid.uuid4().hex[:6]}'
        created = SESSION_HTTP.post(f'{API}/projects',
                                     json={'name': name, 'serve_root': '/tmp',
                                           'posts_dir': 'p', 'assets_dir': 'a',
                                           'md_dir': 'm'}).json()
        pid = created['id']
        try:
            r = SESSION_HTTP.get(f'{API}/projects/{pid}/newest-date')
            assert r.status_code == 200
            d = r.json()
            assert d['count'] == 0
            assert d['date'] is None
        finally:
            SESSION_HTTP.delete(f'{API}/projects/{pid}')
            proj_dir = MIGRATOR_ROOT / 'projects' / pid
            if proj_dir.exists():
                shutil.rmtree(proj_dir)


class TestProjectWipe:
    """POST /api/projects/{id}/wipe clears all data for new-schema projects."""

    def _make_new_schema_project(self, tmp_path) -> tuple[str, Path]:
        """Create a temporary new-schema project with some data files."""
        name = f'Wipe Test {uuid.uuid4().hex[:6]}'
        data_root = tmp_path / 'data'
        # Create new-schema config
        pid = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        proj_dir = MIGRATOR_ROOT / 'projects' / pid
        proj_dir.mkdir(parents=True, exist_ok=True)
        config = {
            'project_name': name,
            'serve_root': str(data_root),
            'data': {
                'source_dir':  'source',
                'cleaned_dir': 'cleaned',
                'assets_dir':  'assets',
                'md_dir':      'md',
            },
            'filter': {'author': ''},
            'server': {'port': 9000},
        }
        (proj_dir / 'config.json').write_text(json.dumps(config))
        (proj_dir / 'state.json').write_text('{"post-a": {"slug": "post-a", "date": "2024-01-01"}}')
        # Create some fake data directories and files
        for d in ('source', 'cleaned', 'assets', 'md'):
            (data_root / d).mkdir(parents=True, exist_ok=True)
            (data_root / d / 'dummy.txt').write_text('data')
        # Register in index
        projects = SESSION_HTTP.get(f'{API}/projects').json()
        projects.append({'id': pid, 'name': name, 'created_at': '2026-01-01T00:00:00'})
        import json as _json
        (MIGRATOR_ROOT / 'projects.json').write_text(_json.dumps(projects, indent=2))
        return pid, data_root

    def test_wipe_clears_data_directories(self, server, tmp_path):
        pid, data_root = self._make_new_schema_project(tmp_path)
        try:
            assert (data_root / 'source').exists()
            r = SESSION_HTTP.post(f'{API}/projects/{pid}/wipe')
            assert r.status_code == 200
            d = r.json()
            assert d['wiped'] is True
            # Data directories should be gone
            assert not (data_root / 'source').exists()
            assert not (data_root / 'cleaned').exists()
            assert not (data_root / 'assets').exists()
        finally:
            SESSION_HTTP.delete(f'{API}/projects/{pid}')
            proj_dir = MIGRATOR_ROOT / 'projects' / pid
            if proj_dir.exists():
                shutil.rmtree(proj_dir)

    def test_wipe_resets_state_to_empty(self, server, tmp_path):
        pid, data_root = self._make_new_schema_project(tmp_path)
        try:
            r = SESSION_HTTP.post(f'{API}/projects/{pid}/wipe')
            assert r.status_code == 200
            state_path = MIGRATOR_ROOT / 'projects' / pid / 'state.json'
            state = json.loads(state_path.read_text())
            assert state == {}
        finally:
            SESSION_HTTP.delete(f'{API}/projects/{pid}')
            proj_dir = MIGRATOR_ROOT / 'projects' / pid
            if proj_dir.exists():
                shutil.rmtree(proj_dir)

    def test_wipe_rejects_legacy_schema_projects(self, server, tmp_path):
        name = f'Legacy Test {uuid.uuid4().hex[:6]}'
        created = SESSION_HTTP.post(f'{API}/projects',
                                     json={'name': name, 'serve_root': str(tmp_path),
                                           'posts_dir': 'p', 'assets_dir': 'a',
                                           'md_dir': 'm'}).json()
        pid = created['id']
        try:
            r = SESSION_HTTP.post(f'{API}/projects/{pid}/wipe')
            assert r.status_code == 400  # wipe not supported for legacy schema
        finally:
            SESSION_HTTP.delete(f'{API}/projects/{pid}')
            proj_dir = MIGRATOR_ROOT / 'projects' / pid
            if proj_dir.exists():
                shutil.rmtree(proj_dir)

    def test_wipe_nonexistent_project_returns_404(self, server):
        r = SESSION_HTTP.post(f'{API}/projects/does-not-exist-xyz/wipe')
        assert r.status_code == 404
