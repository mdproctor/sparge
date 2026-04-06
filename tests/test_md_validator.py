"""
Test suite for md_validator.py — ported from tests/test_md_validator.py
plus additional coverage for previously untested cross-checks.

Run: python3 -m pytest blog-migrator/tests/test_md_validator.py -v
"""
import tempfile
from pathlib import Path

from md_validator import validate, MD_CHECKS, CROSS_CHECKS, Issue

# ── Helpers ───────────────────────────────────────────────────────────────────

MINIMAL_FM = """\
---
layout: post
title: "Test Post"
date: 2011-01-01
author: Mark Proctor
categories: []
tags: []
original_url: https://blog.kie.org/2011/01/test.html
---

"""

def make_md(body: str) -> str:
    return MINIMAL_FM + body

def make_html(body: str) -> str:
    return f'<html><body><article>{body}</article></body></html>'

def issues_of(md: str, html: str = None, check: str = None):
    html_path = None
    if html:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html); html_path = Path(f.name)
    try:
        all_issues = validate(md, 'test-slug', html_path)
        return [i for i in all_issues if i.check == check] if check else all_issues
    finally:
        if html_path and html_path.exists():
            html_path.unlink()

def has_error(issues, check):
    return any(i.level == 'ERROR' and i.check == check for i in issues)

def has_warn(issues, check):
    return any(i.level == 'WARN' and i.check == check for i in issues)

def is_clean(issues, check):
    return not any(i.check == check for i in issues)


# ══════════════════════════════════════════════════════════════════════════════
# MD-ONLY CHECKS
# ══════════════════════════════════════════════════════════════════════════════

class TestOrphanedPlaceholders:
    """LESSON: Code block placeholders left unreplaced appear as raw text."""

    def test_catches_new_format(self):
        assert has_error(issues_of(make_md("@@CODEBLOCK_000@@")), 'orphaned_placeholder')

    def test_catches_old_format(self):
        assert has_error(issues_of(make_md("CODEBLOCK_FENCE_1")), 'orphaned_placeholder')

    def test_clean_passes(self):
        assert is_clean(issues_of(make_md("```java\nint x = 1;\n```")), 'orphaned_placeholder')


class TestStrayDigitAfterFence:
    """LESSON: Partial str.replace('FENCE_1',...) on 'FENCE_10' leaves '0' after ```."""

    def test_catches_digit_after_closing_fence(self):
        assert has_error(issues_of(make_md("```java\ncode\n```0\n\nMore.")), 'stray_digit_after_fence')

    def test_catches_double_digit(self):
        assert has_error(issues_of(make_md("```java\ncode\n```10\n\nMore.")), 'stray_digit_after_fence')

    def test_clean_numbered_list_after_fence(self):
        # A numbered list item after a code block is NOT a stray digit
        assert is_clean(issues_of(make_md("```java\ncode\n```\n\n1. First item")), 'stray_digit_after_fence')

    def test_clean_passes(self):
        assert is_clean(issues_of(make_md("```java\nint x = 1;\n```\n\nText.")), 'stray_digit_after_fence')


class TestBalancedFences:
    """LESSON: Unclosed ``` block causes everything after it to render as code."""

    def test_catches_unclosed_block(self):
        assert has_error(issues_of(make_md("```java\ncode\n```\n\n```python\nprint()\n")), 'unbalanced_fences')

    def test_catches_single_fence(self):
        assert has_error(issues_of(make_md("```java\ncode here")), 'unbalanced_fences')

    def test_clean_two_blocks(self):
        assert is_clean(issues_of(make_md("```java\ncode\n```\n\n```xml\n<tag/>\n```")), 'unbalanced_fences')

    def test_clean_no_code(self):
        assert is_clean(issues_of(make_md("Plain text, no code blocks.")), 'unbalanced_fences')


