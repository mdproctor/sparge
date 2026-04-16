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
    check_md_notation_in_text,
    check_suspicious_encoded_html,
    check_layout_spacer_images,
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
# md_notation_in_text
# ══════════════════════════════════════════════════════════════════════════════

class TestMdNotationInText:
    """LESSON: Inline formatting elements immediately adjacent to a non-space
    character cause html2text to emit **text**(more — no space before the
    punctuation. The MD validator's plain-text phrase from the HTML has a space
    there ("text (more"), so the comparison fails.

    Detecting this in the HTML scan flags the post as "formatting-complex" so
    that MD phrase-check WARNings on it are understood to be structural artefacts
    rather than real content losses.

    Pattern that fires:  <b>Name </b>(Affiliation)
    html2text output:    **Name**(Affiliation)      ← trailing space inside ** eaten
    HTML plain text:     Name (Affiliation          ← space preserved
    """

    def test_b_adjacent_to_open_paren_detected(self):
        """<b>text</b>(more triggers the check."""
        art = article('<p><b>Bob Kowalski</b>(Imperial College London): talk title</p>')
        issues = check_md_notation_in_text(art)
        assert has_type(issues, 'md_notation_in_text'), (
            '<b>text</b>(text) not detected. '
            'html2text produces **text**(text) with no space before "(", '
            'which mismatches the HTML plain text "text (text". '
            'Fix: add check_md_notation_in_text() to scan_html.py.'
        )

    def test_strong_adjacent_to_colon_detected(self):
        """<strong>text</strong>: also triggers — colon is non-space."""
        art = article('<p><strong>Section</strong>: description here</p>')
        issues = check_md_notation_in_text(art)
        assert has_type(issues, 'md_notation_in_text')

    def test_em_adjacent_to_comma_detected(self):
        """<em>text</em>, trailing comma also triggers."""
        art = article('<p>See <em>section A</em>, which explains this.</p>')
        issues = check_md_notation_in_text(art)
        assert has_type(issues, 'md_notation_in_text')

    def test_space_after_closing_tag_not_flagged(self):
        """<b>text</b> word — space before next word is fine; html2text keeps it."""
        art = article('<p><b>Bob Kowalski</b> presented the keynote.</p>')
        assert is_clean(check_md_notation_in_text(art), 'md_notation_in_text')

    def test_formatting_at_end_of_element_not_flagged(self):
        """<b>text</b> at end of paragraph with no following sibling is fine."""
        art = article('<p>See <b>the appendix</b></p>')
        assert is_clean(check_md_notation_in_text(art), 'md_notation_in_text')

    def test_code_blocks_excluded(self):
        """Formatting inside <pre>/<code> is expected; must not flag."""
        art = article('<pre><code><b>bold</b>(call) in code</code></pre>')
        assert is_clean(check_md_notation_in_text(art), 'md_notation_in_text')

    def test_level_is_warn(self):
        """Should be a WARN — informational, not blocking."""
        art = article('<p><b>Name</b>(Org): title</p>')
        issues = check_md_notation_in_text(art)
        assert has_level(issues, 'md_notation_in_text', 'WARN')

    def test_detail_names_the_adjacent_character(self):
        """Detail should show the character immediately after the closing tag."""
        art = article('<p><b>Name</b>(Org): title</p>')
        issues = check_md_notation_in_text(art)
        notation = [i for i in issues if i['type'] == 'md_notation_in_text']
        assert notation
        assert '(' in notation[0]['detail'], (
            f'Detail should name the adjacent character. Got: {notation[0]["detail"]!r}'
        )

    def test_selector_points_to_formatting_element(self):
        """Issue selector targets the <b>/<strong> element for highlighting."""
        art = article('<p><b>Name</b>(Org): title</p>')
        issues = check_md_notation_in_text(art)
        notation = [i for i in issues if i['type'] == 'md_notation_in_text']
        assert notation and notation[0]['selector'] is not None

    def test_scan_post_includes_check(self, tmp_path):
        """scan_post() must run check_md_notation_in_text."""
        html = '<html><body><article><p><b>Name</b>(Org): title here</p></article></body></html>'
        p = tmp_path / 'post.html'
        p.write_text(html)
        issues = scan_post(p)
        assert has_type(issues, 'md_notation_in_text'), (
            'check_md_notation_in_text not called from scan_post(). '
            'Add it to the issues pipeline in scan_post().'
        )


# ══════════════════════════════════════════════════════════════════════════════
# suspicious_encoded_html
# ══════════════════════════════════════════════════════════════════════════════

