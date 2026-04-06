"""
Tests for scan_html.py — the HTML archive scanner.

Each test class documents the issue type it guards against and the
LESSON that motivated the detection logic.

Run: python3 -m pytest blog-migrator/tests/test_scan_html.py -v
"""
import tempfile
from pathlib import Path

from scan_html import (
    scan_post,
    check_data_placeholders,
    check_noscript_remnants,
    check_external_images,
    check_tracking_pixels,
    check_missing_local_images,
    check_empty_embeds,
    check_unreplaced_gists,
    check_wordpress_chrome,
    check_missing_image_signals,
)
from bs4 import BeautifulSoup

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(f'<html><body><article>{html}</article></body></html>', 'lxml')

def article(html: str):
    return parse(html).find('article')

def write_html(html: str) -> Path:
    """Write a full HTML post to a temp file and return its path."""
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False,
                                   dir=tempfile.gettempdir())
    f.write(f'<html><body><article>{html}</article></body></html>')
    f.close()
    return Path(f.name)

def has_type(issues, t):
    return any(i['type'] == t for i in issues)

def has_level(issues, t, level):
    return any(i['type'] == t and i['level'] == level for i in issues)

def is_clean(issues, t):
    return not any(i['type'] == t for i in issues)


# ══════════════════════════════════════════════════════════════════════════════
# data_placeholder
# ══════════════════════════════════════════════════════════════════════════════

class TestDataPlaceholders:
    """LESSON: data: src images are unrecovered lazy-loaded placeholders.
    They render as broken/blank without JS and must be recovered or replaced
    with explicit missing-image placeholders before the archive is useful."""

    def test_catches_data_src(self):
        art = article('<img src="data:image/gif;base64,R0lGODlhAQABAIAAAP" alt="diagram">')
        issues = check_data_placeholders(art)
        assert has_level(issues, 'data_placeholder', 'ERROR')

    def test_catches_data_png(self):
        art = article('<img src="data:image/png;base64,abc123" alt="chart">')
        issues = check_data_placeholders(art)
        assert has_type(issues, 'data_placeholder')

    def test_captures_alt_text_in_detail(self):
        art = article('<img src="data:image/gif;base64,abc" alt="rete diagram">')
        issues = check_data_placeholders(art)
        assert any('rete diagram' in i['detail'] for i in issues)

    def test_clean_local_image(self):
        art = article('<img src="../../assets/images/2011/01/diagram.png" alt="ok">')
        assert is_clean(check_data_placeholders(art), 'data_placeholder')

    def test_clean_http_image(self):
        art = article('<img src="https://example.com/img.png" alt="ok">')
        assert is_clean(check_data_placeholders(art), 'data_placeholder')

    def test_multiple_placeholders(self):
        art = article('<img src="data:gif;base64,a" alt="a"><img src="data:png;base64,b" alt="b">')
        issues = check_data_placeholders(art)
        assert len([i for i in issues if i['type'] == 'data_placeholder']) == 2

    def test_selector_is_generated(self):
        art = article('<img src="data:image/gif;base64,abc" alt="x">')
        issues = check_data_placeholders(art)
        assert issues[0]['selector'] is not None


# ══════════════════════════════════════════════════════════════════════════════
# noscript_remnant
# ══════════════════════════════════════════════════════════════════════════════

class TestNoscriptRemnants:
    """LESSON: After replacing a lazy-loaded <img data-src> with a recovered
    image, the sibling <noscript> containing the original URL must also be
    removed. Orphaned noscripts clutter the DOM and confuse readers."""

    def test_catches_noscript_with_http_url(self):
        art = article('<noscript><img src="https://blog.kie.org/wp-content/img.png"></noscript>')
        issues = check_noscript_remnants(art)
        assert has_type(issues, 'noscript_remnant')

    def test_level_is_warn(self):
        art = article('<noscript><img src="https://example.com/img.png"></noscript>')
        issues = check_noscript_remnants(art)
        assert has_level(issues, 'noscript_remnant', 'WARN')

    def test_clean_empty_noscript(self):
        art = article('<noscript></noscript>')
        assert is_clean(check_noscript_remnants(art), 'noscript_remnant')

    def test_clean_no_noscript(self):
        art = article('<p>Normal paragraph with no noscript.</p>')
        assert is_clean(check_noscript_remnants(art), 'noscript_remnant')