class TestEmptyCodeBlocks:
    """LESSON: Empty ``` ``` blocks add noise and indicate conversion failure."""

    def test_catches_empty_block(self):
        assert has_warn(issues_of(make_md("Text.\n\n```\n```\n\nText.")), 'empty_code_blocks')

    def test_catches_empty_with_lang(self):
        assert has_warn(issues_of(make_md("```java\n```")), 'empty_code_blocks')

    def test_clean_non_empty(self):
        assert is_clean(issues_of(make_md("```java\nint x = 1;\n```")), 'empty_code_blocks')


class TestFrontMatter:
    """LESSON: Missing/malformed front matter causes Jekyll to skip the post."""

    def test_catches_no_front_matter(self):
        assert has_error(issues_of("Just plain text."), 'missing_front_matter')

    def test_catches_unclosed_front_matter(self):
        assert has_error(issues_of("---\ntitle: Test\ndate: 2011-01-01\nauthor: X\n"), 'unclosed_front_matter')

    def test_catches_missing_title(self):
        assert has_error(issues_of("---\ndate: 2011-01-01\nauthor: X\n---\n\nBody."), 'missing_fm_field')

    def test_catches_missing_date(self):
        assert has_error(issues_of("---\ntitle: \"T\"\nauthor: X\n---\n\nBody."), 'missing_fm_field')

    def test_catches_bad_date_format(self):
        assert has_warn(issues_of("---\ntitle: \"T\"\ndate: 01/01/2011\nauthor: X\n---\n\nBody."), 'bad_date_format')

    def test_clean_valid_front_matter(self):
        all_fm_checks = ('missing_front_matter','unclosed_front_matter','missing_fm_field','bad_date_format')
        issues = [i for i in issues_of(make_md("Body.")) if i.check in all_fm_checks]
        assert not issues


class TestEmptyBody:
    """LESSON: Over-aggressive converter cleaning can strip all content."""

    def test_catches_empty_body(self):
        assert has_error(issues_of("---\ntitle: \"T\"\ndate: 2011-01-01\nauthor: X\n---\n\n  "), 'empty_body')

    def test_catches_near_empty_body(self):
        assert has_error(issues_of("---\ntitle: \"T\"\ndate: 2011-01-01\nauthor: X\n---\n\nHi."), 'empty_body')

    def test_clean_substantial_body(self):
        assert is_clean(issues_of(make_md("This is a valid post with enough content to pass the check.")), 'empty_body')


class TestWordpressJunk:
    """LESSON: WordPress metadata lines must be stripped by the converter."""

    def test_catches_byline(self):
        assert has_warn(issues_of(make_md("by Mark Proctor\n\nActual content.")), 'wordpress_junk')

    def test_catches_view_all_posts(self):
        assert has_warn(issues_of(make_md("Content.\n\n[View all posts](https://blog.kie.org)\n\nMore.")), 'wordpress_junk')

    def test_catches_post_comment_link(self):
        assert has_warn(issues_of(make_md("[Post Comment](https://blogger.com/comment)")), 'wordpress_junk')

    def test_clean_normal_content(self):
        assert is_clean(issues_of(make_md("Drools is a rule engine.")), 'wordpress_junk')


class TestHtmlEntities:
    """LESSON: Raw HTML entities should be decoded, not left as-is."""

    def test_catches_amp_entities(self):
        body = " ".join(["This &amp; that &amp; the other &amp; more &amp; even more &amp; another"] * 3)
        assert has_warn(issues_of(make_md(body)), 'html_entities_in_body')

    def test_clean_normal_ampersand(self):
        assert is_clean(issues_of(make_md("Rules & regulations.")), 'html_entities_in_body')

    def test_entities_in_code_not_flagged(self):
        assert is_clean(issues_of(make_md("```xml\n<root>&amp;</root>\n```")), 'html_entities_in_body')