class TestSuspiciousEncodedHtml:
    """LESSON: Blogger and some CMS platforms HTML-encode table/div markup when
    pasted into a rich-text editor.  The result is <pre><code> containing literal
    &lt;table&gt; text — when archived, html2text wraps this as a 20k-char code
    fence rather than a rendered table.  Automated detection lets the human decide
    whether the code block is intentional (e.g. an HTML example) or a conversion
    artefact.  The human can then dismiss the issue if it is intentional.
    """

    def test_pre_code_with_encoded_table_detected(self):
        """<pre><code> containing &lt;table is flagged as suspicious."""
        art = article('<pre><code>&lt;table&gt;&lt;tr&gt;&lt;td&gt;Cell&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;</code></pre>')
        issues = check_suspicious_encoded_html(art)
        assert has_type(issues, 'suspicious_code_content'), (
            '<pre><code> with HTML-encoded table not flagged as suspicious_code_content.'
        )

    def test_pre_code_with_encoded_div_detected(self):
        """`<pre><code>` with &lt;div is also suspicious."""
        art = article('<pre><code>&lt;div class="foo"&gt;content&lt;/div&gt;</code></pre>')
        issues = check_suspicious_encoded_html(art)
        assert has_type(issues, 'suspicious_code_content')

    def test_pre_code_with_real_code_not_flagged(self):
        """Legitimate code (no &lt; HTML tags) must not be flagged."""
        art = article('<pre><code>public class Foo { int x = 1; }</code></pre>')
        assert is_clean(check_suspicious_encoded_html(art), 'suspicious_code_content')

    def test_pre_code_with_xml_escapes_detected(self):
        """XML-escaped content (&lt;?xml) also flagged."""
        art = article('<pre><code>&lt;?xml version="1.0"?&gt;&lt;root/&gt;</code></pre>')
        issues = check_suspicious_encoded_html(art)
        assert has_type(issues, 'suspicious_code_content')

    def test_no_pre_code_not_flagged(self):
        """Inline HTML-encoded entities in a paragraph are fine."""
        art = article('<p>Use &lt;br&gt; for line breaks.</p>')
        assert is_clean(check_suspicious_encoded_html(art), 'suspicious_code_content')

    def test_level_is_warn(self):
        """Must be WARN — human decides if intentional."""
        art = article('<pre><code>&lt;table&gt;&lt;/table&gt;</code></pre>')
        issues = check_suspicious_encoded_html(art)
        assert has_level(issues, 'suspicious_code_content', 'WARN')

    def test_scan_post_includes_check(self, tmp_path):
        """scan_post() must include suspicious_code_content in its output."""
        html = ('<html><body><article>'
                '<pre><code>&lt;table&gt;&lt;tr&gt;&lt;td&gt;A&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;</code></pre>'
                '</article></body></html>')
        p = tmp_path / 'post.html'
        p.write_text(html)
        issues = scan_post(p)
        assert has_type(issues, 'suspicious_code_content'), (
            'check_suspicious_encoded_html not called from scan_post(). '
            'Add it to the issues pipeline.'
        )


# ══════════════════════════════════════════════════════════════════════════════
# layout_spacer_images
# ══════════════════════════════════════════════════════════════════════════════

