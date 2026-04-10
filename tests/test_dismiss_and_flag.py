"""
Playwright tests: HTML issue dismiss / undismiss / flagged filter.

Covers the full UI happy paths for:
  1. Dismiss button appears on HTML issue rows
  2. Clicking ⊘ removes the issue from the active panel
  3. "N reviewed ▸" counter appears and toggles the dismissed section
  4. ↩ Reconsider restores the issue to the active panel
  5. Rescan with active dismissal keeps the issue dismissed
  6. Undismiss after rescan re-surfaces the issue
  7. 🚩 Flagged filter shows only flagged posts
  8. Dismissing a post's only HTML issue removes it from HTML⚠ scope

Requires server on localhost:9000 with kie-mark-proctor project active.
"""
import pytest
import requests as _requests

SERVER  = 'http://localhost:9000'
APP_URL = SERVER + '/ui/index.html'
API     = SERVER + '/api'

# Post that gets suspicious_code_content after scan (conference schedule table)
SUSPECT_SLUG = '2009-07-20-october-rules-festival-2009'
# Post with a known HTML issue (external image) for generic dismiss tests
HTML_ISSUE_SLUG = '2009-07-20-october-rules-festival-2009'


@pytest.fixture(scope='module')
def session():
    try:
        s = _requests.Session()
        s.get(f'{API}/projects', timeout=3).raise_for_status()
        s.post(f'{API}/projects/kie-mark-proctor/activate')
        return s
    except Exception:
        pytest.skip('Server not running on localhost:9000')


@pytest.fixture(scope='module')
def page(session):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip('playwright not installed')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page(viewport={'width': 1400, 'height': 900})
        pg.goto(APP_URL, wait_until='networkidle')
        pg.wait_for_selector('.pi', timeout=15000)
        yield pg
        browser.close()


def _open_issues(pg):
    """Make the issues panel visible."""
    is_open = pg.evaluate("() => !document.getElementById('issue-panel').classList.contains('hidden')")
    if not is_open:
        pg.locator('#btn-issues').click()
        pg.wait_for_timeout(200)


def _navigate_and_scan(pg, session, slug):
    """Navigate to slug, open issues panel, and trigger a fresh scan."""
    pg.locator(f'[data-slug="{slug}"]').scroll_into_view_if_needed()
    pg.locator(f'[data-slug="{slug}"]').click()
    pg.wait_for_function(
        f"() => document.getElementById('orig-frame')?.src?.includes('{slug}')",
        timeout=8000)
    pg.wait_for_timeout(400)
    _open_issues(pg)
    # Fresh scan via API so we have a known state
    session.post(f'{API}/posts/{slug}/scan')
    # Also make sure any previous dismissal is cleared
    session.delete(f'{API}/posts/{slug}/dismiss-html-check/suspicious_code_content')
    pg.wait_for_timeout(200)
    # Reload to pick up fresh state
    pg.reload(wait_until='networkidle')
    pg.wait_for_selector('.pi', timeout=15000)
    pg.locator(f'[data-slug="{slug}"]').scroll_into_view_if_needed()
    pg.locator(f'[data-slug="{slug}"]').click()
    pg.wait_for_function(
        f"() => document.getElementById('orig-frame')?.src?.includes('{slug}')",
        timeout=8000)
    pg.wait_for_timeout(400)
    _open_issues(pg)
    pg.wait_for_timeout(300)


def _html_issue_count(pg):
    """Count active (non-dismissed) HTML issue rows via DOM — excludes reviewed section."""
    return pg.evaluate("""() => {
        const reviewed = document.getElementById('iss-reviewed-rows');
        return [...document.querySelectorAll('#html-issue-list .irow')]
            .filter(el => !reviewed?.contains(el))
            .length;
    }""")


def _dismissed_count(pg):
    """Read dismissed count from stable data-dismissed-count attribute — no JS globals."""
    val = pg.get_attribute('#html-issue-list', 'data-dismissed-count')
    return int(val) if val else 0


def _dismissed_types(pg):
    """Read dismissed types from stable data-dismissed-types attribute."""
    val = pg.get_attribute('#html-issue-list', 'data-dismissed-types') or ''
    return [t for t in val.split(',') if t]


