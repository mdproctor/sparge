"""
Playwright tests: scroll sync quality between HTML and MD panels.

The sync mechanism (buildScrollAnchors) matches h2/h3 headings by text between
the HTML iframe and #md-wrap.  When the MD has unbalanced fences (as with the
DocBook example pattern), all headings after the first unclosed fence render
inside a <code> block — they are not real heading elements — so no anchors are
built for the second half of the document.  The result: HTML scrolling to 80%
leaves the MD panel stuck at a much lower position.

This test proves the sync quality for:
  1. BEFORE fix: MD has unbalanced fences → few/no anchors → poor sync
  2. AFTER fix:  MD regenerated with clean fences → headings match → good sync

Discipline: test written FIRST (will fail for broken MD), fix applied (regenerate
the post), test should then pass.

Run with server on localhost:9000:
  python3 -m pytest tests/test_scroll_sync.py -v
"""
import pytest

SERVER  = 'http://localhost:9000'
APP_URL = SERVER + '/ui/index.html'
API     = SERVER + '/api'

# The specific post known to have DocBook examples with broken fences
TARGET_SLUG = '2013-10-31-configuration-and-convention-based-building-and-utilization'

# How much deviation in scroll percentage we tolerate (0.25 = 25%)
SYNC_TOLERANCE = 0.25


@pytest.fixture(scope='module')
def session():
    try:
        import requests
        s = requests.Session()
        s.get(f'{API}/projects', timeout=3).raise_for_status()
        # Ensure KIE project is active
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


def open_post(page, slug):
    """Select the post, wait for iframe and MD to fully load."""
    page.locator(f'[data-slug="{slug}"]').click()
    # Wait for iframe to load the HTML
    page.wait_for_function(
        f"""() => {{
            const f = document.getElementById('orig-frame');
            return f && f.src && f.src.includes('{slug}') &&
                   f.contentDocument && f.contentDocument.readyState === 'complete' &&
                   f.contentDocument.querySelector('body') !== null;
        }}""",
        timeout=10000,
    )
    # Wait for md-wrap to have rendered content
    page.wait_for_function(
        "() => document.getElementById('md-wrap')?.children.length > 0",
        timeout=8000,
    )
    # Let buildScrollAnchors() fire (it runs in the iframe load event)
    page.wait_for_timeout(800)


def scroll_state(page):
    """Return scroll percentages and anchor count for both panels."""
    return page.evaluate("""() => {
        const frame  = document.getElementById('orig-frame');
        const mdBody = document.getElementById('md-panel-body');
        const iWin   = frame.contentWindow;
        const iDoc   = frame.contentDocument;

        const htmlScroll = iWin.scrollY || 0;
        const htmlMax    = Math.max(0, iDoc.documentElement.scrollHeight - iWin.innerHeight);
        const mdScroll   = mdBody.scrollTop || 0;
        const mdMax      = Math.max(0, mdBody.scrollHeight - mdBody.clientHeight);

        // Count scroll anchors built by buildScrollAnchors()
        // scrollAnchors is declared with 'let' so not on window — use the getter
        const anchors = typeof getScrollAnchors === 'function' ? getScrollAnchors() : [];

        // Count h2/h3/h4 headings in md-wrap (outside .fm-card)
        // This post uses h4 for content sections (DocBook structure)
        const mdHeadings = [...document.querySelectorAll('#md-wrap h2, #md-wrap h3, #md-wrap h4')]
            .filter(el => !el.closest('.fm-card')).length;

        return {
            html_pct:    htmlMax > 0 ? htmlScroll / htmlMax : 0,
            md_pct:      mdMax   > 0 ? mdScroll   / mdMax   : 0,
            html_scroll: htmlScroll,
            html_max:    htmlMax,
            md_scroll:   mdScroll,
            md_max:      mdMax,
            anchor_count: anchors.length,
            md_heading_count: mdHeadings,
        };
    }""")


def scroll_html_to(page, fraction: float):
    """Scroll the HTML iframe to a given fraction (0–1) of its scrollable height."""
    page.evaluate(f"""() => {{
        const f = document.getElementById('orig-frame');
        const maxScroll = f.contentDocument.documentElement.scrollHeight
                        - f.contentWindow.innerHeight;
        f.contentWindow.scrollTo(0, maxScroll * {fraction});
    }}""")
    page.wait_for_timeout(400)  # let sync settle


# ── Anchor quality ────────────────────────────────────────────────────────────

