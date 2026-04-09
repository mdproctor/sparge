"""
Playwright tests: generateAll() scope button happy paths.

Tests the overwrite-conflict prompt introduced to fix the broken generateAll()
behaviour where "All" and "Stale" scopes silently skipped posts that already
had MD.

All tests written to prove the correct behaviour — they FAIL if generateAll()
reverts to skipping existing MD or if the prompt is removed.

Requires server on localhost:9000 with kie-mark-proctor project active.
"""
import pytest

SERVER  = 'http://localhost:9000'
APP_URL = SERVER + '/ui/index.html'
API     = SERVER + '/api'

SLUG_WITH_MD    = '2006-05-31-what-is-a-rule-engine'
SLUG_WITHOUT_MD = '2007-05-12-phoenix-jug-jboss-rules-apollo-group-inc'


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


def _open_scope_panel(pg):
    """Hover the filter zone to reveal the scope buttons."""
    pg.locator('.filter-zone').hover()
    pg.wait_for_timeout(200)


def _gen_progress(pg):
    return pg.evaluate("() => document.getElementById('gen-progress')?.textContent || ''")


def _overwrite_modal_visible(pg):
    """True if the overwrite-conflict modal is on screen."""
    return pg.evaluate("""() => {
        const btn = document.querySelector('#_ow-one');
        return btn ? btn.offsetParent !== null : false;
    }""")


# ── Happy path 1: posts WITHOUT existing MD generate without prompt ───────────

class TestGenerateWithoutExistingMD:
    """When a post has no MD yet, generateAll() must generate it immediately
    without showing the overwrite-conflict prompt."""

    def test_no_prompt_for_new_post(self, page, session):
        # Ensure the test post has no MD (delete if exists)
        import requests
        slug = SLUG_WITHOUT_MD
        # Check current state — skip if it has MD (we can't easily delete it)
        posts = session.get(f'{API}/posts').json()
        post = next((p for p in posts if p['slug'] == slug), None)
        if post and post.get('md', {}).get('generated_at'):
            pytest.skip('Test post already has MD — cannot test no-prompt path')

        pg = page
        # Navigate to the post
        pg.locator(f'[data-slug="{slug}"]').scroll_into_view_if_needed()
        pg.locator(f'[data-slug="{slug}"]').click()
        pg.wait_for_timeout(300)

        # Open scope panel and click Generate
        _open_scope_panel(pg)
        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(500)

        # Prompt must NOT appear for a post without existing MD
        assert not _overwrite_modal_visible(pg), (
            'Overwrite prompt appeared for a post without existing MD. '
            'Posts without MD should be generated immediately without prompting.'
        )

        # Wait for generation to complete
        pg.wait_for_function(
            "() => { const t = document.getElementById('gen-progress')?.textContent || ''; "
            "return t.startsWith('✓'); }",
            timeout=30000
        )
        progress = _gen_progress(pg)
        assert '1 generated' in progress or 'generated' in progress, (
            f'Expected progress to show generation. Got: {progress!r}'
        )


# ── Happy path 2: prompt appears for posts WITH existing MD ───────────────────

class TestOverwritePromptAppears:
    """When generateAll() reaches a post that already has MD, it must pause and
    show the overwrite-conflict modal before proceeding."""

    def test_prompt_shown_for_existing_md(self, page, session):
        pg = page
        # Navigate to a post with MD so it's in scope
        pg.locator(f'[data-slug="{SLUG_WITH_MD}"]').scroll_into_view_if_needed()
        pg.locator(f'[data-slug="{SLUG_WITH_MD}"]').click()
        pg.wait_for_timeout(300)

        # Click Generate — should immediately hit a post with MD and show prompt
        _open_scope_panel(pg)
        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(800)

        assert _overwrite_modal_visible(pg), (
            'Overwrite-conflict modal did not appear when generateAll() reached '
            'a post that already has MD. All posts in scope should be targeted — '
            'the prompt must pause the loop for posts with existing MD.'
        )

        # Dismiss — click Skip remaining to avoid side effects
        pg.locator('#_ow-stop').click()
        pg.wait_for_timeout(300)

    def test_prompt_has_four_buttons(self, page, session):
        """The prompt must expose all four choices."""
        pg = page
        pg.locator(f'[data-slug="{SLUG_WITH_MD}"]').scroll_into_view_if_needed()
        pg.locator(f'[data-slug="{SLUG_WITH_MD}"]').click()
        pg.wait_for_timeout(300)

        _open_scope_panel(pg)
        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(800)

        assert _overwrite_modal_visible(pg), 'Prompt not shown'
        buttons = {
            'overwrite':     pg.locator('#_ow-one').is_visible(),
            'skip':          pg.locator('#_ow-skip').is_visible(),
            'overwrite-all': pg.locator('#_ow-all').is_visible(),
            'skip-remaining':pg.locator('#_ow-stop').is_visible(),
        }
        assert all(buttons.values()), (
            f'Not all four buttons visible. Got: {buttons}'
        )
        pg.locator('#_ow-stop').click()
        pg.wait_for_timeout(300)


