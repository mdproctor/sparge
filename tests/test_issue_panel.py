"""
Playwright tests for the issue panel: scrolling and drag-to-resize.

Tests:
  - Overflow / scrollbar: posts with 3, 5, 7, 10 issues — scroll appears only
    when content overflows the current panel height.
  - Drag-to-resize: dragging the handle up increases panel height; dragging
    down decreases it; height is clamped to [80, 700]; height persists in
    localStorage across page reloads.
  - Scrollbar visibility: overflow-y:auto means the scrollbar is absent when
    content fits and present when it overflows.

Synthetic fixture: 4 posts, one author, each with a different number of
HTML issues (3, 5, 7, 10). MD issues are added to the 10-issue post too
so we can verify both columns can scroll independently.

Run with server on localhost:9000:
  python3 -m pytest tests/test_issue_panel.py -v

Requires: pip install playwright && playwright install chromium
"""
import json
import shutil
import uuid
from pathlib import Path

import pytest

SERVER  = 'http://localhost:9000'
APP_URL = SERVER + '/ui/index.html'
API     = SERVER + '/api'

ISSUE_COUNTS = [3, 5, 7, 10]
PANEL_DEFAULT_H = 200   # px — matches CSS
PANEL_MIN = 80
PANEL_MAX = 700
STORE_KEY = 'sparge-issue-panel-h'

# ── Synthetic state ────────────────────────────────────────────────────────────

_TYPES = ['external_image', 'data_placeholder', 'tracking_pixel',
          'noscript_remnant', 'empty_embed']
_MD_CHECKS = ['missing_fm_field', 'broken_links', 'html_entities_in_body',
              'empty_code_blocks', 'wordpress_junk']


def _html_iss(i):
    t = _TYPES[i % len(_TYPES)]
    return {'type': t, 'check': t, 'level': 'WARN' if i % 3 else 'ERROR',
            'detail': f'Issue #{i + 1}: {t} at element [{i}]', 'selector': None}


def _md_iss(i):
    c = _MD_CHECKS[i % len(_MD_CHECKS)]
    return {'check': c, 'level': 'WARN' if i % 2 else 'ERROR',
            'detail': f'MD issue #{i + 1}: {c}', 'selector': None}


def make_panel_state():
    ts = '2026-01-01T00:00:00'
    state = {}
    for n in ISSUE_COUNTS:
        slug = f'2020-01-{n:02d}-post-{n}-issues'
        entry = {
            'slug': slug,
            'title': f'Post with {n} HTML issues',
            'date': f'2020-01-{n:02d}',
            'author': 'Panel Test Author',
            'original_url': f'http://example.com/{slug}',
            'ingested_at': ts,
            'reviewed': False,
            'html': {
                'hash': uuid.uuid4().hex[:12],
                'issues': [_html_iss(i) for i in range(n)],
                'checked_at': ts,
            },
        }
        # The 10-issue post also gets 10 MD issues so we can test both columns
        if n == 10:
            entry['md'] = {
                'generated_at': ts,
                'html_hash': 'aaa000',
                'issues': [_md_iss(i) for i in range(10)],
                'staged': False,
                'validated_at': ts,
            }
        state[slug] = entry
    return state


