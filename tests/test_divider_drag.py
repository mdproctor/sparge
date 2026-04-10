"""
Tests for the split-pane divider drag behaviour.

The divider separates the HTML viewer (left, contains an iframe) from the MD
viewer (right).  The iframe swallows mousemove events when the cursor moves
over it, which causes leftward drags to stall — the divider moves right fine
but freezes or snaps back when dragging left into the iframe area.

Fix: disable pointer-events on the iframe during a drag and restore them on
mouseup, so the parent document's mousemove handler always fires.

Requires server running on localhost:9000.
"""
from pathlib import Path
import sys
import pytest

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

SERVER  = 'http://localhost:9000'
APP_URL = f'{SERVER}/ui/index.html'

try:
    from playwright.sync_api import sync_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False

import requests


@pytest.fixture(scope='module')
def server():
    try:
        requests.get(f'{SERVER}/api/projects', timeout=3).raise_for_status()
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
        pg.wait_for_function("() => document.querySelectorAll('.pi').length > 0", timeout=20000)
        # Select a post so the iframe loads content
        pg.locator('.pi').first.click()
        pg.wait_for_timeout(1200)
        yield pg
        ctx.close()
        browser.close()


def _divider_x(pg) -> float:
    return pg.evaluate("() => document.getElementById('divider').getBoundingClientRect().left")


def _html_panel_width_pct(pg) -> float:
    return pg.evaluate("""() => {
        const panels = document.getElementById('panels');
        const hp = document.getElementById('html-panel');
        return hp.getBoundingClientRect().width / panels.getBoundingClientRect().width * 100;
    }""")


class TestDividerDrag:
    """Split-pane divider must respond correctly to both left and right drags."""

    def test_drag_right_expands_html_panel(self, page):
        """Dragging the divider right must widen the HTML panel."""
        pg = page
        before = _html_panel_width_pct(pg)
        div_x = _divider_x(pg)
        cy = pg.evaluate("() => document.getElementById('divider').getBoundingClientRect().top + 50")

        pg.mouse.move(div_x + 2, cy)
        pg.mouse.down()
        pg.mouse.move(div_x + 100, cy, steps=20)
        pg.mouse.up()
        pg.wait_for_timeout(100)

        after = _html_panel_width_pct(pg)
        assert after > before + 3, (
            f'Dragging divider right did not expand HTML panel. '
            f'Before: {before:.1f}%, After: {after:.1f}%'
        )

    def test_drag_left_shrinks_html_panel(self, page):
        """Dragging the divider left must shrink the HTML panel.

        Bug: the HTML panel contains an iframe. When the mouse moves left into
        the iframe area, the iframe captures mousemove events and the parent
        document handler stops firing — the divider freezes.

        Fix: set pointer-events:none on the iframe on mousedown, restore on mouseup.
        """
        pg = page
        # First drag right to give room to drag back left
        div_x = _divider_x(pg)
        cy = pg.evaluate("() => document.getElementById('divider').getBoundingClientRect().top + 50")

        # Ensure we're at ~60% first
        pg.mouse.move(div_x + 2, cy)
        pg.mouse.down()
        pg.mouse.move(div_x + 80, cy, steps=15)
        pg.mouse.up()
        pg.wait_for_timeout(100)

        before = _html_panel_width_pct(pg)
        div_x = _divider_x(pg)

        # Now drag left — mouse will pass over the iframe
        pg.mouse.move(div_x + 2, cy)
        pg.mouse.down()
        pg.mouse.move(div_x - 120, cy, steps=30)
        pg.mouse.up()
        pg.wait_for_timeout(100)

        after = _html_panel_width_pct(pg)
        assert after < before - 3, (
            f'Dragging divider left did not shrink HTML panel — iframe swallowed '
            f'the mousemove events so the divider froze. '
            f'Before: {before:.1f}%, After: {after:.1f}%. '
            f'Fix: set pointer-events:none on #orig-frame during mousedown and '
            f'restore on mouseup.'
        )

    def test_iframe_pointer_events_disabled_during_drag(self, page):
        """During a drag, the iframe must have pointer-events:none so it
        does not swallow mousemove events from the parent document."""
        pg = page
        div_x = _divider_x(pg)
        cy = pg.evaluate("() => document.getElementById('divider').getBoundingClientRect().top + 50")

        # Start a drag and check pointer-events mid-drag
        pg.mouse.move(div_x + 2, cy)
        pg.mouse.down()
        pg.mouse.move(div_x - 20, cy, steps=5)

        pe = pg.evaluate("() => getComputedStyle(document.getElementById('orig-frame')).pointerEvents")

        pg.mouse.up()

        assert pe == 'none', (
            f'During drag, #orig-frame pointer-events should be "none" to prevent '
            f'the iframe from swallowing mousemove events. Got: {pe!r}. '
            f'Fix: in the mousedown handler on #divider, set '
            f'document.getElementById("orig-frame").style.pointerEvents = "none" '
            f'and restore to "" in the mouseup handler.'
        )

    def test_iframe_pointer_events_restored_after_drag(self, page):
        """After drag ends, iframe must have pointer-events restored."""
        pg = page
        div_x = _divider_x(pg)
        cy = pg.evaluate("() => document.getElementById('divider').getBoundingClientRect().top + 50")

        pg.mouse.move(div_x + 2, cy)
        pg.mouse.down()
        pg.mouse.move(div_x + 50, cy, steps=10)
        pg.mouse.up()
        pg.wait_for_timeout(100)

        pe = pg.evaluate("() => getComputedStyle(document.getElementById('orig-frame')).pointerEvents")
        assert pe != 'none', (
            f'After drag ends, #orig-frame pointer-events must be restored (not "none"). '
            f'Got: {pe!r}. Fix: in the mouseup handler, clear the inline style.'
        )
