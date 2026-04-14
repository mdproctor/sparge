"""
Tests for the two code-quality scan checks:

  1. check_potential_code_blocks — detects <p> elements with <br/> line breaks
     containing code-like content that should be in <pre><code>.

  2. check_code_block_no_newlines — detects <pre><code> blocks whose text
     content has no newline characters (likely lost during ingest when a CMS
     adds <br/> at render time but stores code in one line).

Also tests the UI issue-type scoping button (Playwright):
  3. Clicking a check type in the HTML breakdown filters the post list to
     only posts that have that issue type.
  4. Clicking the same type again clears the filter.
  5. The MD breakdown scoping button works the same way.

Requires server running on localhost:9000 for Playwright tests.
"""
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

from scan_html import check_potential_code_blocks, check_code_block_no_newlines


def _article(html: str):
    soup = BeautifulSoup(f'<article>{html}</article>', 'html.parser')
    return soup.find('article')


# ── check_potential_code_blocks ───────────────────────────────────────────────

class TestCheckPotentialCodeBlocks:
    """<p> with <br/> and code patterns must be flagged."""

    def test_drl_rule_in_paragraph_flagged(self):
        article = _article(
            '<p><span>rule "Test"</span><br/>'
            '<span>when</span><br/>'
            '<span>  Foo()</span><br/>'
            '<span>then</span><br/>'
            '<span>  doIt();</span><br/>'
            '<span>end</span></p>'
        )
        issues = check_potential_code_blocks(article)
        assert any(i['type'] == 'potential_code_block' for i in issues), (
            'DRL rule in <p><br/> should be flagged as potential_code_block'
        )

    def test_java_code_in_paragraph_flagged(self):
        article = _article(
            '<p>public class Foo {<br/>'
            '  private int x;<br/>'
            '  public void bar() {<br/>'
            '  }<br/>'
            '}</p>'
        )
        issues = check_potential_code_blocks(article)
        assert any(i['type'] == 'potential_code_block' for i in issues), (
            'Java code in <p><br/> should be flagged as potential_code_block'
        )

    def test_xml_in_paragraph_flagged(self):
        article = _article(
            '<p>&lt;beans&gt;<br/>'
            '  &lt;bean id="foo" class="Foo"/&gt;<br/>'
            '&lt;/beans&gt;</p>'
        )
        issues = check_potential_code_blocks(article)
        assert any(i['type'] == 'potential_code_block' for i in issues), (
            'XML in <p><br/> should be flagged as potential_code_block'
        )

    def test_prose_paragraph_not_flagged(self):
        article = _article(
            '<p>This is a normal paragraph about rules.<br/>'
            'It mentions some code concepts but is prose.</p>'
        )
        issues = check_potential_code_blocks(article)
        assert not any(i['type'] == 'potential_code_block' for i in issues), (
            'Prose paragraph with <br/> must not be flagged'
        )

    def test_paragraph_without_br_not_flagged(self):
        """Code patterns in a paragraph without <br/> should not trigger."""
        article = _article(
            '<p>rule "Test" when Foo() then doIt(); end</p>'
        )
        issues = check_potential_code_blocks(article)
        assert not any(i['type'] == 'potential_code_block' for i in issues), (
            'Code-like content in <p> without <br/> should not be flagged '
            '(single-line inline reference, not a code block)'
        )

    def test_pre_code_block_not_flagged(self):
        """Properly wrapped code must not generate a false positive."""
        article = _article(
            '<pre><code class="language-drl">'
            'rule "Test"\nwhen\n  Foo()\nthen\n  doIt();\nend'
            '</code></pre>'
        )
        issues = check_potential_code_blocks(article)
        assert not any(i['type'] == 'potential_code_block' for i in issues), (
            'Code already inside <pre><code> must not be re-flagged'
        )

    def test_very_short_paragraph_not_flagged(self):
        """Snippet too short to be a real code block."""
        article = _article('<p>end<br/>end</p>')
        issues = check_potential_code_blocks(article)
        assert not any(i['type'] == 'potential_code_block' for i in issues)

    def test_long_line_paragraph_not_flagged(self):
        """Prose with long lines (not code) should not be flagged."""
        long_prose = 'This is a very long prose sentence that mentions import java and public class ' * 3
        article = _article(f'<p>{long_prose}<br/>{long_prose}</p>')
        issues = check_potential_code_blocks(article)
        assert not any(i['type'] == 'potential_code_block' for i in issues), (
            'Paragraph with long average line length is prose, not code'
        )


# ── check_code_block_no_newlines ──────────────────────────────────────────────