class TestBrokenLinks:
    """LESSON: [text]() with empty href = broken link."""

    def test_catches_empty_href(self):
        assert has_warn(issues_of(make_md("Click [here]() for more.")), 'broken_links')

    def test_clean_valid_link(self):
        assert is_clean(issues_of(make_md("Click [here](https://drools.org) for more.")), 'broken_links')


class TestDuplicateParagraphs:
    """LESSON: Double-processing can cause the same paragraph to appear twice.

    Uses full content hash — prefix matching causes false positives when two
    different code blocks share a long XML/package prefix.
    """

    def test_catches_duplicate(self):
        para = "This is a long paragraph about Drools rule engines and how they work in practice with real-world examples."
        assert has_error(issues_of(make_md(f"{para}\n\nMiddle.\n\n{para}")), 'duplicate_paragraph')

    def test_clean_no_duplicates(self):
        assert is_clean(issues_of(make_md("First.\n\nSecond.\n\nThird.")), 'duplicate_paragraph')

    def test_clean_similar_code_blocks_different_content(self):
        # Spring XML configs share a long preamble — full hash distinguishes them
        shared = '<?xml version="1.0"?><beans><drools:kbase><drools:resources><drools:resource type="DRL"/>'
        b1 = f"```xml\n{shared}</drools:resources></drools:kbase></beans>\n```"
        b2 = f"```xml\n{shared}</drools:resources></drools:kbase><bean id=\"extra\"/></beans>\n```"
        assert is_clean(issues_of(make_md(f"{b1}\n\nText.\n\n{b2}")), 'duplicate_paragraph')


class TestCodeFenceLanguage:
    """LESSON: Unknown language tags produce unstyled code blocks."""

    def test_catches_unknown_language(self):
        assert has_warn(issues_of(make_md("```droolsrulefile\nrule x end\n```")), 'unknown_fence_language')

    def test_clean_known_java(self):
        assert is_clean(issues_of(make_md("```java\ncode\n```")), 'unknown_fence_language')

    def test_clean_known_drl(self):
        assert is_clean(issues_of(make_md("```drl\nrule x end\n```")), 'unknown_fence_language')

    def test_clean_no_lang_tag(self):
        assert is_clean(issues_of(make_md("```\ngeneric code\n```")), 'unknown_fence_language')


# ══════════════════════════════════════════════════════════════════════════════
# CROSS-VALIDATION CHECKS
# ══════════════════════════════════════════════════════════════════════════════

class TestCodeBlockCount:
    """LESSON: Every <pre> in HTML should produce a fenced block in MD."""

    def test_catches_code_blocks_dropped(self):
        html = make_html('<pre><code class="language-java">int x = 1;</code></pre>')
        assert has_error(issues_of(make_md("No code here."), html), 'code_blocks_dropped')

    def test_clean_matching_count(self):
        html = make_html('<pre><code class="language-java">int x = 1;</code></pre>')
        assert is_clean(issues_of(make_md("```java\nint x = 1;\n```"), html), 'code_blocks_dropped')

    def test_clean_no_code_in_html(self):
        html = make_html('<p>Just text, no code.</p>')
        assert is_clean(issues_of(make_md("Just text, no code."), html), 'code_blocks_dropped')


class TestCodeContentIntegrity:
    """LESSON: Code content must match — not just count."""

    def test_catches_different_code(self):
        html = make_html('<pre><code class="language-java">package com.example; public class Foo {}</code></pre>')
        assert has_error(issues_of(make_md("```java\ncompletely different code\n```"), html), 'code_content_missing')

    def test_clean_matching_code(self):
        code = "package com.example; public class Foo {}"
        html = make_html(f'<pre><code class="language-java">{code}</code></pre>')
        assert is_clean(issues_of(make_md(f"```java\n{code}\n```"), html), 'code_content_missing')