# ══════════════════════════════════════════════════════════════════════════════
# external_image
# ══════════════════════════════════════════════════════════════════════════════

class TestExternalImages:
    """LESSON: Images with http/https src have not been localised.
    External hosts can go down, change URLs, or start serving different content.
    All content images must be downloaded locally for long-term archival."""

    def test_catches_http_image(self):
        art = article('<img src="https://blog.kie.org/wp-content/img.png" alt="x">')
        issues = check_external_images(art)
        assert has_type(issues, 'external_image')

    def test_catches_http_not_https(self):
        art = article('<img src="http://example.com/old-img.jpg" alt="x">')
        issues = check_external_images(art)
        assert has_type(issues, 'external_image')

    def test_clean_local_image(self):
        art = article('<img src="../../assets/images/2011/01/img.png" alt="ok">')
        assert is_clean(check_external_images(art), 'external_image')

    def test_clean_legacy_path(self):
        art = article('<img src="/legacy/assets/images/2011/01/img.png" alt="ok">')
        assert is_clean(check_external_images(art), 'external_image')

    def test_tracking_pixel_not_double_counted(self):
        # 1×1 tracking pixels are skipped by external_image check (they have their own type)
        art = article('<img src="https://stats.wordpress.com/px.gif" width="1" height="1">')
        assert is_clean(check_external_images(art), 'external_image')


# ══════════════════════════════════════════════════════════════════════════════
# tracking_pixel
# ══════════════════════════════════════════════════════════════════════════════

class TestTrackingPixels:
    """LESSON: WordPress themes embed 1×1 tracking pixels from analytics vendors.
    These fire requests to third-party servers when the archive is viewed,
    which is a privacy violation and serves no archival purpose."""

    def test_catches_wordpress_stats_pixel(self):
        art = article('<img src="https://stats.wordpress.com/b.gif" width="1" height="1">')
        assert has_type(check_tracking_pixels(art), 'tracking_pixel')

    def test_catches_quantserve(self):
        art = article('<img src="https://pixel.quantserve.com/pixel/abc.gif" width="1" height="1">')
        assert has_type(check_tracking_pixels(art), 'tracking_pixel')

    def test_catches_google_analytics(self):
        art = article('<img src="https://www.google-analytics.com/collect?v=1" width="1" height="1">')
        assert has_type(check_tracking_pixels(art), 'tracking_pixel')

    def test_level_is_warn(self):
        art = article('<img src="https://stats.wordpress.com/b.gif" width="1" height="1">')
        assert has_level(check_tracking_pixels(art), 'tracking_pixel', 'WARN')

    def test_clean_content_image(self):
        art = article('<img src="https://example.com/diagram.png" width="800" height="600">')
        assert is_clean(check_tracking_pixels(art), 'tracking_pixel')

    def test_clean_local_image(self):
        art = article('<img src="../../assets/images/2011/01/img.png">')
        assert is_clean(check_tracking_pixels(art), 'tracking_pixel')


# ══════════════════════════════════════════════════════════════════════════════
# empty_embed
# ══════════════════════════════════════════════════════════════════════════════

class TestEmptyEmbeds:
    """LESSON: WordPress lazy-loads iframes just like images — the src is
    in data-src or injected by JS. Without JS, these render as empty boxes.
    Each empty iframe needs Playwright recovery or manual URL lookup."""

    def test_catches_iframe_no_src(self):
        art = article('<iframe width="560" height="315"></iframe>')
        assert has_type(check_empty_embeds(art), 'empty_embed')

    def test_catches_iframe_empty_src(self):
        art = article('<iframe src="" width="560" height="315"></iframe>')
        assert has_type(check_empty_embeds(art), 'empty_embed')

    def test_catches_iframe_data_src_only(self):
        # Has data-src but src not wired — WARN not ERROR
        art = article('<iframe data-src="https://www.youtube.com/embed/abc" src=""></iframe>')
        issues = check_empty_embeds(art)
        assert has_level(issues, 'empty_embed', 'WARN')

    def test_no_src_is_error(self):
        art = article('<iframe width="560" height="315"></iframe>')
        assert has_level(check_empty_embeds(art), 'empty_embed', 'ERROR')

    def test_clean_iframe_with_src(self):
        art = article('<iframe src="https://www.youtube.com/embed/abc123" width="560" height="315"></iframe>')
        assert is_clean(check_empty_embeds(art), 'empty_embed')

    def test_clean_no_iframes(self):
        art = article('<p>Text with no embeds.</p>')
        assert is_clean(check_empty_embeds(art), 'empty_embed')


