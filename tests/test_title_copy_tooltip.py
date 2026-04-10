"""
Tests for post title copy button and floating tooltip.

Two locations:
  1. Sidebar post list — each item has a ⎘ copy button (visible on hover)
     and a truncated title that shows the full title in a floating tooltip.
  2. Main post crumb — always-visible ⎘ copy button next to the title,
     hovering the <strong> shows the full title tooltip.

Both copy buttons write the post TITLE (not slug) to the clipboard.
The tooltip uses a fixed-position #float-tip element so it is never
clipped by overflow:hidden ancestors.

Requires server running on localhost:9000.
"""
from pathlib import Path
import sys

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
        ctx = browser.new_context(
            viewport={'width': 1400, 'height': 900},
            permissions=['clipboard-read', 'clipboard-write'],
        )
        pg = ctx.new_page()
        pg.goto(APP_URL, wait_until='networkidle')
        pg.wait_for_function(
            "() => document.querySelectorAll('.pi').length > 0", timeout=20000
        )
        yield pg
        ctx.close()
        browser.close()


def _first_post_title(pg) -> str:
    """Return the full title of the first post in the list."""
    return pg.evaluate("""() => {
        const p = allPosts[0];
        return (p.title || p.slug).replace(/- KIE Community$/, '').trim();
    }""")


def _select_first_post(pg):
    pg.locator('.pi').first.click()
    pg.wait_for_timeout(600)


# ── Sidebar: copy button ───────────────────────────────────────────────────────

class TestSidebarCopyButton:

    def test_copy_button_exists_in_each_post_item(self, server, page):
        pg = page
        copy_btns = pg.locator('.pi-copy')
        assert copy_btns.count() > 0, (
            '.pi-copy button must exist in the post list items'
        )

    def test_copy_button_copies_title_not_slug(self, server, page):
        """Clicking ⎘ must write the post TITLE to the clipboard."""
        pg = page
        full_title = _first_post_title(pg)
        first_pi = pg.locator('.pi').first

        # Hover to reveal the copy button, then click it
        first_pi.hover()
        pg.wait_for_timeout(200)
        copy_btn = first_pi.locator('.pi-copy')
        copy_btn.click()
        pg.wait_for_timeout(300)

        clipped = pg.evaluate("() => navigator.clipboard.readText()")
        assert clipped == full_title, (
            f'Copy button must write the full post title. '
            f'Expected: {full_title!r}, Got: {clipped!r}. '
            f'The copy button must use the full title, not the slug or clipped version.'
        )

    def test_copy_button_shows_checkmark_then_resets(self, server, page):
        """After clicking, the button shows ✓ then reverts to ⎘."""
        pg = page
        first_pi = pg.locator('.pi').first
        first_pi.hover()
        pg.wait_for_timeout(1400)  # let any prior click's reset timer finish
        copy_btn = first_pi.locator('.pi-copy')

        assert copy_btn.text_content() == '⎘', 'Button must start as ⎘'
        copy_btn.click()
        pg.wait_for_timeout(100)
        assert copy_btn.text_content() == '✓', 'Button must show ✓ immediately after click'
        pg.wait_for_timeout(1300)
        assert copy_btn.text_content() == '⎘', 'Button must revert to ⎘ after 1.2s'

    def test_copy_button_does_not_navigate(self, server, page):
        """Clicking ⎘ must not select the post (stopPropagation)."""
        pg = page
        initial_slug = pg.evaluate("() => currentSlug")
        first_pi = pg.locator('.pi').first
        first_pi.hover()
        pg.wait_for_timeout(200)
        copy_btn = first_pi.locator('.pi-copy')
        copy_btn.click()
        pg.wait_for_timeout(300)
        after_slug = pg.evaluate("() => currentSlug")
        assert after_slug == initial_slug, (
            'Clicking the copy button must not change the current post selection'
        )


# ── Sidebar: tooltip ──────────────────────────────────────────────────────────

class TestSidebarTooltip:

    def test_float_tip_element_exists(self, server, page):
        pg = page
        assert pg.evaluate("() => !!document.getElementById('float-tip')"), (
            '#float-tip element must exist in the DOM'
        )

    def test_tooltip_hidden_by_default(self, server, page):
        pg = page
        visible = pg.evaluate(
            "() => document.getElementById('float-tip').style.display !== 'none'"
        )
        assert not visible, '#float-tip must be hidden when no title is hovered'

    def test_tooltip_shows_full_title_on_hover(self, server, page):
        pg = page
        full_title = _first_post_title(pg)
        title_span = pg.locator('.pi').first.locator('.pi-title-text')

        title_span.hover()
        pg.wait_for_timeout(100)

        tip_text = pg.evaluate("() => document.getElementById('float-tip').textContent")
        tip_visible = pg.evaluate(
            "() => document.getElementById('float-tip').style.display !== 'none'"
        )

        assert tip_visible, 'Tooltip must be visible when hovering the title span'
        assert tip_text == full_title, (
            f'Tooltip must show the FULL unclipped title. '
            f'Expected: {full_title!r}, Got: {tip_text!r}'
        )

    def test_tooltip_uses_fixed_position(self, server, page):
        """Tooltip must use position:fixed so it escapes overflow:hidden parents."""
        pg = page
        position = pg.evaluate(
            "() => getComputedStyle(document.getElementById('float-tip')).position"
        )
        assert position == 'fixed', (
            f'#float-tip must use position:fixed to escape overflow:hidden ancestors. '
            f'Got: {position!r}'
        )

    def test_tooltip_hides_on_mouse_leave(self, server, page):
        pg = page
        title_span = pg.locator('.pi').first.locator('.pi-title-text')
        title_span.hover()
        pg.wait_for_timeout(100)
        # Move to neutral area
        pg.mouse.move(700, 500)
        pg.wait_for_timeout(100)
        visible = pg.evaluate(
            "() => document.getElementById('float-tip').style.display !== 'none'"
        )
        assert not visible, 'Tooltip must hide when mouse leaves the title span'

    def test_tooltip_not_clipped(self, server, page):
        """Tooltip must show the title without truncation."""
        pg = page
        # Find a post with a long title (> 46 chars)
        long_slug = pg.evaluate("""() => {
            const p = allPosts.find(x =>
                (x.title||x.slug).replace(/- KIE Community$/,'').trim().length > 46
            );
            return p ? p.slug : null;
        }""")
        if not long_slug:
            pytest.skip('No post with title > 46 chars found')

        full_title = pg.evaluate(f"""() => {{
            const p = allPosts.find(x => x.slug === '{long_slug}');
            return (p.title||p.slug).replace(/- KIE Community$/,'').trim();
        }}""")

        # Scroll the post into view and hover
        pi = pg.locator(f'[data-slug="{long_slug}"]')
        pi.scroll_into_view_if_needed()
        pi.locator('.pi-title-text').hover()
        pg.wait_for_timeout(100)

        tip_text = pg.evaluate("() => document.getElementById('float-tip').textContent")
        assert tip_text == full_title, (
            f'Long title must appear in full in tooltip. '
            f'Expected {len(full_title)} chars, got {len(tip_text)}: {tip_text!r}'
        )