class TestLanguageTags:
    """LESSON: language-X class in HTML must produce matching ```X fence."""

    def test_catches_wrong_language(self):
        html = make_html('<pre><code class="language-drl">rule x end</code></pre>')
        assert has_warn(issues_of(make_md("```java\nrule x end\n```"), html), 'language_tag_missing')

    def test_clean_matching_language(self):
        html = make_html('<pre><code class="language-drl">rule x end</code></pre>')
        assert is_clean(issues_of(make_md("```drl\nrule x end\n```"), html), 'language_tag_missing')


class TestWordCount:
    """LESSON: MD word count < 35% of HTML = likely content loss."""

    def test_catches_low_word_count(self):
        html = make_html('<p>' + ' '.join(['word'] * 500) + '</p>')
        assert has_warn(issues_of(make_md("Just a few words."), html), 'word_count_low')

    def test_clean_adequate_word_count(self):
        text = ' '.join(['word'] * 100)
        assert is_clean(issues_of(make_md(text), make_html(f'<p>{text}</p>')), 'word_count_low')

    def test_threshold_not_triggered_for_short_html(self):
        # < 150 words in HTML: threshold not applied
        html = make_html('<p>' + ' '.join(['word'] * 50) + '</p>')
        assert is_clean(issues_of(make_md("Just a few words."), html), 'word_count_low')


class TestHeadingMatch:
    """LESSON: h2/h3 text from HTML must appear in MD — missing = section dropped."""

    def test_catches_missing_heading(self):
        html = make_html('<h2>Advanced Configuration</h2><p>Content.</p>')
        assert has_warn(issues_of(make_md("Content without the heading."), html), 'heading_missing')

    def test_clean_matching_heading(self):
        html = make_html('<h2>Advanced Configuration</h2><p>Content.</p>')
        assert is_clean(issues_of(make_md("## Advanced Configuration\n\nContent."), html), 'heading_missing')

    def test_ignores_short_headings(self):
        # "Author" is 6 chars — shorter than 5 char threshold? Actually it's >= 5.
        # The check skips headings < 5 chars. "Author" = 6 chars so it IS checked.
        # But it should not appear in MD since we strip it. Test just that no false positive.
        html = make_html('<h2>By</h2><p>Mark Proctor</p>')  # "By" = 2 chars, below threshold
        assert is_clean(issues_of(make_md("Content without by heading."), html), 'heading_missing')


class TestListPreservation:
    """LESSON: <ul>/<ol> lists in HTML should produce list items in MD."""

    def test_catches_lists_dropped(self):
        html = make_html('<ul><li>Item one</li><li>Item two</li><li>Item three</li></ul>')
        assert has_warn(issues_of(make_md("Item one. Item two. Item three."), html), 'lists_dropped')

    def test_clean_lists_present(self):
        html = make_html('<ul><li>Item one</li><li>Item two</li></ul>')
        assert is_clean(issues_of(make_md("- Item one\n- Item two"), html), 'lists_dropped')

    def test_clean_single_item_list_not_flagged(self):
        # Single-item lists (len <= 1) are not flagged
        html = make_html('<ul><li>Single item</li></ul>')
        assert is_clean(issues_of(make_md("Single item."), html), 'lists_dropped')


class TestLinkCount:
    """LESSON: External link count should be comparable — big drop = links stripped."""

    def test_catches_links_dropped(self):
        links = ' '.join(f'<a href="https://example{i}.com">Link {i}</a>' for i in range(10))
        html = make_html(f'<p>{links}</p>')
        assert has_warn(issues_of(make_md("Text with no links."), html), 'links_dropped')

    def test_clean_links_present(self):
        html = make_html('<a href="https://drools.org">Drools</a> is great.')
        assert is_clean(issues_of(make_md("[Drools](https://drools.org) is great."), html), 'links_dropped')

    def test_clean_few_html_links_not_flagged(self):
        # < 5 links: threshold not triggered
        html = make_html('<p><a href="https://a.com">A</a> and <a href="https://b.com">B</a>.</p>')
        assert is_clean(issues_of(make_md("A and B."), html), 'links_dropped')

    def test_clean_angle_bracket_links(self):
        # html2text produces ](<https://...>) — must count as links
        links = ' '.join(f'<a href="https://example{i}.com">Link {i}</a>' for i in range(10))
        html = make_html(f'<p>{links}</p>')
        md = make_md(' '.join(f'[Link {i}](<https://example{i}.com>)' for i in range(10)))
        assert is_clean(issues_of(md, html), 'links_dropped')


