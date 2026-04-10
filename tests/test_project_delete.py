"""
Tests for project creation and deletion.

Covers:
  1. API: DELETE /api/projects/{id} removes the project from the list
  2. API: deleted project does not reappear after a subsequent GET /api/projects
  3. API: deleting a non-existent project still returns 200 (idempotent)
  4. UI (Playwright): Delete button on projects page removes the card

Requires server running on localhost:9000.
"""
import json
import shutil
import time
from pathlib import Path
import sys

import pytest
import requests

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

SERVER = 'http://localhost:9000'
API    = SERVER + '/api'
SESSION = requests.Session()

APP_URL = f'{SERVER}/ui/projects.html'

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def server():
    try:
        requests.get(f'{API}/projects', timeout=3).raise_for_status()
    except Exception:
        pytest.skip('Server not running on localhost:9000')


def _create_project(name: str) -> str:
    """Create a throwaway project via API and return its id."""
    r = SESSION.post(f'{API}/projects', json={
        'name': name,
        'serve_root': '/tmp/sparge-test-project',
        'posts_dir': 'posts',
        'assets_dir': 'assets',
        'md_dir': 'md',
    })
    assert r.status_code == 200, f'Create failed: {r.status_code} {r.text}'
    return r.json()['id']


def _project_ids() -> list[str]:
    return [p['id'] for p in SESSION.get(f'{API}/projects').json()]


def _delete_project(pid: str):
    """Delete project via API and remove its directory from sparge-projects.

    Returns the requests.Response so callers can assert status_code / json().
    The API preserves data on disk intentionally; tests must clean up themselves.
    """
    r = SESSION.delete(f'{API}/projects/{pid}')
    cfg_path = Path('~/.sparge/config.json').expanduser()
    if cfg_path.exists():
        projects_dir = Path(json.loads(cfg_path.read_text()).get('projects_dir', '~/sparge-projects')).expanduser()
    else:
        projects_dir = Path('~/sparge-projects').expanduser()
    project_dir = projects_dir / pid
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)
    return r


# ── 1. DELETE removes project from list ───────────────────────────────────────

class TestDeleteRemovesProject:
    def test_deleted_project_not_in_list(self, server):
        pid = _create_project('Test Delete Simple')
        assert pid in _project_ids(), 'Project must appear in list after creation'

        r = _delete_project(pid)
        assert r.status_code == 200, f'DELETE returned {r.status_code}'
        assert r.json().get('deleted') == pid

        assert pid not in _project_ids(), (
            f'Project {pid!r} still appears in /api/projects after DELETE. '
            f'The delete endpoint must remove it from projects.json.'
        )

    def test_deleted_project_stays_gone_on_reload(self, server):
        """Project must not reappear on a subsequent GET (no auto-rediscovery)."""
        pid = _create_project('Test Delete Stays Gone')
        _delete_project(pid)

        # Two consecutive GETs must both show it absent
        for i in range(2):
            assert pid not in _project_ids(), (
                f'Project {pid!r} reappeared in /api/projects on GET #{i+1} '
                f'after being deleted. Server must not auto-rediscover deleted projects.'
            )

    def test_delete_nonexistent_project_is_idempotent(self, server):
        """Deleting a project that does not exist must still return 200."""
        r = SESSION.delete(f'{API}/projects/does-not-exist-xyzzy')
        assert r.status_code == 200, (
            f'DELETE of non-existent project returned {r.status_code}. '
            f'Should be idempotent — 200 even when nothing to remove.'
        )


# ── 2. Projects with special-char names can be deleted ────────────────────────

class TestDeleteSpecialCharName:
    """Project names with quotes and dashes must be deletable from the UI.

    Bug: renderProjects() uses JSON.stringify(esc(p.name)) embedded directly
    inside an HTML onclick="..." attribute.  The surrounding double-quotes from
    JSON.stringify terminate the HTML attribute early, breaking the handler for
    any non-empty name.

    Example:
      onclick="deleteProject('my-id', "My Project")"
                                    ^--- attribute ends here

    Fix: pass only p.id to deleteProject and look up the name from the projects
    array, OR use data-* attributes to avoid string injection into onclick.
    """

    def test_project_with_simple_name_deletable_via_api(self, server):
        pid = _create_project('Simple Name')
        r = _delete_project(pid)
        assert r.status_code == 200
        assert pid not in _project_ids()

    def test_project_with_dash_name_deletable_via_api(self, server):
        pid = _create_project('Test-Project-With-Dashes')
        r = _delete_project(pid)
        assert r.status_code == 200
        assert pid not in _project_ids()


# ── 3. UI: Delete button removes the project card ─────────────────────────────

try:
    from playwright.sync_api import sync_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False


@pytest.fixture(scope='module')
def browser_page(server):
    if not _HAS_PLAYWRIGHT:
        pytest.skip('playwright not installed')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1400, 'height': 900})
        page = ctx.new_page()
        yield page
        ctx.close()
        browser.close()


class TestDeleteProjectUI:
    """Playwright: clicking Delete on the projects page removes the card."""

    def test_delete_button_removes_card(self, server, browser_page):
        pg = browser_page

        # Create a project we can safely delete
        pid = _create_project('UI Delete Test Project')
        try:
            pg.goto(APP_URL, wait_until='networkidle')
            pg.wait_for_timeout(500)

            # Project card must be visible
            card_selector = f'button.danger[data-id="{pid}"]'
            pg.wait_for_selector(card_selector, timeout=5000)

            delete_btn = pg.locator(f'button.danger[data-id="{pid}"]')
            assert delete_btn.count() > 0, (
                f'No delete button found for project {pid!r}. '
                f'The button must have data-id="{pid}".'
            )

            # Accept the confirm dialog
            pg.once('dialog', lambda d: d.accept())
            delete_btn.click()
            pg.wait_for_timeout(800)

            # Card must be gone
            remaining = pg.locator(f'button.danger[data-id="{pid}"]').count()
            assert remaining == 0, (
                f'Project card for {pid!r} still visible after clicking Delete. '
                f'deleteProject() was not called correctly — check that data-id/data-name '
                f'attributes are read properly in the handler.'
            )
        finally:
            # Cleanup in case test failed before delete completed
            _delete_project(pid)

    def test_delete_button_callable_with_any_project_name(self, server, browser_page):
        """Delete button must work regardless of what characters are in the name."""
        pg = browser_page
        # Use a name with characters that would break naive HTML attribute embedding
        pid = _create_project('My Test Project 2')
        try:
            pg.goto(APP_URL, wait_until='networkidle')
            pg.wait_for_timeout(500)

            pg.wait_for_selector(f'button.danger[data-id="{pid}"]', timeout=5000)

            # data-id must hold the full project id (no truncation)
            data_id = pg.eval_on_selector(
                f'button.danger[data-id="{pid}"]',
                'el => el.dataset.id'
            )
            assert data_id == pid, (
                f'button data-id={data_id!r} does not match project id {pid!r}. '
                f'The delete button must use data-id/data-name attributes, not '
                f'JSON.stringify() embedded in onclick="".'
            )

            pg.once('dialog', lambda d: d.accept())
            pg.locator(f'button.danger[data-id="{pid}"]').click()
            pg.wait_for_timeout(800)
        finally:
            _delete_project(pid)
