package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import static org.junit.jupiter.api.Assertions.*;

class ConvertPostTest {

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    private static Path writeHtml(Path dir, String filename, String content) throws Exception {
        Path p = dir.resolve(filename);
        Files.writeString(p, content);
        return p;
    }

    private static Path writeJson(Path dir, String filename, String json) throws Exception {
        Path p = dir.resolve(filename);
        Files.writeString(p, json);
        return p;
    }

    private static String sidecar(String title, String date) {
        return "{\"title\":\"" + title + "\",\"date\":\"" + date + "\","
             + "\"author\":\"Mark Proctor\",\"categories\":[],\"tags\":[],"
             + "\"original_url\":\"https://example.com/post\"}";
    }

    // ── Front matter ──────────────────────────────────────────────────────────

    @Test
    void frontMatter_hasRequiredFields(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("My Test Post", "2024-03-15T10:00:00Z"));
        writeHtml(tmp, "post.html",
            "<html><body><article><p>Hello world content here for testing purposes.</p></article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertNotNull(md, "convert() should return non-null");
        assertTrue(md.startsWith("---\n"),        "Should start with front matter");
        assertTrue(md.contains("layout: post"),   "Should have layout field");
        assertTrue(md.contains("title: \"My Test Post\""), "Should have title");
        assertTrue(md.contains("date: 2024-03-15"),        "Should have date YYYY-MM-DD");
        assertTrue(md.contains("author: Mark Proctor"),    "Should have author");
    }