class TestLastSectionPresent:
    """LESSON: Last paragraph of HTML should appear in MD — detects end truncation."""

    def test_catches_truncation(self):
        html = make_html(
            '<p>Middle content here for a while.</p>'
            '<p>This is the final conclusion paragraph that should definitely appear.</p>'
        )
        # MD only has the first paragraph — conclusion is missing
        md = make_md("Middle content here for a while and some more words to clear empty_body check.")
        assert has_warn(issues_of(md, html), 'truncated_at_end')

    def test_clean_full_content(self):
        conclusion = "This is the final conclusion paragraph that should definitely appear."
        html = make_html(f'<p>Middle content here for a while.</p><p>{conclusion}</p>')
        assert is_clean(issues_of(make_md(f"Middle content here for a while.\n\n{conclusion}"), html), 'truncated_at_end')


class TestImageCount:
    """LESSON: Content images in HTML must have representation in MD."""

    def test_catches_images_dropped(self):
        imgs = ''.join(f'<img src="/assets/images/2011/01/img{i}.png" alt="img{i}">' for i in range(4))
        assert has_warn(issues_of(make_md("No images."), make_html(f'<p>{imgs}</p>')), 'images_dropped')

    def test_clean_images_present(self):
        html = make_html('<img src="/assets/images/2011/01/img1.png" alt="diagram">')
        assert is_clean(issues_of(make_md("![diagram](/legacy/assets/images/2011/01/img1.png)"), html), 'images_dropped')

    def test_clean_missing_placeholders_count(self):
        html = make_html(''.join(f'<img src="/assets/2011/01/img{i}.png" alt="img">' for i in range(4)))
        md = make_md('\n\n'.join(f'> **📷 Missing image** — img{i}' for i in range(4)))
        assert is_clean(issues_of(md, html), 'images_dropped')


class TestTechnicalTerms:
    """LESSON: Key KIE/Drools technical terms from HTML must appear in MD."""

    def test_catches_drools_missing(self):
        html = make_html('<p>Drools is a powerful rule engine framework.</p>')
        assert has_warn(issues_of(make_md("It is a powerful framework."), html), 'technical_terms_missing')

    def test_clean_term_present(self):
        html = make_html('<p>Drools uses the Rete algorithm.</p>')
        assert is_clean(issues_of(make_md("Drools uses the Rete algorithm."), html), 'technical_terms_missing')

    def test_clean_no_terms_in_html(self):
        html = make_html('<p>General programming concepts.</p>')
        assert is_clean(issues_of(make_md("General programming concepts."), html), 'technical_terms_missing')


# ── Previously untested cross-checks ─────────────────────────────────────────

class TestChromeLeakage:
    """LESSON: WordPress sidebar/comment text must not appear in the MD body.
    NOTE: chrome_leakage is a CROSS_CHECK — HTML must be provided to trigger it."""

    # Provide minimal HTML so cross-checks run
    _html = make_html('<p>Some content.</p>')

    def test_catches_leave_reply(self):
        assert has_warn(issues_of(make_md("Content.\n\nLeave a Reply\n\nMore content."), self._html), 'chrome_leakage')

    def test_catches_recent_posts(self):
        assert has_warn(issues_of(make_md("Content.\n\nRecent Posts\n\nMore content."), self._html), 'chrome_leakage')

    def test_clean_normal_content(self):
        assert is_clean(issues_of(make_md("Drools processes rules efficiently with pattern matching."), self._html), 'chrome_leakage')