class TestLayoutSpacerImages:
    """LESSON: Old HTML table layouts use 1×N transparent GIF images named
    'spacer.gif' (or similar) as invisible column/row separators.  These have
    zero content value in a blog archive — they produce broken-image indicators
    or external requests to defunct servers.  Detecting them lets the human
    decide whether to strip them (almost always yes) and allows the convert_post
    pipeline to remove them automatically in a follow-up fix.
    """

    def test_spacer_by_filename_detected(self):
        """<img src='.../spacer.gif'> is flagged."""
        art = article('<img src="//example.com/images/spacer.gif" width="25" height="1" alt="">')
        issues = check_layout_spacer_images(art)
        assert has_type(issues, 'layout_spacer_image'), (
            'spacer.gif image not detected as layout_spacer_image.'
        )

    def test_spacer_case_insensitive(self):
        """Filename matching must be case-insensitive (Spacer.GIF etc.)."""
        art = article('<img src="/assets/Spacer.GIF" width="1" height="1" alt="">')
        assert has_type(check_layout_spacer_images(art), 'layout_spacer_image')

    def test_height_one_empty_alt_detected(self):
        """1px-tall image with empty alt is a layout spacer even without 'spacer' in name."""
        art = article('<img src="//example.com/pixel.gif" width="100" height="1" alt="">')
        assert has_type(check_layout_spacer_images(art), 'layout_spacer_image')

    def test_content_image_not_flagged(self):
        """Normal content image must not be flagged."""
        art = article('<img src="diagram.png" width="800" height="600" alt="Architecture diagram">')
        assert is_clean(check_layout_spacer_images(art), 'layout_spacer_image')

    def test_height_one_with_real_alt_not_flagged(self):
        """1px-tall image with meaningful alt text is content, not a spacer."""
        art = article('<img src="line.png" width="600" height="1" alt="Horizontal divider">')
        assert is_clean(check_layout_spacer_images(art), 'layout_spacer_image')

    def test_level_is_warn(self):
        """Must be WARN — human confirms before removal."""
        art = article('<img src="spacer.gif" width="1" height="1" alt="">')
        issues = check_layout_spacer_images(art)
        assert has_level(issues, 'layout_spacer_image', 'WARN')

    def test_count_all_spacers(self):
        """All spacer images in a post must be reported (aggregate count)."""
        art = article(
            '<img src="spacer.gif" width="25" height="1" alt="">'
            '<img src="spacer.gif" width="10" height="1" alt="">'
            '<img src="real.png" width="400" height="300" alt="photo">'
        )
        issues = check_layout_spacer_images(art)
        spacer_issues = [i for i in issues if i['type'] == 'layout_spacer_image']
        # Reported as one aggregate issue with the count, not one-per-image
        assert spacer_issues, 'No spacer issues reported'
        assert '2' in spacer_issues[0]['detail'], (
            f'Expected count of 2 in detail. Got: {spacer_issues[0]["detail"]!r}'
        )

    def test_scan_post_includes_check(self, tmp_path):
        """scan_post() must run check_layout_spacer_images."""
        html = ('<html><body><article>'
                '<img src="//example.com/spacer.gif" width="25" height="1" alt="">'
                '</article></body></html>')
        p = tmp_path / 'post.html'
        p.write_text(html)
        issues = scan_post(p)
        assert has_type(issues, 'layout_spacer_image'), (
            'check_layout_spacer_images not called from scan_post().'
        )


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


class TestMissingLocalImagesWithPostsDir:
    """check_missing_local_images resolves assets from posts_dir, not post_path."""

    def test_resolves_from_posts_dir_not_post_path(self, tmp_path):
        """When posts_dir is given, assets are resolved relative to it —
        not relative to the scanned file. This ensures enriched copies
        (outside the original posts tree) resolve correctly."""
        # Set up a realistic project layout:
        #   serve_root/
        #     legacy/
        #       posts/mark-proctor/{slug}.html   <- original
        #       assets/images/test.jpg           <- asset EXISTS here
        #     sparge-projects/{id}/enriched/{slug}.html  <- enriched copy

        serve_root = tmp_path / 'serve_root'
        posts_dir  = serve_root / 'legacy' / 'posts' / 'mark-proctor'
        assets_dir = serve_root / 'legacy' / 'assets' / 'images'
        enriched_dir = tmp_path / 'sparge-projects' / 'proj' / 'enriched'

        posts_dir.mkdir(parents=True)
        assets_dir.mkdir(parents=True)
        enriched_dir.mkdir(parents=True)

        # Create an asset at the correct location
        (assets_dir / 'test.jpg').write_bytes(b'JPEG')

        html = '''<html><body><article>
            <img src="../../assets/images/test.jpg" alt="present">
            <img src="../../assets/images/missing.jpg" alt="absent">
        </article></body></html>'''

        # Write enriched copy — lives OUTSIDE the original posts tree
        enriched_file = enriched_dir / 'my-post.html'
        enriched_file.write_text(html)

        from bs4 import BeautifulSoup
        from scan_html import check_missing_local_images
        soup = BeautifulSoup(html, 'lxml')
        article = soup.find('article')

        # WITHOUT posts_dir: resolves from enriched_dir.parent.parent.parent
        # which is tmp_path/sparge-projects — assets not there, so BOTH flagged
        issues_no_dir = check_missing_local_images(article, enriched_file, posts_dir=None)
        assert len(issues_no_dir) == 2, \
            'Without posts_dir both images appear missing (old behaviour)'

        # WITH posts_dir: resolves from posts_dir.parent.parent = serve_root/legacy/
        # test.jpg IS there, missing.jpg is not
        issues_with_dir = check_missing_local_images(article, enriched_file, posts_dir=posts_dir)
        assert len(issues_with_dir) == 1, \
            'With posts_dir only the truly missing image is flagged'
        assert 'missing.jpg' in issues_with_dir[0]['detail']

    def test_scan_post_passes_posts_dir_through(self, tmp_path):
        """scan_post() accepts posts_dir and passes it to check_missing_local_images."""
        serve_root = tmp_path / 'serve_root'
        posts_dir  = serve_root / 'legacy' / 'posts' / 'mark-proctor'
        assets_dir = serve_root / 'legacy' / 'assets' / 'images'
        enriched_dir = tmp_path / 'enriched'

        posts_dir.mkdir(parents=True)
        assets_dir.mkdir(parents=True)
        enriched_dir.mkdir(parents=True)
        (assets_dir / 'logo.jpg').write_bytes(b'JPEG')

        html = '<html><body><article><img src="../../assets/images/logo.jpg"></article></body></html>'
        enriched_file = enriched_dir / 'post.html'
        enriched_file.write_text(html)

        from scan_html import scan_post

        # Without posts_dir: logo.jpg appears missing (wrong base)
        issues_bad = scan_post(enriched_file, posts_dir=None)
        missing_bad = [i for i in issues_bad if i['type'] == 'missing_local_image']
        assert len(missing_bad) == 1

        # With posts_dir: logo.jpg found correctly
        issues_good = scan_post(enriched_file, posts_dir=posts_dir)
        missing_good = [i for i in issues_good if i['type'] == 'missing_local_image']
        assert len(missing_good) == 0


