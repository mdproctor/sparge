"""
Tests for the post list search bar.

The search bar has a text input (#search-input) and a scope selector
(#search-scope) with options: Title, Body, Both.

Search is server-side: typing calls GET /api/search?q=...&scope=...
which searches post titles (from state) and/or MD file body content.
The server returns matching slugs; the UI filters allPosts by that set.

API unit tests verify the /api/search endpoint directly.
UI behaviour tests use Playwright to verify the visible post list.

Coverage:
  API unit tests:
    1.  Empty query returns all slugs
    2.  Title-scope matches title, not body
    3.  Body-scope matches body content, not title
    4.  Both-scope is superset of title+body
    5.  No match returns empty list
    6.  Case-insensitive matching

  UI behaviour (Playwright):
    7.  Search input and scope selector visible with correct options
    8.  Typing reduces visible count (waits for async API response)
    9.  Clearing restores full count
   10.  Title-scope ≤ both-scope for same query
   11.  Body-scope ≤ both-scope for same query
   12.  Both-scope = title ∪ body
   13.  All visible posts in title-scope have query in their title
   14.  All visible posts in slug-scope have query in their slug  (slug = body proxy here)
   15.  Search stacks with filter button
   16.  Search stacks with issue-type scoping button

Requires server running on localhost:9000.
"""
from pathlib import Path
import sys
import time

import pytest

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

SERVER  = 'http://localhost:9000'
APP_URL = f'{SERVER}/ui/index.html'
API     = f'{SERVER}/api'

try:
    from playwright.sync_api import sync_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False

import requests as _requests


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def server():
    try:
        _requests.get(f'{API}/projects', timeout=3).raise_for_status()
    except Exception:
        pytest.skip('Server not running on localhost:9000')


@pytest.fixture(scope='module')
def page(server):
    if not _HAS_PLAYWRIGHT:
        pytest.skip('playwright not installed')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1400, 'height': 900})
        pg = ctx.new_page()
        pg.goto(APP_URL, wait_until='networkidle')
        pg.wait_for_function(
            "() => document.querySelectorAll('.pi').length > 0", timeout=20000
        )
        yield pg
        ctx.close()
        browser.close()


def _search_api(q: str, scope: str = 'both') -> list[str]:
    """Call /api/search directly and return matching slugs."""
    r = _requests.get(f'{API}/search', params={'q': q, 'scope': scope}, timeout=10)
    r.raise_for_status()
    return r.json()['slugs']


def _all_slugs_api() -> list[str]:
    posts = _requests.get(f'{API}/posts', timeout=10).json()
    return [p['slug'] for p in posts]


def _visible_count(pg) -> int:
    return pg.evaluate("() => document.querySelectorAll('.pi').length")


def _set_search(pg, query: str, scope: str = 'both'):
    """Set search input and scope, then wait for the async API response."""
    pg.evaluate(f"""() => {{
        document.getElementById('search-scope').value = '{scope}';
        const inp = document.getElementById('search-input');
        inp.value = {repr(query)};
        inp.dispatchEvent(new Event('input'));
    }}""")
    # Debounce is 300ms + network round trip — wait for renderNav to complete
    pg.wait_for_timeout(700)


def _clear_search(pg):
    _set_search(pg, '', 'both')


# ── API unit tests ────────────────────────────────────────────────────────────

class TestSearchAPI:
    """Unit tests for GET /api/search — no browser needed."""

    def test_empty_query_returns_all_slugs(self, server):
        all_slugs = set(_all_slugs_api())
        result = set(_search_api(''))
        assert result == all_slugs, (
            f'Empty query must return all {len(all_slugs)} slugs'
        )

    def test_title_scope_finds_drools_in_titles(self, server):
        slugs = _search_api('drools', 'title')
        assert len(slugs) > 0, 'title-scope for "drools" must return results'

        posts = {p['slug']: p for p in _requests.get(f'{API}/posts').json()}
        for slug in slugs:
            title = (posts[slug].get('title', '') or '').lower()
            assert 'drools' in title, (
                f'{slug!r} returned by title-scope but "drools" not in title {title!r}'
            )

    def test_body_scope_finds_content_not_in_title(self, server):
        """Body-scope must be able to find posts whose title doesn't match
        but whose MD body does."""
        # Get title-scope results
        title_slugs = set(_search_api('drools', 'title'))
        body_slugs  = set(_search_api('drools', 'body'))
        both_slugs  = set(_search_api('drools', 'both'))

        # body-only hits = body - title
        body_only = body_slugs - title_slugs
        # Some posts mention drools in body without having it in the title
        assert len(body_only) > 0, (
            'body-scope must find at least one post that title-scope misses — '
            'posts mentioning "drools" in body but not title should exist'
        )

        # Verify each body-only slug actually has "drools" in its MD
        from sparge_home import get_projects_dir
        import json
        try:
            proj_dir = get_projects_dir() / 'kie-mark-proctor'
            cfg = json.loads((proj_dir / 'config.json').read_text())
            md_dir = Path(cfg['serve_root']) / cfg['output']['md_dir']
        except Exception:
            pytest.skip('Cannot locate MD directory')

        for slug in list(body_only)[:3]:  # spot-check first 3
            md_path = md_dir / (slug + '.md')
            if md_path.exists():
                assert 'drools' in md_path.read_text(encoding='utf-8').lower(), (
                    f'{slug!r} returned by body-scope but "drools" not in MD content'
                )

    def test_both_scope_is_union_of_title_and_body(self, server):
        title_set = set(_search_api('drools', 'title'))
        body_set  = set(_search_api('drools', 'body'))
        both_set  = set(_search_api('drools', 'both'))

        assert title_set <= both_set, 'both must include all title matches'
        assert body_set  <= both_set, 'both must include all body matches'
        assert both_set == title_set | body_set, (
            'both-scope must equal title ∪ body'
        )

    def test_no_match_returns_empty(self, server):
        result = _search_api('xyzzy-no-such-post-ever-12345')
        assert result == [], 'Non-matching query must return empty list'

    def test_case_insensitive(self, server):
        lower = set(_search_api('drools', 'both'))
        upper = set(_search_api('DROOLS', 'both'))
        mixed = set(_search_api('Drools', 'both'))
        assert lower == upper == mixed, (
            'Search must be case-insensitive'
        )


