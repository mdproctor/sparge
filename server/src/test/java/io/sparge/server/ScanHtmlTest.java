package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class ScanHtmlTest {

    private static Element article(String html) {
        Document doc = Jsoup.parse("<article>" + html + "</article>");
        return doc.selectFirst("article");
    }

    private static List<ScanHtml.Issue> scan(String html) {
        return ScanHtml.checkAll(article(html));
    }

    // ── Happy path ─────────────────────────────────────────────────────────────

    @Test
    void cleanArticleReturnsNoIssues() {
        List<ScanHtml.Issue> issues = scan(
            "<h1>Title</h1><p>Normal paragraph.</p>" +
            "<img src=\"../../assets/img001.jpg\" alt=\"Figure\"/>"
        );
        assertEquals(0, issues.size(), "Clean article must return no issues");
    }

    // ── data_placeholder ──────────────────────────────────────────────────────

    @Test
    void dataPlaceholderDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"data:image/gif;base64,R0lGODlh\" alt=\"lazy image\"/>"
        );
        assertEquals(1, issues.size());
        assertEquals("data_placeholder", issues.get(0).type());
        assertEquals("ERROR", issues.get(0).level());
    }

    @Test
    void regularImageNotFlaggedAsDataPlaceholder() {
        assertEquals(0, scan("<img src=\"../../assets/img.jpg\"/>").stream()
                .filter(i -> i.type().equals("data_placeholder")).count());
    }

    @Test
    void multipleDataPlaceholdersAllDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"data:image/gif;base64,abc\"/>" +
            "<img src=\"data:image/png;base64,xyz\"/>"
        );
        assertEquals(2, issues.stream().filter(i -> i.type().equals("data_placeholder")).count());
    }

    // ── noscript_remnant ──────────────────────────────────────────────────────

    @Test
    void noscriptWithHttpUrlDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<noscript><img src=\"https://example.com/img.jpg\"/></noscript>"
        );
        assertEquals(1, issues.stream().filter(i -> i.type().equals("noscript_remnant")).count());
        assertEquals("WARN", issues.stream().filter(i -> i.type().equals("noscript_remnant"))
                .findFirst().get().level());
    }

    @Test
    void noscriptWithoutUrlNotFlagged() {
        assertEquals(0, scan("<noscript>JavaScript is disabled</noscript>").stream()
                .filter(i -> i.type().equals("noscript_remnant")).count());
    }

    // ── external_image ────────────────────────────────────────────────────────

    @Test
    void externalImageDetected() {
        assertTrue(scan("<img src=\"https://example.com/photo.jpg\" width=\"800\" height=\"600\"/>")
                .stream().anyMatch(i -> i.type().equals("external_image")));
    }

    @Test
    void externalImageLevelIsWarn() {
        scan("<img src=\"https://example.com/photo.jpg\"/>").stream()
                .filter(i -> i.type().equals("external_image"))
                .forEach(i -> assertEquals("WARN", i.level()));
    }

    @Test
    void localImageNotFlaggedAsExternal() {
        assertEquals(0, scan("<img src=\"../../assets/local.jpg\"/>").stream()
                .filter(i -> i.type().equals("external_image")).count());
    }

    @Test
    void oneByOneExternalImageNotFlaggedAsExternal() {
        // 1x1 images are caught by tracking_pixel, not external_image
        assertFalse(scan("<img src=\"https://example.com/pixel.gif\" width=\"1\" height=\"1\"/>")
                .stream().anyMatch(i -> i.type().equals("external_image")));
    }

    // ── tracking_pixel ────────────────────────────────────────────────────────

    @Test
    void trackingPixelByDomainDetected() {
        assertTrue(scan("<img src=\"https://stats.wordpress.com/g.gif\"/>")
                .stream().anyMatch(i -> i.type().equals("tracking_pixel")));
    }

    @Test
    void trackingPixelByDimensionDetected() {
        assertTrue(scan("<img src=\"https://unknown-analytics.com/t.gif\" width=\"1\" height=\"1\"/>")
                .stream().anyMatch(i -> i.type().equals("tracking_pixel")));
    }

    @Test
    void trackingPixelLevelIsWarn() {
        scan("<img src=\"https://stats.wordpress.com/g.gif\"/>").stream()
                .filter(i -> i.type().equals("tracking_pixel"))
                .forEach(i -> assertEquals("WARN", i.level()));
    }

    @Test
    void normalLargeImageNotFlaggedAsTrackingPixel() {
        assertEquals(0, scan("<img src=\"https://example.com/photo.jpg\" width=\"800\" height=\"600\"/>").stream()
                .filter(i -> i.type().equals("tracking_pixel")).count());
    }

    // ── missing_local_image ───────────────────────────────────────────────────

    @Test
    void missingLocalImageDetected(@TempDir Path dir) throws Exception {
        Path postPath = dir.resolve("post.html");
        Files.writeString(postPath,
                "<article><img src=\"../../assets/missing.jpg\"/></article>");
        Files.createDirectories(dir.resolve("assets"));

        List<ScanHtml.Issue> issues = ScanHtml.scanPost(postPath, null);
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("missing_local_image")));
    }

    @Test
    void existingLocalImageNotFlagged(@TempDir Path dir) throws Exception {
        Path assetsDir = dir.resolve("assets");
        Files.createDirectories(assetsDir);
        Files.writeString(assetsDir.resolve("present.jpg"), "fake");
        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
                "<article><img src=\"../../assets/present.jpg\"/></article>");

        assertFalse(ScanHtml.scanPost(postPath, postsDir).stream()
                .anyMatch(i -> i.type().equals("missing_local_image")));
    }

    // ── empty_embed ───────────────────────────────────────────────────────────

    @Test
    void emptyIframeIsError() {
        List<ScanHtml.Issue> issues = scan("<iframe title=\"video\"></iframe>");
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("empty_embed")));
        issues.stream().filter(i -> i.type().equals("empty_embed"))
                .forEach(i -> assertEquals("ERROR", i.level()));
    }

    @Test
    void iframeWithSrcNotFlagged() {
        assertEquals(0, scan("<iframe src=\"https://youtube.com/embed/abc\"></iframe>").stream()
                .filter(i -> i.type().equals("empty_embed")).count());
    }

    @Test
    void iframeWithDataSrcButNoSrcIsWarn() {
        scan("<iframe data-src=\"https://youtube.com/embed/abc\"></iframe>").stream()
                .filter(i -> i.type().equals("empty_embed"))
                .forEach(i -> assertEquals("WARN", i.level()));
    }

    // ── unreplaced_gist ───────────────────────────────────────────────────────

    @Test
    void unreplacedGistIsError() {
        List<ScanHtml.Issue> issues = scan(
            "<script src=\"https://gist.github.com/user/abc123.js\"></script>"
        );
        assertEquals(1, issues.stream().filter(i -> i.type().equals("unreplaced_gist")).count());
        assertEquals("ERROR", issues.stream().filter(i -> i.type().equals("unreplaced_gist"))
                .findFirst().get().level());
    }

    @Test
    void nonGistScriptNotFlagged() {
        assertEquals(0, scan("<script src=\"https://cdn.example.com/lib.js\"></script>").stream()
                .filter(i -> i.type().equals("unreplaced_gist")).count());
    }

    // ── wordpress_chrome ──────────────────────────────────────────────────────

    @Test
    void addtoanyShareWidgetDetected() {
        assertTrue(scan("<div class=\"addtoany_share_save_container\">Share this post</div>")
                .stream().anyMatch(i -> i.type().equals("wordpress_chrome")));
    }

    @Test
    void commentsAreaDetected() {
        assertTrue(scan("<div id=\"comments\">Leave a comment here</div>")
                .stream().anyMatch(i -> i.type().equals("wordpress_chrome")));
    }

    @Test
    void authorBylineTextDetected() {
        assertTrue(scan("<p>by Mark Proctor - April 2026</p>")
                .stream().anyMatch(i -> i.type().equals("wordpress_chrome")));
    }

    @Test
    void normalParagraphNotFlaggedAsChrome() {
        assertEquals(0, scan("<p>This is a normal article paragraph about rule engines.</p>").stream()
                .filter(i -> i.type().equals("wordpress_chrome")).count());
    }

    // ── missing_image_signal ──────────────────────────────────────────────────

    @Test
    void asShownBelowWithoutImageDetected() {
        assertTrue(scan("<p>As shown below:</p><p>Some text here.</p>")
                .stream().anyMatch(i -> i.type().equals("missing_image_signal")));
    }

    @Test
    void asShownBelowFollowedByImageNotFlagged() {
        assertEquals(0, scan("<p>As shown below:</p><img src=\"../../assets/img.jpg\"/>").stream()
                .filter(i -> i.type().equals("missing_image_signal")).count());
    }

    @Test
    void normalParagraphNotFlaggedAsMissingSignal() {
        assertEquals(0, scan("<p>Drools is a rules engine framework.</p>").stream()
                .filter(i -> i.type().equals("missing_image_signal")).count());
    }

    // ── md_notation_in_text ───────────────────────────────────────────────────

    @Test
    void boldAdjacentToParenDetected() {
        assertTrue(scan("<p><b>Bob Kowalski</b>(Imperial College London)</p>")
                .stream().anyMatch(i -> i.type().equals("md_notation_in_text")));
    }

    @Test
    void boldFollowedBySpaceNotFlagged() {
        assertEquals(0, scan("<p><b>text</b> (with space before paren)</p>").stream()
                .filter(i -> i.type().equals("md_notation_in_text")).count());
    }

    @Test
    void boldInsideCodeBlockNotFlagged() {
        assertEquals(0, scan("<pre><code><b>keyword</b>(arg)</code></pre>").stream()
                .filter(i -> i.type().equals("md_notation_in_text")).count());
    }

    // ── suspicious_code_content ───────────────────────────────────────────────

    @Test
    void htmlEncodedTableInCodeDetected() {
        assertTrue(scan("<pre><code>&lt;table&gt;&lt;tr&gt;&lt;td&gt;data&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;</code></pre>")
                .stream().anyMatch(i -> i.type().equals("suspicious_code_content")));
    }

    @Test
    void htmlEncodedTableLevelIsWarn() {
        scan("<pre><code>&lt;table&gt;&lt;tr&gt;&lt;td&gt;data&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;</code></pre>").stream()
                .filter(i -> i.type().equals("suspicious_code_content"))
                .forEach(i -> assertEquals("WARN", i.level()));
    }

    @Test
    void normalCodeBlockNotFlaggedAsSuspicious() {
        assertEquals(0, scan("<pre><code>public class Foo { void bar() {} }</code></pre>").stream()
                .filter(i -> i.type().equals("suspicious_code_content")).count());
    }

    // ── layout_spacer_image ───────────────────────────────────────────────────

    @Test
    void spacerGifDetectedByName() {
        assertTrue(scan("<img src=\"../../assets/spacer.gif\" width=\"10\" height=\"1\" alt=\"\"/>")
                .stream().anyMatch(i -> i.type().equals("layout_spacer_image")));
    }

    @Test
    void onePixelNoAltDetected() {
        assertTrue(scan("<img src=\"../../assets/img.gif\" height=\"1\" alt=\"\"/>")
                .stream().anyMatch(i -> i.type().equals("layout_spacer_image")));
    }

    @Test
    void trackingPixelNotDoubleReportedAsSpacer() {
        assertFalse(scan("<img src=\"https://stats.wordpress.com/g.gif\" width=\"1\" height=\"1\" alt=\"\"/>")
                .stream().anyMatch(i -> i.type().equals("layout_spacer_image")));
    }

    // ── imgur_image ───────────────────────────────────────────────────────────

    @Test
    void imgurImgSrcDetected() {
        assertTrue(scan("<img src=\"https://i.imgur.com/abc123.jpg\"/>")
                .stream().anyMatch(i -> i.type().equals("imgur_image")));
    }

    @Test
    void imgurLinkDetected() {
        assertTrue(scan("<a href=\"https://imgur.com/gallery/abc\">See image</a>")
                .stream().anyMatch(i -> i.type().equals("imgur_image")));
    }

    @Test
    void webArchiveImgurNotFlagged() {
        assertEquals(0, scan("<img src=\"https://web.archive.org/web/2020/https://i.imgur.com/abc.jpg\"/>").stream()
                .filter(i -> i.type().equals("imgur_image")).count());
    }

    // ── linenumber_table_code ─────────────────────────────────────────────────

    @Test
    void linenumberTableDetected() {
        assertTrue(scan(
            "<table><tr><td><pre>1\n2\n3\n</pre></td>" +
            "<td><pre>rule \"R\"\nwhen\n  Foo()\nthen\n  bar();\nend</pre></td></tr></table>"
        ).stream().anyMatch(i -> i.type().equals("linenumber_table_code")));
    }

    @Test
    void normalTableNotFlagged() {
        assertEquals(0, scan(
            "<table><tr><td>Name</td><td>Value</td></tr><tr><td>Foo</td><td>Bar</td></tr></table>"
        ).stream().filter(i -> i.type().equals("linenumber_table_code")).count());
    }

    // ── potential_code_block ──────────────────────────────────────────────────

    @Test
    void shortProseNotFlaggedAsPotentialCode() {
        assertEquals(0, scan("<p>Click here.</p>").stream()
                .filter(i -> i.type().equals("potential_code_block")).count());
    }

    // ── code_no_newlines ──────────────────────────────────────────────────────

    @Test
    void codeBlockBrTagsDetected() {
        assertTrue(scan(
            "<pre><code>rule \"R\"<br/>when<br/>  Foo()<br/>then<br/>  bar();<br/>end</code></pre>"
        ).stream().anyMatch(i -> i.type().equals("code_no_newlines")));
    }

    @Test
    void properlyFormattedCodeNotFlagged() {
        assertEquals(0, scan(
            "<pre><code>rule \"R\"\nwhen\n  Foo()\nthen\n  bar();\nend</code></pre>"
        ).stream().filter(i -> i.type().equals("code_no_newlines")).count());
    }

    @Test
    void shortCodeOneLinerNotFlagged() {
        assertEquals(0, scan("<pre><code>foo.bar();</code></pre>").stream()
                .filter(i -> i.type().equals("code_no_newlines")).count());
    }

    // ── CSS selector ──────────────────────────────────────────────────────────

    @Test
    void elementWithIdGetsSelectorById() {
        Element el = article("<img id=\"main-image\" src=\"../../assets/img.jpg\"/>")
                .selectFirst("img");
        assertEquals("#main-image", ScanHtml.selector(el));
    }

    @Test
    void nestedElementGetsSelectorPath() {
        Element el = article("<p><b>text</b></p>").selectFirst("b");
        String sel = ScanHtml.selector(el);
        assertNotNull(sel);
        assertTrue(sel.contains("b"));
    }

    // ── Issue record ──────────────────────────────────────────────────────────

    @Test
    void issueHasRequiredFields() {
        ScanHtml.Issue issue = scan("<img src=\"data:image/gif;base64,abc\" alt=\"test\"/>").get(0);
        assertNotNull(issue.type());
        assertNotNull(issue.level());
        assertNotNull(issue.detail());
    }
}