class TestWordpressChromByline:
    """The scan must NOT report wordpress_chrome for the systematic
    'by Author - Date Category Article' byline pattern.

    This byline appears in all 580 KIE posts as a classless <div>.
    convert_post.py already strips it during conversion — flagging it in
    every scan clutters the issue panel with false-positives that need
    no human action.

    The scanner should still detect genuine chrome leakage (sidebars,
    related-posts widgets, comment forms) that the converter may miss.
    """

    def _make_html(self, article_body: str) -> str:
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/></head>
<body><article>{article_body}</article></body></html>"""

    def _scan(self, html: str, tmp_path) -> list:
        from scan_html import scan_post
        hp = tmp_path / 'post.html'
        hp.write_text(html, encoding='utf-8')
        return scan_post(hp)

    def test_byline_div_not_reported(self, tmp_path):
        """'by Author - Date Category Article' in a short unclassed <div>
        must NOT produce a wordpress_chrome issue.

        FAILS before fix (scan currently reports it).
        PASSES after pre-stripping bylines in scan_post().
        """
        html = self._make_html("""
            <div>by Mark Proctor - May 12, 2007 Rules Article</div>
            <h1>The Real Title</h1>
            <p>Actual post content here.</p>
        """)
        issues = self._scan(html, tmp_path)
        bylines = [i for i in issues
                   if i['type'] == 'wordpress_chrome'
                   and 'Rules Article' in i.get('detail', '')]
        assert not bylines, (
            f'Byline metadata "by Author - Date Category Article" must not be '
            f'reported as wordpress_chrome — convert_post.py already strips it, '
            f'so it is noise not a real issue.\n'
            f'Issues found: {[i["detail"] for i in bylines]}')

    def test_various_byline_formats_not_reported(self, tmp_path):
        """Different date/category formats must all be suppressed."""
        for byline in [
            "by Mark Proctor - October 31, 2013 Tools Article",
            "by Mark Proctor - January 1, 2007 Process Rules Article",
            "by Mark Proctor - June 6, 2007 Rules Article",
        ]:
            html = self._make_html(f"<div>{byline}</div><p>Content.</p>")
            issues = self._scan(html, tmp_path)
            chrome = [i for i in issues if i['type'] == 'wordpress_chrome']
            assert not chrome, (
                f'Byline {byline!r} must not be reported. '
                f'Got: {[i["detail"] for i in chrome]}')

    def test_genuine_chrome_still_detected(self, tmp_path):
        """Real chrome leakage (sidebar widgets, related posts) must still be caught."""
        html = self._make_html("""
            <div>by Mark Proctor - May 2007 Rules Article</div>
            <p>Content here.</p>
            <div>You might also like</div>
            <div>Leave a Reply</div>
        """)
        issues = self._scan(html, tmp_path)
        chrome_types = {i['type'] for i in issues}
        # byline removed, but sidebar/comment chrome still caught
        bylines = [i for i in issues
                   if i['type'] == 'wordpress_chrome' and 'Rules Article' in i.get('detail','')]
        other_chrome = [i for i in issues
                        if i['type'] == 'wordpress_chrome' and 'Rules Article' not in i.get('detail','')]
        assert not bylines, 'Byline must still be suppressed even alongside other chrome'
        assert other_chrome, (
            'Genuine chrome (sidebar widgets, comment forms) must still be detected '
            'even after byline suppression')