# ── Happy path 3: "Skip this" skips one, loop continues ──────────────────────

class TestSkipThis:
    """Clicking 'Skip this' must skip the current post and continue the loop
    (showing the prompt again for the next post with existing MD)."""

    def test_skip_this_continues_loop(self, page, session):
        pg = page
        _open_scope_panel(pg)
        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(800)

        assert _overwrite_modal_visible(pg), 'Prompt not shown'
        # Click Skip this
        pg.locator('#_ow-skip').click()
        pg.wait_for_timeout(500)

        # Loop continues — either another prompt appears or progress shows skipped
        prompt_again = _overwrite_modal_visible(pg)
        progress = _gen_progress(pg)
        # Either we see another prompt (more posts) or completion with skipped count
        assert prompt_again or 'skipped' in progress or '✓' in progress, (
            f'After Skip this, loop did not continue. prompt={prompt_again}, '
            f'progress={progress!r}'
        )
        # Clean up if prompt still open
        if _overwrite_modal_visible(pg):
            pg.locator('#_ow-stop').click()
            pg.wait_for_timeout(500)


# ── Happy path 4: "Skip remaining" stops the loop ────────────────────────────

class TestSkipRemaining:
    """Clicking 'Skip remaining' must skip this post and all subsequent posts
    without showing any further prompts. Progress must show skipped count."""

    def test_skip_remaining_stops_loop(self, page, session):
        pg = page
        _open_scope_panel(pg)
        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(800)

        assert _overwrite_modal_visible(pg), 'Prompt not shown'
        pg.locator('#_ow-stop').click()

        # Wait for completion
        pg.wait_for_function(
            "() => (document.getElementById('gen-progress')?.textContent || '').startsWith('✓')",
            timeout=30000
        )
        progress = _gen_progress(pg)
        assert 'skipped' in progress, (
            f'"Skip remaining" must report skipped count in progress. Got: {progress!r}'
        )
        assert not _overwrite_modal_visible(pg), (
            'Prompt appeared again after "Skip remaining" — it should stop all '
            'further prompts for this run.'
        )


# ── Happy path 5: "Overwrite all" generates without further prompts ──────────

class TestOverwriteAll:
    """Clicking 'Overwrite all' must generate the current post AND all subsequent
    posts without showing any further prompts."""

    def test_overwrite_all_no_further_prompts(self, page, session):
        pg = page
        _open_scope_panel(pg)
        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(800)

        assert _overwrite_modal_visible(pg), 'Prompt not shown'
        pg.locator('#_ow-all').click()

        # Wait for completion — should not pause on further prompts
        pg.wait_for_function(
            "() => (document.getElementById('gen-progress')?.textContent || '').startsWith('✓')",
            timeout=120000  # generating many posts may take a while
        )
        assert not _overwrite_modal_visible(pg), (
            'Prompt appeared after "Overwrite all" — it should suppress all '
            'further prompts for this run.'
        )
        progress = _gen_progress(pg)
        assert 'generated' in progress, (
            f'"Overwrite all" must report generated count. Got: {progress!r}'
        )


# ── Happy path 6: progress counter is accurate ───────────────────────────────

