"""
Playwright tests for the issue breakdown scoping panel.

Tests the HTML and MD issue breakdown panels in the nav sidebar:
  - Arrow expands/collapses each breakdown
  - Each breakdown shows the correct issue types and per-type post counts
  - Clicking an issue type sub-filters the post list to the correct subset
  - Author filter + issue type filter combine correctly
  - Edge cases: toggle off, switch to different filter, empty subsets

Uses a synthetic test project written directly into state.json — no
ingest or scan needed. This gives full control over which issues each
post has, making assertions exact.

Two authors (Alice Test, Bob Test) with 8 posts:

  HTML issues:
    external_image:   alice-external, bob-multi              (2 posts)
    data_placeholder: alice-data                             (1 post)
    noscript_remnant: alice-noscript                         (1 post)
    tracking_pixel:   bob-tracking, bob-multi                (2 posts)
    empty_embed:      bob-embed                              (1 post)

  MD issues:
    missing_fm_field:      alice-md                          (1 post)
    broken_links:          alice-md                          (1 post)
    html_entities_in_body: bob-md                            (1 post)

Run with server on localhost:9000:
  python3 -m pytest tests/test_issue_breakdown.py -v

Requires: pip install playwright && playwright install chromium
"""
import json
import shutil
import uuid
from pathlib import Path

import pytest

SERVER   = 'http://localhost:9000'
APP_URL  = SERVER + '/ui/index.html'   # root redirects to projects.html; main app is here
API      = SERVER + '/api'

# ── Synthetic state ────────────────────────────────────────────────────────────

ALICE = 'Alice Test'
BOB   = 'Bob Test'

SLUGS = {
    'alice_external':  '2020-01-15-alice-external',
    'alice_data':      '2020-02-20-alice-data',
    'alice_noscript':  '2020-03-10-alice-noscript',
    'alice_md':        '2020-04-05-alice-md-issues',
    'bob_tracking':    '2020-01-20-bob-tracking',
    'bob_embed':       '2020-02-15-bob-embed',
    'bob_multi':       '2020-03-25-bob-multi',
    'bob_md':          '2020-04-10-bob-md-issues',
}


def _html_iss(itype, level, detail):
    return {'type': itype, 'check': itype, 'level': level, 'detail': detail, 'selector': None}


def _md_iss(check, level, detail):
    return {'check': check, 'level': level, 'detail': detail, 'selector': None}


def _post(slug, title, author, html_issues=None, md_issues=None):
    ts = '2026-01-01T00:00:00'
    e = {
        'slug': slug, 'title': title,
        'date': slug[:10], 'author': author,
        'original_url': f'http://example.com/{slug}',
        'ingested_at': ts, 'reviewed': False,
    }
    if html_issues is not None:
        e['html'] = {'hash': uuid.uuid4().hex[:12], 'issues': html_issues, 'checked_at': ts}
    if md_issues is not None:
        e['md'] = {
            'generated_at': ts, 'html_hash': 'aaa000',
            'issues': md_issues, 'staged': False, 'validated_at': ts,
        }
    return slug, e


def make_state():
    return dict([
        _post(SLUGS['alice_external'], 'Alice: External Image', ALICE,
              html_issues=[_html_iss('external_image', 'WARN', 'http://example.com/img.jpg')]),
        _post(SLUGS['alice_data'], 'Alice: Data Placeholder', ALICE,
              html_issues=[_html_iss('data_placeholder', 'ERROR', 'Unrecovered data: placeholder')]),
        _post(SLUGS['alice_noscript'], 'Alice: Noscript Remnant', ALICE,
              html_issues=[_html_iss('noscript_remnant', 'WARN', 'Orphaned noscript: http://x.com/img.jpg')]),
        _post(SLUGS['alice_md'], 'Alice: MD Issues', ALICE,
              md_issues=[_md_iss('missing_fm_field', 'ERROR', 'Required field missing: tags'),
                         _md_iss('broken_links', 'WARN', '2 empty links [text]()')]),
        _post(SLUGS['bob_tracking'], 'Bob: Tracking Pixel', BOB,
              html_issues=[_html_iss('tracking_pixel', 'WARN', 'Tracking pixel from doubleclick.net')]),
        _post(SLUGS['bob_embed'], 'Bob: Empty Embed', BOB,
              html_issues=[_html_iss('empty_embed', 'WARN', 'iframe with no src')]),
        _post(SLUGS['bob_multi'], 'Bob: External + Tracking', BOB,
              html_issues=[_html_iss('external_image', 'WARN', 'http://other.com/img.jpg'),
                           _html_iss('tracking_pixel', 'WARN', 'Tracking pixel from google.com')]),
        _post(SLUGS['bob_md'], 'Bob: HTML Entities', BOB,
              md_issues=[_md_iss('html_entities_in_body', 'WARN', '3 HTML entities in body')]),
    ])