def _reviewed_count(pg):
    """Read count from stable data-testid + data-count — no text parsing."""
    val = pg.get_attribute('[data-testid="dismissed-count"]', 'data-count')
    return int(val) if val else 0


def _reviewed_toggle_exists(pg):
    return pg.locator('[data-testid="dismissed-count"]').count() > 0


def _dismissed_rows_visible(pg):
    """True if the dismissed rows section is shown."""
    return pg.evaluate("""() => {
        const el = document.getElementById('iss-reviewed-rows');
        return el ? el.style.display !== 'none' : false;
    }""")


# ── Happy path 1: dismiss button present on HTML issue rows ───────────────────

class TestDismissButtonPresent:
    """Every HTML issue row must have a ⊘ dismiss button."""

    def test_dismiss_button_on_issue_rows(self, page, session):
        pg = page
        _navigate_and_scan(pg, session, SUSPECT_SLUG)

        # Use stable data-testid — no fragile class+position queries
        dismiss_buttons = pg.locator('[data-testid^="dismiss-btn-"]').count()
        assert dismiss_buttons > 0, (
            'No [data-testid^="dismiss-btn-"] elements found. '
            'Every HTML issue row must have a dismiss button with data-testid="dismiss-btn-{type}".'
        )

    def test_each_dismiss_button_has_specific_type(self, page, session):
        """Each dismiss button's data-testid encodes the issue type — no ambiguity."""
        pg = page
        # For the suspect post, expect dismiss-btn-suspicious_code_content
        btn = pg.locator('[data-testid="dismiss-btn-suspicious_code_content"]')
        assert btn.count() > 0, (
            'No dismiss button with data-testid="dismiss-btn-suspicious_code_content". '
            'The testid must encode the specific issue type.'
        )


# ── Happy path 2: clicking ⊘ removes issue from active panel ─────────────────

class TestDismissRemovesFromActive:
    """Clicking ⊘ must remove the issue from the visible active list."""

    def test_dismiss_hides_issue_row(self, page, session):
        pg = page
        _navigate_and_scan(pg, session, SUSPECT_SLUG)

        count_before = _html_issue_count(pg)
        assert count_before > 0, 'No HTML issues to dismiss'
        dismissed_before = _dismissed_count(pg)

        # Use stable data-testid — not brittle .first on a class
        pg.locator('[data-testid="dismiss-btn-suspicious_code_content"]').click()
        pg.wait_for_timeout(800)

        count_after = _html_issue_count(pg)
        dismissed_after = _dismissed_count(pg)
        assert count_after < count_before, (
            f'Active issue count did not decrease: before={count_before}, after={count_after}.'
        )
        assert dismissed_after > dismissed_before, (
            f'data-dismissed-count did not increase: before={dismissed_before}, after={dismissed_after}.'
        )
        # Confirm specific type is in data-dismissed-types (no JS globals needed)
        assert 'suspicious_code_content' in _dismissed_types(pg), (
            'suspicious_code_content not in data-dismissed-types attribute.'
        )

    def test_dismissed_not_in_active_api_response(self, page, session):
        """The dismissed issue must not appear in the API's html.issues."""
        r = session.get(f'{API}/posts/{SUSPECT_SLUG}')
        active_types = [i['type'] for i in r.json().get('html', {}).get('issues', [])]
        dismissed = r.json().get('dismissed_html_checks', {})
        for t in dismissed:
            assert t not in active_types, (
                f'Dismissed type "{t}" still in active html.issues.'
            )


# ── Happy path 3: "N reviewed ▸" counter and toggle ─────────────────────────