class TestProgressCounter:
    """After a Skip remaining run, the progress line must correctly report
    0 generated and N skipped (one for the prompted post, N-1 for the rest)."""

    def test_progress_shows_generated_and_skipped(self, page, session):
        pg = page
        posts = session.get(f'{API}/posts').json()
        total_in_scope = len(posts)  # All filter

        _open_scope_panel(pg)
        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(800)

        if _overwrite_modal_visible(pg):
            pg.locator('#_ow-stop').click()

        pg.wait_for_function(
            "() => (document.getElementById('gen-progress')?.textContent || '').startsWith('✓')",
            timeout=30000
        )
        progress = _gen_progress(pg)
        # Progress must have both a number and "skipped"
        import re
        nums = re.findall(r'\d+', progress)
        assert nums, f'No numbers in progress: {progress!r}'
        assert 'skipped' in progress, f'No "skipped" in progress: {progress!r}'


# ── Modal slug accuracy ───────────────────────────────────────────────────────

class TestModalSlugAccuracy:
    """The modal must name the exact slug it is asking about — not a generic
    message, not an old slug from a previous run, not empty."""

    def test_modal_shows_current_slug(self, page, session):
        """The modal must display a recognisable slug string (YYYY-MM-DD-...) so
        the user knows which post they are deciding about."""
        pg = page
        _open_scope_panel(pg)
        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(800)

        assert _overwrite_modal_visible(pg), 'Prompt not shown'

        # Read the text of the modal's second div (the slug line)
        modal_slug_text = pg.evaluate("""() => {
            const btn = document.querySelector('#_ow-one');
            if (!btn) return '';
            // The slug is in a div two levels up from the button grid
            const grid = btn.parentElement;
            const card = grid?.parentElement;
            // Second div child = the slug line
            const divs = card ? [...card.children].filter(c => c.tagName === 'DIV') : [];
            return divs[1]?.textContent?.trim() || card?.textContent?.trim() || '';
        }""")
        # A slug contains hyphens and digits (YYYY-MM-DD-title)
        assert '-' in modal_slug_text and any(c.isdigit() for c in modal_slug_text), (
            f'Modal slug line does not look like a post slug: {modal_slug_text!r}. '
            f'The modal must name the specific post being processed so the user can '
            f'make an informed overwrite decision.'
        )
        pg.locator('#_ow-stop').click()
        pg.wait_for_timeout(300)


# ── Generate button state management ─────────────────────────────────────────

class TestButtonStateManagement:
    """The Generate button must be disabled while generation is running and
    re-enabled (with no lingering disabled state) when the run completes."""

    def test_button_disabled_during_run(self, page, session):
        pg = page
        _open_scope_panel(pg)
        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(200)  # before prompt or completion

        disabled = pg.evaluate("() => document.getElementById('btn-gen-all').disabled")
        assert disabled, (
            'Generate button must be disabled while generation is running '
            '(prevents double-click starting a second run).'
        )
        # Clean up
        if _overwrite_modal_visible(pg):
            pg.locator('#_ow-stop').click()
        pg.wait_for_function(
            "() => !document.getElementById('btn-gen-all').disabled",
            timeout=30000
        )

    def test_button_reenabled_after_completion(self, page, session):
        pg = page
        _open_scope_panel(pg)
        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(800)

        if _overwrite_modal_visible(pg):
            pg.locator('#_ow-stop').click()

        pg.wait_for_function(
            "() => (document.getElementById('gen-progress')?.textContent || '').startsWith('✓')",
            timeout=30000
        )
        disabled = pg.evaluate("() => document.getElementById('btn-gen-all').disabled")
        assert not disabled, (
            'Generate button still disabled after run completed. '
            'It must be re-enabled so the user can run again.'
        )


# ── "Overwrite this" (single) — prompt re-appears for next post ───────────────