# ── Main post crumb: copy + tooltip ───────────────────────────────────────────

class TestCrumbCopyAndTooltip:

    def test_crumb_has_copy_button(self, server, page):
        pg = page
        _select_first_post(pg)
        btn = pg.locator('#post-crumb .crumb-copy')
        assert btn.is_visible(), (
            '.crumb-copy button must be visible in #post-crumb after selecting a post'
        )
        assert btn.text_content() == '⎘'

    def test_crumb_copy_button_copies_title(self, server, page):
        """Clicking ⎘ in the crumb copies the full post title to clipboard."""
        pg = page
        _select_first_post(pg)
        full_title = _first_post_title(pg)

        pg.locator('#post-crumb .crumb-copy').click()
        pg.wait_for_timeout(300)

        clipped = pg.evaluate("() => navigator.clipboard.readText()")
        assert clipped == full_title, (
            f'Crumb copy button must write the full post title. '
            f'Expected: {full_title!r}, Got: {clipped!r}'
        )

    def test_crumb_copy_shows_checkmark(self, server, page):
        pg = page
        _select_first_post(pg)
        btn = pg.locator('#post-crumb .crumb-copy')
        btn.click()
        pg.wait_for_timeout(100)
        assert btn.text_content() == '✓'
        pg.wait_for_timeout(1300)
        assert btn.text_content() == '⎘'

    def test_crumb_title_tooltip_shows_full_title(self, server, page):
        """Hovering the <strong> in the crumb shows the full title tooltip."""
        pg = page
        _select_first_post(pg)
        full_title = _first_post_title(pg)

        pg.locator('#post-crumb strong').hover()
        pg.wait_for_timeout(100)

        tip_text = pg.evaluate("() => document.getElementById('float-tip').textContent")
        tip_visible = pg.evaluate(
            "() => document.getElementById('float-tip').style.display !== 'none'"
        )

        assert tip_visible, 'Tooltip must be visible when hovering the crumb title'
        assert tip_text == full_title, (
            f'Crumb tooltip must show the full title. '
            f'Expected: {full_title!r}, Got: {tip_text!r}'
        )


# ── Regression: title must not be squeezed by date/copy button ────────────────

class TestCrumbTitleSpaceRegression:
    """The title in the post crumb must receive most of the available crumb
    width, not be squeezed by the date/author span or copy button.

    Regression: adding display:flex to #post-crumb with flex-shrink:0 on the
    date span caused the date (~159px) to consume a fixed share of the crumb,
    leaving the title only ~190px of ~366px — cutting visible chars from ~48
    to ~25.

    Fix: title+date are wrapped in a single .crumb-title-block flex child that
    takes all remaining flex space.  Title and date clip together from the right,
    so the title dominates and the date is sacrificed first.
    """

    def test_title_block_takes_most_of_crumb_width(self, server, page):
        """The title content block must occupy ≥ 85% of the crumb width."""
        pg = page
        _select_first_post(pg)

        ratio = pg.evaluate("""() => {
            const crumb = document.getElementById('post-crumb');
            const block = crumb.querySelector('.crumb-title-block');
            if (!block) return 0;
            return block.getBoundingClientRect().width /
                   crumb.getBoundingClientRect().width;
        }""")

        assert ratio >= 0.85, (
            f'Title block must occupy ≥ 85% of crumb width, got {ratio:.1%}. '
            f'The date span or copy button is stealing too much space. '
            f'Wrap <strong> + date in a single .crumb-title-block flex child '
            f'so they clip together from the right.'
        )

    def test_copy_button_stays_small(self, server, page):
        """The ⎘ copy button must take no more than 30px — it must not expand."""
        pg = page
        _select_first_post(pg)

        copy_w = pg.evaluate("""() => {
            const btn = document.querySelector('#post-crumb .crumb-copy');
            return btn ? btn.getBoundingClientRect().width : 999;
        }""")

        assert copy_w <= 30, (
            f'Copy button must be ≤ 30px wide, got {copy_w}px. '
            f'It should be flex-shrink:0 with no flex-grow.'
        )