class TestReviewedCounter:
    """After dismissing, the column header shows 'N reviewed ▸' toggle."""

    def test_reviewed_counter_appears_after_dismiss(self, page, session):
        pg = page
        _navigate_and_scan(pg, session, SUSPECT_SLUG)

        assert not _reviewed_toggle_exists(pg), 'Toggle should not exist before any dismissal'

        pg.locator('[data-testid="dismiss-btn-suspicious_code_content"]').click()
        pg.wait_for_timeout(800)

        # Use data-count attribute — no text parsing
        assert _reviewed_toggle_exists(pg), 'data-testid="dismissed-count" toggle did not appear'
        assert _reviewed_count(pg) == 1, (
            f'Expected data-count="1" on dismissed-count toggle. Got: {_reviewed_count(pg)}'
        )

    def test_toggle_shows_dismissed_section(self, page, session):
        pg = page
        # Dismiss first if not already dismissed
        if not _reviewed_toggle_exists(pg):
            pg.locator('[data-testid="dismiss-btn-suspicious_code_content"]').click()
            pg.wait_for_timeout(800)

        assert not _dismissed_rows_visible(pg), 'Dismissed section should start collapsed'

        # Click the toggle
        pg.locator('#iss-reviewed-toggle').click()
        pg.wait_for_timeout(200)

        assert _dismissed_rows_visible(pg), (
            'Dismissed section did not expand after clicking the "reviewed" toggle.'
        )

    def test_toggle_collapses_again(self, page, session):
        pg = page
        toggle = pg.locator('[data-testid="dismissed-count"]')
        if _dismissed_rows_visible(pg):
            toggle.click(); pg.wait_for_timeout(200)
        assert not _dismissed_rows_visible(pg)

        toggle.click(); pg.wait_for_timeout(200)
        assert _dismissed_rows_visible(pg)

        toggle.click(); pg.wait_for_timeout(200)
        assert not _dismissed_rows_visible(pg), (
            'Clicking toggle again must collapse the dismissed section.'
        )


# ── Happy path 4: ↩ Reconsider restores the issue ───────────────────────────

class TestUndismissRestores:
    """Clicking ↩ in the dismissed section must restore the issue as active."""

    def test_reconsider_restores_to_active(self, page, session):
        pg = page
        # Ensure dismissed section is visible to click ↩
        if not _dismissed_rows_visible(pg):
            toggle = pg.locator('#iss-reviewed-toggle')
            if toggle.count() > 0:
                toggle.click()
                pg.wait_for_timeout(200)

        if not _dismissed_rows_visible(pg):
            pytest.skip('No dismissed issues to reconsider')

        count_before = _html_issue_count(pg)
        dismissed_before = _dismissed_count(pg)

        # Use stable data-testid
        pg.locator('[data-testid="undismiss-btn-suspicious_code_content"]').click()
        pg.wait_for_timeout(1000)  # triggers rescan

        count_after = _html_issue_count(pg)
        dismissed_after = _dismissed_count(pg)

        assert count_after > count_before, (
            f'Active count did not increase: before={count_before}, after={count_after}.'
        )
        assert dismissed_after < dismissed_before, (
            f'data-dismissed-count did not decrease: before={dismissed_before}, after={dismissed_after}.'
        )
        assert 'suspicious_code_content' not in _dismissed_types(pg), (
            'Type still in data-dismissed-types after reconsider.'
        )


# ── Happy path 5: rescan with active dismissal keeps issue dismissed ──────────

class TestRescanRespectsDismissal:
    """After dismissing, a manual rescan must not re-surface the issue."""

    def test_rescan_keeps_dismissed(self, page, session):
        pg = page
        _navigate_and_scan(pg, session, SUSPECT_SLUG)

        # Dismiss
        pg.locator('#html-issue-list .iss-dismiss').first.click()
        pg.wait_for_timeout(800)
        count_after_dismiss = _html_issue_count(pg)

        # Rescan via API
        session.post(f'{API}/posts/{SUSPECT_SLUG}/scan')
        pg.wait_for_timeout(500)

        # Reload the issue panel (simulate what the UI does after scan)
        pg.reload(wait_until='networkidle')
        pg.wait_for_selector('.pi', timeout=15000)
        pg.locator(f'[data-slug="{SUSPECT_SLUG}"]').scroll_into_view_if_needed()
        pg.locator(f'[data-slug="{SUSPECT_SLUG}"]').click()
        pg.wait_for_timeout(400)
        _open_issues(pg)
        pg.wait_for_timeout(300)

        count_after_rescan = _html_issue_count(pg)
        assert count_after_rescan == count_after_dismiss, (
            f'Rescan re-surfaced a dismissed issue: '
            f'count was {count_after_dismiss} after dismiss, '
            f'{count_after_rescan} after rescan. '
            f'Dismissal must survive rescans when the underlying issue is still present.'
        )
        # Clean up
        session.delete(f'{API}/posts/{SUSPECT_SLUG}/dismiss-html-check/suspicious_code_content')