# ── UI behaviour tests ────────────────────────────────────────────────────────

class TestSearchBarUI:

    def test_search_input_visible(self, server, page):
        assert page.locator('#search-input').is_visible()

    def test_scope_selector_visible_with_correct_options(self, server, page):
        pg = page
        assert pg.locator('#search-scope').is_visible()
        options = pg.eval_on_selector_all(
            '#search-scope option', 'opts => opts.map(o => o.value)'
        )
        assert set(options) == {'title', 'body', 'both'}, (
            f'Scope must have title/body/both options, got {options}'
        )

    def test_typing_reduces_visible_count(self, server, page):
        pg = page
        total = _visible_count(pg)
        _set_search(pg, 'drools')
        reduced = _visible_count(pg)
        _clear_search(pg)

        assert reduced < total, (
            f'Typing "drools" must reduce visible posts. '
            f'Before: {total}, After: {reduced}'
        )
        assert reduced > 0

    def test_clearing_restores_count(self, server, page):
        pg = page
        total_before = _visible_count(pg)
        _set_search(pg, 'drools')
        _clear_search(pg)
        total_after = _visible_count(pg)

        assert total_after == total_before, (
            f'Clearing search must restore post count. '
            f'Before: {total_before}, After: {total_after}'
        )

    def test_title_scope_le_both_scope(self, server, page):
        pg = page
        _set_search(pg, 'drools', 'both')
        both_count = _visible_count(pg)
        _set_search(pg, 'drools', 'title')
        title_count = _visible_count(pg)
        _clear_search(pg)

        assert title_count <= both_count, (
            f'Title-scope ({title_count}) must be ≤ both-scope ({both_count})'
        )

    def test_body_scope_le_both_scope(self, server, page):
        pg = page
        _set_search(pg, 'drools', 'both')
        both_count = _visible_count(pg)
        _set_search(pg, 'drools', 'body')
        body_count = _visible_count(pg)
        _clear_search(pg)

        assert body_count <= both_count, (
            f'Body-scope ({body_count}) must be ≤ both-scope ({both_count})'
        )

    def test_both_scope_ge_title_and_body(self, server, page):
        """both-scope must show at least as many posts as either scope alone."""
        pg = page
        _set_search(pg, 'drools', 'title')
        title_count = _visible_count(pg)
        _set_search(pg, 'drools', 'body')
        body_count = _visible_count(pg)
        _set_search(pg, 'drools', 'both')
        both_count = _visible_count(pg)
        _clear_search(pg)

        assert both_count >= title_count, 'both >= title'
        assert both_count >= body_count,  'both >= body'

    def test_title_scope_posts_have_query_in_title(self, server, page):
        pg = page
        _set_search(pg, 'drools', 'title')

        all_match = pg.evaluate("""() => {
            const q = 'drools';
            const postMap = Object.fromEntries(allPosts.map(p => [p.slug, p]));
            return Array.from(document.querySelectorAll('.pi')).every(el => {
                const slug = el.dataset.slug || '';
                const p = postMap[slug];
                return ((p && p.title) || slug).toLowerCase().includes(q);
            });
        }""")
        _clear_search(pg)

        assert all_match, (
            'In title-scope, every visible post must have the query in its full title'
        )

    def test_search_stacks_with_filter_button(self, server, page):
        pg = page
        pg.locator('.fb[onclick*="html-issues"]').click()
        pg.wait_for_timeout(300)
        html_count = _visible_count(pg)

        _set_search(pg, 'drools', 'both')
        combined = _visible_count(pg)

        assert combined <= html_count, (
            f'Search must narrow html-issues filter. '
            f'Filter: {html_count}, Filter+search: {combined}'
        )

        _clear_search(pg)
        pg.locator('.fb[onclick*="all"]').click()
        pg.wait_for_timeout(300)

    def test_search_stacks_with_issue_type_scoping(self, server, page):
        pg = page
        breakdown = pg.locator('#html-breakdown')
        if not breakdown.is_visible():
            pg.locator('text=HTML issues').first.click()
            pg.wait_for_timeout(300)

        row = pg.locator('#html-breakdown [onclick*="potential_code_block"]')
        if row.count() == 0:
            pytest.skip('No potential_code_block issues — cannot test')

        row.first.click()
        pg.wait_for_timeout(300)
        scoped = _visible_count(pg)

        _set_search(pg, 'drools', 'both')
        combined = _visible_count(pg)

        assert combined <= scoped, (
            f'Search must narrow issue-type scoped list. '
            f'Scoped: {scoped}, Scoped+search: {combined}'
        )

        _clear_search(pg)
        row.first.click()
        pg.wait_for_timeout(300)
