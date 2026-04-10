"""
Playwright test: after applying convert_post.py fixes, re-generating the
'Configuration and Convention based Building and Utilization' post must:
  1. Show a diff (not "No change") — the fixed code produces different output
  2. After accepting the new version, prose_in_code must not appear in md.issues
  3. The [](<url>) and [text](<url>) DocBook artifacts must be gone from the MD

This test was written FIRST against the broken state (server has stale code,
disk has old MD):
  - prose_in_code still reported
  - generate says "No change" (server serves old code, matches old disk)

After restart + regeneration:
  - generate shows a diff
  - accepting it removes the artifacts
  - prose_in_code is gone

Run with server on localhost:9000:
  python3 -m pytest tests/test_md_generate_current.py -v
"""
import pytest

SERVER  = 'http://localhost:9000'
APP_URL = SERVER + '/ui/index.html'
API     = SERVER + '/api'
SLUG    = '2013-10-31-configuration-and-convention-based-building-and-utilization'


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

        pg.locator(f'[data-slug="{SLUG}"]').click()
        pg.wait_for_function(
            f"() => document.getElementById('orig-frame')?.src?.includes('{SLUG}')",
            timeout=8000)
        pg.wait_for_timeout(600)
        yield pg
        browser.close()


def open_issues(page):
    btn = page.locator('#btn-issues')
    if 'active' not in (btn.get_attribute('class') or ''):
        btn.click()
        page.wait_for_timeout(200)


def md_issue_checks(page) -> list:
    """Return the check names of all visible MD issues."""
    return page.evaluate("""() =>
        [...document.querySelectorAll('#md-issue-list .irow')]
        .map(r => (r.dataset.check || ''))
        .filter(Boolean)
    """)


def generate_md(page) -> str:
    """Click the Generate MD button and return the resulting button text."""
    page.locator('#btn-gen').click()
    page.wait_for_function("""() => {
        const btn = document.getElementById('btn-gen');
        const modal = document.getElementById('diff-modal');
        return btn.textContent.includes('No change') ||
               btn.textContent.includes('Done') ||
               btn.textContent.includes('Generate') ||
               (modal && modal.classList.contains('open'));
    }""", timeout=20000)
    page.wait_for_timeout(300)
    return page.locator('#btn-gen').inner_text()


# ── Before fix: tests that show the broken state ───────────────────────────────
# These are documented expectations of the broken state.
# They should FAIL after the fix (they are "anti-tests" documenting the bug).
# After the fix (restart + regenerate) the assertions below become the real ones.

class TestAfterFixAndRegeneration:
    """After server restart (loads fixed convert_post.py) and regeneration,
    the post must have clean MD without DocBook link artifacts or false-positive
    prose_in_code warnings.

    Test-first: these assertions FAIL if the server has stale code or the MD
    has not been regenerated. They PASS once:
      1. Server is restarted (loads fixed convert_post.py)
      2. The post is regenerated (accepting the diff in the UI or via API)
    """

    def test_generate_produces_diff_not_no_change(self, page):
        """After server restart, generate-md must detect the fixed output differs
        from the stale disk content and show a diff (not 'No change').

        FAILS if server has stale code: stale server produces same output as
        stale disk → 'No change'.
        PASSES after restart: fixed server produces different output → diff shown.

        Note: after this test runs (and if the diff was accepted), subsequent
        runs will also see 'No change' — because the disk is now up to date.
        This test is designed for the FIRST run after a restart.
        """
        # Check what's on disk first
        import requests, re
        from pathlib import Path
        s = requests.Session()
        cfg = s.get(f'{API}/config').json()
        md_dir = cfg.get('output', {}).get('md_dir', 'mark-proctor')
        disk = s.get(f'http://localhost:9000/{md_dir}/{SLUG}.md').text
        empty_links_on_disk = len(re.findall(r'^\[\]\(<https?://', disk, re.M))
        bracket_lines_on_disk = len([l for l in disk.splitlines() if l.strip().startswith('[')])

        btn_result = generate_md(page)
        modal_open = page.evaluate("document.getElementById('diff-modal').classList.contains('open')")

        if empty_links_on_disk > 0 or bracket_lines_on_disk > 0:
            # Disk still has old content — the fixed server should detect a diff
            assert modal_open, (
                f'After server restart the fixed convert_post.py should produce '
                f'different output (no [](<url>) artifacts), causing a diff. '
                f'Got button: {btn_result!r}. '
                f'Disk has {empty_links_on_disk} empty links and {bracket_lines_on_disk} bracket lines. '
                f'Check that the server was restarted with the latest code.')
        else:
            # Disk already has clean content (test ran before, diff was accepted)
            assert btn_result.strip() in ('✓ No change', '↺ Generate MD', '✓ Done'), (
                f'Post already regenerated — expected no-change. Got: {btn_result!r}')

    def test_md_has_no_empty_link_artifacts(self, page, session):
        """The MD file must not contain [](<url>) DocBook navigation artifacts.

        FAILS if disk has stale MD (62+ empty links).
        PASSES after regeneration with fixed convert_post.py (0 empty links).
        """
        import re
        cfg = session.get(f'{API}/config').json()
        md_dir = cfg.get('output', {}).get('md_dir', 'mark-proctor')
        disk = session.get(f'{SERVER}/{md_dir}/{SLUG}.md').text
        empty = re.findall(r'^\[\]\(<https?://[^)]+>\)', disk, re.M)
        assert not empty, (
            f'MD file has {len(empty)} empty [](<url>) DocBook link artifacts. '
            f'Regenerate after server restart to clear them.')

    def test_md_has_no_bracket_line_artifacts(self, page, session):
        """The MD file must not have lines starting with '[' from DocBook link wrappers.

        FAILS if disk has stale MD (63 bracket lines).
        PASSES after regeneration (0 bracket lines).
        """
        cfg = session.get(f'{API}/config').json()
        md_dir = cfg.get('output', {}).get('md_dir', 'mark-proctor')
        disk = session.get(f'{SERVER}/{md_dir}/{SLUG}.md').text
        bracket = [l for l in disk.splitlines() if l.strip().startswith('[')]
        assert not bracket, (
            f'MD file has {len(bracket)} lines starting with "[" (DocBook link artifacts). '
            f'Sample: {bracket[0][:80]!r}. '
            f'Regenerate after server restart to clear them.')

    def test_prose_in_code_not_in_md_issues(self, page, session):
        """After regeneration and re-validation, prose_in_code must not appear
        in md.issues for this post.

        FAILS if the server still has the old chk_prose_in_code (before fullmatch fix)
        OR if the MD has not been regenerated (old md.issues cached in state).
        PASSES after restart + regeneration + validation with the fixed validator.
        """
        post = session.get(f'{API}/posts/{SLUG}').json()
        checks = [i['check'] for i in post.get('md', {}).get('issues', [])]
        assert 'prose_in_code' not in checks, (
            f'prose_in_code still in md.issues after fix. '
            f'The validator fix (filter out code-char matches) may not be loaded. '
            f'Restart server and regenerate the post. Current issues: {checks}')

    def test_prose_in_code_not_visible_in_ui(self, page):
        """The issue panel must not show prose_in_code after regeneration."""
        open_issues(page)
        # Reload state in UI
        page.locator(f'[data-slug="{SLUG}"]').click()
        page.wait_for_timeout(600)
        open_issues(page)
        checks = md_issue_checks(page)
        assert 'prose_in_code' not in checks, (
            f'prose_in_code still shown in UI issue panel. '
            f'Checks visible: {checks}')