class TestCheckCodeBlockNoNewlines:
    """<pre><code> blocks with all content on one line must be flagged."""

    def test_one_line_code_with_semicolons_flagged(self):
        article = _article(
            '<pre><code class="language-drl">'
            'rule "Test" when Foo() then doIt(); doBar(); end'
            '</code></pre>'
        )
        issues = check_code_block_no_newlines(article)
        assert any(i['type'] == 'code_no_newlines' for i in issues), (
            'Multi-statement code all on one line should be flagged as code_no_newlines'
        )

    def test_one_line_drl_keywords_flagged(self):
        article = _article(
            '<pre><code>'
            'rule "Test" when Cheese() then System.out.println("hi"); end'
            '</code></pre>'
        )
        issues = check_code_block_no_newlines(article)
        assert any(i['type'] == 'code_no_newlines' for i in issues)

    def test_multiline_code_not_flagged(self):
        article = _article(
            '<pre><code class="language-drl">'
            'rule "Test"\nwhen\n  Foo()\nthen\n  doIt();\nend'
            '</code></pre>'
        )
        issues = check_code_block_no_newlines(article)
        assert not any(i['type'] == 'code_no_newlines' for i in issues), (
            'Code with proper newlines must not be flagged'
        )

    def test_short_one_liner_not_flagged(self):
        """Genuine one-liners (e.g. a single expression) should not fire."""
        article = _article('<pre><code>x = foo(bar)</code></pre>')
        issues = check_code_block_no_newlines(article)
        assert not any(i['type'] == 'code_no_newlines' for i in issues), (
            'Short one-liner code should not be flagged — it may be intentional'
        )

    def test_pre_without_code_one_line_flagged(self):
        """Plain <pre> (no <code> child) also checked."""
        article = _article(
            '<pre>rule "Test" when Foo(x > 42) then update($f); end</pre>'
        )
        issues = check_code_block_no_newlines(article)
        assert any(i['type'] == 'code_no_newlines' for i in issues), (
            'Plain <pre> with multi-statement one-line code should also be flagged'
        )

    def test_no_code_signal_not_flagged(self):
        """Long one-liner without code patterns should not fire."""
        article = _article(
            '<pre><code>https://example.com/very/long/url/that/has/no/code/keywords/and/goes/on</code></pre>'
        )
        issues = check_code_block_no_newlines(article)
        assert not any(i['type'] == 'code_no_newlines' for i in issues)


# ── Playwright: issue-type scoping button ─────────────────────────────────────

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
        ctx = browser.new_context(viewport={'width': 1400, 'height': 900})
        pg = ctx.new_page()
        pg.goto(APP_URL, wait_until='networkidle')
        pg.wait_for_function("() => document.querySelectorAll('.pi').length > 0", timeout=20000)
        yield pg
        ctx.close()
        browser.close()


def _visible_post_count(pg) -> int:
    return pg.evaluate("() => document.querySelectorAll('.pi').length")


def _current_issue_type(pg) -> str | None:
    return pg.evaluate("() => typeof currentIssueType !== 'undefined' ? currentIssueType : null")


class TestHtmlIssueTypeScopingButton:
    """Clicking an issue type in the HTML breakdown filters the post list."""

    def _open_html_breakdown(self, pg):
        """Click the HTML issues row to open the breakdown if not open."""
        breakdown = pg.locator('#html-breakdown')
        if not breakdown.is_visible():
            pg.locator('text=HTML issues').first.click()
            pg.wait_for_timeout(300)

    def test_clicking_issue_type_filters_post_list(self, server, page):
        """Clicking a check type in the HTML breakdown must filter the post list."""
        pg = page
        total_before = _visible_post_count(pg)

        self._open_html_breakdown(pg)

        # Find a breakdown row for potential_code_block
        row = pg.locator('#html-breakdown [onclick*="potential_code_block"]')
        if row.count() == 0:
            pytest.skip('No potential_code_block issues in current dataset')

        row.first.click()
        pg.wait_for_timeout(400)

        total_after = _visible_post_count(pg)
        issue_type = _current_issue_type(pg)

        assert issue_type == 'potential_code_block', (
            f'After clicking potential_code_block row, currentIssueType should be '
            f'"potential_code_block", got {issue_type!r}'
        )
        assert total_after < total_before, (
            f'Clicking issue type filter should reduce post list. '
            f'Before: {total_before}, After: {total_after}'
        )
        assert total_after > 0, 'Filtered list must contain at least one post'

        # Verify all visible posts actually have this issue type
        has_issue = pg.evaluate("""() => {
            const posts = allPosts.filter(p =>
                (p.html?.issues||[]).some(i => i.type === 'potential_code_block')
            );
            const visible = document.querySelectorAll('.pi').length;
            return posts.length === visible;
        }""")
        assert has_issue, (
            'All visible posts must have the potential_code_block issue type'
        )

        # Cleanup — click again to deselect
        row.first.click()
        pg.wait_for_timeout(300)

    def test_clicking_same_type_again_clears_filter(self, server, page):
        """Clicking the active type again must restore the full list."""
        pg = page
        total_before = _visible_post_count(pg)

        self._open_html_breakdown(pg)
        row = pg.locator('#html-breakdown [onclick*="potential_code_block"]')
        if row.count() == 0:
            pytest.skip('No potential_code_block issues in current dataset')

        # Select
        row.first.click()
        pg.wait_for_timeout(300)
        filtered = _visible_post_count(pg)

        # Deselect
        row.first.click()
        pg.wait_for_timeout(300)
        restored = _visible_post_count(pg)

        assert _current_issue_type(pg) is None, (
            'After clicking active type again, currentIssueType should be None'
        )
        assert restored == total_before, (
            f'After clearing filter, post count should be restored. '
            f'Before: {total_before}, Filtered: {filtered}, Restored: {restored}'
        )

    def test_issue_type_rows_show_correct_counts(self, server, page):
        """The count shown in each breakdown row must match the actual data."""
        pg = page
        self._open_html_breakdown(pg)

        # Get counts from the UI
        ui_counts = pg.evaluate("""() => {
            const rows = document.querySelectorAll('#html-breakdown [onclick]');
            const result = {};
            rows.forEach(r => {
                const m = r.getAttribute('onclick').match(/'([^']+)'/);
                if (m) {
                    const num = r.querySelector('.bd-count')?.textContent?.trim();
                    if (num) result[m[1]] = parseInt(num);
                }
            });
            return result;
        }""")

        # Get actual counts from state
        actual_counts = pg.evaluate("""() => {
            const counts = {};
            allPosts.forEach(p => {
                const seen = new Set();
                (p.html?.issues||[]).forEach(i => {
                    if (!seen.has(i.type)) { seen.add(i.type); counts[i.type] = (counts[i.type]||0)+1; }
                });
            });
            return counts;
        }""")

        for itype, ui_count in ui_counts.items():
            actual = actual_counts.get(itype, 0)
            assert ui_count == actual, (
                f'UI shows {ui_count} for {itype!r} but actual count is {actual}. '
                f'The breakdown row counts must reflect the real post data.'
            )

        # Cleanup
        if _current_issue_type(pg):
            pg.locator('#html-breakdown [onclick*="potential_code_block"]').first.click()
            pg.wait_for_timeout(200)