SLUGS = {n: f'2020-01-{n:02d}-post-{n}-issues' for n in ISSUE_COUNTS}


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

    tmp = tmp_path_factory.mktemp('panel_test')
    uid = uuid.uuid4().hex[:8]

    r = session.post(f'{API}/projects', json={
        'name': f'panel-{uid}',
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

    (proj_dir / 'state.json').write_text(json.dumps(make_panel_state(), indent=2))
    (tmp / 'posts').mkdir(exist_ok=True)
    (tmp / 'md').mkdir(exist_ok=True)

    session.post(f'{API}/projects/{pid}/activate')

    posts = session.get(f'{API}/posts').json()
    assert len(posts) == len(ISSUE_COUNTS), f'Expected {len(ISSUE_COUNTS)} posts, got {len(posts)}'

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

def select_post(page, n: int):
    """Click the post with n issues and wait for the panel to be ready."""
    slug = SLUGS[n]
    page.locator(f'[data-slug="{slug}"]').click()
    page.wait_for_timeout(200)


def open_issues(page):
    """Open the issues panel if not already open."""
    btn = page.locator('#btn-issues')
    if 'active' not in (btn.get_attribute('class') or ''):
        btn.click()
        page.wait_for_timeout(150)


def close_issues(page):
    """Close the issues panel if open."""
    btn = page.locator('#btn-issues')
    if 'active' in (btn.get_attribute('class') or ''):
        btn.click()
        page.wait_for_timeout(150)


def panel_height(page) -> int:
    return int(page.evaluate(
        "document.getElementById('issue-panel').getBoundingClientRect().height"
    ))


def html_col_scrollable(page) -> bool:
    """True if the HTML issue column content overflows its container."""
    return page.evaluate("""() => {
        const col = document.querySelector('#issue-panel .issue-col');
        return col ? col.scrollHeight > col.clientHeight : false;
    }""")


def md_col_scrollable(page) -> bool:
    """True if the MD issue column content overflows its container."""
    return page.evaluate("""() => {
        const cols = document.querySelectorAll('#issue-panel .issue-col');
        const col = cols[1];
        return col ? col.scrollHeight > col.clientHeight : false;
    }""")


def html_col_scroll_top(page) -> int:
    return page.evaluate(
        "document.querySelector('#issue-panel .issue-col').scrollTop"
    )


def set_html_col_scroll(page, value: int):
    page.evaluate(
        f"document.querySelector('#issue-panel .issue-col').scrollTop = {value}"
    )


def get_stored_height(page) -> int | None:
    val = page.evaluate(f"localStorage.getItem('{STORE_KEY}')")
    return int(val) if val is not None else None


def clear_stored_height(page):
    page.evaluate(f"localStorage.removeItem('{STORE_KEY}')")


def drag_resize_handle(page, delta_y: int):
    """Drag the resize handle by delta_y pixels (negative = up = bigger panel)."""
    handle = page.locator('#issue-resize-handle')
    bb = handle.bounding_box()
    assert bb is not None, 'Resize handle not found'
    cx = bb['x'] + bb['width'] / 2
    cy = bb['y'] + bb['height'] / 2
    page.mouse.move(cx, cy)
    page.mouse.down()
    page.mouse.move(cx, cy + delta_y, steps=10)
    page.mouse.up()
    page.wait_for_timeout(100)


# ── Tests: resize handle presence ─────────────────────────────────────────────

class TestResizeHandlePresence:

    def test_resize_handle_exists(self, page):
        handle = page.locator('#issue-resize-handle')
        assert handle.count() == 1, 'Resize handle element must exist'

    def test_resize_handle_is_first_child_of_panel(self, page):
        result = page.evaluate("""() => {
            const panel = document.getElementById('issue-panel');
            return panel.children[0].id === 'issue-resize-handle';
        }""")
        assert result, 'Resize handle must be the first child of #issue-panel'

    def test_resize_handle_has_ns_resize_cursor(self, page):
        cursor = page.evaluate("""() =>
            window.getComputedStyle(document.getElementById('issue-resize-handle')).cursor
        """)
        assert cursor == 'ns-resize', f'Handle cursor should be ns-resize, got {cursor}'

    def test_resize_handle_visible_when_panel_open(self, page):
        select_post(page, 7)
        open_issues(page)
        handle = page.locator('#issue-resize-handle')
        assert handle.is_visible(), 'Resize handle should be visible when panel is open'


# ── Tests: scrollbar / overflow ────────────────────────────────────────────────

class TestScrollOverflow:
    """Verify overflow-y:auto means scrollbar appears only when needed."""

    def test_3_issues_no_overflow_at_default_height(self, page):
        """3 issues at 200px panel height — content should fit without scrolling."""
        close_issues(page)
        clear_stored_height(page)
        page.reload(wait_until='networkidle')
        page.wait_for_selector('.pi', timeout=10000)

        select_post(page, 3)
        open_issues(page)
        assert not html_col_scrollable(page), (
            '3 issues should fit in the panel without overflow at default height')

    def test_10_issues_overflows_at_default_height(self, page):
        """10 issues at 200px panel height — content must overflow."""
        close_issues(page)
        clear_stored_height(page)
        page.reload(wait_until='networkidle')
        page.wait_for_selector('.pi', timeout=10000)

        select_post(page, 10)
        open_issues(page)
        assert html_col_scrollable(page), (
            '10 issues must overflow the panel at default 200px height')

    def test_7_issues_overflows_at_minimum_height(self, page):
        """7 issues fit at 200px but must overflow when panel is shrunk to ~90px."""
        close_issues(page)
        clear_stored_height(page)
        page.reload(wait_until='networkidle')
        page.wait_for_selector('.pi', timeout=10000)

        select_post(page, 7)
        open_issues(page)
        # Shrink the panel so only ~3 rows fit
        page.evaluate("document.getElementById('issue-panel').style.height = '90px'")
        page.wait_for_timeout(100)
        assert html_col_scrollable(page), (
            '7 issues must overflow the panel when it is shrunk to 90px')

    def test_5_issues_overflow_depends_on_row_height(self, page):
        """5 issues: record whether it overflows — then verify state is consistent."""
        close_issues(page)
        clear_stored_height(page)
        page.reload(wait_until='networkidle')
        page.wait_for_selector('.pi', timeout=10000)

        select_post(page, 5)
        open_issues(page)
        overflows = html_col_scrollable(page)
        # Consistency check: if it overflows, scrollHeight > clientHeight
        result = page.evaluate("""() => {
            const col = document.querySelector('#issue-panel .issue-col');
            return { sh: col.scrollHeight, ch: col.clientHeight };
        }""")
        if overflows:
            assert result['sh'] > result['ch'], 'scrollHeight > clientHeight when overflowing'
        else:
            assert result['sh'] <= result['ch'], 'scrollHeight <= clientHeight when not overflowing'

    def test_3_issues_no_scrollbar_visible(self, page):
        """overflow-y:auto — no scrollbar element when content fits."""
        close_issues(page)
        clear_stored_height(page)
        page.reload(wait_until='networkidle')
        page.wait_for_selector('.pi', timeout=10000)

        select_post(page, 3)
        open_issues(page)
        # clientWidth == offsetWidth means no scrollbar gutter
        result = page.evaluate("""() => {
            const col = document.querySelector('#issue-panel .issue-col');
            return col.clientWidth === col.offsetWidth;
        }""")
        assert result, '3 issues: no scrollbar gutter should be allocated when content fits'

    def test_10_issues_can_scroll_to_bottom(self, page):
        """With 10 issues overflowing, scrolling to bottom should reveal last issue."""
        close_issues(page)
        clear_stored_height(page)
        page.reload(wait_until='networkidle')
        page.wait_for_selector('.pi', timeout=10000)

        select_post(page, 10)
        open_issues(page)

        # Scroll to bottom
        page.evaluate("""() => {
            const col = document.querySelector('#issue-panel .issue-col');
            col.scrollTop = col.scrollHeight;
        }""")
        page.wait_for_timeout(100)

        # Last .irow should be visible
        rows = page.locator('#html-issue-list .irow').all()
        assert len(rows) == 10, f'Expected 10 issue rows, got {len(rows)}'
        last_row_visible = page.evaluate("""() => {
            const col = document.querySelector('#issue-panel .issue-col');
            const rows = col.querySelectorAll('.irow');
            const last = rows[rows.length - 1];
            const cr = last.getBoundingClientRect();
            const pr = col.getBoundingClientRect();
            return cr.bottom <= pr.bottom + 2;  // 2px tolerance
        }""")
        assert last_row_visible, 'Last issue row should be visible after scrolling to bottom'

    def test_md_column_independently_scrollable_with_10_issues(self, page):
        """10-issue post has 10 MD issues too — MD column must scroll independently."""
        close_issues(page)
        clear_stored_height(page)
        page.reload(wait_until='networkidle')
        page.wait_for_selector('.pi', timeout=10000)

        select_post(page, 10)
        open_issues(page)

        assert md_col_scrollable(page), (
            'MD column with 10 issues must be independently scrollable')

        # Scroll MD column while HTML column stays at 0
        page.evaluate("""() => {
            const cols = document.querySelectorAll('#issue-panel .issue-col');
            cols[0].scrollTop = 0;
            cols[1].scrollTop = cols[1].scrollHeight;
        }""")
        page.wait_for_timeout(100)

        html_scroll = page.evaluate(
            "document.querySelectorAll('#issue-panel .issue-col')[0].scrollTop"
        )
        md_scroll = page.evaluate(
            "document.querySelectorAll('#issue-panel .issue-col')[1].scrollTop"
        )
        assert html_scroll == 0, 'HTML column scroll should be independent of MD column'
        assert md_scroll > 0, 'MD column should have scrolled'


# ── Tests: drag-to-resize ──────────────────────────────────────────────────────

class TestDragToResize:

    def _prepare(self, page, n=7):
        """Reset state, open panel for post with n issues."""
        close_issues(page)
        clear_stored_height(page)
        page.reload(wait_until='networkidle')
        page.wait_for_selector('.pi', timeout=10000)
        select_post(page, n)
        open_issues(page)

    def test_drag_up_increases_panel_height(self, page):
        self._prepare(page)
        h_before = panel_height(page)
        drag_resize_handle(page, -80)   # negative = drag up = bigger
        h_after = panel_height(page)
        assert h_after > h_before, (
            f'Dragging up should increase panel height. Before={h_before}, After={h_after}')

    def test_drag_down_decreases_panel_height(self, page):
        self._prepare(page)
        # First make the panel tall enough to drag down
        drag_resize_handle(page, -150)
        h_before = panel_height(page)
        drag_resize_handle(page, 80)    # positive = drag down = smaller
        h_after = panel_height(page)
        assert h_after < h_before, (
            f'Dragging down should decrease panel height. Before={h_before}, After={h_after}')

    def test_panel_height_cannot_go_below_minimum(self, page):
        self._prepare(page)
        # Drag far down — should clamp at PANEL_MIN
        drag_resize_handle(page, 600)
        h = panel_height(page)
        assert h >= PANEL_MIN, (
            f'Panel height should not go below {PANEL_MIN}px minimum, got {h}')

    def test_panel_height_cannot_exceed_maximum(self, page):
        self._prepare(page)
        # Drag far up — should clamp at PANEL_MAX
        drag_resize_handle(page, -800)
        h = panel_height(page)
        assert h <= PANEL_MAX, (
            f'Panel height should not exceed {PANEL_MAX}px maximum, got {h}')

    def test_drag_stores_height_in_localstorage(self, page):
        self._prepare(page)
        drag_resize_handle(page, -100)
        h = panel_height(page)
        stored = get_stored_height(page)
        assert stored is not None, 'Height should be stored in localStorage after drag'
        assert abs(stored - h) <= 2, (
            f'Stored height ({stored}) should match panel height ({h})')

    def test_stored_height_restored_on_reload(self, page):
        self._prepare(page)
        drag_resize_handle(page, -120)
        h_after_drag = panel_height(page)

        # Reload without clearing localStorage
        select_post(page, 7)
        open_issues(page)
        page.reload(wait_until='networkidle')
        page.wait_for_selector('.pi', timeout=10000)
        select_post(page, 7)
        open_issues(page)

        h_restored = panel_height(page)
        assert abs(h_restored - h_after_drag) <= 5, (
            f'Panel height should be restored from localStorage after reload. '
            f'Expected ~{h_after_drag}, got {h_restored}')

    def test_expanding_panel_removes_overflow_on_3_issue_post(self, page):
        """3 issues: start at default (no overflow). Expanding does not break anything."""
        self._prepare(page, n=3)
        assert not html_col_scrollable(page), '3 issues should not overflow at default height'
        drag_resize_handle(page, -100)
        assert not html_col_scrollable(page), '3 issues should not overflow after expanding panel'

    def test_expanding_panel_removes_overflow_on_10_issue_post(self, page):
        """10 issues overflow at default. After expanding enough, overflow should clear."""
        self._prepare(page, n=10)
        assert html_col_scrollable(page), '10 issues should overflow at default height'

        # Expand to max
        drag_resize_handle(page, -700)
        h = panel_height(page)
        assert h > PANEL_DEFAULT_H, 'Panel should have expanded'

        # At max height (700px) 10 rows of ~22px each = ~220px content — should fit
        if h >= 400:
            assert not html_col_scrollable(page), (
                f'10 issues should not overflow when panel is {h}px tall '
                f'(content ~220px). scrollHeight vs clientHeight mismatch.')

    def test_shrinking_panel_causes_overflow_on_7_issue_post(self, page):
        """7 issues: expand first (no overflow), then shrink to min (should overflow)."""
        self._prepare(page, n=7)
        # Expand fully — no overflow
        drag_resize_handle(page, -700)
        assert not html_col_scrollable(page), '7 issues should not overflow in a tall panel'

        # Shrink to minimum
        drag_resize_handle(page, 700)
        h = panel_height(page)
        assert h <= PANEL_MIN + 10, f'Panel should be near minimum, got {h}'
        assert html_col_scrollable(page), '7 issues must overflow in a very short panel'

    def test_handle_has_dragging_class_during_drag(self, page):
        """The handle gains .dragging during the mouse-down gesture."""
        self._prepare(page, n=5)
        handle = page.locator('#issue-resize-handle')
        bb = handle.bounding_box()
        cx = bb['x'] + bb['width'] / 2
        cy = bb['y'] + bb['height'] / 2

        page.mouse.move(cx, cy)
        page.mouse.down()
        page.wait_for_timeout(50)

        classes = handle.get_attribute('class') or ''
        page.mouse.up()  # release before asserting so we clean up

        assert 'dragging' in classes, (
            f'Handle should have .dragging class during mouse-down. Got: {classes!r}')

    def test_handle_loses_dragging_class_after_release(self, page):
        self._prepare(page, n=5)
        drag_resize_handle(page, -50)
        classes = page.locator('#issue-resize-handle').get_attribute('class') or ''
        assert 'dragging' not in classes, (
            'Handle should not retain .dragging class after mouse-up')


# ── Tests: issue row counts ────────────────────────────────────────────────────

class TestIssueRowCounts:
    """Verify the correct number of .irow elements are rendered for each post."""

    def _open_post(self, page, n):
        close_issues(page)
        clear_stored_height(page)
        page.reload(wait_until='networkidle')
        page.wait_for_selector('.pi', timeout=10000)
        select_post(page, n)
        open_issues(page)

    def test_3_issue_post_renders_3_rows(self, page):
        self._open_post(page, 3)
        count = page.locator('#html-issue-list .irow').count()
        assert count == 3, f'Expected 3 HTML issue rows, got {count}'

    def test_5_issue_post_renders_5_rows(self, page):
        self._open_post(page, 5)
        count = page.locator('#html-issue-list .irow').count()
        assert count == 5, f'Expected 5 HTML issue rows, got {count}'

    def test_7_issue_post_renders_7_rows(self, page):
        self._open_post(page, 7)
        count = page.locator('#html-issue-list .irow').count()
        assert count == 7, f'Expected 7 HTML issue rows, got {count}'

    def test_10_issue_post_renders_10_html_rows(self, page):
        self._open_post(page, 10)
        count = page.locator('#html-issue-list .irow').count()
        assert count == 10, f'Expected 10 HTML issue rows, got {count}'

    def test_10_issue_post_renders_10_md_rows(self, page):
        self._open_post(page, 10)
        count = page.locator('#md-issue-list .irow').count()
        assert count == 10, f'Expected 10 MD issue rows, got {count}'

    def test_3_issue_post_md_col_shows_no_issues_message(self, page):
        self._open_post(page, 3)
        # 3-issue post has no MD issues — should show placeholder text
        no_iss = page.locator('#md-issue-list .no-iss')
        assert no_iss.count() > 0, 'MD column should show "no issues" message for post with no MD issues'