class TestDuplicateParagraph:
    """duplicate_paragraph must only flag paragraphs repeated by the CONVERTER,
    not paragraphs the author genuinely wrote twice in the source HTML.

    The 'Any KieModule can be loaded from a Resource location...' paragraph
    appears TWICE in the source HTML (the author repeated it before two different
    code examples). The validator must not report this as a conversion bug.

    Test-first: these FAIL before the fix (validator reports ERROR for content
    that is faithfully duplicated from the source).
    PASS after fix: cross-check against HTML; only report when duplication is
    NOT present in the source.
    """

    def test_duplicate_not_reported_when_present_in_source_html(self, page, session):
        """If a paragraph appears twice in BOTH the HTML and the MD, it must NOT
        be reported as duplicate_paragraph — it is faithful to the source.

        FAILS before fix: chk_duplicate_paragraphs has no HTML context, so it
        reports the duplicate regardless of whether it's in the source.
        PASSES after fix: cross-check skips duplicates that also exist in the HTML.
        """
        post = session.get(f'{API}/posts/{SLUG}').json()
        checks = [i['check'] for i in post.get('md', {}).get('issues', [])]
        # The duplicate is real in the HTML — it must not be reported as an error
        assert 'duplicate_paragraph' not in checks, (
            f'duplicate_paragraph reported for "Any KieModule..." paragraph which '
            f'appears TWICE in the source HTML (author repetition, not a conversion bug). '
            f'The validator must cross-check against the HTML before reporting. '
            f'Current issues: {checks}')

    def test_duplicate_not_visible_in_ui_panel(self, page):
        """The issue panel must not show duplicate_paragraph for this post."""
        open_issues(page)
        page.locator(f'[data-slug="{SLUG}"]').click()
        page.wait_for_timeout(600)
        open_issues(page)
        checks = md_issue_checks(page)
        assert 'duplicate_paragraph' not in checks, (
            f'duplicate_paragraph shown in UI for a paragraph that is faithfully '
            f'duplicated from the source HTML. Checks: {checks}')


class TestDuplicateListBlockFaithful:
    """duplicate_paragraph must not fire when the same list block appears
    in TWO separate sections of the HTML (e.g. the same JVM flags documented
    for both WildFly and Tomcat).

    Bug: the HTML comparison used clean[:40] (markdown-formatted, with "  * "
    list markers) against html_text.get_text() (plain text, no list markers).
    The markdown formatting is invisible in HTML plain text so html_text.count()
    always returned 0, making the check fire even for faithful duplicates.

    Fix: strip all non-alphanumeric characters from both sides before comparing
    — only the character sequence matters, not the formatting.

    Test written AFTER the fix (violation noted — this class is the regression
    guard to prevent the fix being reverted).
    """

    def test_faithful_duplicate_list_not_flagged(self, session):
        """Same JVM flag bullets in WildFly + Tomcat sections must not be reported."""
        slug = '2015-10-20-installing-kie-server-and-workbench-on-same-server-2'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        assert not any(i['check'] == 'duplicate_paragraph' for i in issues), (
            f'duplicate_paragraph fired for "-Dorg.drools.server.ext.disabled=true" '
            f'bullets that appear in BOTH WildFly and Tomcat config sections of the '
            f'source HTML. The HTML comparison was comparing markdown list-marker '
            f'formatted text ("  * disable BRM:") against HTML plain text '
            f'("disable BRM:") — the "  * " prefix is invisible in HTML, so '
            f'html_text.count() always returned 0, falsely triggering the check. '
            f'Fix: compare alphanumeric-only fingerprints from both sides. '
            f'Issues: {issues}'
        )


class TestCrossCheckFalsePositives:
    """Three cross-checks produce false positives for this post.
    All tests written FIRST (fail), then fixes applied (pass).

    1. code_content_missing: \xa0 in HTML code vs spaces in MD — not found even though present
    2. links_dropped: 119/120 links are blog-nav artifacts we stripped — not real loss
    3. content_phrase_missing: phrase extraction joins stopword-stripped words, never
       matches raw MD body even when the paragraph IS there
    """

    def test_code_content_missing_is_false_positive(self, session):
        """code_content_missing must not fire when code IS in the MD.
        The \xa0 in HTML code text fails the string-in-md search even though the
        same code (with regular spaces) is in the MD.
        Fix: normalise \xa0 → space in code text before checking.
        """
        post = session.get(f'{API}/posts/{SLUG}').json()
        checks = [i['check'] for i in post.get('md', {}).get('issues', [])]
        assert 'code_content_missing' not in checks, (
            'code_content_missing reported but code IS in the MD — '
            '\xa0 (non-breaking space) in HTML code text prevents the search from '
            'matching the same code with regular spaces in the MD. '
            f'Current issues: {checks}')

    def test_links_dropped_is_false_positive(self, session):
        """links_dropped must not fire when the dropped links are blog-navigation artifacts.
        119 of 120 links are http://blog.athico.com/ — the DocBook navigation we
        correctly stripped. Only 1 is a real external link (GitHub).
        Fix: count unique link destinations, or exclude links with <3 distinct hrefs.
        """
        post = session.get(f'{API}/posts/{SLUG}').json()
        checks = [i['check'] for i in post.get('md', {}).get('issues', [])]
        assert 'links_dropped' not in checks, (
            'links_dropped reported but 119/120 HTML links are DocBook navigation '
            'artifacts (blog.athico.com) that were correctly stripped. '
            'Fix: exclude repeated same-URL navigation links from the count. '
            f'Current issues: {checks}')

    def test_content_phrase_missing_is_false_positive(self, session):
        """content_phrase_missing must not fire when the HTML paragraph IS in the MD.
        The phrase extraction (join words[1:5] after stripping punctuation) creates
        'install deploy kiemodule machine' which is never literally found in the raw MD
        even though the original sentence is present.
        Fix: use a raw substring match instead of reconstructed phrase.
        """
        post = session.get(f'{API}/posts/{SLUG}').json()
        checks = [i['check'] for i in post.get('md', {}).get('issues', [])]
        assert 'content_phrase_missing' not in checks, (
            'content_phrase_missing reported for paragraphs that ARE in the MD. '
            'The phrase extraction strips punctuation/stopwords and joins the result, '
            'but the joined phrase does not literally appear in the raw MD body. '
            f'Current issues: {checks}')