# Expected per-type post sets
HTML_EXPECTED = {
    'external_image':    {SLUGS['alice_external'], SLUGS['bob_multi']},
    'data_placeholder':  {SLUGS['alice_data']},
    'noscript_remnant':  {SLUGS['alice_noscript']},
    'tracking_pixel':    {SLUGS['bob_tracking'], SLUGS['bob_multi']},
    'empty_embed':       {SLUGS['bob_embed']},
}
MD_EXPECTED = {
    'missing_fm_field':      {SLUGS['alice_md']},
    'broken_links':          {SLUGS['alice_md']},
    'html_entities_in_body': {SLUGS['bob_md']},
}

ALL_HTML_SLUGS = {SLUGS['alice_external'], SLUGS['alice_data'], SLUGS['alice_noscript'],
                  SLUGS['bob_tracking'], SLUGS['bob_embed'], SLUGS['bob_multi']}
ALL_MD_SLUGS   = {SLUGS['alice_md'], SLUGS['bob_md']}

ALICE_HTML_SLUGS = {SLUGS['alice_external'], SLUGS['alice_data'], SLUGS['alice_noscript']}
BOB_HTML_SLUGS   = {SLUGS['bob_tracking'], SLUGS['bob_embed'], SLUGS['bob_multi']}


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
    import requests

    tmp = tmp_path_factory.mktemp('breakdown')
    uid = uuid.uuid4().hex[:8]

    r = session.post(f'{API}/projects', json={
        'name': f'breakdown-{uid}',
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

    (proj_dir / 'state.json').write_text(json.dumps(make_state(), indent=2))
    (tmp / 'posts').mkdir(exist_ok=True)
    (tmp / 'md').mkdir(exist_ok=True)

    session.post(f'{API}/projects/{pid}/activate')

    # Verify the API is serving our synthetic posts before opening the browser
    posts = session.get(f'{API}/posts').json()
    assert len(posts) == 8, f'Expected 8 synthetic posts, got {len(posts)}'

    yield {'id': pid, 'dir': proj_dir}

    session.delete(f'{API}/projects/{pid}')
    if proj_dir.exists():
        shutil.rmtree(proj_dir)
    session.post(f'{API}/projects/kie-mark-proctor/activate')


@pytest.fixture(scope='module')
def page(test_project, session):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip('playwright not installed — run: pip install playwright && playwright install chromium')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page(viewport={'width': 1280, 'height': 900})
        pg.goto(APP_URL, wait_until='networkidle')
        pg.wait_for_selector('.pi', timeout=10000)
        yield pg
        browser.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def visible_slugs(page) -> set:
    """Slugs of post items currently rendered in the post list."""
    return {el.get_attribute('data-slug')
            for el in page.locator('.pi[data-slug]').all()}


def visible_titles(page) -> list:
    return page.locator('.pi-title').all_inner_texts()


def reset_to_all(page):
    """Click All filter, clear author, move mouse away from filter zone."""
    page.locator('.filter-always button:has-text("All")').click()
    page.locator('#author-select').select_option(value='')
    page.wait_for_timeout(300)
    page.mouse.move(700, 600)
    page.wait_for_timeout(100)


def open_html_breakdown(page):
    arrow = page.locator('#html-arr')
    if 'open' not in (arrow.get_attribute('class') or ''):
        page.locator('.srow.expandable').filter(has_text='HTML issues').click()
        page.wait_for_timeout(250)


def open_md_breakdown(page):
    arrow = page.locator('#md-arr')
    if 'open' not in (arrow.get_attribute('class') or ''):
        page.locator('.srow.expandable').filter(has_text='MD issues').click()
        page.wait_for_timeout(250)


def close_html_breakdown(page):
    if 'open' in (page.locator('#html-arr').get_attribute('class') or ''):
        page.locator('.srow.expandable').filter(has_text='HTML issues').click()
        page.wait_for_timeout(250)


def close_md_breakdown(page):
    if 'open' in (page.locator('#md-arr').get_attribute('class') or ''):
        page.locator('.srow.expandable').filter(has_text='MD issues').click()
        page.wait_for_timeout(250)


def click_html_type(page, key: str):
    """Click an HTML issue type row by its data-key."""
    row = page.locator(f'#html-breakdown .itr[data-key="{key}"]')
    row.wait_for(state='visible', timeout=3000)
    row.click()
    page.wait_for_timeout(200)


def click_md_check(page, key: str):
    """Click an MD issue check row by its data-key."""
    row = page.locator(f'#md-breakdown .itr[data-key="{key}"]')
    row.wait_for(state='visible', timeout=3000)
    row.click()
    page.wait_for_timeout(200)


def select_author(page, author: str):
    page.locator('#author-select').select_option(label=author)
    page.wait_for_timeout(350)


def clear_author(page):
    page.locator('#author-select').select_option(value='')
    page.wait_for_timeout(350)


def breakdown_keys(page, panel_id: str) -> set:
    """Return the data-key values of all visible .itr rows in a breakdown panel."""
    return {el.get_attribute('data-key')
            for el in page.locator(f'#{panel_id} .itr').all()}


def breakdown_count(page, panel_id: str, key: str) -> int:
    """Return the displayed count for a given data-key in a breakdown panel."""
    count_el = page.locator(f'#{panel_id} .itr[data-key="{key}"] .itr-count')
    return int(count_el.inner_text())


# ── Tests: arrow expand / collapse ────────────────────────────────────────────

class TestBreakdownToggle:

    def test_html_breakdown_hidden_by_default(self, page):
        reset_to_all(page)
        panel = page.locator('#html-breakdown')
        assert panel.is_hidden(), 'HTML breakdown should be hidden at rest'

    def test_md_breakdown_hidden_by_default(self, page):
        reset_to_all(page)
        assert page.locator('#md-breakdown').is_hidden(), 'MD breakdown should be hidden at rest'

    def test_html_arrow_rotates_on_open(self, page):
        reset_to_all(page)
        close_html_breakdown(page)
        arrow = page.locator('#html-arr')
        assert 'open' not in (arrow.get_attribute('class') or ''), 'Arrow should not be open initially'
        page.locator('.srow.expandable').filter(has_text='HTML issues').click()
        page.wait_for_timeout(250)
        assert 'open' in (arrow.get_attribute('class') or ''), 'Arrow should gain .open class after expand'

    def test_html_breakdown_visible_after_click(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        assert page.locator('#html-breakdown').is_visible(), 'HTML breakdown should be visible after toggle'

    def test_html_breakdown_hidden_after_second_click(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        page.locator('.srow.expandable').filter(has_text='HTML issues').click()
        page.wait_for_timeout(250)
        assert page.locator('#html-breakdown').is_hidden(), 'HTML breakdown should hide on second click'

    def test_md_breakdown_visible_after_click(self, page):
        reset_to_all(page)
        open_md_breakdown(page)
        assert page.locator('#md-breakdown').is_visible(), 'MD breakdown should be visible after toggle'

    def test_md_arrow_rotates_on_open(self, page):
        reset_to_all(page)
        close_md_breakdown(page)
        page.locator('.srow.expandable').filter(has_text='MD issues').click()
        page.wait_for_timeout(250)
        assert 'open' in (page.locator('#md-arr').get_attribute('class') or '')

    def test_md_breakdown_hidden_after_second_click(self, page):
        reset_to_all(page)
        open_md_breakdown(page)
        page.locator('.srow.expandable').filter(has_text='MD issues').click()
        page.wait_for_timeout(250)
        assert page.locator('#md-breakdown').is_hidden()

    def test_both_can_be_open_simultaneously(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        open_md_breakdown(page)
        assert page.locator('#html-breakdown').is_visible()
        assert page.locator('#md-breakdown').is_visible()


# ── Tests: breakdown contents ──────────────────────────────────────────────────

class TestBreakdownContents:

    def setup_method(self, method):
        pass  # reset handled per-test

    def test_html_breakdown_shows_all_expected_types(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        keys = breakdown_keys(page, 'html-breakdown')
        assert keys == set(HTML_EXPECTED.keys()), (
            f'HTML breakdown types mismatch.\nExpected: {set(HTML_EXPECTED.keys())}\nGot: {keys}')

    def test_html_breakdown_counts_correct(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        for key, expected_slugs in HTML_EXPECTED.items():
            count = breakdown_count(page, 'html-breakdown', key)
            assert count == len(expected_slugs), (
                f'{key}: expected count {len(expected_slugs)}, got {count}')

    def test_md_breakdown_shows_all_expected_checks(self, page):
        reset_to_all(page)
        open_md_breakdown(page)
        keys = breakdown_keys(page, 'md-breakdown')
        assert keys == set(MD_EXPECTED.keys()), (
            f'MD breakdown checks mismatch.\nExpected: {set(MD_EXPECTED.keys())}\nGot: {keys}')

    def test_md_breakdown_counts_correct(self, page):
        reset_to_all(page)
        open_md_breakdown(page)
        for key, expected_slugs in MD_EXPECTED.items():
            count = breakdown_count(page, 'md-breakdown', key)
            assert count == len(expected_slugs), (
                f'{key}: expected count {len(expected_slugs)}, got {count}')

    def test_html_breakdown_sorted_highest_count_first(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        counts = [int(el.inner_text())
                  for el in page.locator('#html-breakdown .itr-count').all()]
        assert counts == sorted(counts, reverse=True), (
            f'HTML breakdown not sorted descending: {counts}')

    def test_md_breakdown_sorted_highest_count_first(self, page):
        reset_to_all(page)
        open_md_breakdown(page)
        counts = [int(el.inner_text())
                  for el in page.locator('#md-breakdown .itr-count').all()]
        assert counts == sorted(counts, reverse=True), (
            f'MD breakdown not sorted descending: {counts}')


# ── Tests: HTML issue type filtering ──────────────────────────────────────────

class TestHtmlIssueTypeFilter:

    def test_clicking_external_image_shows_correct_subset(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'external_image')
        assert visible_slugs(page) == HTML_EXPECTED['external_image'], (
            f'external_image filter: wrong post set. Got: {visible_slugs(page)}')

    def test_clicking_data_placeholder_shows_correct_subset(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'data_placeholder')
        assert visible_slugs(page) == HTML_EXPECTED['data_placeholder']

    def test_clicking_noscript_remnant_shows_correct_subset(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'noscript_remnant')
        assert visible_slugs(page) == HTML_EXPECTED['noscript_remnant']

    def test_clicking_tracking_pixel_shows_correct_subset(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'tracking_pixel')
        assert visible_slugs(page) == HTML_EXPECTED['tracking_pixel']

    def test_clicking_empty_embed_shows_correct_subset(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'empty_embed')
        assert visible_slugs(page) == HTML_EXPECTED['empty_embed']

    def test_active_row_gets_active_class(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'external_image')
        row = page.locator('#html-breakdown .itr[data-key="external_image"]')
        assert 'active' in (row.get_attribute('class') or ''), 'Clicked row should have .active class'

    def test_html_warning_filter_button_activates_on_type_click(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'data_placeholder')
        html_btn = page.locator('.filter-always button').filter(has_text='HTML⚠')
        assert 'active' in (html_btn.get_attribute('class') or ''), (
            'HTML⚠ filter button should be active when an issue type is selected')

    def test_clicking_same_type_twice_deselects(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'tracking_pixel')
        assert visible_slugs(page) == HTML_EXPECTED['tracking_pixel']
        # Click again to deselect
        click_html_type(page, 'tracking_pixel')
        assert visible_slugs(page) == ALL_HTML_SLUGS, (
            f'After deselect, should show all HTML issue posts. Got: {visible_slugs(page)}')

    def test_deselected_row_loses_active_class(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'empty_embed')
        click_html_type(page, 'empty_embed')  # deselect
        row = page.locator('#html-breakdown .itr[data-key="empty_embed"]')
        assert 'active' not in (row.get_attribute('class') or '')

    def test_switching_to_all_filter_clears_type_selection(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'external_image')
        # Now click All
        page.locator('.filter-always button:has-text("All")').click()
        page.wait_for_timeout(200)
        # Should show all 8 posts
        assert len(visible_slugs(page)) == 8, (
            f'After All filter, expected 8 posts, got {len(visible_slugs(page))}')

    def test_switching_issue_types_updates_list(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'external_image')
        assert visible_slugs(page) == HTML_EXPECTED['external_image']
        # Now click a different type
        click_html_type(page, 'tracking_pixel')
        assert visible_slugs(page) == HTML_EXPECTED['tracking_pixel'], (
            'Switching from one type to another should update post list immediately')


# ── Tests: MD check filtering ─────────────────────────────────────────────────

class TestMdCheckFilter:

    def test_clicking_missing_fm_field_shows_correct_subset(self, page):
        reset_to_all(page)
        open_md_breakdown(page)
        click_md_check(page, 'missing_fm_field')
        assert visible_slugs(page) == MD_EXPECTED['missing_fm_field']

    def test_clicking_broken_links_shows_correct_subset(self, page):
        reset_to_all(page)
        open_md_breakdown(page)
        click_md_check(page, 'broken_links')
        assert visible_slugs(page) == MD_EXPECTED['broken_links']

    def test_clicking_html_entities_shows_correct_subset(self, page):
        reset_to_all(page)
        open_md_breakdown(page)
        click_md_check(page, 'html_entities_in_body')
        assert visible_slugs(page) == MD_EXPECTED['html_entities_in_body']

    def test_md_warning_filter_button_activates_on_check_click(self, page):
        reset_to_all(page)
        open_md_breakdown(page)
        click_md_check(page, 'missing_fm_field')
        md_btn = page.locator('.filter-always button').filter(has_text='MD⚠')
        assert 'active' in (md_btn.get_attribute('class') or '')

    def test_clicking_same_check_twice_deselects(self, page):
        reset_to_all(page)
        open_md_breakdown(page)
        click_md_check(page, 'html_entities_in_body')
        click_md_check(page, 'html_entities_in_body')
        assert visible_slugs(page) == ALL_MD_SLUGS

    def test_switching_to_all_clears_md_check(self, page):
        reset_to_all(page)
        open_md_breakdown(page)
        click_md_check(page, 'broken_links')
        page.locator('.filter-always button:has-text("All")').click()
        page.wait_for_timeout(200)
        assert len(visible_slugs(page)) == 8


# ── Tests: author + issue type combination ────────────────────────────────────

class TestAuthorAndIssueType:

    def test_author_alice_html_issues_shows_alice_posts_only(self, page):
        reset_to_all(page)
        page.locator('.filter-always button').filter(has_text='HTML⚠').click()
        page.wait_for_timeout(200)
        select_author(page, ALICE)
        assert visible_slugs(page) == ALICE_HTML_SLUGS

    def test_author_bob_html_issues_shows_bob_posts_only(self, page):
        reset_to_all(page)
        page.locator('.filter-always button').filter(has_text='HTML⚠').click()
        page.wait_for_timeout(200)
        select_author(page, BOB)
        assert visible_slugs(page) == BOB_HTML_SLUGS

    def test_author_alice_then_external_image_narrows_to_one(self, page):
        """Alice has external_image. Selecting Alice then external_image → 1 post."""
        reset_to_all(page)
        select_author(page, ALICE)
        open_html_breakdown(page)
        click_html_type(page, 'external_image')
        expected = HTML_EXPECTED['external_image'] & ALICE_HTML_SLUGS
        assert visible_slugs(page) == expected, (
            f'Alice + external_image: expected {expected}, got {visible_slugs(page)}')

    def test_author_bob_then_external_image_narrows_to_one(self, page):
        """Bob has external_image (via bob_multi). Bob + external_image → 1 post."""
        reset_to_all(page)
        select_author(page, BOB)
        open_html_breakdown(page)
        click_html_type(page, 'external_image')
        expected = HTML_EXPECTED['external_image'] & BOB_HTML_SLUGS
        assert visible_slugs(page) == expected

    def test_author_alice_then_tracking_pixel_shows_zero(self, page):
        """Alice has no tracking_pixel posts. Alice + tracking_pixel → 0 posts."""
        reset_to_all(page)
        select_author(page, ALICE)
        open_html_breakdown(page)
        # tracking_pixel only exists for Bob — it won't appear in Alice's breakdown
        keys = breakdown_keys(page, 'html-breakdown')
        assert 'tracking_pixel' not in keys, (
            'tracking_pixel should not appear in Alice-filtered breakdown')

    def test_author_bob_breakdown_counts_are_bob_only(self, page):
        """After selecting Bob, HTML breakdown counts should reflect only Bob's posts."""
        reset_to_all(page)
        select_author(page, BOB)
        open_html_breakdown(page)
        # Bob has: external_image(1 via bob_multi), tracking_pixel(2), empty_embed(1)
        # Alice's types (data_placeholder, noscript_remnant) should not appear
        keys = breakdown_keys(page, 'html-breakdown')
        assert 'data_placeholder' not in keys, 'data_placeholder is Alice-only, should not appear for Bob'
        assert 'noscript_remnant' not in keys, 'noscript_remnant is Alice-only, should not appear for Bob'
        assert 'tracking_pixel' in keys, 'tracking_pixel should appear for Bob'

    def test_author_alice_md_issues(self, page):
        reset_to_all(page)
        select_author(page, ALICE)
        page.locator('.filter-always button').filter(has_text='MD⚠').click()
        page.wait_for_timeout(200)
        assert visible_slugs(page) == {SLUGS['alice_md']}

    def test_author_bob_md_issues(self, page):
        reset_to_all(page)
        select_author(page, BOB)
        page.locator('.filter-always button').filter(has_text='MD⚠').click()
        page.wait_for_timeout(200)
        assert visible_slugs(page) == {SLUGS['bob_md']}

    def test_author_alice_broken_links_check(self, page):
        reset_to_all(page)
        select_author(page, ALICE)
        open_md_breakdown(page)
        click_md_check(page, 'broken_links')
        assert visible_slugs(page) == {SLUGS['alice_md']}

    def test_author_alice_html_entities_check_shows_zero(self, page):
        """html_entities_in_body is Bob-only. Alice + that check → not in Alice's breakdown."""
        reset_to_all(page)
        select_author(page, ALICE)
        open_md_breakdown(page)
        keys = breakdown_keys(page, 'md-breakdown')
        assert 'html_entities_in_body' not in keys

    def test_clear_author_restores_full_scope(self, page):
        reset_to_all(page)
        select_author(page, ALICE)
        open_html_breakdown(page)
        click_html_type(page, 'external_image')
        assert len(visible_slugs(page)) == 1
        # Clear author — should show both external_image posts
        clear_author(page)
        assert visible_slugs(page) == HTML_EXPECTED['external_image'], (
            'Clearing author should restore both-author scope for the active issue type')


# ── Tests: edge cases and regression guards ───────────────────────────────────

class TestEdgeCases:

    def test_issue_type_filter_persists_when_breakdown_collapses(self, page):
        """Closing the breakdown panel should not clear the active filter."""
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'data_placeholder')
        assert visible_slugs(page) == HTML_EXPECTED['data_placeholder']
        # Collapse the breakdown
        close_html_breakdown(page)
        # Filter should still be active
        assert visible_slugs(page) == HTML_EXPECTED['data_placeholder'], (
            'Closing breakdown panel must not clear the active issue type filter')

    def test_html_filter_button_active_after_breakdown_close(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'noscript_remnant')
        close_html_breakdown(page)
        html_btn = page.locator('.filter-always button').filter(has_text='HTML⚠')
        assert 'active' in (html_btn.get_attribute('class') or '')

    def test_md_type_does_not_affect_html_filter(self, page):
        """Selecting an MD check must not change the HTML breakdown or filter."""
        reset_to_all(page)
        open_html_breakdown(page)
        open_md_breakdown(page)
        click_md_check(page, 'broken_links')
        # HTML breakdown should still show HTML-based counts, not be affected
        keys = breakdown_keys(page, 'html-breakdown')
        assert keys == set(HTML_EXPECTED.keys()), (
            'Selecting an MD check should not modify the HTML breakdown')

    def test_html_type_does_not_affect_md_filter(self, page):
        reset_to_all(page)
        open_html_breakdown(page)
        open_md_breakdown(page)
        click_html_type(page, 'tracking_pixel')
        # MD breakdown should still show MD-based counts
        keys = breakdown_keys(page, 'md-breakdown')
        assert keys == set(MD_EXPECTED.keys())

    def test_rapid_type_switching_ends_at_correct_subset(self, page):
        """Clicking multiple types quickly should settle at the last one."""
        reset_to_all(page)
        open_html_breakdown(page)
        for key in ['external_image', 'data_placeholder', 'tracking_pixel', 'empty_embed']:
            click_html_type(page, key)
        page.wait_for_timeout(300)
        assert visible_slugs(page) == HTML_EXPECTED['empty_embed'], (
            f'After rapid switching, final type (empty_embed) should be active. '
            f'Got: {visible_slugs(page)}')

    def test_bob_multi_appears_in_both_external_and_tracking_filters(self, page):
        """bob_multi has both external_image and tracking_pixel — must appear in both."""
        reset_to_all(page)
        open_html_breakdown(page)
        click_html_type(page, 'external_image')
        assert SLUGS['bob_multi'] in visible_slugs(page), (
            'bob_multi should appear in external_image filter')
        click_html_type(page, 'tracking_pixel')
        assert SLUGS['bob_multi'] in visible_slugs(page), (
            'bob_multi should appear in tracking_pixel filter')

    def test_alice_md_appears_in_both_missing_fm_and_broken_links(self, page):
        """alice_md has both missing_fm_field and broken_links."""
        reset_to_all(page)
        open_md_breakdown(page)
        click_md_check(page, 'missing_fm_field')
        assert SLUGS['alice_md'] in visible_slugs(page)
        click_md_check(page, 'broken_links')
        assert SLUGS['alice_md'] in visible_slugs(page)

    def test_stats_html_count_matches_html_filter_count(self, page):
        """The 'HTML issues' stat number must equal the count of HTML⚠ filtered posts."""
        reset_to_all(page)
        html_stat = int(page.locator('#s-html').inner_text())
        page.locator('.filter-always button').filter(has_text='HTML⚠').click()
        page.wait_for_timeout(200)
        assert len(visible_slugs(page)) == html_stat, (
            f'HTML stat ({html_stat}) must match count of posts shown by HTML⚠ filter '
            f'({len(visible_slugs(page))})')

    def test_stats_md_count_matches_md_filter_count(self, page):
        reset_to_all(page)
        md_stat = int(page.locator('#s-mdiss').inner_text())
        page.locator('.filter-always button').filter(has_text='MD⚠').click()
        page.wait_for_timeout(200)
        assert len(visible_slugs(page)) == md_stat

    def test_bob_author_tracking_pixel_count_is_two(self, page):
        """Bob has 2 tracking_pixel posts. Bob's breakdown must show 2."""
        reset_to_all(page)
        select_author(page, BOB)
        open_html_breakdown(page)
        count = breakdown_count(page, 'html-breakdown', 'tracking_pixel')
        assert count == 2, f'Bob tracking_pixel count should be 2, got {count}'

    def test_alice_author_external_image_count_is_one(self, page):
        """Alice has 1 external_image post. Alice's breakdown must show 1."""
        reset_to_all(page)
        select_author(page, ALICE)
        open_html_breakdown(page)
        count = breakdown_count(page, 'html-breakdown', 'external_image')
        assert count == 1, f'Alice external_image count should be 1, got {count}'


# ── Generate scope button behaviour ───────────────────────────────────────────

class TestGenerateScopeButton:
    """The ⚙ Generate scope action has two modes:

    - All / HTML⚠ / Stale / etc. filter → generates only posts WITHOUT MD yet
      (the standard behaviour: don't touch existing MD)
    - MD⚠ filter (or a specific MD check sub-filter) → regenerates ALL posts
      in scope, even those that already have MD, because the user is explicitly
      looking at posts whose MD needs fixing.

    Uses Playwright route interception to count which slugs actually receive a
    generate-md POST, without touching real files on disk.
    """

    # Slugs with MD already (from make_state — have md.generated_at)
    WITH_MD    = {SLUGS['alice_md'], SLUGS['bob_md']}
    # Slugs without MD
    WITHOUT_MD = {SLUGS['alice_external'], SLUGS['alice_data'], SLUGS['alice_noscript'],
                  SLUGS['bob_tracking'],   SLUGS['bob_embed'],  SLUGS['bob_multi']}

    def _intercept_generate(self, page):
        """Route all generate-md calls to a mock 200 response and collect called slugs."""
        import re as _re, json as _json
        called = []

        def handler(route):
            m = _re.search(r'/posts/([^/]+)/generate-md', route.request.url)
            if m:
                import urllib.parse
                called.append(urllib.parse.unquote(m.group(1)))
            route.fulfill(
                status=200,
                content_type='application/json',
                body=_json.dumps({'slug': 'mock', 'md': {
                    'generated_at': '2026-01-01T00:00:00',
                    'issues': [], 'staged': False,
                }}),
            )

        page.route('**/generate-md', handler)
        return called

    def _click_generate(self, page):
        """Hover the filter zone to reveal scope buttons, click ⚙ Generate, and
        wait until generation is complete (button re-enabled).

        Uses force=True on hover because child buttons inside .filter-zone can
        intercept the pointer when Playwright targets the container's centre point.
        """
        page.locator('.filter-zone').hover(force=True)
        page.wait_for_timeout(300)  # hover transition
        page.locator('#btn-gen-all').click()
        # Wait until the button is re-enabled — that signals the async loop finished
        page.wait_for_function(
            "() => !document.getElementById('btn-gen-all').disabled",
            timeout=15000,
        )

    def _progress_text(self, page) -> str:
        """Read the progress span immediately after generation completes.

        The progress text is cleared after 5 seconds. A stale timer from a
        previous test can race with this read, so we check the text right after
        the button re-enables (generation complete) without adding extra sleeps.
        """
        return page.locator('#gen-progress').inner_text().strip()

    def teardown_method(self, method):
        pass  # unroute handled in each test via try/finally

    # ── All filter: skip posts that already have MD ────────────────────────────

    def test_all_filter_skips_posts_with_existing_md(self, page):
        """In All mode, Generate must not call generate-md for posts that already have MD."""
        reset_to_all(page)
        called = self._intercept_generate(page)
        try:
            self._click_generate(page)
            assert self.WITH_MD.isdisjoint(set(called)), (
                f'Generate in All mode called generate-md for posts that already have MD: '
                f'{self.WITH_MD & set(called)}')
        finally:
            page.unroute('**/generate-md')

    def test_all_filter_only_calls_posts_without_md(self, page):
        """In All mode, Generate calls generate-md for exactly the posts without MD."""
        reset_to_all(page)
        called = self._intercept_generate(page)
        try:
            self._click_generate(page)
            assert set(called) == self.WITHOUT_MD, (
                f'All mode generate called wrong set.\n'
                f'  Expected: {self.WITHOUT_MD}\n'
                f'  Got:      {set(called)}')
        finally:
            page.unroute('**/generate-md')

    def test_all_filter_progress_says_generated_not_regenerated(self, page):
        """Progress message in All mode must say 'generated', not 'regenerated'."""
        reset_to_all(page)
        called = self._intercept_generate(page)
        try:
            self._click_generate(page)  # waits for button re-enable (generation complete)
            text = self._progress_text(page)
            assert 'generated' in text.lower(), (
                f'Progress should say "generated" in All mode. Got: {text!r}')
            assert 'regenerated' not in text.lower(), (
                f'Progress must not say "regenerated" in All mode. Got: {text!r}')
        finally:
            page.unroute('**/generate-md')

    # ── MD⚠ filter: regenerate all in scope ───────────────────────────────────

    def test_md_issues_filter_regenerates_posts_with_existing_md(self, page):
        """In MD⚠ mode, Generate must call generate-md for posts that already have MD."""
        reset_to_all(page)
        page.locator('.filter-always button').filter(has_text='MD⚠').click()
        page.wait_for_timeout(200)
        called = self._intercept_generate(page)
        try:
            self._click_generate(page)
            assert self.WITH_MD.issubset(set(called)), (
                f'MD⚠ mode Generate must regenerate posts with existing MD.\n'
                f'  Expected to include: {self.WITH_MD}\n'
                f'  Actually called:     {set(called)}')
        finally:
            page.unroute('**/generate-md')

    def test_md_issues_filter_calls_only_md_issue_posts(self, page):
        """In MD⚠ mode, Generate calls only the posts visible in the MD⚠ scope."""
        reset_to_all(page)
        page.locator('.filter-always button').filter(has_text='MD⚠').click()
        page.wait_for_timeout(200)
        called = self._intercept_generate(page)
        try:
            self._click_generate(page)
            # Should call exactly the posts with MD issues, none without
            assert set(called) == self.WITH_MD, (
                f'MD⚠ mode should regenerate only MD-issue posts.\n'
                f'  Expected: {self.WITH_MD}\n'
                f'  Got:      {set(called)}')
            assert self.WITHOUT_MD.isdisjoint(set(called)), (
                f'MD⚠ mode must not generate posts without MD: '
                f'{self.WITHOUT_MD & set(called)}')
        finally:
            page.unroute('**/generate-md')

    def test_md_issues_filter_progress_says_regenerating(self, page):
        """Progress message in MD⚠ mode must say 'regenerat' not 'generat' only."""
        reset_to_all(page)
        page.locator('.filter-always button').filter(has_text='MD⚠').click()
        page.wait_for_timeout(200)
        called = self._intercept_generate(page)
        try:
            self._click_generate(page)
            text = self._progress_text(page)
            assert 'regenerat' in text.lower(), (
                f'Progress should say "regenerat..." in MD⚠ mode. Got: {text!r}')
        finally:
            page.unroute('**/generate-md')

    # ── MD check sub-filter: also regenerates ─────────────────────────────────

    def test_md_check_subfilter_also_regenerates(self, page):
        """Clicking a specific MD check row (currentMdCheck set) also triggers regenerate mode."""
        reset_to_all(page)
        open_md_breakdown(page)
        click_md_check(page, 'missing_fm_field')  # sets currentMdCheck
        page.wait_for_timeout(200)
        called = self._intercept_generate(page)
        try:
            self._click_generate(page)
            # missing_fm_field only applies to alice_md
            assert SLUGS['alice_md'] in called, (
                f'Generate with missing_fm_field sub-filter must regenerate alice_md. '
                f'Called: {called}')
            assert SLUGS['bob_md'] not in called, (
                f'bob_md (no missing_fm_field issue) must not be regenerated. '
                f'Called: {called}')
            # Should not touch posts without MD
            assert self.WITHOUT_MD.isdisjoint(set(called)), (
                f'MD check sub-filter must not generate posts without MD: '
                f'{self.WITHOUT_MD & set(called)}')
        finally:
            page.unroute('**/generate-md')

    def test_md_check_subfilter_progress_says_regenerating(self, page):
        reset_to_all(page)
        open_md_breakdown(page)
        click_md_check(page, 'html_entities_in_body')
        page.wait_for_timeout(200)
        called = self._intercept_generate(page)
        try:
            self._click_generate(page)
            text = self._progress_text(page)
            assert 'regenerat' in text.lower(), (
                f'Progress must say "regenerat..." with MD check sub-filter active. Got: {text!r}')
        finally:
            page.unroute('**/generate-md')

    # ── Nothing to generate/regenerate ────────────────────────────────────────

    def test_html_issues_filter_is_not_regenerate_mode(self, page):
        """HTML⚠ filter must use normal generate-only mode — posts with MD are not regenerated."""
        reset_to_all(page)
        page.locator('.filter-always button').filter(has_text='HTML⚠').click()
        page.wait_for_timeout(200)
        # alice_md and bob_md have no html.issues, so they're not in HTML⚠ scope
        # The HTML⚠ posts (alice_external etc.) have no MD → Generate runs in normal mode
        called = self._intercept_generate(page)
        try:
            self._click_generate(page)
            assert self.WITH_MD.isdisjoint(set(called)), (
                f'HTML⚠ mode must not call generate-md for MD-issue-only posts: '
                f'{self.WITH_MD & set(called)}')
        finally:
            page.unroute('**/generate-md')
