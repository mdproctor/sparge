package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class MdValidatorTest {

    private static final String VALID_FM =
        "---\nlayout: post\ntitle: \"My Post\"\ndate: 2024-03-15\n"
        + "author: Mark Proctor\ncategories: []\ntags: []\noriginal_url: https://example.com\n---\n\n";

    private static List<MdIssue> validate(String md) {
        return MdValidator.validate(md, "test-slug", null);
    }

    private static boolean hasCheck(List<MdIssue> issues, String check) {
        return issues.stream().anyMatch(i -> i.check().equals(check));
    }

    // ── Clean baseline ────────────────────────────────────────────────────────

    @Test
    void cleanPost_hasNoIssues() {
        String md = VALID_FM
            + "# Introduction\n\nThis is valid content with enough words here.\n\n"
            + "```java\npublic class Example {}\n```\n\nMore content here.\n";
        List<MdIssue> issues = validate(md);
        issues.forEach(i -> System.out.println("  Unexpected: " + i));
        assertTrue(issues.isEmpty(), "Clean post should have no issues but got: " + issues);
    }

    // ── Orphaned placeholders ─────────────────────────────────────────────────

    @Test
    void orphanedPlaceholder_detected() {
        String md = VALID_FM + "Content.\n\n@@CODEBLOCK_001@@\n\nMore.\n";
        assertTrue(hasCheck(validate(md), "orphaned_placeholder"));
    }

    @Test
    void noOrphanedPlaceholder_passes() {
        String md = VALID_FM + "No placeholders here.\n";
        assertFalse(hasCheck(validate(md), "orphaned_placeholder"));
    }

    // ── Stray digit after fence ───────────────────────────────────────────────

    @Test
    void strayDigitAfterFence_detected() {
        String md = VALID_FM + "```0\ncode\n```\n";
        assertTrue(hasCheck(validate(md), "stray_digit_after_fence"));
    }

    // ── Balanced fences ───────────────────────────────────────────────────────

    @Test
    void unbalancedFence_detected() {
        String md = VALID_FM + "```java\ncode without closing fence\n";
        assertTrue(hasCheck(validate(md), "unbalanced_fences"),
                "Unclosed fence should be detected");
    }

    @Test
    void balancedFence_passes() {
        String md = VALID_FM + "```java\npublic void foo() {}\n```\n";
        assertFalse(hasCheck(validate(md), "unbalanced_fences"));
    }

    // ── Empty code block ──────────────────────────────────────────────────────

    @Test
    void emptyCodeBlock_detected() {
        String md = VALID_FM + "Text.\n\n```\n```\n";
        assertTrue(hasCheck(validate(md), "empty_code_block"));
    }

    // ── Front matter ──────────────────────────────────────────────────────────

    @Test
    void missingTitle_detected() {
        String md = "---\nlayout: post\ndate: 2024-03-15\nauthor: X\n---\n\nContent here.\n";
        assertTrue(hasCheck(validate(md), "front_matter_invalid"),
                "Missing title should be detected");
    }

    @Test
    void missingDate_detected() {
        String md = "---\nlayout: post\ntitle: \"T\"\nauthor: X\n---\n\nContent here.\n";
        assertTrue(hasCheck(validate(md), "front_matter_invalid"));
    }

    @Test
    void badDateFormat_detected() {
        String md = "---\nlayout: post\ntitle: \"T\"\ndate: 15/03/2024\nauthor: X\n---\n\nContent.\n";
        assertTrue(hasCheck(validate(md), "front_matter_invalid"));
    }

    @Test
    void missingFrontMatter_detected() {
        String md = "# Just content\n\nNo front matter.\n";
        assertTrue(hasCheck(validate(md), "front_matter_invalid"));
    }

    @Test
    void validFrontMatter_passes() {
        String md = VALID_FM + "Sufficient content here for the post.\n";
        assertFalse(hasCheck(validate(md), "front_matter_invalid"));
    }

    // ── Empty body ────────────────────────────────────────────────────────────

    @Test
    void emptyBody_detected() {
        String md = VALID_FM.strip() + "\n\n";
        assertTrue(hasCheck(validate(md), "empty_body"));
    }

    @Test
    void veryShortBody_detected() {
        String md = VALID_FM + "Hi.\n";
        assertTrue(hasCheck(validate(md), "empty_body"),
                "Body with < 20 chars should be detected");
    }

    // ── WordPress junk ────────────────────────────────────────────────────────

    @Test
    void viewAllPosts_detected() {
        String md = VALID_FM + "Real content.\n\nView all posts by Mark Proctor\n";
        assertTrue(hasCheck(validate(md), "wordpress_junk"));
    }

    @Test
    void postComment_detected() {
        String md = VALID_FM + "Content.\n\nPost Comment\n\nMore text here.\n";
        assertTrue(hasCheck(validate(md), "wordpress_junk"));
    }

    // ── HTML entities ─────────────────────────────────────────────────────────

    @Test
    void manyEntities_detected() {
        String md = VALID_FM + "a &amp; b &amp; c &amp; d &amp; e &amp; f more.\n";
        assertTrue(hasCheck(validate(md), "html_entities_in_body"),
                "6+ &amp; entities should trigger html_entities_in_body");
    }

    @Test
    void fewEntities_passes() {
        String md = VALID_FM + "Only one &amp; entity here.\n";
        assertFalse(hasCheck(validate(md), "html_entities_in_body"));
    }

    // ── Local image paths ─────────────────────────────────────────────────────

    @Test
    void relativeImagePath_detected() {
        String md = VALID_FM + "![img](../../assets/images/foo.png)\n";
        assertTrue(hasCheck(validate(md), "local_image_paths"));
    }

    @Test
    void legacyImagePath_passes() {
        String md = VALID_FM + "![img](/legacy/assets/images/foo.png)\n";
        assertFalse(hasCheck(validate(md), "local_image_paths"));
    }

    // ── Broken links ──────────────────────────────────────────────────────────

    @Test
    void emptyHref_detected() {
        String md = VALID_FM + "[Link text]()\n\nContent.\n";
        assertTrue(hasCheck(validate(md), "broken_md_links"));
    }

    // ── Triple blanks ─────────────────────────────────────────────────────────

    @Test
    void tripleBlankLines_detected() {
        String md = VALID_FM + "Para one.\n\n\n\nPara two.\n";
        assertTrue(hasCheck(validate(md), "no_triple_blanks"));
    }

    @Test
    void doubleBlankLines_passes() {
        String md = VALID_FM + "Para one.\n\nPara two.\n";
        assertFalse(hasCheck(validate(md), "no_triple_blanks"));
    }

    // ── Excessive line length ─────────────────────────────────────────────────

    @Test
    void longLine_detected() {
        String md = VALID_FM + "x".repeat(8100) + "\n";
        assertTrue(hasCheck(validate(md), "excessive_line_length"));
    }

    // ── Code fence language ───────────────────────────────────────────────────

    @Test
    void unknownLanguage_detected() {
        String md = VALID_FM + "```unknownlang\ncode\n```\n";
        assertTrue(hasCheck(validate(md), "code_fence_language"));
    }

    @Test
    void knownLanguage_passes() {
        String md = VALID_FM + "```java\npublic void foo() {}\n```\n";
        assertFalse(hasCheck(validate(md), "code_fence_language"));
    }

    @Test
    void noLanguageFence_passes() {
        String md = VALID_FM + "```\ngeneric code\n```\n";
        assertFalse(hasCheck(validate(md), "code_fence_language"));
    }

    // ── Cross-checks with HTML ────────────────────────────────────────────────

    @Test
    void crossWordCount_largeLoss_detected(@TempDir Path tmp) throws Exception {
        StringBuilder words = new StringBuilder();
        for (int i = 0; i < 200; i++) words.append("word").append(i).append(" ");
        Path html = tmp.resolve("post.html");
        Files.writeString(html,
            "<html><body><article><p>" + words + "</p></article></body></html>");
        String md = VALID_FM + "Short body only.\n";
        List<MdIssue> issues = MdValidator.validate(md, "post", html);
        assertTrue(hasCheck(issues, "word_count"),
                "MD with far fewer words should trigger word_count");
    }

    @Test
    void crossWordCount_acceptable_passes(@TempDir Path tmp) throws Exception {
        Path html = tmp.resolve("post.html");
        Files.writeString(html,
            "<html><body><article><p>This post has a reasonable amount of content words here.</p></article></body></html>");
        String md = VALID_FM + "This post has a reasonable amount of content words here.\n";
        List<MdIssue> issues = MdValidator.validate(md, "post", html);
        assertFalse(hasCheck(issues, "word_count"));
    }

    @Test
    void crossHeadingMatch_missingHeading_detected(@TempDir Path tmp) throws Exception {
        Path html = tmp.resolve("post.html");
        Files.writeString(html,
            "<html><body><article>"
            + "<h2>Very Important Section Title Here</h2>"
            + "<p>Content with enough words to matter here.</p>"
            + "</article></body></html>");
        String md = VALID_FM + "No heading present at all.\n\nContent with enough words to matter here.\n";
        List<MdIssue> issues = MdValidator.validate(md, "post", html);
        assertTrue(hasCheck(issues, "heading_match"),
                "Missing HTML heading in MD should be detected");
    }

    @Test
    void crossTechnicalTerms_lost_detected(@TempDir Path tmp) throws Exception {
        Path html = tmp.resolve("post.html");
        Files.writeString(html,
            "<html><body><article><p>Drools and OptaPlanner are KIE projects used for rules.</p></article></body></html>");
        String md = VALID_FM + "Rules engine projects are very interesting systems.\n";
        List<MdIssue> issues = MdValidator.validate(md, "post", html);
        assertTrue(hasCheck(issues, "technical_terms"),
                "Lost KIE terms should be detected");
    }

    @Test
    void crossTechnicalTerms_preserved_passes(@TempDir Path tmp) throws Exception {
        Path html = tmp.resolve("post.html");
        Files.writeString(html,
            "<html><body><article><p>Drools is a rules engine built by the KIE team.</p></article></body></html>");
        String md = VALID_FM + "Drools is a rules engine built by the KIE team.\n";
        List<MdIssue> issues = MdValidator.validate(md, "post", html);
        assertFalse(hasCheck(issues, "technical_terms"));
    }

    @Test
    void crossLastSection_truncation_detected(@TempDir Path tmp) throws Exception {
        Path html = tmp.resolve("post.html");
        Files.writeString(html,
            "<html><body><article>"
            + "<p>Introduction paragraph content here.</p>"
            + "<p>This very specific final paragraph content should appear in the markdown output text.</p>"
            + "</article></body></html>");
        String md = VALID_FM + "Introduction paragraph content here.\n\nSomething completely different was written.\n";
        List<MdIssue> issues = MdValidator.validate(md, "post", html);
        assertTrue(hasCheck(issues, "last_section_present"),
                "Missing final paragraph should be detected");
    }
}