class TestListsDropped:
    """lists_dropped must not fire when list items ARE in the MD but indented.
    
    The validator uses ^[-*]\\s which only matches bullets at column 0.
    The converted MD has '  * item' (2-space indent from nested structure).
    Fix: allow optional leading whitespace in the list-item regex.
    """

    def test_lists_dropped_is_false_positive(self, session):
        """lists_dropped must not fire when list content is present in the MD.
        FAILS: regex ^[-*]\\s misses '  * item' (indented bullets).
        PASSES: regex ^\\s*[-*]\\s allows any leading whitespace.
        """
        post = session.get(f'{API}/posts/{SLUG}').json()
        checks = [i['check'] for i in post.get('md', {}).get('issues', [])]
        assert 'lists_dropped' not in checks, (
            'lists_dropped reported but list items ARE in the MD as indented bullets '
            '("  * Project: ..."). The regex ^[-*]\\s misses indented list items. '
            f'Current issues: {checks}')


RULES_FESTIVAL_SLUG = '2009-07-20-october-rules-festival-2009'


class TestStaleAssetState:
    """The assets badge must reflect the CURRENT state of the HTML, not a stale
    scan from before generate-md modified the source file.

    For 'October Rules Festival 2009', the HTML contained 2 author profile photos
    in <a href=".../search_authors=..."> wrappers.  convert_post.py correctly removes
    these as blog chrome (author avatar links) and writes back to the source HTML.
    After generate-md runs, the source HTML has 0 images.  A subsequent re-scan
    must show 0 broken assets, not the stale 'broken=2'.

    Test-first: FAILS with stale scan state (broken=2 in state.json).
    PASSES after re-scanning (state updated to reflect 0 images in current HTML).
    """

    def test_assets_badge_not_showing_broken_after_rescan(self, page, session):
        """After re-scanning, the assets badge must not show broken images
        for a post whose source HTML was modified by generate-md to remove
        author avatar images (correct blog chrome removal).

        FAILS if state.json still has stale broken=2 from before generate-md.
        PASSES after re-scan updates the state to reflect current HTML.
        """
        # Re-scan to update the stale asset state
        r = session.post(f'{API}/posts/{RULES_FESTIVAL_SLUG}/scan')
        assert r.status_code == 200, f'Scan failed: {r.status_code}'

        post = session.get(f'{API}/posts/{RULES_FESTIVAL_SLUG}').json()
        assets = post.get('assets', {})
        broken = assets.get('broken', 0)

        assert broken == 0, (
            f'After re-scan, broken assets must be 0 for this post. Got broken={broken}. '
            f'The 2 "missing" images were author profile photos correctly stripped by '
            f'convert_post.py as blog chrome. The stale scan state from before '
            f'generate-md ran must be cleared by re-scanning.')

    def test_images_not_localised_not_in_html_issues_after_rescan(self, page, session):
        """After re-scan, the HTML issues panel must not show images_not_localised."""
        session.post(f'{API}/posts/{RULES_FESTIVAL_SLUG}/scan')

        # Reload the UI
        page.locator(f'[data-slug="{RULES_FESTIVAL_SLUG}"]').click()
        page.wait_for_timeout(500)
        page.locator('#btn-issues').click()
        page.wait_for_timeout(200)

        html_issue_checks = page.evaluate("""() =>
            [...document.querySelectorAll('#html-issue-list .irow')]
            .map(r => r.dataset.check || '')
            .filter(Boolean)
        """)
        assert 'images_not_localised' not in html_issue_checks, (
            f'images_not_localised shown in HTML issues after re-scan. '
            f'This is a stale asset state issue — the images were author avatars '
            f'correctly removed as blog chrome. '
            f'HTML issue checks: {html_issue_checks}')


class TestAssetScanPathResolution:
    """scan_assets must resolve relative image paths from the ORIGINAL posts
    directory, not from the enriched copy's location.

    When the enriched copy is at sparge-projects/.../enriched/slug.html,
    relative paths like '../../assets/img.jpg' resolve to the wrong location.
    The same paths resolve correctly from the original posts directory.

    Test-first: FAILS because scan uses enriched path for resolution → broken=2.
    PASSES after scan_assets accepts original_path for relative path resolution.
    """

    def test_scan_assets_with_original_path_gives_zero_broken(self, session):
        """scan_assets must resolve relative image paths from the original HTML location.

        The avatar images in this post use relative paths (../../assets/...) that
        are correct relative to the original posts dir but wrong relative to the
        enriched copy's location.  The fix: scan_assets accepts original_path and
        uses it as the base for relative path resolution.

        Note: after generate-md strips author avatar images (blog chrome), both
        the enriched copy and the original may show 0 images.  The test verifies
        the API-level fix via test_server_scan_shows_zero_broken_after_fix.
        """
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
        from scan_assets import scan_assets

        cfg = session.get(f'{API}/config').json()
        posts_dir = Path(cfg['serve_root']) / cfg['source']['posts_dir']
        original = posts_dir / f'{RULES_FESTIVAL_SLUG}.html'

        # Original path: scan with correct base dir — must never show broken
        result_original = scan_assets(original)
        assert result_original['broken'] == 0, (
            f'scan_assets with original path must show 0 broken. '
            f'Got: {result_original}')

    def test_server_scan_shows_zero_broken_after_fix(self, session):
        """After the server passes original_path to scan_assets, re-scanning
        must return broken=0 for this post.

        FAILS before fix: server passes enriched path only → broken=2.
        PASSES after fix: server also passes original_path → broken=0.
        """
        r = session.post(f'{API}/posts/{RULES_FESTIVAL_SLUG}/scan')
        assert r.status_code == 200
        assets = r.json().get('assets', {})
        assert assets.get('broken', -1) == 0, (
            f'Server scan must show broken=0 for this post (images ARE localised '
            f'at the correct path relative to the original HTML). '
            f'Got: {assets}. '
            f'The scan_assets function needs original_path for relative path resolution '
            f'when scanning an enriched copy.')