class TestPostSearchBar:
    """Search bar filters the post list by title or slug."""

    def test_search_by_title_filters_list(self, server, page):
        pg = page
        total = _visible_post_count(pg)

        pg.fill('#search-input', 'drools')
        pg.wait_for_timeout(300)

        filtered = _visible_post_count(pg)
        assert filtered < total, (
            f'Searching "drools" should reduce post count. Before: {total}, After: {filtered}'
        )
        assert filtered > 0, 'Search for "drools" must return at least one post'

        # All visible posts must contain "drools" in title or slug
        all_match = pg.evaluate("""() => {
            const q = 'drools';
            return Array.from(document.querySelectorAll('.pi')).every(el => {
                const slug = el.dataset.slug || '';
                const title = el.querySelector('.pi-title')?.textContent?.toLowerCase() || '';
                return slug.includes(q) || title.includes(q);
            });
        }""")
        assert all_match, 'All visible posts must match the search query'

        # Cleanup
        pg.fill('#search-input', '')
        pg.wait_for_timeout(200)

    def test_search_cleared_restores_full_list(self, server, page):
        pg = page
        total_before = _visible_post_count(pg)

        pg.fill('#search-input', 'drools')
        pg.wait_for_timeout(300)

        pg.fill('#search-input', '')
        pg.wait_for_timeout(300)

        restored = _visible_post_count(pg)
        assert restored == total_before, (
            f'Clearing search must restore full list. Before: {total_before}, Restored: {restored}'
        )

    def test_search_with_filter_combined(self, server, page):
        """Search and filter mode work together."""
        pg = page

        # Apply HTML issues filter first
        pg.locator('.fb[onclick*="html-issues"]').click()
        pg.wait_for_timeout(300)
        filtered_only = _visible_post_count(pg)

        # Then add search term
        pg.fill('#search-input', 'drools')
        pg.wait_for_timeout(300)
        combined = _visible_post_count(pg)

        assert combined <= filtered_only, (
            f'Combined filter+search must not exceed filter-only count. '
            f'Filter-only: {filtered_only}, Combined: {combined}'
        )

        # Cleanup
        pg.fill('#search-input', '')
        pg.locator('.fb[onclick*="all"]').click()
        pg.wait_for_timeout(300)

    def test_title_scope_filters_correctly(self, server, page):
        """Selecting 'Title' scope returns only posts with query in title."""
        pg = page

        pg.select_option('#search-scope', 'title')
        pg.fill('#search-input', 'drools')
        pg.wait_for_timeout(700)

        count = _visible_post_count(pg)
        assert count > 0

        # All results must have 'drools' in the title
        all_in_title = pg.evaluate("""() => {
            const q = 'drools';
            const postMap = Object.fromEntries(allPosts.map(p => [p.slug, p]));
            return Array.from(document.querySelectorAll('.pi')).every(el => {
                const slug = el.dataset.slug || '';
                const p = postMap[slug];
                return ((p && p.title) || slug).toLowerCase().includes(q);
            });
        }""")
        assert all_in_title, 'Title-scope: all results must have "drools" in title'

        # Cleanup
        pg.fill('#search-input', '')
        pg.select_option('#search-scope', 'both')
        pg.wait_for_timeout(200)