# ══════════════════════════════════════════════════════════════════════════════
# unreplaced_gist
# ══════════════════════════════════════════════════════════════════════════════

class TestUnreplacedGists:
    """LESSON: GitHub Gist embeds are <script src="gist.github.com/..."> tags.
    They require JS to render and must be replaced with the raw code content
    fetched from the GitHub API during archival."""

    def test_catches_gist_script(self):
        art = article('<script src="https://gist.github.com/user/abc123def.js"></script>')
        assert has_type(check_unreplaced_gists(art), 'unreplaced_gist')

    def test_catches_without_user(self):
        art = article('<script src="https://gist.github.com/abc123.js"></script>')
        assert has_type(check_unreplaced_gists(art), 'unreplaced_gist')

    def test_level_is_error(self):
        art = article('<script src="https://gist.github.com/user/abc.js"></script>')
        assert has_level(check_unreplaced_gists(art), 'unreplaced_gist', 'ERROR')

    def test_clean_non_gist_script(self):
        art = article('<script src="https://cdnjs.cloudflare.com/highlight.js"></script>')
        assert is_clean(check_unreplaced_gists(art), 'unreplaced_gist')

    def test_clean_inlined_gist(self):
        # Properly replaced with a <pre> block
        art = article('<pre><code class="language-java">int x = 1;</code></pre>')
        assert is_clean(check_unreplaced_gists(art), 'unreplaced_gist')

    def test_clean_no_scripts(self):
        art = article('<p>Plain content, no scripts.</p>')
        assert is_clean(check_unreplaced_gists(art), 'unreplaced_gist')


# ══════════════════════════════════════════════════════════════════════════════
# wordpress_chrome
# ══════════════════════════════════════════════════════════════════════════════

class TestWordpressChrome:
    """LESSON: WordPress theme elements (share widgets, bylines, author boxes,
    comment forms) leak into the article body when stripping is incomplete.
    Theme variations mean the CSS-selector approach misses some elements."""

    def test_catches_leave_reply(self):
        art = article('<div><p>Leave a Reply</p><form></form></div>')
        assert has_type(check_wordpress_chrome(art), 'wordpress_chrome')

    def test_catches_share_this(self):
        art = article('<p>Share this:</p>')
        assert has_type(check_wordpress_chrome(art), 'wordpress_chrome')

    def test_catches_view_all_posts_by(self):
        art = article('<p>View all posts by Mark Proctor</p>')
        assert has_type(check_wordpress_chrome(art), 'wordpress_chrome')

    def test_catches_addtoany_class(self):
        art = article('<div class="addtoany_share_save_container"><a>Share</a></div>')
        assert has_type(check_wordpress_chrome(art), 'wordpress_chrome')

    def test_clean_normal_content(self):
        art = article('<p>Drools is a rule engine used in enterprise applications.</p>')
        assert is_clean(check_wordpress_chrome(art), 'wordpress_chrome')

    def test_clean_legitimate_author_mention(self):
        # Mentioning the author in body text is fine — short paragraphs only checked
        long_text = 'Mark Proctor has been working on Drools for over 15 years, ' \
                    'contributing to multiple major versions of the engine and its ecosystem tools.'
        art = article(f'<p>{long_text}</p>')
        assert is_clean(check_wordpress_chrome(art), 'wordpress_chrome')


# ══════════════════════════════════════════════════════════════════════════════
# missing_image_signal
# ══════════════════════════════════════════════════════════════════════════════