class TestContentPhraseMissingWithLinks:
    """content_phrase_missing must not fire when a phrase IS in the MD but
    contains inline markdown link syntax wrapping key terms.

    HTML: 'Drools is a <a href="...">Rule Engine</a> but...'
    MD:   'Drools is a [Rule Engine](<url>) but...'

    The substring search '...rule engine but...' fails because '[Rule Engine](<url>)'
    interrupts the match. Fix: strip markdown inline links before searching.
    This is universal — applies to any blog where key terms are hyperlinked.
    """

    def test_phrase_with_inline_links_not_flagged(self, session):
        """content_phrase_missing must not fire for 'what-is-a-rule-engine' where
        the missing phrase is actually present but has inline markdown link syntax.

        FAILS before fix: raw substring search misses '[Rule Engine](<url>)' interpolation.
        PASSES after fix: strip markdown links from body before searching.
        """
        post = session.get(f'{API}/posts/2006-05-31-what-is-a-rule-engine').json()
        checks = [i['check'] for i in post.get('md', {}).get('issues', [])]
        assert 'content_phrase_missing' not in checks, (
            'content_phrase_missing fired for "Drools is a Rule Engine..." but the '
            'phrase IS in the MD as "Drools is a [Rule Engine](<url>) but..." — '
            'the inline markdown link interrupts the substring match. '
            'Fix: strip [text](<url>) → text from body before phrase search. '
            f'Current issues: {checks}')


class TestTruncatedAtEnd:
    """truncated_at_end must not fire when content IS in the MD.

    Two false-positive patterns found across 116 reported cases:

    1. Word-merge: get_text() concatenates inline link text without spaces.
       HTML: 'Peter Lin<a href="...">has</a> been doing...'
       get_text(strip=True) → 'Peter Linhas been doing...'  (no space)
       MD:   'Peter Lin has been doing...'  (space from markdown link)
       Fix: use separator=' ' in get_text() so inline elements add spaces.

    2. html2text reordering: <span>DBM</span><br/>text causes html2text to
       place the paragraph earlier in the MD than HTML source order suggests.
       The paragraph IS in the MD body — just not at the very end.
       Fix: search anywhere in MD body (not just the tail).
    """

    def test_word_merge_not_flagged(self, session):
        """'Peter Linhas' (merged) ≠ 'Peter Lin has' (MD) → false positive.
        FAILS before fix: get_text(strip=True) merges inline link text.
        PASSES after fix: separator=' ' adds spaces between inline elements.
        """
        slug = '2007-01-28-enhancing-jbossrules-dsl'
        post = session.get(f'{API}/posts/{slug}').json()
        r = session.post(f'{API}/posts/{slug}/validate-md')
        checks = [i['check'] for i in r.json().get('md', {}).get('issues', [])]
        assert 'truncated_at_end' not in checks, (
            f'truncated_at_end is a false positive for "{slug}": the last HTML '
            f'paragraph has inline links that create word-merges in get_text(). '
            f'Content IS in the MD. Fix: use separator=" " in get_text(). '
            f'Issues: {checks}')

    def test_reordering_not_flagged(self, session):
        """html2text reorders <span>DBM</span><br/>text paragraphs earlier in output.
        The paragraph is in the MD body but not at the very end.
        FAILS before fix: validator only checks if phrase is near the MD end.
        PASSES after fix: search anywhere in MD body.
        """
        slug = '2006-11-17-declarative-behavioural-modelling-dbm-and-jbpm-jboss-rules-integration'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        checks = [i['check'] for i in r.json().get('md', {}).get('issues', [])]
        assert 'truncated_at_end' not in checks, (
            f'truncated_at_end is a false positive for "{slug}": html2text '
            f'reordered the <span>DBM</span><br/> paragraph to appear earlier '
            f'in the MD output than the HTML source order suggests. '
            f'The paragraph IS in the MD. Fix: search entire body, not just end. '
            f'Issues: {checks}')


class TestLinksDroppedShareWidgets:
    """links_dropped must not fire for social sharing widget links.

    WordPress/CMS platforms add 7 share buttons per post (Facebook, Twitter,
    LinkedIn, Reddit, Email, Tumblr, Copy Link) via addtoany or similar widgets.
    Each generates a unique href containing the post URL as a ?linkurl= parameter.
    Our frequency filter (≥5 same href) misses them because each is different.

    Universal pattern: ?linkurl=https%3A (encoded URL as query param) identifies
    ANY sharing widget — addtoany, sharethis, buffer, etc.  Not domain-specific.

    Test-first: FAILS before fix (7 share links inflate unique href count).
    PASSES after fix: exclude hrefs containing ?linkurl= from the link count.
    """

    def test_post_with_sharing_widgets_not_flagged(self, session):
        """links_dropped must not fire when the only 'dropped' links are share widgets."""
        # jboss-drools-vs-jboss-rules-part-deux has 9 unique hrefs: 7 addtoany + 2 nav
        # The MD has 0-1 real links — should not be flagged since there are no real content links
        slug = '2007-07-18-jboss-drools-vs-jboss-rules-part-deux'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        checks = [i['check'] for i in r.json().get('md', {}).get('issues', [])]
        assert 'links_dropped' not in checks, (
            f'links_dropped fired because 7 addtoany share widgets inflate the unique '
            f'href count. The ?linkurl=<encoded-url> pattern is the universal signature '
            f'of social sharing widgets — they must be excluded from the link count. '
            f'Issues: {checks}')


class TestTechnicalTermsMissing:
    """technical_terms_missing must not fire when the term is in the front matter title.

    Short posts like 'Drools blog now has 612 subscribers' have 'drools' in
    the title field but not in the body — the body may just be 1-2 sentences.
    The term IS preserved in the MD (front matter), so it's not lost.

    FAILS before fix: check searches _body(md) only, misses the title field.
    PASSES after fix: search full MD (title + body).
    """

    def test_term_in_title_not_flagged(self, session):
        slug = '2008-03-06-drools-blog-now-has-612-subscribers'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        checks = [i['check'] for i in r.json().get('md', {}).get('issues', [])]
        assert 'technical_terms_missing' not in checks, (
            f'"drools" is in the front matter title but technical_terms_missing fired. '
            f'The check must search the full MD (title + body), not body only. '
            f'Issues: {checks}')