class TestBlockquotePreserved:
    """LESSON: HTML <blockquote> should produce > lines in MD."""

    def test_catches_blockquote_dropped(self):
        html = make_html('<blockquote>This is an important quoted passage from a blog post.</blockquote><p>After.</p>')
        assert has_warn(issues_of(make_md("After."), html), 'blockquotes_dropped')

    def test_clean_blockquote_present(self):
        html = make_html('<blockquote>This is an important quoted passage from a blog post.</blockquote>')
        assert is_clean(issues_of(make_md("> This is an important quoted passage from a blog post."), html), 'blockquotes_dropped')

    def test_clean_no_blockquotes_in_html(self):
        html = make_html('<p>Just a paragraph, no quotes.</p>')
        assert is_clean(issues_of(make_md("Just a paragraph, no quotes."), html), 'blockquotes_dropped')


class TestYoutubeLinkCount:
    """LESSON: YouTube embed figures in HTML should appear as links in MD."""

    def test_catches_youtube_dropped(self):
        html = make_html('<figure class="video-embed"><a href="https://youtube.com/watch?v=abc123"><img src="/thumb.jpg"></a></figure>')
        assert has_warn(issues_of(make_md("No video link here."), html), 'youtube_links_dropped')

    def test_clean_youtube_present(self):
        html = make_html('<figure class="video-embed"><a href="https://youtube.com/watch?v=abc123"><img src="/thumb.jpg"></a></figure>')
        assert is_clean(issues_of(make_md("[Watch on YouTube](https://youtube.com/watch?v=abc123)"), html), 'youtube_links_dropped')


class TestTableAcknowledged:
    """LESSON: HTML <table> should have some representation in MD."""

    def test_catches_table_dropped(self):
        html = make_html('<table><tr><th>Col A</th><th>Col B</th></tr><tr><td>foo</td><td>bar</td></tr></table>')
        assert has_warn(issues_of(make_md("No table here at all."), html), 'table_dropped')

    def test_clean_table_present_as_md(self):
        html = make_html('<table><tr><th>Col A</th><th>Col B</th></tr><tr><td>foo</td><td>bar</td></tr></table>')
        assert is_clean(issues_of(make_md("| Col A | Col B |\n|---|---|\n| foo | bar |"), html), 'table_dropped')

    def test_clean_no_table_in_html(self):
        html = make_html('<p>Just text, no table.</p>')
        assert is_clean(issues_of(make_md("Just text, no table."), html), 'table_dropped')


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATOR STRUCTURE META-TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestValidatorStructure:
    """Ensure the validator is well-formed and all checks are registered."""

    def test_md_checks_are_callable(self):
        for fn in MD_CHECKS:
            assert callable(fn), f'{fn} is not callable'

    def test_cross_checks_are_callable(self):
        for fn in CROSS_CHECKS:
            assert callable(fn), f'{fn} is not callable'

    def test_all_md_checks_return_list(self):
        md = make_md("Some valid content here for testing purposes.")
        for fn in MD_CHECKS:
            result = fn(md, 'test')
            assert isinstance(result, list), f'{fn.__name__} did not return a list'

    def test_clean_post_has_no_errors(self):
        """A well-formed post should pass all MD checks cleanly."""
        md = make_md(
            "Drools is a [rule engine](https://drools.org) from the KIE community.\n\n"
            "## How it works\n\n"
            "The Rete algorithm processes rules efficiently:\n\n"
            "```java\nKieSession session = kieContainer.newKieSession();\n"
            "session.insert(new Fact());\nsession.fireAllRules();\n```\n\n"
            "- Feature one\n- Feature two\n- Feature three\n\n"
            "Visit the [KIE website](https://kie.org) for more information."
        )
        errors = [i for i in issues_of(md) if i.level == 'ERROR']
        assert not errors, f'Clean post has errors: {errors}'