class TestMissingImageSignals:
    """LESSON: Authors write phrases like "as shown below" before images.
    When an image was not recovered, the text becomes a dangling reference.
    These should be detected and flagged so a placeholder can be inserted."""

    def test_catches_as_shown_below(self):
        art = article('<p>The workflow is as shown below.</p><p>Next paragraph.</p>')
        assert has_type(check_missing_image_signals(art), 'missing_image_signal')

    def test_catches_following_screenshot(self):
        art = article('<p>The following screenshot shows the configuration panel.</p><p>After.</p>')
        assert has_type(check_missing_image_signals(art), 'missing_image_signal')

    def test_catches_click_to_enlarge(self):
        art = article('<p>Click to enlarge</p><p>After.</p>')
        assert has_type(check_missing_image_signals(art), 'missing_image_signal')

    def test_clean_when_image_follows(self):
        art = article('<p>As shown below.</p><img src="../../assets/img.png" alt="x">')
        assert is_clean(check_missing_image_signals(art), 'missing_image_signal')

    def test_clean_when_placeholder_follows(self):
        art = article('<p>As shown below.</p><div class="missing-image">📷 Missing image</div>')
        assert is_clean(check_missing_image_signals(art), 'missing_image_signal')

    def test_clean_normal_paragraph(self):
        art = article('<p>Drools uses the Rete algorithm to process rules efficiently.</p>')
        assert is_clean(check_missing_image_signals(art), 'missing_image_signal')

    def test_ignores_long_paragraphs(self):
        # Signal phrases in long paragraphs are incidental, not markers
        long = 'As shown below is a detailed analysis of the Rete network algorithm, ' \
               'which forms the core of the Drools production rule system and ' * 5
        art = article(f'<p>{long}</p><p>After.</p>')
        assert is_clean(check_missing_image_signals(art), 'missing_image_signal')


# ══════════════════════════════════════════════════════════════════════════════
# scan_post integration
# ══════════════════════════════════════════════════════════════════════════════

class TestScanPostIntegration:
    """Integration tests for the full scan_post() function."""

    def test_clean_post_has_no_issues(self):
        path = write_html('<h2>Rule Engines</h2><p>Drools is a rule engine.</p>')
        try:
            issues = scan_post(path)
            # A clean post with no problematic elements should have no errors
            errors = [i for i in issues if i['level'] == 'ERROR']
            assert not errors, f'Clean post has errors: {errors}'
        finally:
            path.unlink()

    def test_detects_multiple_issue_types(self):
        # Post with data: placeholder AND empty iframe AND gist
        html = (
            '<p>Content here.</p>'
            '<img src="data:image/gif;base64,abc" alt="diagram">'
            '<iframe width="560" height="315"></iframe>'
            '<script src="https://gist.github.com/user/abc.js"></script>'
        )
        path = write_html(html)
        try:
            issues = scan_post(path)
            types = {i['type'] for i in issues}
            assert 'data_placeholder' in types
            assert 'empty_embed' in types
            assert 'unreplaced_gist' in types
        finally:
            path.unlink()

    def test_returns_selectors(self):
        path = write_html('<img src="data:image/gif;base64,abc" alt="x">')
        try:
            issues = scan_post(path)
            # At least one issue should have a selector
            assert any(i.get('selector') for i in issues)
        finally:
            path.unlink()

    def test_handles_missing_article_element(self):
        # Falls back to body if no <article>
        import tempfile
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
        f.write('<html><body><p>No article tag here.</p></body></html>')
        f.close()
        path = Path(f.name)
        try:
            issues = scan_post(path)
            # Should not crash, may return no issues or no_article issue
            assert isinstance(issues, list)
        finally:
            path.unlink()

    def test_handles_unreadable_file(self):
        # Non-existent file should return an error issue, not crash
        issues = scan_post(Path('/tmp/this-file-does-not-exist-xyz.html'))
        assert any(i['level'] == 'ERROR' for i in issues)


# ══════════════════════════════════════════════════════════════════════════════
# Selector generation
# ══════════════════════════════════════════════════════════════════════════════

class TestSelectorGeneration:
    """Selectors are used for in-browser highlighting — must be non-None
    for elements that can be uniquely addressed."""

    def test_selector_for_img(self):
        from scan_html import _selector
        soup = BeautifulSoup('<article><p><img src="data:gif" alt="x"></p></article>', 'lxml')
        img = soup.find('img')
        sel = _selector(img)
        assert sel is not None
        assert 'img' in sel

    def test_selector_uses_id_when_available(self):
        from scan_html import _selector
        soup = BeautifulSoup('<article><div id="main-content"><p>text</p></div></article>', 'lxml')
        div = soup.find('div', id='main-content')
        sel = _selector(div)
        assert sel == '#main-content'

    def test_selector_with_nth_of_type(self):
        from scan_html import _selector
        soup = BeautifulSoup('<article><p>first</p><p>second</p></article>', 'lxml')
        second_p = soup.find_all('p')[1]
        sel = _selector(second_p)
        assert 'nth-of-type(2)' in sel