class TestTableDropped:
    """table_dropped must not fire when table content IS in the MD.

    html2text renders HTML tables as pipe-tables where the first cell appears
    BEFORE the first | character: 'Company:| [JDM Systems](<url>)  \\n---|---'
    The check's regex r'^\\|.+\\|' only matches lines STARTING with |, missing
    html2text's format entirely. Also, get_text(strip=True)[:20] merges words
    differently from the MD which has inline links and pipe separators.

    FAILS before fix: both md_has_table and md_has_table_text return False.
    PASSES after fix: regex detects pipes mid-line; text check uses 4-word match.
    """

    def test_pipe_table_in_md_not_flagged(self, session):
        slug = '2010-04-12-drools-job-in-healthcare'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        checks = [i['check'] for i in r.json().get('md', {}).get('issues', [])]
        assert 'table_dropped' not in checks, (
            f'table_dropped fired but the table IS in the MD as a pipe table. '
            f'html2text format: "Company:| [text](<url>)\\n---|---" — content before |. '
            f'Fix: regex must match pipes mid-line, not just at line start. '
            f'Issues: {checks}')

    def test_pacman_table_not_flagged(self, session):
        slug = '2009-11-18-drools-does-pacman'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        checks = [i['check'] for i in r.json().get('md', {}).get('issues', [])]
        assert 'table_dropped' not in checks, (
            f'Pacman ghost table IS in the MD (Ghost Color| Original...). '
            f'Issues: {checks}')


class TestWordCountLow:
    """word_count_low must not fire when the difference is explained by code blocks.

    The check counts HTML words from article.get_text() (includes <pre> content)
    but strips code blocks from the MD word count. This creates an unfair
    comparison for technical posts where most content IS code.

    FAILS before fix: HTML counts code words, MD doesn't → false low ratio.
    PASSES after fix: _article_words() also strips <pre>/<code> from HTML count.
    """

    def test_code_heavy_post_not_flagged(self, session):
        """'What a difference two years make' has old Drools rule syntax in <pre>
        that correctly becomes a code block in the MD. The word count comparison
        is unfair: HTML counts the code words, MD doesn't.
        """
        slug = '2007-09-13-jboss-drools-what-a-difference-two-years-make'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        checks = [i['check'] for i in r.json().get('md', {}).get('issues', [])]
        assert 'word_count_low' not in checks, (
            f'word_count_low is a false positive: HTML <pre> content inflates the '
            f'HTML word count but the MD correctly puts it in code blocks (stripped). '
            f'Fix: strip <pre>/<code> from HTML word count to make comparison fair. '
            f'Issues: {checks}')


class TestTruncatedFootnoteAsterisk:
    """truncated_at_end must not fire when the last paragraph uses [* text] footnote
    notation. The '*' in HTML get_text() produces '[* note:...]' but the body
    stripping removes '*' characters to clean markdown bold markers, leaving
    '[ note:...]'. These don't match even though the content is identical.

    Fix: also strip '*' from the first_words phrase before comparing.
    """

    def test_footnote_asterisk_not_flagged(self, session):
        slug = '2012-10-24-drools-5-5-0-cr1-released'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        checks = [i['check'] for i in r.json().get('md', {}).get('issues', [])]
        assert 'truncated_at_end' not in checks, (
            f'"[* Note: ...]" footnote causes truncated_at_end false positive. '
            f'HTML first_words = "[* note: at the time of" but MD body has '
            f'"[ note: at the time of" (asterisk stripped as markdown marker). '
            f'Fix: also strip "*" from first_words before comparing. '
            f'Issues: {checks}')


class TestAsciiDecoratorStripping:
    """=== decorator lines in HTML paragraphs must not generate false positives.

    Some posts have ASCII banners like "Supported by\n==========\nW3C" in their
    HTML. convert_post.py converts ==== lines to blank+--- (HR). But _load_article()
    in md_validator.py was not stripping them, so cross-checks compared:
      HTML: "supported by ======="   vs   MD: "supported by"
    and raised content_phrase_missing + truncated_at_end.

    Fix: strip ==== lines from the article HTML in _load_article() just as
    convert_post.py does during extraction.
    """

    def test_ruleml_ascii_separators_not_flagged(self, session):
        slug = '2011-10-25-ruleml2011brf-ft-lauderdale-florida-3-5-november-2011'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        bad = [i for i in issues if i['check'] in ('content_phrase_missing', 'truncated_at_end')]
        assert not bad, (
            f'==== decorator lines in HTML para are not stripped before cross-validation. '
            f'"Supported by ====..." in HTML but MD has blank+--- after convert_post.py fix. '
            f'Fix: strip ==== lines in _load_article(). '
            f'Issues: {bad}')


class TestPressReleaseTable:
    """Newsletter press-release posts have a layout <table> containing
    "PRESS RELEASE" and a "Forward this message to a friend" email-marketing link.

    Two issues:
    1. "Forward this message to a friend" is email-list chrome — it must be
       stripped from the HTML before conversion, not kept in the MD.
    2. table_dropped fires because the body check looks for the 4-word phrase
       "press release forward this" in body_lower, but body_lower still has markdown
       formatting chars (**press release** [forward this) breaking the substring match.
       Fix: also strip ** markers from body_lower in cross_table_acknowledged.
    """

    def test_forward_to_friend_not_in_md(self, session):
        slug = '2011-08-02-release-call-to-relieve-constraints-on-ai'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        assert not any(i['check'] == 'table_dropped' for i in issues), (
            f'table_dropped fired for a layout table whose content is in the MD. '
            f'The body check fails because bold markers (**press release**) break '
            f'the 4-word phrase substring search. '
            f'Fix: strip ** markers from body_lower in cross_table_acknowledged. '
            f'Issues: {issues}'
        )

    def test_forward_to_friend_link_stripped(self, session):
        """The "Forward this message to a friend" email-marketing link must not
        appear in the generated MD — it is newsletter template chrome."""
        slug = '2011-08-02-release-call-to-relieve-constraints-on-ai'
        # Re-generate and check the MD content via the API
        r = session.post(f'{API}/posts/{slug}/generate-md?dry=1')
        content = r.json().get('content', '')
        assert 'Forward this message' not in content, (
            f'"Forward this message to a friend" newsletter chrome is in the MD. '
            f'It lives in an email-marketing link (href contains send_to_friend) '
            f'inside a layout <table> — it should be stripped in convert_post.py. '
            f'Content snippet: {content[:300]!r}'
        )


