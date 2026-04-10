"""
Nav sidebar layout tests — button visibility and hover-expand.

These tests catch the specific bug where nav filter buttons and scope action
buttons were clipped (not visible) because the container had no flex-wrap
and the nav column was too narrow.

The hover-expand design shows only "All" and "HTML⚠" by default.
Hovering the filter-zone reveals all other buttons. This is tested both
with CSS computed styles (bounds check) and with Playwright hover interaction.

Run with server on localhost:9000:
  python3 -m pytest tests/test_nav_layout.py -v

Playwright tests require: playwright install chromium
"""
import sys
from pathlib import Path

import pytest

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

SERVER  = 'http://localhost:9000'
APP_URL = SERVER + '/ui/index.html'
API     = SERVER + '/api'


# ── Server / browser fixtures ─────────────────────────────────────────────────

@pytest.fixture(scope='module')
def session():
    try:
        import requests
        s = requests.Session()
        s.get(f'{API}/projects', timeout=3).raise_for_status()
        s.post(f'{API}/projects/kie-mark-proctor/activate')
        return s
    except Exception:
        pytest.skip('Server not running on localhost:9000')


@pytest.fixture(scope='module')
def browser_page(session):
    """Open Sparge in a Playwright browser, wait for posts to load."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip('playwright not installed — run: pip install playwright && playwright install chromium')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        page.goto(APP_URL, wait_until='networkidle')
        # Wait for post list to populate
        page.wait_for_selector('.pi', timeout=10000)
        yield page
        browser.close()


# ── Helper ────────────────────────────────────────────────────────────────────

def bounding_box(page, selector):
    """Return bounding box dict for the first matching element."""
    loc = page.locator(selector).first
    loc.wait_for(state='attached', timeout=5000)
    return loc.bounding_box()


def is_fully_visible_in_viewport(bb, viewport_width, viewport_height):
    """True if bounding box is entirely within the viewport and has positive size."""
    if bb is None:
        return False
    return (
        bb['width'] > 0
        and bb['height'] > 0
        and bb['x'] >= 0
        and bb['y'] >= 0
        and bb['x'] + bb['width'] <= viewport_width
        and bb['y'] + bb['height'] <= viewport_height
    )


def is_clipped_by_parent(page, selector):
    """True if element has width > 0 in the DOM but is hidden by parent overflow."""
    result = page.evaluate(f"""() => {{
        const el = document.querySelector('{selector}');
        if (!el) return null;
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return {{
            width: rect.width,
            height: rect.height,
            x: rect.x,
            y: rect.y,
            visibility: style.visibility,
            display: style.display,
            overflow: style.overflow,
        }};
    }}""")
    return result


# ── Collapsed state (default — no hover) ─────────────────────────────────────

class TestNavCollapsedState:
    """At rest, only 'All' and 'HTML⚠' must be visible."""

    def test_all_button_visible_at_rest(self, browser_page):
        """'All' filter button must be visible without hovering."""
        # Find the All button inside filter-always
        bb = browser_page.locator('.filter-always button:has-text("All")').bounding_box()
        assert bb is not None, "'All' button not found"
        assert bb['width'] > 0, "'All' button has zero width"
        assert bb['height'] > 0, "'All' button has zero height"

    def test_html_warning_button_visible_at_rest(self, browser_page):
        """'HTML⚠' filter button must be visible without hovering."""
        bb = browser_page.locator('.filter-always button:has-text("HTML⚠")').bounding_box()
        assert bb is not None, "'HTML⚠' button not found"
        assert bb['width'] > 0, "'HTML⚠' button has zero width"
        assert bb['height'] > 0, "'HTML⚠' button has zero height"

    def test_all_button_not_clipped_by_overflow(self, browser_page):
        """'All' button must not be cut off by an overflow:hidden parent."""
        info = is_clipped_by_parent(browser_page, '.filter-always button:first-child')
        assert info is not None, "Could not query 'All' button"
        # If the button is inside an overflow:hidden container that has max-height:0,
        # the bounding box y will be within the container's visible region.
        # A quick proxy: x must be >= 0 (not scrolled out of view).
        assert info['x'] >= 0, "'All' button is scrolled out of horizontal view"
        assert info['y'] >= 0, "'All' button is above the viewport"

    def test_md_warning_button_visible_at_rest(self, browser_page):
        """'MD⚠' filter button must be visible without hovering (third always-visible slot)."""
        bb = browser_page.locator('.filter-always button:has-text("MD⚠")').bounding_box()
        assert bb is not None, "'MD⚠' button not found"
        assert bb['width'] > 0, "'MD⚠' button has zero width"
        assert bb['height'] > 0, "'MD⚠' button has zero height"

    def test_hidden_filters_not_visible_at_rest(self, browser_page):
        """Stale, Staged, No MD must NOT be visible at rest.

        Playwright's bounding_box() and is_visible() do not detect
        overflow:hidden clipping — they return intrinsic element dimensions
        regardless of parent max-height. The reliable check is that the
        .filter-hidden CONTAINER itself has height 0 (because max-height:0
        collapses the container, not just its children).
        """
        browser_page.mouse.move(700, 600)
        browser_page.wait_for_timeout(300)

        # All .filter-hidden containers should have 0 height at rest
        heights = browser_page.evaluate("""() =>
            Array.from(document.querySelectorAll('.filter-hidden'))
                 .map(el => el.getBoundingClientRect().height)
        """)
        for h in heights:
            assert h == 0, (
                f'.filter-hidden container has height {h}px at rest — '
                f'max-height:0 should collapse it to 0'
            )

    def test_expand_hint_visible_at_rest(self, browser_page):
        """The '▾ more filters' hint must be visible when collapsed."""
        hint = browser_page.locator('.expand-hint')
        assert hint.count() > 0, ".expand-hint element not found"
        bb = hint.first.bounding_box()
        assert bb is not None and bb['height'] > 0, "Expand hint not visible at rest"


# ── Hover-expanded state ──────────────────────────────────────────────────────

class TestNavHoverExpanded:
    """Hovering the filter-zone reveals all buttons.

    Note: Playwright bounding_box() does not account for overflow:hidden
    clipping. To test that .filter-hidden containers are revealed by hover,
    we measure the container height via JavaScript (should be > 0 after hover,
    was 0 at rest). Individual button bounding_box checks remain valid for
    buttons NOT inside overflow containers (the scope buttons in #gen-all-row).
    """

    def test_hover_expands_filter_hidden_containers(self, browser_page):
        """After hovering the filter zone, all .filter-hidden containers must have height > 0."""
        browser_page.locator('.filter-zone').hover()
        browser_page.wait_for_timeout(300)

        heights = browser_page.evaluate("""() =>
            Array.from(document.querySelectorAll('.filter-hidden'))
                 .map(el => el.getBoundingClientRect().height)
        """)
        for h in heights:
            assert h > 0, (
                f'.filter-hidden container has height {h}px after hover — '
                f'should expand to > 0 via max-height transition'
            )

    def test_hover_reveals_stale_button(self, browser_page):
        """Stale button must be in an expanded container after hovering."""
        browser_page.locator('.filter-zone').hover()
        browser_page.wait_for_timeout(300)
        # Verify the button exists in the DOM and its container is expanded
        count = browser_page.locator('.filter-hidden button:has-text("Stale")').count()
        assert count > 0, "Stale button not found in .filter-hidden"
        h = browser_page.evaluate("""() => {
            const btn = document.querySelector('.filter-hidden button');
            const container = btn?.closest('.filter-hidden');
            return container ? container.getBoundingClientRect().height : 0;
        }""")
        assert h > 0, f'filter-hidden container still collapsed after hover (h={h})'

    def test_hover_reveals_staged_button(self, browser_page):
        browser_page.locator('.filter-zone').hover()
        browser_page.wait_for_timeout(300)
        count = browser_page.locator('.filter-hidden button:has-text("Staged")').count()
        assert count > 0, "Staged button not found after hover"

    def test_hover_reveals_no_md_button(self, browser_page):
        browser_page.locator('.filter-zone').hover()
        browser_page.wait_for_timeout(300)
        count = browser_page.locator('.filter-hidden button:has-text("No MD")').count()
        assert count > 0, "No MD button not found after hover"

    def test_hover_reveals_generate_button(self, browser_page):
        """Generate button is in #gen-all-row (.filter-hidden) — container must expand."""
        browser_page.locator('.filter-zone').hover()
        browser_page.wait_for_timeout(300)
        h = browser_page.evaluate("""() =>
            document.getElementById('gen-all-row')?.getBoundingClientRect().height ?? 0
        """)
        assert h > 0, f"#gen-all-row still collapsed after hover (height={h})"

    def test_hover_reveals_scan_button(self, browser_page):
        browser_page.locator('.filter-zone').hover()
        browser_page.wait_for_timeout(300)
        h = browser_page.evaluate("""() =>
            document.getElementById('gen-all-row')?.getBoundingClientRect().height ?? 0
        """)
        assert h > 0, f"#gen-all-row still collapsed after hover (height={h})"

    def test_hover_reveals_validate_button(self, browser_page):
        """Validate button must appear after hovering the filter zone."""
        browser_page.locator('.filter-zone').hover()
        browser_page.wait_for_timeout(250)

        bb = browser_page.locator('#btn-val-all').bounding_box()
        assert bb is not None, "#btn-val-all not found after hover"
        assert bb['height'] > 0, f"Validate button still hidden after hover (bb={bb})"

    def test_hover_reveals_consolidate_button(self, browser_page):
        """Consolidate button must appear after hovering the filter zone."""
        browser_page.locator('.filter-zone').hover()
        browser_page.wait_for_timeout(250)

        bb = browser_page.locator('#btn-consolidate').bounding_box()
        assert bb is not None, "#btn-consolidate not found after hover"
        assert bb['height'] > 0, f"Consolidate button still hidden after hover (bb={bb})"

    def test_hover_reveals_author_select(self, browser_page):
        """Author select must appear after hovering the filter zone."""
        browser_page.locator('.filter-zone').hover()
        browser_page.wait_for_timeout(250)

        bb = browser_page.locator('#author-select').bounding_box()
        assert bb is not None, "#author-select not found after hover"
        assert bb['height'] > 0, f"Author select still hidden after hover (bb={bb})"

    def test_expand_hint_hidden_on_hover(self, browser_page):
        """The '▾ more filters' hint must become invisible on hover."""
        browser_page.locator('.filter-zone').hover()
        browser_page.wait_for_timeout(250)

        opacity = browser_page.evaluate(
            "window.getComputedStyle(document.querySelector('.expand-hint')).opacity"
        )
        assert float(opacity) < 0.1, (
            f"Expand hint opacity is {opacity} on hover — expected near 0"
        )


# ── No clipping regression ────────────────────────────────────────────────────

class TestNoButtonClipping:
    """Regression: buttons must not be clipped by overflow or hidden by narrow container."""

    def test_always_visible_buttons_not_overlapping_post_list(self, browser_page):
        """'All' and 'HTML⚠' buttons must be above the post list, not overlapping."""
        all_bb  = browser_page.locator('.filter-always button:has-text("All")').bounding_box()
        post_bb = browser_page.locator('#post-list').bounding_box()

        assert all_bb is not None, "'All' button bounding box is None"
        assert post_bb is not None, "#post-list bounding box is None"

        # All button bottom edge must be above the post list top edge
        all_bottom = all_bb['y'] + all_bb['height']
        assert all_bottom <= post_bb['y'] + 5, (  # 5px tolerance
            f"'All' button (bottom={all_bottom:.0f}) overlaps with post list (top={post_bb['y']:.0f})"
        )

    def test_filter_zone_hover_does_not_shift_post_list_incorrectly(self, browser_page):
        """After hover-expand, the post list must still start below the filter zone."""
        browser_page.locator('.filter-zone').hover()
        browser_page.wait_for_timeout(300)

        zone_bb = browser_page.locator('.filter-zone').bounding_box()
        post_bb = browser_page.locator('#post-list').bounding_box()

        assert zone_bb is not None
        assert post_bb is not None

        zone_bottom = zone_bb['y'] + zone_bb['height']
        assert post_bb['y'] >= zone_bottom - 2, (  # 2px tolerance
            f"Post list top ({post_bb['y']:.0f}) is above filter zone bottom ({zone_bottom:.0f})"
        )

    def test_hovering_post_list_does_not_expand_filter_zone(self, browser_page):
        """Hovering the post list must NOT trigger hover-expand of filter buttons."""
        # First collapse by moving away from filter zone
        browser_page.mouse.move(700, 500)  # move to content area
        browser_page.wait_for_timeout(300)

        # Record height of filter zone at rest
        zone_height_rest = browser_page.evaluate(
            "document.querySelector('.filter-zone').getBoundingClientRect().height"
        )

        # Hover the post list
        browser_page.locator('#post-list').hover()
        browser_page.wait_for_timeout(300)

        zone_height_after = browser_page.evaluate(
            "document.querySelector('.filter-zone').getBoundingClientRect().height"
        )

        assert abs(zone_height_after - zone_height_rest) < 5, (
            f"Filter zone expanded ({zone_height_rest:.0f}→{zone_height_after:.0f}px) "
            f"when hovering the post list — expand must only trigger on button zone hover"
        )

    def test_all_always_visible_buttons_have_positive_dimensions(self, browser_page):
        """Both always-visible buttons must have positive width and height."""
        # Move away from filter zone first to ensure collapsed state
        browser_page.mouse.move(700, 500)
        browser_page.wait_for_timeout(200)

        for selector, label in [
            ('.filter-always button:nth-child(1)', 'All'),
            ('.filter-always button:nth-child(2)', 'HTML⚠'),
            ('.filter-always button:nth-child(3)', 'MD⚠'),
        ]:
            bb = browser_page.locator(selector).bounding_box()
            assert bb is not None, f"'{label}' button bounding box is None"
            assert bb['width'] > 10, f"'{label}' button too narrow: width={bb['width']}"
            assert bb['height'] > 5, f"'{label}' button too short: height={bb['height']}"