    @Test
    void frontMatter_stripsKieCommunityFromTitle(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Rule Engine Basics - KIE Community", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html",
            "<html><body><article><p>Content.</p></article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("title: \"Rule Engine Basics\""),
                "Should strip '- KIE Community' from title: " + md.substring(0, Math.min(200, md.length())));
    }

    @Test
    void frontMatter_withCategoriesAndTags(@TempDir Path tmp) throws Exception {
        Path json = writeJson(tmp, "meta.json",
            "{\"title\":\"Post\",\"date\":\"2024-01-01T00:00:00Z\","
          + "\"author\":\"Mark Proctor\","
          + "\"categories\":[\"Drools\",\"Rules\"],\"tags\":[\"rete\",\"jbpm\"],"
          + "\"original_url\":\"https://example.com\"}");
        writeHtml(tmp, "meta.html",
            "<html><body><article><p>Content here.</p></article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("meta.html"), json);

        assertTrue(md.contains("  - Drools"), "Should list category Drools");
        assertTrue(md.contains("  - Rules"),  "Should list category Rules");
        assertTrue(md.contains("  - rete"),   "Should list tag rete");
        assertTrue(md.contains("  - jbpm"),   "Should list tag jbpm");
    }

    // ── Junk removal ──────────────────────────────────────────────────────────

    @Test
    void junkSelectors_removed(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<header class=\"entry-header\">HEADER JUNK</header>"
            + "<div class=\"entry-meta\">META JUNK</div>"
            + "<!-- HTML COMMENT -->"
            + "<p>Real content paragraph here for testing.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertFalse(md.contains("HEADER JUNK"),  "entry-header should be removed");
        assertFalse(md.contains("META JUNK"),    "entry-meta should be removed");
        assertFalse(md.contains("HTML COMMENT"), "HTML comments should be removed");
        assertTrue(md.contains("Real content"),  "Real content should be preserved");
    }

    @Test
    void commentsSection_removed(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<div id=\"comments\"><p>Comment text here</p></div>"
            + "<div class=\"addtoany_share_save_container\">Share</div>"
            + "<p>Article body content paragraph.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertFalse(md.contains("Comment text"), "#comments should be removed");
        assertTrue(md.contains("Article body"),  "Article content should be preserved");
    }

    // ── Code blocks ───────────────────────────────────────────────────────────

    @Test
    void codeBlock_withLanguage_preservedAsFenced(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<p>Example code:</p>"
            + "<pre><code class=\"language-java\">public class Hello {\n"
            + "    System.out.println(\"Hello\");\n"
            + "}</code></pre>"
            + "<p>After code block.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("```java"),               "Should have java fence");
        assertTrue(md.contains("public class Hello"),    "Code content preserved");
        assertTrue(md.contains("System.out.println"),    "Code content preserved");
        assertFalse(md.contains("@@CODEBLOCK_"),         "No orphaned placeholders");
    }

    @Test
    void codeBlock_withBackticksInCode_usesLongerFence(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<pre><code>use `backtick` here</code></pre>"
            + "<p>After block.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("use `backtick` here"), "Backtick content preserved");
        assertFalse(md.contains("@@CODEBLOCK_"),       "No orphaned placeholders");
    }

    @Test
    void multipleCodes_noOrphanedPlaceholders(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<pre><code>code one</code></pre>"
            + "<p>Middle content.</p>"
            + "<pre><code class=\"language-xml\">&lt;bean id=\"x\"/&gt;</code></pre>"
            + "<p>End content.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertFalse(md.contains("@@CODEBLOCK_"),
                "All placeholders should be restored, none orphaned: " + md);
        assertTrue(md.contains("code one"),  "First code block preserved");
    }

    // ── HTML→MD conversion ────────────────────────────────────────────────────

    @Test
    void headings_convertedToHashStyle(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<h2>Section One</h2><p>Content here.</p>"
            + "<h3>Subsection Alpha</h3><p>More content.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("## Section One"),    "h2 should become ##");
        assertTrue(md.contains("### Subsection"),    "h3 should become ###");
        assertFalse(md.contains("Section One\n==="), "Should not use setext headings");
    }

    @Test
    void imagePathsFixed(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<img src=\"../../assets/images/drools.png\" alt=\"Drools\">"
            + "<p>Content paragraph here.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("/legacy/assets/images/drools.png"),
                "../../assets/ should become /legacy/assets/");
        assertFalse(md.contains("../../assets/"), "Old relative path should be gone");
    }

    @Test
    void dataUriImages_removed(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<img src=\"data:image/png;base64,AAAA\" alt=\"spacer\">"
            + "<p>Real content paragraph here for testing.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertFalse(md.contains("data:image"),  "data: URI images should be removed");
        assertTrue(md.contains("Real content"), "Real content preserved");
    }

    @Test
    void tripleNewlines_collapsed(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<p>Para one.</p><p>Para two.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertFalse(md.contains("\n\n\n\n"), "Should not have 4+ consecutive newlines");
    }

    // ── Fix 1: NBSP normalization ─────────────────────────────────────────────

    @Test
    void codeBlock_nonBreakingSpaces_normalized(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        // HTML with non-breaking space (U+00A0) inside code
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<pre><code>int\u00a0x\u00a0=\u00a01;</code></pre>"
            + "<p>Content after.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("int x = 1;"),
                "Non-breaking spaces in code should be normalized to regular spaces");
        assertFalse(md.contains("\u00a0"), "No NBSP should remain in output");
    }

    // ── Fix 2: Heading-link unwrapping ───────────────────────────────────────

    @Test
    void heading_withLink_linkStripped(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<h2><a href=\"https://example.com/section\">Section Title</a></h2>"
            + "<p>Content here.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("## Section Title"),
                "Heading should contain plain text, not a link");
        // The link inside the heading should be removed (heading as anchor is chrome)
        // At minimum the heading text should appear
        assertTrue(md.contains("Section Title"), "Heading text should be preserved");
    }

    // ── Fix 3: Duplicate h3 title removal ────────────────────────────────────

    @Test
    void duplicateH3Title_removed(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Introduction to Drools", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<h3>Introduction to Drools</h3>"
            + "<p>Real content here.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        // The h3 that duplicates the title should be removed
        // Count occurrences — title in front matter + duplicate h3 = 2 would be wrong
        long headingCount = md.lines()
            .filter(l -> l.startsWith("### Introduction to Drools"))
            .count();
        assertEquals(0, headingCount,
                "H3 that duplicates the post title should be removed from body");
    }

    // ── Fix 4: SQL→Java language remap ───────────────────────────────────────

    @Test
    void codeBlock_sqlTagWithJavaContent_remappedToJava(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<pre><code class=\"language-sql\">public class Foo {\n"
            + "    void bar() {}\n"
            + "}</code></pre>"
            + "<p>Content.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("```java"),
                "SQL tag with Java-looking content should be remapped to java");
        assertFalse(md.contains("```sql"),
                "SQL language tag should be removed when content is Java");
    }

    // ── Fix 5: === separator → --- ────────────────────────────────────────────

    @Test
    void equalsSeparator_convertedToHr(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<p>Section one content here.</p>"
            + "<p>=====================================</p>"
            + "<p>Section two content here.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertFalse(md.contains("====="),
                "=== separator lines should be converted, not left as-is");
    }

    // ── Fix 6: Nav-link dedup ─────────────────────────────────────────────────

    @Test
    void navLinks_repeatedHref_unwrapped(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        // Simulate repeated nav links (same href appearing 5+ times)
        StringBuilder navLinks = new StringBuilder();
        for (int i = 0; i < 10; i++) {
            navLinks.append("<a href=\"https://blog.example.com/nav\">Navigate</a> ");
        }
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<p>Real article content.</p>"
            + "<div>" + navLinks + "</div>"
            + "<p>More article content.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        long navLinkCount = md.lines()
            .filter(l -> l.contains("blog.example.com/nav"))
            .count();
        assertTrue(navLinkCount <= 2,
                "Repeated nav links (10x same href) should be collapsed, found " + navLinkCount + " lines with nav link");
    }

    // ── Integration: real KIE post ─────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void convertRealKiePost_producesValidFrontMatter() throws Exception {
        Path postsDir = Paths.get(System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor");
        Path html = Files.list(postsDir)
                .filter(p -> p.toString().endsWith(".html"))
                .filter(p -> p.resolveSibling(
                        p.getFileName().toString().replace(".html", ".json")).toFile().exists())
                .findFirst()
                .orElse(null);
        if (html == null) return;

        String md = ConvertPost.convert(html, null);

        assertNotNull(md,                        "convert() should not return null");
        assertTrue(md.startsWith("---\n"),       "Should have front matter");
        assertTrue(md.contains("layout: post"), "Should have layout");
        assertTrue(md.contains("title:"),       "Should have title");
        assertTrue(md.contains("date:"),        "Should have date");
        assertFalse(md.contains("@@CODEBLOCK_"), "No orphaned placeholders");
        String body = md.substring(md.indexOf("---\n", 4) + 4).strip();
        assertTrue(body.length() > 50, "Body should have meaningful content, got: " + body.length() + " chars");
    }
}