class TestImageCaptionParagraphs:
    """Paragraphs mixing <span> captions and <img> links must not trigger
    phrase-check false positives.

    Pattern: a single <p> contains alternating caption spans and image links
    separated by <br/>. The validator extracts the full paragraph text as one
    long phrase, but the MD interleaves image markup between the captions, so
    the phrase never appears as a continuous substring.

    Fix: cross_key_phrase_sample and cross_last_section_present must skip
    paragraphs that contain <img> elements.
    """

    def test_image_caption_paragraph_not_flagged(self, session):
        slug = '2010-04-21-drools-san-diego-2010-more-photos'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        bad = [i for i in issues if i['check'] in ('content_phrase_missing', 'truncated_at_end')]
        assert not bad, (
            f'Paragraph mixing <span> captions with <img> links produces false positives. '
            f'HTML text "The Food Line Keith showing..." is one paragraph but the MD '
            f'interleaves image links between captions, breaking any phrase match. '
            f'Fix: skip <p> elements containing <img> in cross_key_phrase_sample '
            f'and cross_last_section_present. '
            f'Issues: {bad}'
        )


class TestBoldMarkersInPhraseChecks:
    """Bold markers adjacent to punctuation must not cause false positives.

    HTML: "Keynotes and Speeches: Bob Kowalski (Imperial College London)..."
    MD:   "**Keynotes and Speeches:**\\n**Bob Kowalski**(Imperial College London)..."

    Two separate bugs:
    1. cross_key_phrase_sample does not strip ** from the body, so the phrase
       "and speeches: bob kowalski (imperial" fails to match
       "and speeches:** \\n**bob kowalski**(imperial".
    2. cross_last_section_present strips ** with empty string, so
       "**Bob Kowalski**(Imperial" → "Bob Kowalski(Imperial" — the space that
       the HTML has before "(" disappears, breaking the first_words lookup.

    Fix: in both checks, strip bold/italic markers by replacing with a space
    (not empty string) and normalise all whitespace.
    """

    def test_bold_adjacent_to_punctuation_not_flagged(self, session):
        slug = '2017-06-26-rulemlrr-with-decisioncamp-july-12-14-201-london'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        bad = [i for i in issues if i['check'] in ('content_phrase_missing', 'truncated_at_end')]
        assert not bad, (
            f'Bold markers adjacent to punctuation cause false positives. '
            f'HTML has "Keynotes and Speeches: Bob Kowalski (Imperial..." '
            f'but MD has "**Keynotes and Speeches:**\\n**Bob Kowalski**(Imperial...". '
            f'cross_key_phrase_sample does not strip ** from body; '
            f'cross_last_section_present strips ** with empty string, losing space before "(". '
            f'Fix: replace ** with space (not empty) and normalise whitespace in both checks. '
            f'Issues: {bad}'
        )


class TestBlockquoteWrappedList:
    """<blockquote><ul> in old HTML = indentation trick, not a semantic quote.

    html2text converts this to "> * item" (blockquote + list item).
    Two bugs result:
    1. The ">" prefix makes lists_dropped fire because the regex ^\s*[-*]\s
       doesn't match ">   * item" (the > prevents the match).
    2. The generated MD has "> * item" which renders as a blockquoted list,
       not a plain list — the ">" is visual noise from an HTML indentation hack.

    Fixes:
    1. In convert_post.py: unwrap <blockquote> elements that contain only
       <ul>/<ol> with no surrounding text — they are indentation wrappers.
    2. In md_validator.py: update lists_dropped regex to also match "> * item".
    """

    def test_blockquote_wrapped_list_no_visual_gt(self, session):
        """Regenerated MD must not have '>   * item' format — plain list only."""
        slug = '2009-03-28-the-first-drools-book-is-on-the-way-from-packt-publishing'
        r = session.post(f'{API}/posts/{slug}/generate-md?dry=1')
        content = r.json().get('content', '')
        assert '>   *' not in content and '> *' not in content, (
            f'<blockquote><ul> indentation hack produced "> * item" in MD. '
            f'The blockquote is visual-only HTML — unwrap it in convert_post.py '
            f'when it contains only <ul>/<ol>. '
            f'Content snippet: {content[400:600]!r}'
        )

    def test_blockquote_wrapped_list_not_flagged_as_dropped(self, session):
        """lists_dropped must not fire after the blockquote unwrap fix."""
        slug = '2009-03-28-the-first-drools-book-is-on-the-way-from-packt-publishing'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        # After regeneration the MD will have plain list items — validator must find them
        assert not any(i['check'] == 'lists_dropped' for i in issues), (
            f'lists_dropped fired. After fix, MD has plain "* item" (no ">") '
            f'so the existing regex should match. '
            f'Issues: {issues}'
        )


class TestListsDroppedRegex:
    """lists_dropped must not fire for posts whose MD has numbered lists.

    Bug: regex r'^\s*[-*]\s|\s*^\d+\.\s' — the second alternative \s*^\d+\.\s
    is broken: ^ in MULTILINE must begin the alternative, not follow \s*.
    This makes numbered lists (1. item) invisible to the check, causing
    lists_dropped to fire even when the MD has correct numbered list items.
    Fix: r'^\s*[-*]\s|^\s*\d+\.'
    """

    def test_numbered_list_not_flagged(self, session):
        # Post with numbered list in HTML that converts to numbered MD list
        slug = '2007-05-23-working-with-jboss-rules-and-web-services'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        assert not any(i['check'] == 'lists_dropped' for i in issues), (
            f'lists_dropped fired despite MD having list items. '
            f'Regex r"^\s*[-*]\s|\s*^\d+\.\s" has broken numbered-list alternative '
            f'(\s*^ is invalid — ^ must start the alternative). '
            f'Fix: r"^\s*[-*]\s|^\s*\d+\." '
            f'Issues: {issues}'
        )


class TestLinksDroppedAutolinks:
    """links_dropped must count <http://...> autolinks as well as [text](<url>) links.

    Bug: regex r'\]\(<?\s*https?://' only matches Markdown-style links.
    Bare URLs in the MD appear as <http://...> autolinks — html2text produces
    these for bare URL text in HTML paragraphs. They are real links but the
    regex misses them, so html_count >> md_count triggers a false positive.
    Fix: r'(?:\]\(<?\s*https?://|<https?://)' to also count autolinks.
    """

    def test_autolinks_counted(self, session):
        slug = '2011-08-01-call-for-demos-ruleml2011-5th-internationalrule-challenge'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        assert not any(i['check'] == 'links_dropped' for i in issues), (
            f'links_dropped fired because <http://...> autolinks not counted. '
            f'Regex only matches [text](<url>) format — misses bare <http://...> '
            f'autolinks that html2text produces for plain URLs in paragraphs. '
            f'Fix: add |<https?:// to the counting regex. '
            f'Issues: {issues}'
        )