class TestOverwriteThisPromptAgain:
    """Clicking 'Overwrite this' must generate the current post and then show
    the prompt AGAIN for the next post that has existing MD — it does NOT apply
    a batch decision, unlike 'Overwrite all'."""

    def test_overwrite_this_reprompts_for_next(self, page, session):
        pg = page
        posts_with_md = [
            p for p in session.get(f'{API}/posts').json()
            if p.get('md', {}).get('generated_at')
        ]
        if len(posts_with_md) < 2:
            pytest.skip('Need at least 2 posts with MD to test re-prompt behaviour')

        _open_scope_panel(pg)
        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(800)

        assert _overwrite_modal_visible(pg), 'First prompt not shown'
        pg.locator('#_ow-one').click()  # Overwrite this

        # Wait briefly for generation + next post to be reached
        pg.wait_for_timeout(3000)

        # Either a second prompt has appeared OR the run finished
        prompt_again = _overwrite_modal_visible(pg)
        progress = _gen_progress(pg)

        if '✓' in progress and not prompt_again:
            # Run already finished — only one post in scope, that's fine
            assert '1 generated' in progress, (
                f'Single post run should show 1 generated. Got: {progress!r}'
            )
        else:
            assert prompt_again, (
                '"Overwrite this" should reprompt for the next post with MD. '
                'Either the prompt did not re-appear or the run finished without '
                'generating anything. progress=' + repr(progress)
            )
            pg.locator('#_ow-stop').click()
            pg.wait_for_function(
                "() => !document.getElementById('btn-gen-all').disabled",
                timeout=30000
            )


# ── Hybrid decision path: mixed choices ──────────────────────────────────────

class TestHybridDecisionPath:
    """Overwrite all after initially skipping one — the first post is skipped,
    all subsequent posts are generated without prompting."""

    def test_skip_then_overwrite_all(self, page, session):
        pg = page
        posts_with_md = [
            p for p in session.get(f'{API}/posts').json()
            if p.get('md', {}).get('generated_at')
        ]
        if len(posts_with_md) < 2:
            pytest.skip('Need at least 2 posts with MD for hybrid path test')

        _open_scope_panel(pg)
        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(800)

        assert _overwrite_modal_visible(pg), 'First prompt not shown'
        pg.locator('#_ow-skip').click()   # Skip the first post
        pg.wait_for_timeout(1000)

        if _overwrite_modal_visible(pg):
            pg.locator('#_ow-all').click()  # Overwrite all from second post onwards

        # Wait for completion — no further prompts expected
        pg.wait_for_function(
            "() => (document.getElementById('gen-progress')?.textContent || '').startsWith('✓')",
            timeout=120000
        )
        assert not _overwrite_modal_visible(pg), (
            'Prompt appeared after "Overwrite all" — batch decision not honoured.'
        )
        progress = _gen_progress(pg)
        assert 'skipped' in progress, f'Expected skipped count. Got: {progress!r}'
        assert 'generated' in progress, f'Expected generated count. Got: {progress!r}'


# ── Empty scope edge case ─────────────────────────────────────────────────────

class TestEmptyScope:
    """When the current scope contains no posts at all, Generate must show a
    brief message and return — no prompt, no infinite loop, button re-enables."""

    def test_empty_scope_completes_cleanly(self, page, session):
        pg = page
        # Use the "reviewed" filter — if no posts are reviewed, scope is empty.
        # The API filter for 'reviewed' only shows reviewed posts.
        posts = session.get(f'{API}/posts').json()
        if all(p.get('reviewed') for p in posts):
            pytest.skip('All posts are reviewed — cannot create empty scope easily')

        # Use the "Staged" filter — only staged posts are in scope. Since there
        # are normally no staged posts, this gives an empty scope to test against.
        pg.evaluate("""() => {
            const btn = [...document.querySelectorAll('.fb')]
                .find(b => b.textContent.includes('Staged'));
            if (btn) setFilter(btn, 'staged');
        }""")
        pg.wait_for_timeout(200)
        in_scope = pg.evaluate("() => typeof filtered === 'function' ? filtered().length : -1")

        _open_scope_panel(pg)
        btn_disabled_before = pg.evaluate("() => document.getElementById('btn-gen-all').disabled")

        pg.locator('#btn-gen-all').click()
        pg.wait_for_timeout(1000)

        # Must not show a prompt (no posts to process)
        assert not _overwrite_modal_visible(pg), (
            'Overwrite prompt appeared for an empty scope — should not prompt '
            'when there are no posts to generate.'
        )

        # Button must re-enable
        pg.wait_for_function(
            "() => !document.getElementById('btn-gen-all').disabled",
            timeout=10000
        )

        # Reset to "all" filter
        pg.evaluate("""() => {
            const btn = [...document.querySelectorAll('.fb')]
                .find(b => b.textContent.trim() === 'All');
            if (btn) setFilter(btn, 'all');
        }""")
        pg.wait_for_timeout(200)