class TestScrollAnchorQuality:
    """The number of scroll anchors reflects how well headings match.
    Broken MD (unbalanced fences) → headings inside code block → few anchors.
    Fixed MD (properly rendered) → headings visible → more anchors.
    """

    def test_scroll_anchors_exist(self, page):
        open_post(page, TARGET_SLUG)
        state = scroll_state(page)
        assert state['anchor_count'] >= 2, (
            f'Must have at least 2 anchors (start + end). Got: {state["anchor_count"]}')

    def test_md_headings_visible_outside_code_blocks(self, page):
        """Heading elements in #md-wrap must be real rendered headings, not trapped
        inside a code block due to unbalanced fences.

        This post's sections are h4 (DocBook structure).  The check covers h2+h3+h4
        so it catches both the unbalanced-fence case (0 headings) and the h4-only case.

        This test FAILS for the broken MD (fences unclosed → headings in code block)
        and PASSES after regeneration + buildScrollAnchors extended to h4.
        """
        open_post(page, TARGET_SLUG)
        count = page.evaluate("""() =>
            [...document.querySelectorAll('#md-wrap h2, #md-wrap h3, #md-wrap h4')]
            .filter(el => !el.closest('.fm-card')).length
        """)
        assert count >= 3, (
            f'Expected ≥3 rendered h2/h3/h4 headings in #md-wrap outside code blocks, '
            f'got {count}.\n'
            f'If 0 or 1: the MD likely has unbalanced fences causing all content after '
            f'the first unclosed fence to render as a code block, hiding all headings. '
            f'Regenerate the post to fix.')

    def test_anchor_count_reflects_heading_matches(self, page):
        """More headings → more anchor points → better sync.
        Broken MD has few matching headings so anchors ≈ 2 (just start + end).
        Fixed MD should have significantly more.
        """
        open_post(page, TARGET_SLUG)
        state = scroll_state(page)
        assert state['anchor_count'] >= 4, (
            f'Expected ≥4 scroll anchors (start + matched headings + end), '
            f'got {state["anchor_count"]}. '
            f'Too few anchors means the sync falls back to purely proportional '
            f'mapping, which is inaccurate when HTML and MD have different structures.')


# ── Sync accuracy at multiple scroll positions ─────────────────────────────────

class TestScrollSyncAccuracy:
    """Scrolling the HTML panel should move the MD panel to approximately the
    same relative position.  With broken fences, the second half of the post
    has no anchors so MD stays misaligned.

    These tests FAIL for the broken MD and PASS after regeneration.
    """

    def _check_sync_at(self, page, fraction: float, label: str):
        open_post(page, TARGET_SLUG)
        scroll_html_to(page, fraction)
        state = scroll_state(page)
        deviation = abs(state['html_pct'] - state['md_pct'])
        assert deviation <= SYNC_TOLERANCE, (
            f'Scroll sync at {label} ({fraction:.0%}) is off:\n'
            f'  HTML at {state["html_pct"]:.1%},  MD at {state["md_pct"]:.1%}\n'
            f'  Deviation: {deviation:.1%} (tolerance: {SYNC_TOLERANCE:.0%})\n'
            f'  Anchors: {state["anchor_count"]},  '
            f'  MD headings: {state["md_heading_count"]}\n'
            f'This suggests the MD has broken rendering (e.g. unbalanced fences '
            f'causing headings to be inside a code block). Regenerate the post.')

    def test_sync_at_30_percent(self, page):
        """At 30% HTML scroll, MD must be within 25% of that position."""
        self._check_sync_at(page, 0.30, '30%')

    def test_sync_at_60_percent(self, page):
        """At 60% HTML scroll, MD must be within 25% of that position."""
        self._check_sync_at(page, 0.60, '60%')

    def test_sync_at_80_percent(self, page):
        """At 80% HTML scroll — where the broken anchors hurt the most — MD must
        stay within 25%.  This is the most likely to fail with broken fences."""
        self._check_sync_at(page, 0.80, '80%')


# ── Regression: after regeneration sync quality improves ──────────────────────

class TestSyncAfterRegeneration:
    """After calling generate-md (which applies the DocBook link unwrapping fix),
    the MD should render correctly, headings should be visible, and sync should
    work within tolerance at all positions.
    """

    def test_regeneration_improves_heading_count(self, page, session):
        """After regeneration, #md-wrap should have ≥3 visible h2/h3 headings."""
        # Regenerate with the fixed convert_post.py
        r = session.post(f'{API}/posts/{TARGET_SLUG}/generate-md')
        assert r.status_code == 200, f'generate-md failed: {r.status_code}'

        # Reload page to pick up new MD
        page.reload(wait_until='networkidle')
        page.wait_for_selector('.pi', timeout=10000)
        open_post(page, TARGET_SLUG)

        state = scroll_state(page)
        assert state['md_heading_count'] >= 3, (
            f'After regeneration, expected ≥3 visible headings in #md-wrap. '
            f'Got {state["md_heading_count"]}. '
            f'The DocBook link unwrapping fix may not have been applied correctly.')

    def test_sync_at_80_percent_after_regeneration(self, page, session):
        """After regeneration, sync at 80% should be within tolerance."""
        open_post(page, TARGET_SLUG)
        scroll_html_to(page, 0.80)
        state = scroll_state(page)
        deviation = abs(state['html_pct'] - state['md_pct'])
        assert deviation <= SYNC_TOLERANCE, (
            f'After regeneration, sync at 80% is still off:\n'
            f'  HTML {state["html_pct"]:.1%}, MD {state["md_pct"]:.1%}, '
            f'deviation {deviation:.1%}. '
            f'Anchors: {state["anchor_count"]}')