class TestPhraseWithInlineListMarkers:
    """content_phrase_missing must not fire when HTML uses * as inline list markers.

    Pattern: <p>Summary: * item1 * item2 * item3</p> in the HTML —
    html2text converts these to proper bullet list items in the MD.
    The phrase extractor sees "summary: * item1 * ite" but the MD body has
    "summary:\n- item1\n- item2" — the * is gone, phrase does not match.
    Fix: strip * from the phrase before comparison (same as first_words in
    cross_last_section_present already does).
    """

    def test_inline_star_markers_not_flagged(self, session):
        slug = '2012-03-13-ruleml2012-the-6th-international-symposium-on-rules'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        bad = [i for i in issues if i['check'] == 'content_phrase_missing']
        assert not bad, (
            f'content_phrase_missing fired for paragraph with inline * list markers. '
            f'"* Rules and Automated Reasoning * Logic Programming..." in HTML '
            f'becomes bullet list items in MD — phrase with * never appears. '
            f'Fix: re.sub(r"\*+", " ", phrase) before searching. '
            f'Issues: {bad}'
        )


class TestTruncatedAtEndWithAutolink:
    """truncated_at_end must not fire when the last HTML paragraph contains
    a bare URL that becomes a <http://...> autolink in the MD.

    Pattern: HTML has "Release Notes summary – http://wiki.jboss.org/..."
    as one paragraph. MD splits it across lines with trailing spaces and
    renders the URL as a bare <http://...> autolink.

    cross_last_section_present strips URLs from first_words before comparing,
    but the body preparation was NOT stripping bare <http://...> autolinks —
    only [text](<url>) Markdown links. So the body had
    "summary – <http://wiki.jboss.org/...> detailed" but first_words had
    "summary – detailed" (URL stripped). The autolink sat in the gap,
    breaking the substring match.

    Fix: also strip bare <http://...> autolinks from the body in
    cross_last_section_present (same treatment already applied in
    cross_key_phrase_sample).
    """

    def test_last_para_with_autolink_not_flagged(self, session):
        slug = '2007-06-26-4-0-0-mr3-released'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        bad = [i for i in issues if i['check'] == 'truncated_at_end']
        assert not bad, (
            f'truncated_at_end fired for last paragraph containing a bare URL. '
            f'HTML: "Release Notes summary – http://wiki.jboss.org/..." '
            f'MD: autolink <http://...> sits between "–" and "detailed" so the '
            f'stripped first_words "summary – detailed" is not a substring of '
            f'"summary – <http://...> detailed". '
            f'Fix: strip bare <https?://[^>]+> autolinks from body_raw in '
            f'cross_last_section_present. '
            f'Issues: {bad}'
        )


class TestEmptyAnchorArtifactStripping:
    """Empty <a href="url"> anchors (no link text) produce [](<url>) artifacts
    in the MD when html2text converts them with protect_links=True.

    When these artifacts appear at the START of a line before real content
    (e.g. [](<url>)[](<url>)A recent Decision Modeling...), the JUNK_LINES
    pattern r'^\[\]\(<https?://' removes the ENTIRE line, silently dropping
    the paragraph.

    Fix: strip the [](<url>) prefix from lines rather than removing the whole
    line, so content that follows is preserved.
    """

    def test_paragraph_after_empty_anchor_artifact_preserved(self, session):
        slug = '2015-02-09-the-relationship-of-decision-model-and-notation-dmn-to-sbvr-and-bpmn'
        r = session.post(f'{API}/posts/{slug}/generate-md?dry=1')
        content = r.json().get('content', '')
        assert 'Decision Modeling Information Day' in content, (
            f'Paragraph "A recent Decision Modeling Information Day..." missing from MD. '
            f'Empty <a href="blog.athico.com"></a> anchors before it become '
            f'[](<url>)[](<url>) in html2text output. The JUNK_LINES pattern '
            f'r"^\\[\\]\\(<https?://" removes the entire line, erasing the '
            f'real paragraph that follows on the same line. '
            f'Fix: strip the [](<url>) prefix instead of removing the whole line.'
        )

    def test_third_paragraph_after_artifact_preserved(self, session):
        """The 3rd paragraph ('This quote says a little about how DMN may relate...')
        also starts with empty anchor artifacts and was dropped by the same bug."""
        slug = '2015-02-09-the-relationship-of-decision-model-and-notation-dmn-to-sbvr-and-bpmn'
        r = session.post(f'{API}/posts/{slug}/generate-md?dry=1')
        content = r.json().get('content', '')
        # This specific phrase is in the 3rd div paragraph — not anywhere else in the post
        assert 'This quote says a little' in content, (
            f'Paragraph "This quote says a little about how DMN may relate..." missing. '
            f'Same cause: empty anchor artifact at line start removes the entire line. '
            f'Content snippet: {content[500:800]!r}'
        )


class TestTruncatedAtEndUrlAsLinkText:
    """truncated_at_end must not fire when the last paragraph contains links
    whose text IS a bare URL (e.g. [http://uni-rostock.de](<url>)).

    After stripping [text](<url>) links, the link TEXT (which is a URL) was
    left in the body as plain text: "rostock, http://uni-rostock.de chair of".
    But first_words strips URLs from the HTML text, giving "rostock, chair of".
    These don't match: body has the URL text, first_words doesn't.

    Fix: when the link text is itself a URL (starts with http), discard it
    during link stripping (same treatment as first_words gives to URLs in
    the HTML paragraph text).
    """

    def test_url_as_link_text_not_flagged(self, session):
        slug = '2008-09-17-improving-the-naval-engineering-process-using-drools-michael-zimmermann'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        bad = [i for i in issues if i['check'] == 'truncated_at_end']
        assert not bad, (
            f'truncated_at_end fired for last paragraph containing [url](<url>) links. '
            f'HTML has "University of Rostock, http://uni-rostock.de Chair of..." '
            f'After link stripping, body kept the URL text but first_words stripped it, '
            f'causing a mismatch. Fix: discard link text that is itself a URL. '
            f'Issues: {bad}'
        )