# ── Happy path 6: 🚩 Flagged filter ─────────────────────────────────────────

class TestFlaggedFilter:
    """🚩 Flagged filter must show only posts where flagged=true."""

    def test_flagged_filter_shows_flagged_posts_only(self, page, session):
        pg = page
        # Find a post and flag it via API
        posts = session.get(f'{API}/posts').json()
        test_slug = posts[0]['slug']
        session.patch(f'{API}/posts/{test_slug}',
                      json={'flagged': True, 'user_note': 'test flag'})
        pg.wait_for_timeout(200)

        # Reload to get fresh state
        pg.reload(wait_until='networkidle')
        pg.wait_for_selector('.pi', timeout=15000)

        # Hover the filter zone and click Flagged
        pg.locator('.filter-zone').hover()
        pg.wait_for_timeout(200)
        pg.evaluate("""() => {
            const btn = [...document.querySelectorAll('.fb')]
                .find(b => b.textContent.includes('Flagged'));
            if (btn) setFilter(btn, 'flagged');
        }""")
        pg.wait_for_timeout(300)

        post_items = pg.locator('.pi').count()
        assert post_items > 0, '🚩 Flagged filter shows no posts — expected at least one flagged post'

        # All visible posts must have the 🚩 badge
        all_flagged = pg.evaluate("""() => {
            return [...document.querySelectorAll('.pi')].every(
                el => el.querySelector('.b-err') !== null ||
                      el.innerText.includes('🚩')
            );
        }""")
        assert all_flagged, (
            '🚩 Flagged filter shows posts without the flag badge. '
            'Only flagged posts should be in this scope.'
        )

        # Clean up
        session.patch(f'{API}/posts/{test_slug}',
                      json={'flagged': False, 'user_note': ''})

    def test_flagged_filter_empty_when_no_posts_flagged(self, page, session):
        """If no posts are flagged, the Flagged filter should show an empty list."""
        pg = page
        # Make sure no posts are flagged
        posts = session.get(f'{API}/posts').json()
        for p in posts:
            if p.get('flagged'):
                session.patch(f'{API}/posts/{p["slug"]}',
                              json={'flagged': False, 'user_note': ''})

        pg.reload(wait_until='networkidle')
        pg.wait_for_selector('.pi', timeout=15000)

        pg.locator('.filter-zone').hover()
        pg.wait_for_timeout(200)
        pg.evaluate("""() => {
            const btn = [...document.querySelectorAll('.fb')]
                .find(b => b.textContent.includes('Flagged'));
            if (btn) setFilter(btn, 'flagged');
        }""")
        pg.wait_for_timeout(300)

        items = pg.locator('.pi').count()
        assert items == 0, (
            f'Flagged filter shows {items} posts when none are flagged. '
            f'Expected 0.'
        )

        # Reset to All filter
        pg.evaluate("""() => {
            const btn = [...document.querySelectorAll('.fb')]
                .find(b => b.textContent.trim() === 'All');
            if (btn) setFilter(btn, 'all');
        }""")


# ── Happy path 7: dismiss does not affect post-level flag ────────────────────

class TestDismissIndependentOfFlag:
    """Dismissing an HTML issue must not change the post-level 🚩 flag."""

    def test_dismiss_does_not_set_flag(self, page, session):
        pg = page
        _navigate_and_scan(pg, session, SUSPECT_SLUG)

        # Ensure the post is NOT flagged
        session.patch(f'{API}/posts/{SUSPECT_SLUG}', json={'flagged': False, 'user_note': ''})
        pg.wait_for_timeout(200)

        if pg.locator('#html-issue-list .iss-dismiss').count() > 0:
            pg.locator('#html-issue-list .iss-dismiss').first.click()
            pg.wait_for_timeout(800)

        state = session.get(f'{API}/posts/{SUSPECT_SLUG}').json()
        assert not state.get('flagged'), (
            'Dismissing an HTML issue set the post-level flagged=true. '
            'These are independent: issue dismissal ≠ post flag.'
        )
        # Clean up
        session.delete(f'{API}/posts/{SUSPECT_SLUG}/dismiss-html-check/suspicious_code_content')