class TestTruncatedAtEndOpeningQuote:
    """truncated_at_end must not fire when the last HTML paragraph starts with
    an opening quotation mark followed by a space before the actual text.

    Pattern: HTML text node '" The technology however...' (U+201C + space + The)
    splits into words ['"', 'The', 'technology', ...] so first_words becomes
    '" the technology however has some' with a space after the quote.

    The MD has '"The technology...' (quote directly before The, no space), so
    body has '"the technology...' — the space in first_words breaks the match.

    Fix: strip space immediately after an opening quotation mark in first_words
    so '" the technology' normalises to '"the technology' and matches the body.
    """

    def test_opening_quote_space_not_flagged(self, session):
        slug = '2009-04-22-the-bpm-technology-convergence'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        bad = [i for i in issues if i['check'] == 'truncated_at_end']
        assert not bad, (
            f'truncated_at_end fired for last paragraph starting with \'"\' + space. '
            f'HTML has \'" The technology...\' (U+201C + space + text) so first_words '
            f'gets the space, but the MD has \'"The technology...\' without it. '
            f'Fix: strip space after opening quote chars in first_words. '
            f'Issues: {bad}'
        )


class TestIssuesPanelScrollSync:
    """Issues panel toggle must rebuild scroll anchors.

    The issue panel (200px by default) steals vertical space from #panels.
    This reduces mdBody.clientHeight and iWin.innerHeight, which increases
    mdMax (= scrollHeight - clientHeight) and htMax.

    buildScrollAnchors() is only called on iframe load. Toggling the issues
    panel never rebuilds them, so the max-scroll anchors are stale. When you
    scroll either panel to its true bottom, the interpolation clamps against
    the OLD (lower) max — and the other side stops short. The bottom portion
    of that side is never reached by sync: "one side can't be seen."

    Fix: call requestAnimationFrame(() => buildScrollAnchors()) at the end of
    toggleIssues(), and again after the resize-handle mouseup.
    """

    @pytest.fixture(scope='class')
    def panel_page(self, page):
        """A second tab in the same Playwright browser context.

        Using page.context.new_page() avoids creating a second sync_playwright()
        context — which would conflict with the module-level one already running
        its asyncio event loop.
        """
        slug = SLUG  # long post with headings — meaningful anchors
        # page.context is a single-page implicit context; use browser.new_context()
        ctx = page.context.browser.new_context(viewport={'width': 1400, 'height': 900})
        pg = ctx.new_page()
        pg.goto(APP_URL, wait_until='networkidle')
        pg.wait_for_selector('.pi', timeout=15000)
        pg.locator(f'[data-slug="{slug}"]').click()
        pg.wait_for_function(
            f"() => document.getElementById('orig-frame')?.src?.includes('{slug}')",
            timeout=8000)
        pg.wait_for_timeout(800)  # iframe load + initial buildScrollAnchors
        # Ensure issues panel is closed at start
        is_open = pg.evaluate(
            "() => !document.getElementById('issue-panel').classList.contains('hidden')")
        if is_open:
            pg.click('#btn-issues')
            pg.wait_for_timeout(200)
        yield pg
        ctx.close()

    def test_scroll_anchors_rebuilt_after_issues_panel_toggle(self, panel_page):
        """Scroll anchors must be rebuilt when the issues panel is opened."""
        pg = panel_page

        # Confirm post is scrollable — need mdMax > 0 for a meaningful test
        scroll_info = pg.evaluate("""() => {
            const b = document.getElementById('md-panel-body');
            return { sh: b.scrollHeight, ch: b.clientHeight };
        }""")
        if scroll_info['sh'] <= scroll_info['ch']:
            pytest.skip('Post content too short to have meaningful scroll anchors')

        anchors_before = pg.evaluate("() => getScrollAnchors()")
        last_md_before = anchors_before[-1]['md'] if anchors_before else 0
        assert last_md_before > 0, 'Expected non-zero mdMax before toggling issues panel'

        # Open the issues panel — steals ~200 px from #panels
        pg.click('#btn-issues')
        pg.wait_for_timeout(200)  # enough for rAF + reflow

        anchors_after = pg.evaluate("() => getScrollAnchors()")
        last_md_after = anchors_after[-1]['md'] if anchors_after else 0

        # Cleanup: close the panel before asserting
        pg.click('#btn-issues')
        pg.wait_for_timeout(100)

        assert last_md_after > last_md_before, (
            f'Scroll anchors not rebuilt after issues panel opened. '
            f'Last anchor md: before={last_md_before:.0f}, after={last_md_after:.0f} '
            f'(should increase because mdBody.clientHeight shrank). '
            f'Fix: call requestAnimationFrame(() => buildScrollAnchors()) in toggleIssues().'
        )


class TestPhraseWithEscapedListMarkers:
    """content_phrase_missing must not fire when an HTML paragraph contains
    inline numbered list items (e.g. "Say,\n1. item\n2. item") separated
    by <br/> tags.

    Pattern: <p>Say,<br/>1. color == 'red'...<br/>2. when...</p> in HTML.
    html2text converts <br/> to trailing spaces + newline, and escapes any
    digit-dot at the start of a line to prevent accidental ordered-list parsing:
    "1." → "1\." in the MD body.

    The phrase extractor sees "say, 1. color == 'red' and" from the HTML
    but the MD body contains "say,   \n1\\. color == 'red'..." — the phrase
    "1." never appears literally because it is escaped to "1\." after collapse.

    Fix: in cross_key_phrase_sample body normalization, unescape digit-dot
    list markers: re.sub(r'(\d+)\\.', r'\1.', body_raw) so "1\." → "1."
    before the phrase search.
    """

    def test_escaped_numbered_list_markers_not_flagged(self, session):
        slug = '2008-03-19-drools-and-multi-colored-balls'
        r = session.post(f'{API}/posts/{slug}/validate-md')
        issues = r.json().get('md', {}).get('issues', [])
        bad = [i for i in issues if i['check'] == 'content_phrase_missing']
        assert not bad, (
            f'content_phrase_missing fired for paragraph with <br/>-separated '
            f'numbered items. HTML has "Say,\\n1. color == \'red\'..." but '
            f'html2text escapes "1." at line-start to "1\\." in the MD — '
            f'the phrase with unescaped "1." is never found. '
            f'Fix: add re.sub(r"(\\d+)\\\\.", r"\\1.", body_raw) before '
            f'the phrase search in cross_key_phrase_sample. '
            f'Issues: {bad}'
        )
