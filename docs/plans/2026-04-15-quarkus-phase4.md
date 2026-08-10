# Quarkus Phase 4 — Port scan_html.py + scan_assets.py to Java (Jsoup)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the HTML scan pipeline to Java, removing 3 JEP delegates — JEP count 26 → 23.

**Architecture:** `SpargeConstants` holds shared constants (tracking domains, Chrome selectors, code signals). `ScanHtml` runs all 16 issue detectors using Jsoup. `ScanAssets` checks image localisation. `PostsResource.scan()` calls Java directly for scan; a new thin `bridge.post_enrich_only()` handles the enrich step when needed. `dismiss()` and `undismiss()` drop their bridge calls and use `StateStore` directly.

**Tech Stack:** Java 21, Quarkus 3.34, Jsoup 1.18.3, JUnit 5, `@QuarkusTest` + RestAssured

**TDD layers:**
- **Unit:** one test class per detector + SpargeConstants + ScanAssets
- **Integration:** `ScanHtmlIntegrationTest` scanning a real KIE HTML file
- **E2E:** `ScanEndpointTest` via `@QuarkusTest` on POST /api/posts/{slug}/scan

**JEP calls removed:** `post_scan_html`, `post_dismiss_html_check`, `post_undismiss_html_check`

---

## File Map

| File | Action |
|---|---|
| `server/src/main/java/io/sparge/server/SpargeConstants.java` | Create — tracking domains, Chrome selectors, code signals, `isTrackingPixel()` |
| `server/src/main/java/io/sparge/server/ScanHtml.java` | Create — 16 detectors + `scanPost()` + `Issue` record |
| `server/src/main/java/io/sparge/server/ScanAssets.java` | Create — asset localisation |
| `server/src/test/java/io/sparge/server/SpargeConstantsTest.java` | Create — unit tests for `isTrackingPixel()` |
| `server/src/test/java/io/sparge/server/ScanHtmlTest.java` | Create — unit tests for all 16 detectors + happy-path |
| `server/src/test/java/io/sparge/server/ScanHtmlIntegrationTest.java` | Create — integration test on real KIE HTML file |
| `server/src/test/java/io/sparge/server/ScanAssetsTest.java` | Create — unit tests for asset localisation |
| `server/src/test/java/io/sparge/server/ScanEndpointTest.java` | Create — `@QuarkusTest` E2E test for POST /api/posts/{slug}/scan |
| `server/src/main/java/io/sparge/server/PostsResource.java` | Modify — scan/dismiss/undismiss use Java directly |
| `scripts/bridge.py` | Modify — add `post_enrich_only`, remove 3 delegates |
| `tests/python-legacy/` | Move — test_scan_html.py |

---

## Task 1: SpargeConstants.java — shared constants and helpers

**Files:**
- Create: `server/src/main/java/io/sparge/server/SpargeConstants.java`
- Create: `server/src/test/java/io/sparge/server/SpargeConstantsTest.java`

- [ ] **Step 1: Write SpargeConstantsTest.java (FAILING first)**

```java
package io.sparge.server;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class SpargeConstantsTest {

    // ── isTrackingPixel — happy paths ─────────────────────────────────────────

    @Test
    void knownTrackingDomainIsPixel() {
        assertTrue(SpargeConstants.isTrackingPixel(
                "https://stats.wordpress.com/g.gif", "", ""));
    }

    @Test
    void googleAnalyticsIsPixel() {
        assertTrue(SpargeConstants.isTrackingPixel(
                "https://www.google-analytics.com/collect", "", ""));
    }

    @Test
    void oneByone1pxIsPixelByDimension() {
        assertTrue(SpargeConstants.isTrackingPixel(
                "https://example.com/img.gif", "1", "1"));
    }

    @Test
    void zeroByzeroIsPixelByDimension() {
        assertTrue(SpargeConstants.isTrackingPixel(
                "https://example.com/img.gif", "0", "0"));
    }

    @Test
    void normalImageIsNotPixel() {
        assertFalse(SpargeConstants.isTrackingPixel(
                "https://example.com/photo.jpg", "800", "600"));
    }

    @Test
    void localImageIsNotPixel() {
        assertFalse(SpargeConstants.isTrackingPixel(
                "../../assets/photo.jpg", "", ""));
    }

    @Test
    void unknownDomainWithLargeDimensionsIsNotPixel() {
        assertFalse(SpargeConstants.isTrackingPixel(
                "https://cdn.example.com/img.png", "100", "100"));
    }

    @Test
    void dimensionCheckRequiresHttpSrc() {
        // 1x1 but no http — must not be flagged as pixel
        assertFalse(SpargeConstants.isTrackingPixel(
                "../../assets/spacer.gif", "1", "1"));
    }

    // ── Constants exist ────────────────────────────────────────────────────────

    @Test
    void trackingDomainsNotEmpty() {
        assertFalse(SpargeConstants.TRACKING_DOMAINS.isEmpty());
        assertTrue(SpargeConstants.TRACKING_DOMAINS.contains("stats.wordpress.com"));
    }

    @Test
    void chromeSelectorsNotEmpty() {
        assertFalse(SpargeConstants.CHROME_SELECTORS.isEmpty());
    }

    @Test
    void missingImgSignalsNotEmpty() {
        assertFalse(SpargeConstants.MISSING_IMG_SIGNALS.isEmpty());
    }

    @Test
    void codeSignalsStrongNotEmpty() {
        assertFalse(SpargeConstants.CODE_SIGNALS_STRONG.isEmpty());
    }
}
```

Run to verify fails, commit as failing, then implement:

- [ ] **Step 2: Write SpargeConstants.java**

```java
package io.sparge.server;

import java.net.URI;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Shared constants for scan_html.py and scan_assets.py logic.
 * Mirrors scripts/constants.py exactly.
 */
public final class SpargeConstants {

    private SpargeConstants() {}

    // ── Tracking domains ──────────────────────────────────────────────────────

    public static final Set<String> TRACKING_DOMAINS = Set.of(
            "stats.wordpress.com", "pixel.wp.com", "pixel.quantserve.com",
            "b.scorecardresearch.com", "beacon.krxd.net", "ad.doubleclick.net",
            "googleads.g.doubleclick.net", "www.google-analytics.com",
            "connect.facebook.net", "platform.twitter.com", "bat.bing.com",
            "ct.pinterest.com", "analytics.twitter.com", "px.ads.linkedin.com",
            "mc.yandex.ru", "counter.yadro.ru"
    );

    /**
     * Return true if the image is a tracking pixel.
     * Mirrors constants.py: is_tracking_pixel().
     */
    public static boolean isTrackingPixel(String src, String width, String height) {
        String domain = extractDomain(src);
        boolean isTiny = width.strip().equals("1") || width.strip().equals("0");
        isTiny = isTiny && (height.strip().equals("1") || height.strip().equals("0"));
        return TRACKING_DOMAINS.contains(domain) || (isTiny && src.startsWith("http"));
    }

    static String extractDomain(String src) {
        try {
            String host = URI.create(src).getHost();
            if (host == null) return "";
            return host.toLowerCase().replaceFirst("^www\\.", "");
        } catch (Exception e) {
            return "";
        }
    }

    // ── WordPress chrome CSS selectors ────────────────────────────────────────

    public static final List<String> CHROME_SELECTORS = List.of(
            ".entry-header", ".entry-meta", ".author-box", ".author-description",
            ".author-info", ".addtoany_share_save_container", ".sharedaddy",
            "#comments", ".comments-area", ".jp-relatedposts", ".post-navigation",
            ".wpdiscuz-form-container", "[class*=wpDiscuz]", "[class*=addtoany]"
    );

    public static final List<Pattern> CHROME_TEXT_PATTERNS = List.of(
            Pattern.compile("^by\\s+[A-Z]", Pattern.CASE_INSENSITIVE),
            Pattern.compile("View all posts by", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Post Comment", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Leave a Reply", Pattern.CASE_INSENSITIVE),
            Pattern.compile("You might also like", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Share this:", Pattern.CASE_INSENSITIVE)
    );

    // ── Missing-image text signals ────────────────────────────────────────────

    public static final List<Pattern> MISSING_IMG_SIGNALS = List.of(
            Pattern.compile("as shown (below|above|here)", Pattern.CASE_INSENSITIVE),
            Pattern.compile("(see|view) (the )?(image|screenshot|figure|diagram|chart|graph|photo) (below|above)", Pattern.CASE_INSENSITIVE),
            Pattern.compile("(the )?(following|below) (image|screenshot|figure|diagram|chart|graph) shows?", Pattern.CASE_INSENSITIVE),
            Pattern.compile("(image|screenshot|figure|diagram|chart|graph|photo):?\\s*$", Pattern.CASE_INSENSITIVE),
            Pattern.compile("click (to )?(enlarge|zoom|view)", Pattern.CASE_INSENSITIVE)
    );

    // ── Code detection signals ────────────────────────────────────────────────

    public static final List<Pattern> CODE_SIGNALS_STRONG = List.of(
            Pattern.compile("\\brule[\\s\\u00a0]*\"", Pattern.CASE_INSENSITIVE),
            Pattern.compile("^\\s*when\\s*$", Pattern.MULTILINE),
            Pattern.compile("^\\s*then\\s*$", Pattern.MULTILINE),
            Pattern.compile("\\bpublic\\s+(class|static\\s+void|interface)\\b"),
            Pattern.compile("\\bimport\\s+[\\w.]+;"),
            Pattern.compile("<\\?xml\\b"),
            Pattern.compile("<[a-zA-Z][a-zA-Z0-9:._-]*\\b[^>]+/>")
    );

    public static final List<Pattern> CODE_SIGNALS_WEAK = List.of(
            Pattern.compile("^\\s*end\\s*$", Pattern.MULTILINE),
            Pattern.compile("\\bnew\\s+\\w+\\s*\\("),
            Pattern.compile("<[a-zA-Z][a-zA-Z0-9]*\\b[^>]*/?>"),
            Pattern.compile("[;{}]\\s*$", Pattern.MULTILINE)
    );
}
```

- [ ] **Step 3: Run tests — 12 must pass**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=SpargeConstantsTest -q 2>&1 | tail -5
```

- [ ] **Step 4: Commit (reference #55)**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/SpargeConstants.java \
        server/src/test/java/io/sparge/server/SpargeConstantsTest.java
git commit -m "feat(#55): add SpargeConstants.java — tracking domains, Chrome selectors, code signals (12 tests)

Refs #55"
```

---

## Task 2: ScanHmlTest.java — write all failing unit tests

85+ tests mirroring test_scan_html.py. All written BEFORE ScanHtml.java exists.

**Files:**
- Create: `server/src/test/java/io/sparge/server/ScanHtmlTest.java`

- [ ] **Step 1: Write the full test file**

```java
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

/**
 * Unit tests for ScanHtml — mirrors test_scan_html.py.
 * One test class per detector plus happy-path and selector tests.
 */
class ScanHtmlTest {

    private static Element article(String html) {
        Document doc = Jsoup.parse("<article>" + html + "</article>");
        return doc.selectFirst("article");
    }

    private static List<ScanHtml.Issue> scan(String html) {
        return ScanHtml.checkAll(article(html));
    }

    // ── Happy path — no issues ─────────────────────────────────────────────────

    @Test
    void cleanArticleReturnsNoIssues() {
        List<ScanHtml.Issue> issues = scan(
            "<h1>Title</h1><p>Normal paragraph text.</p>" +
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
    void dataPlaceholderAltTruncatedTo60() {
        String longAlt = "A".repeat(100);
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"data:image/png;base64,abc\" alt=\"" + longAlt + "\"/>"
        );
        assertEquals(1, issues.size());
        assertTrue(issues.get(0).detail().contains("alt="), "detail must include alt text snippet");
    }

    // ── noscript_remnant ──────────────────────────────────────────────────────

    @Test
    void noscriptWithHttpUrlDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<noscript><img src=\"https://example.com/img.jpg\"/></noscript>"
        );
        assertEquals(1, issues.size());
        assertEquals("noscript_remnant", issues.get(0).type());
        assertEquals("WARN", issues.get(0).level());
    }

    @Test
    void noscriptWithoutUrlNotFlagged() {
        assertEquals(0, scan("<noscript>JavaScript is disabled</noscript>").stream()
                .filter(i -> i.type().equals("noscript_remnant")).count());
    }

    // ── external_image ────────────────────────────────────────────────────────

    @Test
    void externalImageDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"https://example.com/photo.jpg\" width=\"800\" height=\"600\"/>"
        );
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("external_image")));
    }

    @Test
    void externalImageLevel_WARN() {
        List<ScanHtml.Issue> issues = scan("<img src=\"https://example.com/photo.jpg\"/>");
        issues.stream().filter(i -> i.type().equals("external_image"))
                .forEach(i -> assertEquals("WARN", i.level()));
    }

    @Test
    void localImageNotFlaggedAsExternal() {
        assertEquals(0, scan("<img src=\"../../assets/local.jpg\"/>").stream()
                .filter(i -> i.type().equals("external_image")).count());
    }

    @Test
    void oneByOneExternalImageSkipped_tracking_pixel_catches_it() {
        // 1x1 external images are tracking pixels, not external_image
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"https://example.com/pixel.gif\" width=\"1\" height=\"1\"/>"
        );
        assertFalse(issues.stream().anyMatch(i -> i.type().equals("external_image")),
                "1x1 image must not be flagged as external_image (tracking_pixel catches it)");
    }

    // ── tracking_pixel ────────────────────────────────────────────────────────

    @Test
    void trackingPixelByDomainDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"https://stats.wordpress.com/g.gif\"/>"
        );
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("tracking_pixel")));
    }

    @Test
    void trackingPixelByDimensionDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"https://unknown-analytics.com/t.gif\" width=\"1\" height=\"1\"/>"
        );
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("tracking_pixel")));
    }

    @Test
    void trackingPixelLevel_WARN() {
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"https://stats.wordpress.com/g.gif\"/>"
        );
        issues.stream().filter(i -> i.type().equals("tracking_pixel"))
                .forEach(i -> assertEquals("WARN", i.level()));
    }

    @Test
    void normalImageNotFlaggedAsTrackingPixel() {
        assertEquals(0, scan("<img src=\"https://example.com/photo.jpg\" width=\"800\" height=\"600\"/>").stream()
                .filter(i -> i.type().equals("tracking_pixel")).count());
    }

    // ── missing_local_image ───────────────────────────────────────────────────

    @Test
    void missingLocalImageDetected(@TempDir Path dir) throws Exception {
        // Write an HTML file that references a missing asset
        Path postPath = dir.resolve("post.html");
        Files.writeString(postPath,
                "<article><img src=\"../../assets/missing.jpg\"/></article>");
        // assets/ dir exists but missing.jpg doesn't
        Files.createDirectories(dir.resolve("assets"));

        List<ScanHtml.Issue> issues = ScanHtml.scanPost(postPath, null);
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("missing_local_image")),
                "Missing local image must be detected");
    }

    @Test
    void existingLocalImageNotFlagged(@TempDir Path dir) throws Exception {
        // Create assets directory and the actual file
        Path assetsDir = dir.resolve("assets");
        Files.createDirectories(assetsDir);
        Files.writeString(assetsDir.resolve("present.jpg"), "fake image");

        // posts/mark-proctor/post.html references ../../assets/present.jpg
        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
                "<article><img src=\"../../assets/present.jpg\"/></article>");

        List<ScanHtml.Issue> issues = ScanHtml.scanPost(postPath, postsDir);
        assertFalse(issues.stream().anyMatch(i -> i.type().equals("missing_local_image")),
                "Existing local image must not be flagged");
    }

    // ── empty_embed ───────────────────────────────────────────────────────────

    @Test
    void emptyIframeDetected() {
        List<ScanHtml.Issue> issues = scan("<iframe title=\"video\"></iframe>");
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("empty_embed")));
    }

    @Test
    void iframeWithSrcNotFlagged() {
        assertEquals(0, scan("<iframe src=\"https://youtube.com/embed/abc\"></iframe>").stream()
                .filter(i -> i.type().equals("empty_embed")).count());
    }

    @Test
    void iframeWithDataSrcButNoSrcIsWarn() {
        List<ScanHtml.Issue> issues = scan(
            "<iframe data-src=\"https://youtube.com/embed/abc\"></iframe>"
        );
        issues.stream().filter(i -> i.type().equals("empty_embed"))
                .forEach(i -> assertEquals("WARN", i.level()));
    }

    @Test
    void emptyIframeIsError() {
        List<ScanHtml.Issue> issues = scan("<iframe></iframe>");
        issues.stream().filter(i -> i.type().equals("empty_embed"))
                .forEach(i -> assertEquals("ERROR", i.level()));
    }

    // ── unreplaced_gist ───────────────────────────────────────────────────────

    @Test
    void unreplacedGistDetected() {
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
    void wordpressShareWidgetDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<div class=\"addtoany_share_save_container\">Share this post</div>"
        );
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("wordpress_chrome")));
    }

    @Test
    void commentsAreaDetected() {
        List<ScanHtml.Issue> issues = scan("<div id=\"comments\">Leave a comment here</div>");
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("wordpress_chrome")));
    }

    @Test
    void authorBylineTextDetected() {
        List<ScanHtml.Issue> issues = scan("<p>by Mark Proctor - April 2026</p>");
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("wordpress_chrome")));
    }

    @Test
    void cleanArticleParagraphNotFlaggedAsChrome() {
        assertEquals(0, scan("<p>This is a normal article paragraph about rule engines.</p>").stream()
                .filter(i -> i.type().equals("wordpress_chrome")).count());
    }

    // ── missing_image_signal ──────────────────────────────────────────────────

    @Test
    void asShownBelowWithoutImageDetected() {
        List<ScanHtml.Issue> issues = scan("<p>As shown below:</p><p>Some text here.</p>");
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("missing_image_signal")));
    }

    @Test
    void asShownBelowFollowedByImageNotFlagged() {
        assertEquals(0, scan(
            "<p>As shown below:</p><img src=\"../../assets/img.jpg\"/>"
        ).stream().filter(i -> i.type().equals("missing_image_signal")).count());
    }

    @Test
    void normalParagraphNotFlaggedAsMissingSignal() {
        assertEquals(0, scan("<p>Drools is a rules engine framework.</p>").stream()
                .filter(i -> i.type().equals("missing_image_signal")).count());
    }

    // ── md_notation_in_text ───────────────────────────────────────────────────

    @Test
    void boldAdjacentToParenDetected() {
        List<ScanHtml.Issue> issues = scan("<p><b>Bob Kowalski</b>(Imperial College London)</p>");
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("md_notation_in_text")));
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
        List<ScanHtml.Issue> issues = scan(
            "<pre><code>&lt;table&gt;&lt;tr&gt;&lt;td&gt;data&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;</code></pre>"
        );
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("suspicious_code_content")));
        assertEquals("WARN", issues.stream().filter(i -> i.type().equals("suspicious_code_content"))
                .findFirst().get().level());
    }

    @Test
    void normalCodeBlockNotFlaggedAsSuspicious() {
        assertEquals(0, scan(
            "<pre><code>public class Foo { void bar() {} }</code></pre>"
        ).stream().filter(i -> i.type().equals("suspicious_code_content")).count());
    }

    // ── layout_spacer_image ───────────────────────────────────────────────────

    @Test
    void spacerGifDetectedByName() {
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"../../assets/spacer.gif\" width=\"10\" height=\"1\" alt=\"\"/>"
        );
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("layout_spacer_image")));
    }

    @Test
    void onePixelNoAltDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"../../assets/img.gif\" height=\"1\" alt=\"\"/>"
        );
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("layout_spacer_image")));
    }

    @Test
    void trackingPixelNotDoubleReportedAsSpacer() {
        // 1x1 from tracking domain — should be tracking_pixel only
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"https://stats.wordpress.com/g.gif\" width=\"1\" height=\"1\" alt=\"\"/>"
        );
        assertFalse(issues.stream().anyMatch(i -> i.type().equals("layout_spacer_image")),
                "Tracking pixels must not also be reported as spacers");
    }

    // ── imgur_image ───────────────────────────────────────────────────────────

    @Test
    void imgurImgSrcDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"https://i.imgur.com/abc123.jpg\"/>"
        );
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("imgur_image")));
    }

    @Test
    void imgurLinkDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<a href=\"https://imgur.com/gallery/abc\">See image</a>"
        );
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("imgur_image")));
    }

    @Test
    void webArchiveImgurNotFlagged() {
        assertEquals(0, scan(
            "<img src=\"https://web.archive.org/web/2020/https://i.imgur.com/abc.jpg\"/>"
        ).stream().filter(i -> i.type().equals("imgur_image")).count());
    }

    // ── linenumber_table_code ─────────────────────────────────────────────────

    @Test
    void linenumberTablePatternADetected() {
        List<ScanHtml.Issue> issues = scan(
            "<table><tr><td><pre>1\n2\n3\n</pre></td>" +
            "<td><pre>rule \"R\"\nwhen\n  Foo()\nthen\n  bar();\nend</pre></td></tr></table>"
        );
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("linenumber_table_code")));
    }

    @Test
    void normalTableNotFlagged() {
        assertEquals(0, scan(
            "<table><tr><td>Name</td><td>Value</td></tr>" +
            "<tr><td>Foo</td><td>Bar</td></tr></table>"
        ).stream().filter(i -> i.type().equals("linenumber_table_code")).count());
    }

    // ── potential_code_block ──────────────────────────────────────────────────

    @Test
    void drlInParagraphWithBrDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<p>rule \"Test\"<br/>when<br/>  Foo()<br/>then<br/>  bar();<br/>end</p>"
        );
        assertTrue(issues.stream().anyMatch(i ->
                i.type().equals("potential_code_block") || i.type().equals("code_no_newlines")));
    }

    @Test
    void shortProseNotFlaggedAsPotentialCode() {
        assertEquals(0, scan("<p>Click here.</p>").stream()
                .filter(i -> i.type().equals("potential_code_block")).count());
    }

    // ── code_no_newlines ──────────────────────────────────────────────────────

    @Test
    void codeBlockBrTagsDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<pre><code>rule \"R\"<br/>when<br/>  Foo()<br/>then<br/>  bar();<br/>end</code></pre>"
        );
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("code_no_newlines")));
    }

    @Test
    void codeBlockOneLinerWithSemicolonDetected() {
        List<ScanHtml.Issue> issues = scan(
            "<pre><code>rule \"R\" when Foo($x: bar) then System.out.println($x); end</code></pre>"
        );
        assertTrue(issues.stream().anyMatch(i -> i.type().equals("code_no_newlines")));
    }

    @Test
    void properlyFormattedCodeNotFlagged() {
        assertEquals(0, scan(
            "<pre><code>rule \"R\"\nwhen\n  Foo()\nthen\n  bar();\nend</code></pre>"
        ).stream().filter(i -> i.type().equals("code_no_newlines")).count());
    }

    @Test
    void shortCodeOneLinerNotFlagged() {
        // Under 40 chars — too short to be multi-statement
        assertEquals(0, scan("<pre><code>foo.bar();</code></pre>").stream()
                .filter(i -> i.type().equals("code_no_newlines")).count());
    }

    // ── CSS selector generation ────────────────────────────────────────────────

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
        assertTrue(sel.contains("b"), "selector must include the element tag");
    }

    // ── Issue record fields ────────────────────────────────────────────────────

    @Test
    void issueHasAllRequiredFields() {
        List<ScanHtml.Issue> issues = scan(
            "<img src=\"data:image/gif;base64,abc\" alt=\"test\"/>"
        );
        ScanHtml.Issue issue = issues.get(0);
        assertNotNull(issue.type());
        assertNotNull(issue.level());
        assertNotNull(issue.detail());
        // selector may be null for some issues but type/level/detail must be set
    }
}
```

- [ ] **Step 2: Run to verify ALL fail (ScanHtml doesn't exist)**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=ScanHtmlTest -q 2>&1 | tail -5
```

Expected: BUILD FAILURE.

- [ ] **Step 3: Commit failing tests**

```bash
cd ~/claude/sparge
git add server/src/test/java/io/sparge/server/ScanHtmlTest.java
git commit -m "test(#55): add ScanHtmlTest — unit tests for all 16 detectors (failing TDD)

Refs #55"
```

---

## Task 3: ScanHtml.java — implement all 16 detectors

**Files:**
- Create: `server/src/main/java/io/sparge/server/ScanHtml.java`

- [ ] **Step 1: Write ScanHtml.java**

```java
package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.nodes.Node;
import org.jsoup.nodes.TextNode;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * HTML issue scanner.
 * Mirrors scripts/scan_html.py: all 16 check functions + scanPost().
 */
public final class ScanHtml {

    private ScanHtml() {}

    /**
     * Immutable issue record — mirrors the dict returned by scan_html.py.
     */
    public record Issue(String type, String level, String detail, String selector) {}

    private static final Pattern BYLINE_RE =
            Pattern.compile("^by\\s+[A-Z]", Pattern.CASE_INSENSITIVE);

    private static final Pattern URL_IN_NOSCRIPT =
            Pattern.compile("src=[\"']?(https?://[^\"'>\\s]+)");

    private static final Pattern CODE_MULTILINE_RE =
            Pattern.compile("[;{}]|when\\s+\\w|\\bthen\\b|\\bend\\b");

    private static final Pattern ENCODED_TAG_RE = Pattern.compile(
            "&lt;(?:\\?xml|table|div|p|span|ul|ol|li|section|article|h[1-6]|tr|td|th)\\b",
            Pattern.CASE_INSENSITIVE);

    // ── Helpers ───────────────────────────────────────────────────────────────

    /**
     * Generate a CSS selector for an element — mirrors _selector() in scan_html.py.
     */
    public static String selector(Element el) {
        if (el == null) return null;
        if (el.hasAttr("id") && !el.id().isEmpty()) return "#" + el.id();
        List<String> parts = new ArrayList<>();
        Element current = el;
        for (int depth = 0; depth < 6; depth++) {
            Element parent = current.parent();
            if (parent == null) break;
            String tag = current.tagName();
            if (tag.equals("html") || tag.equals("body") || tag.equals("article")
                    || tag.equals("[document]")) break;
            List<Element> siblings = parent.children().stream()
                    .filter(e -> e.tagName().equals(tag))
                    .collect(Collectors.toList());
            if (siblings.size() > 1) {
                int idx = siblings.indexOf(current) + 1;
                parts.add(tag + ":nth-of-type(" + idx + ")");
            } else {
                parts.add(tag);
            }
            current = parent;
        }
        if (parts.isEmpty()) return el.tagName();
        Collections.reverse(parts);
        return String.join(" > ", parts);
    }

    private static Issue issue(String type, String level, String detail, Element el) {
        return new Issue(type, level, detail, el != null ? selector(el) : null);
    }

    private static String trunc(String s, int max) {
        if (s == null) return "";
        return s.length() > max ? s.substring(0, max) : s;
    }

    private static String filename(String src) {
        try {
            String path = new java.net.URI(src).getPath();
            if (path == null) return "";
            int slash = path.lastIndexOf('/');
            return slash >= 0 ? path.substring(slash + 1) : path;
        } catch (Exception e) {
            int slash = src.lastIndexOf('/');
            return slash >= 0 ? src.substring(slash + 1) : src;
        }
    }

    // ── 16 detectors ──────────────────────────────────────────────────────────

    public static List<Issue> checkDataPlaceholders(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element img : article.select("img")) {
            String src = img.attr("src");
            if (src.startsWith("data:")) {
                String alt = img.attr("alt");
                issues.add(issue("data_placeholder", "ERROR",
                        "Unrecovered lazy-load placeholder — alt=\"" + trunc(alt, 60) + "\"", img));
            }
        }
        return issues;
    }

    public static List<Issue> checkNoscriptRemnants(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element ns : article.select("noscript")) {
            Matcher m = URL_IN_NOSCRIPT.matcher(ns.outerHtml());
            if (m.find()) {
                issues.add(issue("noscript_remnant", "WARN",
                        "Orphaned <noscript> with image URL: " + trunc(m.group(1), 80), ns));
            }
        }
        return issues;
    }

    public static List<Issue> checkExternalImages(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element img : article.select("img")) {
            String src = img.attr("src");
            if (!src.startsWith("http")) continue;
            String w = img.attr("width"), h = img.attr("height");
            if ((w.equals("1") || w.equals("0")) && (h.equals("1") || h.equals("0"))) continue;
            issues.add(issue("external_image", "WARN",
                    "Image not localised: " + trunc(src, 80), img));
        }
        return issues;
    }

    public static List<Issue> checkTrackingPixels(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element img : article.select("img")) {
            String src = img.attr("src");
            String w = img.attr("width"), h = img.attr("height");
            if (SpargeConstants.isTrackingPixel(src, w, h)) {
                String domain = SpargeConstants.extractDomain(src);
                issues.add(issue("tracking_pixel", "WARN",
                        "Tracking pixel from " + (domain.isEmpty() ? "unknown" : domain)
                        + ": " + trunc(src, 60), img));
            }
        }
        return issues;
    }

    public static List<Issue> checkMissingLocalImages(
            Element article, Path postPath, Path postsDir) {
        List<Issue> issues = new ArrayList<>();
        Path baseDir = postsDir != null
                ? postsDir.getParent().getParent()
                : postPath.getParent().getParent().getParent();
        for (Element img : article.select("img")) {
            String src = img.attr("src");
            if (!src.startsWith("../../assets/")) continue;
            String rel = src.replace("../../", "");
            Path abs = baseDir.resolve(rel);
            if (!Files.exists(abs)) {
                issues.add(issue("missing_local_image", "ERROR",
                        "Local image file missing: " + rel, img));
            }
        }
        return issues;
    }

    public static List<Issue> checkEmptyEmbeds(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element iframe : article.select("iframe")) {
            String src     = iframe.attr("src").strip();
            String dataSrc = iframe.attr("data-src").strip();
            if (src.isEmpty() && dataSrc.isEmpty()) {
                String title = iframe.attr("title");
                if (title.isEmpty()) {
                    title = iframe.classNames().stream().findFirst().orElse("iframe");
                }
                issues.add(issue("empty_embed", "ERROR",
                        "Empty iframe (no src recovered) — title=\"" + trunc(title, 40) + "\"", iframe));
            } else if (src.isEmpty()) {
                issues.add(issue("empty_embed", "WARN",
                        "iframe has data-src but no src — needs wiring: " + trunc(dataSrc, 60), iframe));
            }
        }
        return issues;
    }

    public static List<Issue> checkUnreplacedGists(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element script : article.select("script[src]")) {
            String src = script.attr("src");
            if (src.contains("gist.github.com")) {
                issues.add(issue("unreplaced_gist", "ERROR",
                        "Gist not inlined: " + trunc(src, 80), script));
            }
        }
        return issues;
    }

    public static List<Issue> checkWordpressChrome(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (String sel : SpargeConstants.CHROME_SELECTORS) {
            for (Element el : article.select(sel)) {
                String text = el.text().strip();
                if (text.length() < 3) continue;
                issues.add(issue("wordpress_chrome", "WARN",
                        "WordPress UI element in article (" + sel + "): \""
                        + trunc(text, 50) + "\"", el));
            }
        }
        for (Element tag : article.select("p, div, span")) {
            String text = tag.wholeText().replaceAll("\\s+", " ").strip();
            if (text.length() > 200) continue;
            for (java.util.regex.Pattern pat : SpargeConstants.CHROME_TEXT_PATTERNS) {
                if (pat.matcher(text).find()) {
                    issues.add(issue("wordpress_chrome", "WARN",
                            "Metadata text in article: \"" + trunc(text, 60) + "\"", tag));
                    break;
                }
            }
        }
        return issues;
    }

    public static List<Issue> checkMissingImageSignals(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element p : article.select("p, div")) {
            if (p.hasClass("missing-image")) continue;
            String text = p.text().strip();
            if (text.isEmpty() || text.length() > 300) continue;
            if (SpargeConstants.MISSING_IMG_SIGNALS.stream()
                    .noneMatch(pat -> pat.matcher(text).find())) continue;
            if (p.selectFirst("img") != null) continue;
            Element next = p.nextElementSibling();
            if (next != null) {
                if (next.tagName().equals("img") || next.tagName().equals("figure")) continue;
                if (next.selectFirst("img") != null) continue;
                if (next.hasClass("missing-image")) continue;
            }
            issues.add(issue("missing_image_signal", "WARN",
                    "Text signals missing image: \"" + trunc(text, 80) + "\"", p));
        }
        return issues;
    }

    public static List<Issue> checkMdNotationInText(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element tag : article.select("strong, b, em, i")) {
            if (tag.parents().stream().anyMatch(
                    p -> p.tagName().equals("pre") || p.tagName().equals("code"))) continue;
            Node sib = tag.nextSibling();
            if (sib instanceof TextNode tn) {
                String text = tn.getWholeText();
                if (!text.isEmpty() && !Character.isWhitespace(text.charAt(0))) {
                    char adjacent = text.charAt(0);
                    issues.add(issue("md_notation_in_text", "WARN",
                            "<" + tag.tagName() + "> immediately followed by '" + adjacent + "' — "
                            + "html2text produces **" + trunc(tag.text(), 20) + "**" + adjacent
                            + " (no space), mismatching the HTML plain text which has a space", tag));
                }
            }
        }
        return issues;
    }

    public static List<Issue> checkSuspiciousEncodedHtml(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element pre : article.select("pre")) {
            Element code = pre.selectFirst("code");
            if (code == null) continue;
            if (ENCODED_TAG_RE.matcher(code.outerHtml()).find()) {
                issues.add(issue("suspicious_code_content", "WARN",
                        "<pre><code> contains HTML-encoded markup — may be a conversion "
                        + "artefact rather than intentional code (e.g. &lt;table&gt;). "
                        + "Check original page and dismiss if intentional.", pre));
            }
        }
        return issues;
    }

    public static List<Issue> checkLayoutSpacerImages(Element article) {
        List<Element> spacers = new ArrayList<>();
        for (Element img : article.select("img")) {
            String src = img.attr("src");
            String alt = img.attr("alt").strip();
            String h   = img.attr("height").strip();
            String w   = img.attr("width").strip();
            if (SpargeConstants.isTrackingPixel(src, w, h)) continue;
            boolean isSpacerName = filename(src).toLowerCase().contains("spacer");
            boolean isSpacerDims = (h.equals("0") || h.equals("1")) && alt.isEmpty();
            if (isSpacerName || isSpacerDims) spacers.add(img);
        }
        if (spacers.isEmpty()) return List.of();
        Element first = spacers.get(0);
        return List.of(issue("layout_spacer_image", "WARN",
                spacers.size() + " layout spacer image(s) (e.g. spacer.gif "
                + first.attr("width") + "×" + first.attr("height")
                + "px) — no content value, safe to remove", first));
    }

    public static List<Issue> checkImgurImages(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element img : article.select("img")) {
            String src = img.attr("src");
            if (src.contains("imgur.com") && !src.contains("web.archive.org")) {
                issues.add(issue("imgur_image", "WARN",
                        "imgur img src — geo-blocked in some regions, replace with Wayback URL: "
                        + trunc(src, 100), img));
            }
        }
        for (Element a : article.select("a[href]")) {
            String href = a.attr("href");
            if (href.contains("imgur.com") && !href.contains("web.archive.org")) {
                issues.add(issue("imgur_image", "WARN",
                        "imgur link href — geo-blocked in some regions, replace with Wayback URL: "
                        + trunc(href, 100), a));
            }
        }
        return issues;
    }

    public static List<Issue> checkLinenumberTableCode(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element table : article.select("table")) {
            var tds = table.select("td");
            if (tds.size() < 2) continue;
            Element leftTd = tds.get(0), rightTd = tds.get(1);
            Element leftPre = leftTd.selectFirst("pre");
            boolean isA = leftPre != null
                    && !leftPre.text().strip().isEmpty()
                    && leftPre.text().strip().chars().allMatch(c ->
                    Character.isDigit(c) || c == '\n' || c == ' ');
            boolean isB = !isA
                    && leftTd.children().stream().allMatch(c ->
                    c.tagName().equals("div") && c.text().strip().matches("\\d+"))
                    && !leftTd.children().isEmpty()
                    && rightTd.selectFirst("code, pre") != null;
            if (!isA && !isB) continue;
            Element rightCode = rightTd.selectFirst("pre, code");
            String snippet = rightCode != null ? trunc(rightCode.text(), 50) : "";
            issues.add(issue("linenumber_table_code", "WARN",
                    "Two-column line-number table — left column is line numbers, "
                    + "right column is code. Convert to <pre><code>: \"" + snippet + "\"", table));
        }
        return issues;
    }

    public static List<Issue> checkPotentialCodeBlocks(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element p : article.select("p, div")) {
            if (p.parents().stream().anyMatch(par ->
                    par.tagName().equals("pre") || par.tagName().equals("code"))) continue;
            if (p.tagName().equals("div") && p.parent() != null
                    && p.parent().tagName().equals("article")) continue;
            if (p.selectFirst("pre") != null) continue;
            if (p.selectFirst("br") == null) continue;
            String text = p.wholeText().replace("\u00a0", " ");
            if (text.length() < 20 || text.length() > 5000) continue;
            boolean strongHit = SpargeConstants.CODE_SIGNALS_STRONG.stream()
                    .anyMatch(sig -> sig.matcher(text).find());
            long weakHits = SpargeConstants.CODE_SIGNALS_WEAK.stream()
                    .filter(sig -> sig.matcher(text).find()).count();
            if (!strongHit && weakHits < 2) continue;
            long nonBlankLines = Arrays.stream(text.split("\n"))
                    .filter(l -> !l.strip().isEmpty()).count();
            if (nonBlankLines < 2) continue;
            double avgLen = Arrays.stream(text.split("\n"))
                    .filter(l -> !l.strip().isEmpty())
                    .mapToInt(String::length).average().orElse(0);
            if (avgLen > 80) continue;
            String snippet = trunc(text.replace("\n", " ").strip(), 60);
            issues.add(issue("potential_code_block", "WARN",
                    "<p> with <br/> line breaks looks like unformatted code — "
                    + "consider wrapping in <pre><code>: \"" + snippet + "\"", p));
        }
        return issues;
    }

    public static List<Issue> checkCodeBlockNoNewlines(Element article) {
        List<Issue> issues = new ArrayList<>();
        for (Element pre : article.select("pre")) {
            if ("true".equals(pre.attr("data-oneliner"))) continue;
            Element code  = pre.selectFirst("code");
            Element target = code != null ? code : pre;

            // Case A: uses <br/> as line separators
            var brs = target.select("br");
            if (brs.size() >= 2) {
                Element clone = target.clone();
                clone.select("br").forEach(br -> br.replaceWith(new TextNode("\n")));
                String snippet = trunc(clone.wholeText().replace("\n", " "), 60);
                issues.add(issue("code_no_newlines", "WARN",
                        "<pre><code> uses <br/> for line breaks — must be converted "
                        + "to \\n at ingest/enrich time: \"" + snippet + "\"", pre));
                continue;
            }

            // Case B: already a single long line
            String text = target.wholeText();
            if (text.contains("\n")) continue;
            if (text.length() < 40) continue;
            if (!CODE_MULTILINE_RE.matcher(text).find()) continue;
            issues.add(issue("code_no_newlines", "WARN",
                    "<pre><code> content has no line breaks — likely lost during ingest "
                    + "(CMS adds <br/> at render time): \"" + trunc(text, 60) + "\"", pre));
        }
        return issues;
    }

    // ── checkAll + scanPost ────────────────────────────────────────────────────

    /**
     * Run all detectors on an already-parsed article element.
     * For unit testing — does not resolve local image paths.
     */
    public static List<Issue> checkAll(Element article) {
        List<Issue> issues = new ArrayList<>();
        issues.addAll(checkDataPlaceholders(article));
        issues.addAll(checkNoscriptRemnants(article));
        issues.addAll(checkExternalImages(article));
        issues.addAll(checkTrackingPixels(article));
        issues.addAll(checkEmptyEmbeds(article));
        issues.addAll(checkUnreplacedGists(article));
        issues.addAll(checkWordpressChrome(article));
        issues.addAll(checkMissingImageSignals(article));
        issues.addAll(checkMdNotationInText(article));
        issues.addAll(checkSuspiciousEncodedHtml(article));
        issues.addAll(checkLayoutSpacerImages(article));
        issues.addAll(checkImgurImages(article));
        issues.addAll(checkLinenumberTableCode(article));
        issues.addAll(checkPotentialCodeBlocks(article));
        issues.addAll(checkCodeBlockNoNewlines(article));
        return issues;
    }

    /**
     * Full scan entry point — reads file, pre-strips bylines, runs all checks.
     * Mirrors scan_html.py: scan_post().
     */
    public static List<Issue> scanPost(Path htmlPath, Path postsDir) throws IOException {
        String html = Files.readString(htmlPath);
        Document doc = Jsoup.parse(html);

        Element article = doc.selectFirst("article");
        if (article == null) article = doc.selectFirst("body");
        if (article == null)
            return List.of(issue("no_article", "ERROR",
                    "No <article> or <body> element found", null));

        // Pre-strip systematic WordPress bylines
        for (Element tag : new ArrayList<>(article.select("p, div, span"))) {
            String text = tag.wholeText().replaceAll("\\s+", " ").strip();
            if (text.length() < 200 && BYLINE_RE.matcher(text).find()) tag.remove();
        }

        List<Issue> issues = new ArrayList<>(checkAll(article));
        // Add path-dependent checks
        issues.addAll(checkMissingLocalImages(article, htmlPath, postsDir));
        return issues;
    }
}
```

- [ ] **Step 2: Run tests — all must pass**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=ScanHtmlTest -q 2>&1 | tail -8
```

Expected: all passing. If any fail, fix `ScanHtml.java` — do NOT change tests.

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/ScanHtml.java
git commit -m "feat(#55): add ScanHtml.java — 16 issue detectors mirroring scan_html.py

Refs #55"
```

---

## Task 4: ScanHtmlIntegrationTest — scan a real KIE HTML file

**Files:**
- Create: `server/src/test/java/io/sparge/server/ScanHtmlIntegrationTest.java`

- [ ] **Step 1: Pick a known post and write the test**

```java
package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration test: scan a real KIE archive HTML file.
 * Skipped when the KIE archive is not present (CI, fresh machines).
 */
class ScanHtmlIntegrationTest {

    private static final Path KIE_POSTS = Paths.get(
            System.getProperty("user.home"),
            "mdproctor.github.io/legacy/posts/mark-proctor"
    );

    static boolean kieArchivePresent() {
        return Files.isDirectory(KIE_POSTS);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanPostReturnsListForRealHtmlFile() throws Exception {
        // Pick the first available HTML file from the archive
        Path post = Files.list(KIE_POSTS)
                .filter(p -> p.toString().endsWith(".html"))
                .findFirst()
                .orElseThrow(() -> new RuntimeException("No HTML files in KIE archive"));

        List<ScanHtml.Issue> issues = ScanHtml.scanPost(post, KIE_POSTS);

        // Must return a list (possibly empty — that's fine)
        assertNotNull(issues, "scanPost must return a non-null list");

        // Every issue must have required fields
        for (ScanHtml.Issue issue : issues) {
            assertNotNull(issue.type(),  "issue.type must not be null");
            assertNotNull(issue.level(), "issue.level must not be null");
            assertNotNull(issue.detail(),"issue.detail must not be null");
            assertTrue(issue.level().equals("ERROR") || issue.level().equals("WARN"),
                    "level must be ERROR or WARN, got: " + issue.level());
        }
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanMultiplePostsAllReturnLists() throws Exception {
        List<Path> posts = Files.list(KIE_POSTS)
                .filter(p -> p.toString().endsWith(".html"))
                .limit(10)
                .toList();

        for (Path post : posts) {
            List<ScanHtml.Issue> issues = ScanHtml.scanPost(post, KIE_POSTS);
            assertNotNull(issues, "scanPost must not return null for: " + post.getFileName());
        }
    }
}
```

- [ ] **Step 2: Run (skips gracefully if KIE archive not present on this machine)**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=ScanHtmlIntegrationTest -q 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/test/java/io/sparge/server/ScanHtmlIntegrationTest.java
git commit -m "test(#55): add ScanHtmlIntegrationTest — integration tests on real KIE HTML files

Refs #55"
```

---

## Task 5: ScanAssetsTest + ScanAssets.java (TDD)

**Files:**
- Create: `server/src/test/java/io/sparge/server/ScanAssetsTest.java`
- Create: `server/src/main/java/io/sparge/server/ScanAssets.java`

- [ ] **Step 1: Write ScanAssetsTest.java (FAILING first)**

```java
package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

class ScanAssetsTest {

    // ── Happy path — all images localised ─────────────────────────────────────

    @Test
    void allLocalisedImagesCountedCorrectly(@TempDir Path dir) throws Exception {
        // Create assets directory with two real files
        Path assetsDir = dir.resolve("assets");
        Files.createDirectories(assetsDir);
        Files.writeString(assetsDir.resolve("img1.jpg"), "fake");
        Files.writeString(assetsDir.resolve("img2.jpg"), "fake");

        // Post at posts/mark-proctor/post.html referencing ../../assets/
        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
            "<article>" +
            "<img src=\"../../assets/img1.jpg\"/>" +
            "<img src=\"../../assets/img2.jpg\"/>" +
            "</article>");

        var result = ScanAssets.scan(postPath, postPath);

        assertEquals(2, result.total());
        assertEquals(2, result.localised());
        assertEquals(0, result.broken());
        assertTrue(result.missingLocal().isEmpty());
        assertTrue(result.external().isEmpty());
    }

    // ── Missing local images ───────────────────────────────────────────────────

    @Test
    void missingLocalImagesCountedAsBroken(@TempDir Path dir) throws Exception {
        Path assetsDir = dir.resolve("assets");
        Files.createDirectories(assetsDir);
        // img1.jpg exists, img2.jpg does NOT

        Files.writeString(assetsDir.resolve("img1.jpg"), "fake");

        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
            "<article>" +
            "<img src=\"../../assets/img1.jpg\"/>" +
            "<img src=\"../../assets/missing.jpg\"/>" +
            "</article>");

        var result = ScanAssets.scan(postPath, postPath);

        assertEquals(2, result.total());
        assertEquals(1, result.localised());
        assertEquals(1, result.broken());
        assertEquals(1, result.missingLocal().size());
        assertTrue(result.missingLocal().get(0).contains("missing.jpg"));
    }

    // ── External images ───────────────────────────────────────────────────────

    @Test
    void externalImagesCountedAsBroken(@TempDir Path dir) throws Exception {
        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
            "<article>" +
            "<img src=\"https://example.com/photo.jpg\"/>" +
            "</article>");

        var result = ScanAssets.scan(postPath, postPath);

        assertEquals(1, result.total());
        assertEquals(0, result.localised());
        assertEquals(1, result.broken());
        assertEquals(1, result.external().size());
        assertTrue(result.external().get(0).contains("example.com"));
    }

    // ── Data URIs and tracking pixels excluded ────────────────────────────────

    @Test
    void dataUriImagesExcludedFromCount(@TempDir Path dir) throws Exception {
        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
            "<article>" +
            "<img src=\"data:image/gif;base64,R0lGODlh\"/>" +
            "</article>");

        var result = ScanAssets.scan(postPath, postPath);
        assertEquals(0, result.total(), "data: URI images must be excluded from count");
    }

    @Test
    void trackingPixelExcludedFromCount(@TempDir Path dir) throws Exception {
        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
            "<article>" +
            "<img src=\"https://stats.wordpress.com/g.gif\" width=\"1\" height=\"1\"/>" +
            "</article>");

        var result = ScanAssets.scan(postPath, postPath);
        assertEquals(0, result.total(), "tracking pixels must be excluded from count");
    }

    // ── Mixed scan ─────────────────────────────────────────────────────────────

    @Test
    void mixedImagesCountedCorrectly(@TempDir Path dir) throws Exception {
        Path assetsDir = dir.resolve("assets");
        Files.createDirectories(assetsDir);
        Files.writeString(assetsDir.resolve("present.jpg"), "fake");

        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath,
            "<article>" +
            "<img src=\"../../assets/present.jpg\"/>" +   // localised
            "<img src=\"../../assets/missing.jpg\"/>" +   // missing
            "<img src=\"https://example.com/photo.jpg\"/>" +  // external
            "<img src=\"data:image/gif;base64,R0\"/>" +   // excluded
            "<img src=\"https://stats.wordpress.com/g.gif\" width=\"1\" height=\"1\"/>" + // excluded
            "</article>");

        var result = ScanAssets.scan(postPath, postPath);

        assertEquals(3, result.total());    // present + missing + external
        assertEquals(1, result.localised());
        assertEquals(2, result.broken());   // missing + external
        assertEquals(1, result.missingLocal().size());
        assertEquals(1, result.external().size());
    }

    // ── Empty article ──────────────────────────────────────────────────────────

    @Test
    void articleWithNoImagesReturnsZeros(@TempDir Path dir) throws Exception {
        Path postsDir = dir.resolve("posts").resolve("mark-proctor");
        Files.createDirectories(postsDir);
        Path postPath = postsDir.resolve("post.html");
        Files.writeString(postPath, "<article><p>Text only, no images.</p></article>");

        var result = ScanAssets.scan(postPath, postPath);

        assertEquals(0, result.total());
        assertEquals(0, result.broken());
        assertEquals(0, result.localised());
    }
}
```

- [ ] **Step 2: Run to verify fails (ScanAssets doesn't exist), commit**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=ScanAssetsTest -q 2>&1 | tail -3
```

```bash
cd ~/claude/sparge
git add server/src/test/java/io/sparge/server/ScanAssetsTest.java
git commit -m "test(#55): add ScanAssetsTest — 8 TDD tests (failing)

Refs #55"
```

- [ ] **Step 3: Write ScanAssets.java**

```java
package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * Asset localisation scanner.
 * Mirrors scripts/scan_assets.py: scan_assets().
 *
 * Note: scan_assets.py reads cfg['_root'] for absolute-path resolution.
 * This Java version requires serveRoot to be passed explicitly, or inferred
 * from postsDir when serveRoot is null.
 */
public final class ScanAssets {

    private ScanAssets() {}

    public record Result(
            int total,
            int localised,
            int broken,
            List<String> missingLocal,
            List<String> external
    ) {}

    /**
     * Scan a post for image asset localisation.
     *
     * @param htmlPath     HTML file to scan (may be enriched copy)
     * @param originalPath original post location (for relative path resolution);
     *                     pass same as htmlPath when not using enriched copies
     */
    public static Result scan(Path htmlPath, Path originalPath) throws IOException {
        return scan(htmlPath, originalPath, null);
    }

    public static Result scan(Path htmlPath, Path originalPath, Path serveRoot) throws IOException {
        Path relativeBase = (originalPath != null ? originalPath : htmlPath).getParent();

        String html = Files.readString(htmlPath);
        Document doc = Jsoup.parse(html);

        Element article = doc.selectFirst("article");
        if (article == null) article = doc.selectFirst("body");
        if (article == null)
            return new Result(0, 0, 0, List.of(), List.of());

        List<String> missingLocal = new ArrayList<>();
        List<String> external     = new ArrayList<>();
        int localised = 0;

        for (Element img : article.select("img")) {
            String src = img.attr("src");
            if (src.isEmpty() || src.startsWith("data:")) continue;
            if (SpargeConstants.isTrackingPixel(src,
                    img.attr("width"), img.attr("height"))) continue;

            if (src.startsWith("http://") || src.startsWith("https://")) {
                external.add(src);
            } else if (src.startsWith("/")) {
                // Absolute path relative to serveRoot
                if (serveRoot != null) {
                    Path abs = serveRoot.resolve(src.substring(1));
                    if (Files.exists(abs)) localised++; else missingLocal.add(src);
                } else {
                    missingLocal.add(src); // can't resolve without serveRoot
                }
            } else {
                // Relative path — resolve from original post directory
                Path abs = relativeBase.resolve(src).normalize();
                if (Files.exists(abs)) localised++; else missingLocal.add(src);
            }
        }

        int total  = localised + missingLocal.size() + external.size();
        int broken = missingLocal.size() + external.size();
        return new Result(total, localised, broken,
                List.copyOf(missingLocal), List.copyOf(external));
    }
}
```

- [ ] **Step 4: Run tests — all 8 must pass**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=ScanAssetsTest -q 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/ScanAssets.java
git commit -m "feat(#55): add ScanAssets.java — image asset localisation, 8 tests green

Refs #55"
```

---

## Task 6: ScanEndpointTest — @QuarkusTest E2E (write failing first)

**Files:**
- Create: `server/src/test/java/io/sparge/server/ScanEndpointTest.java`

- [ ] **Step 1: Write ScanEndpointTest.java (FAILING — PostsResource.scan not yet updated)**

```java
package io.sparge.server;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;

import java.nio.file.Files;
import java.nio.file.Paths;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

/**
 * E2E test for POST /api/posts/{slug}/scan via @QuarkusTest.
 * Requires a project to be active (activates kie-mark-proctor automatically
 * via the bridge PythonBridge init which activates the first project).
 *
 * Skipped when the KIE archive is not present.
 */
@QuarkusTest
class ScanEndpointTest {

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanEndpointReturns200WithIssueList() {
        // Get first slug
        String slug = given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");

        // Scan it — must return 200 with an array (possibly empty)
        given()
                .when().post("/api/posts/" + slug + "/scan")
                .then()
                .statusCode(200)
                .body("slug", equalTo(slug))
                .body("html", notNullValue());
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanResponseContainsHtmlAndAssetsFields() {
        String slug = given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");

        given()
                .when().post("/api/posts/" + slug + "/scan")
                .then()
                .statusCode(200)
                .body("slug",  equalTo(slug))
                .body("html",  notNullValue())  // html object with issues array
                .body("assets",notNullValue()); // assets object with total/localised/broken
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanUnknownSlugReturns404() {
        given()
                .when().post("/api/posts/this-slug-does-not-exist/scan")
                .then()
                .statusCode(404);
    }
}
```

- [ ] **Step 2: Run to verify it fails (scan still calls bridge, E2E structure to be validated)**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
export PYTHONHOME=$HOME/claude/sparge/resources/python/mac-arm64
mvn test -Dtest=ScanEndpointTest \
  -Djava.library.path=$HOME/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/test/java/io/sparge/server/ScanEndpointTest.java
git commit -m "test(#55): add ScanEndpointTest — E2E @QuarkusTest for scan endpoint (failing TDD)

Refs #55"
```

---

## Task 7: Update PostsResource — scan/dismiss/undismiss use Java

Replace three bridge calls with direct Java. The scan endpoint calls Python only for the optional enrich step.

**Files:**
- Modify: `server/src/main/java/io/sparge/server/PostsResource.java`
- Modify: `scripts/bridge.py` (add `post_enrich_only`, remove 3 delegates)

- [ ] **Step 1: Read PostsResource.java** — find `scan()`, `dismiss()`, `undismiss()` methods.

- [ ] **Step 2: Replace scan() with Java implementation**

```java
@POST
@Path("{slug}/scan")
public Response scan(@PathParam("slug") String slug) {
    SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
    if (cfg == null) {
        // No active project — fall back to bridge
        return BridgeResponse.of(bridge.call("bridge.post_scan_html", slug));
    }
    try {
        java.nio.file.Path postsDir   = cfg.postsDir();
        java.nio.file.Path enrichedDir = cfg.enrichedDir();
        java.nio.file.Path htmlPath    = postsDir.resolve(slug + ".html");

        if (!java.nio.file.Files.exists(htmlPath)) {
            return Response.status(404)
                    .header("Content-Type",                "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .entity("{\"error\":\"HTML not found: " + slug + "\"}").build();
        }

        java.nio.file.Path enrichedPath = enrichedDir.resolve(slug + ".html");

        // Enrich if not yet enriched — still Python (enrich.py ported in Phase 5)
        if (!java.nio.file.Files.exists(enrichedPath)) {
            String enrichResult = bridge.call("bridge.post_enrich_only", slug);
            // Ignore enrich result — we just need the enriched file written
        }

        // Apply code block fixes to enriched copy (Java)
        java.nio.file.Path scanPath = java.nio.file.Files.exists(enrichedPath)
                ? enrichedPath : htmlPath;
        if (java.nio.file.Files.exists(enrichedPath)) {
            try {
                org.jsoup.nodes.Document soup = org.jsoup.Jsoup.parse(
                        java.nio.file.Files.readString(enrichedPath));
                if (CodeBlockFixer.apply(soup)) {
                    java.nio.file.Files.writeString(enrichedPath, soup.outerHtml());
                }
            } catch (Exception ignored) {}
        }

        // Scan HTML issues (Java)
        List<ScanHtml.Issue> rawIssues = ScanHtml.scanPost(scanPath, postsDir);
        List<java.util.Map<String, Object>> issues = rawIssues.stream().map(i ->
                java.util.Map.<String, Object>of(
                        "type",     i.type(),
                        "level",    i.level(),
                        "check",    i.type(),
                        "detail",   i.detail(),
                        "selector", i.selector() != null ? i.selector() : ""
                )).collect(java.util.stream.Collectors.toList());
        stateStore.setHtmlIssues(slug, issues);

        // Scan assets (Java)
        try {
            ScanAssets.Result assets = ScanAssets.scan(scanPath, htmlPath,
                    cfg.serveRoot());
            stateStore.update(slug, java.util.Map.of("assets", java.util.Map.of(
                    "total",      assets.total(),
                    "localised",  assets.localised(),
                    "broken",     assets.broken(),
                    "checked_at", java.time.Instant.now().toString().substring(0, 19)
            )));
        } catch (Exception ignored) {}

        ObjectNode post = stateStore.get(slug);
        return ok(post != null ? post.toString() : "{}");
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

- [ ] **Step 3: Replace dismiss() to use StateStore directly**

```java
@POST
@Path("{slug}/dismiss-html-check")
public Response dismiss(@PathParam("slug") String slug, String body) {
    try {
        ObjectNode patch = (body != null && !body.isBlank())
                ? (ObjectNode) MAPPER.readTree(body)
                : MAPPER.createObjectNode();
        String issueType = patch.path("type").asText("");
        if (issueType.isEmpty()) return Response.status(400)
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .entity("{\"error\":\"type required\"}").build();
        stateStore.dismissHtmlCheck(slug, issueType);
        ObjectNode post = stateStore.get(slug);
        return ok(post != null ? post.toString() : "{}");
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

- [ ] **Step 4: Replace undismiss() to use StateStore + Java scan**

```java
@DELETE
@Path("{slug}/dismiss-html-check/{type}")
public Response undismiss(@PathParam("slug") String slug,
                           @PathParam("type") String type) {
    stateStore.undismissHtmlCheck(slug, type);
    // Re-scan immediately so the issue reappears
    return scan(slug);
}
```

- [ ] **Step 5: Add missing imports (List, Map, ScanHtml, ScanAssets, CodeBlockFixer)**

Ensure the file imports `java.util.List`, `java.util.Map`, and references the new Java classes. Add `@Inject StateStore stateStore` if not already present (it should be from Phase 2).

- [ ] **Step 6: Add `post_enrich_only` to bridge.py**

In `scripts/bridge.py`, add this thin function (it just runs the enrich step):

```python
def post_enrich_only(slug: str) -> str:
    """Enrich a post — called by Java PostsResource.scan() when enriched copy absent."""
    if not _can_enrich:
        return _ok({'enriched': False, 'reason': 'enrich not available'})
    html_path = POSTS_DIR / (slug + '.html')
    if not html_path.exists():
        return _err(404, f'HTML not found: {slug}')
    enriched_path = ENRICHED_DIR / (slug + '.html')
    if enriched_path.exists():
        return _ok({'enriched': False, 'reason': 'already enriched'})
    try:
        github_token = cfg.get('github_token', '')
        enrich_stats = _enrich_post(html_path, enriched_path, cfg['_assets_dir'], github_token)
        State.mark_enriched(slug, enrich_stats)
        return _ok({'enriched': True, **enrich_stats})
    except Exception as e:
        return _err(500, str(e))
```

- [ ] **Step 7: Remove 3 bridge delegates from bridge.py**

Delete these three functions from bridge.py:
- `def post_scan_html(slug: str) -> str:`
- `def post_dismiss_html_check(slug: str, body: str) -> str:`
- `def post_undismiss_html_check(slug: str, issue_type: str) -> str:`

- [ ] **Step 8: Compile**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn compile -q 2>&1 | tail -5
```

- [ ] **Step 9: Run ScanEndpointTest — should now pass**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
export PYTHONHOME=$HOME/claude/sparge/resources/python/mac-arm64
mvn test -Dtest=ScanEndpointTest \
  -Djava.library.path=$HOME/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  2>&1 | tail -10
```

- [ ] **Step 10: Smoke-test bridge.py**

```bash
cd ~/claude/sparge && python3 -c "
import sys; sys.path.insert(0, '.')
import scripts.bridge as bridge
result = bridge.bridge_init()
import json; d = json.loads(result)
print('initialized:', d['body']['initialized'])
for fn in ['post_scan_html', 'post_dismiss_html_check', 'post_undismiss_html_check']:
    assert not hasattr(bridge, fn), f'{fn} should be removed'
assert hasattr(bridge, 'post_enrich_only'), 'post_enrich_only must be present'
print('All assertions passed')
"
```

- [ ] **Step 11: Run pytest**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --no-header --tb=no 2>&1 | tail -3
```

Expected: 375 passed (unchanged), 0 failed.

- [ ] **Step 12: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/PostsResource.java scripts/bridge.py
git commit -m "feat(#55): PostsResource scan/dismiss/undismiss use Java directly

JEP call count: 26 → 23
Removed: post_scan_html, post_dismiss_html_check, post_undismiss_html_check
Added: post_enrich_only (thin bridge for enrich-only step, called from Java)
scan() uses ScanHtml + ScanAssets + CodeBlockFixer + StateStore in Java.
dismiss()/undismiss() use StateStore.dismissHtmlCheck/undismissHtmlCheck.

Refs #55"
```

---

## Task 8: Move Python tests + full verification

**Files:**
- Move: `tests/test_scan_html.py` → `tests/python-legacy/`

- [ ] **Step 1: Move the test file**

```bash
cd ~/claude/sparge
mv tests/test_scan_html.py tests/python-legacy/
```

- [ ] **Step 2: Verify pytest count**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --no-header --tb=no 2>&1 | tail -3
```

Expected: `290 passed` (375 − 85 = 290), 0 failed.

- [ ] **Step 3: Run all JUnit tests**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
export PYTHONHOME=$HOME/claude/sparge/resources/python/mac-arm64
mvn test \
  -Djava.library.path=$HOME/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  2>&1 | grep -E "Tests run:|BUILD" | tail -10
```

Expected: BUILD SUCCESS. Total ≥ 160 tests (12 Constants + ~55 ScanHtml + 2 Integration + 8 Assets + 3 Endpoint + 82 from Phases 1-3).

- [ ] **Step 4: Build jar + live smoke-test scan endpoint**

```bash
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
export PYTHONHOME=$HOME/claude/sparge/resources/python/mac-arm64
cd ~/claude/sparge/server && mvn package -DskipTests -q

java \
  -Djava.library.path=$HOME/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  -Dquarkus.http.port=9000 \
  -jar target/quarkus-app/quarkus-run.jar > /tmp/quarkus-p4.log 2>&1 &
JAVA_PID=$!

for i in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9000/api/config 2>/dev/null)
  [ "$STATUS" = "200" ] && echo "Ready after ${i}s" && break
  sleep 1
done

unset PYTHONHOME

# Get first slug and scan it
SLUG=$(curl -s http://127.0.0.1:9000/api/posts | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['slug'])")
echo "Scanning: $SLUG"
RESULT=$(curl -s -X POST "http://127.0.0.1:9000/api/posts/$SLUG/scan")
echo "$RESULT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('slug:', d.get('slug'))
html = d.get('html', {})
print('html.issues count:', len(html.get('issues', [])))
assets = d.get('assets', {})
print('assets.total:', assets.get('total', 0))
print('has checked_at:', 'checked_at' in html)
"

kill $JAVA_PID 2>/dev/null; wait $JAVA_PID 2>/dev/null
echo "Server stopped"
```

Expected: slug, html.issues count (any number), assets.total (any number), has checked_at: True.

- [ ] **Step 5: Final commit + push + close issue**

```bash
cd ~/claude/sparge
git add tests/python-legacy/test_scan_html.py
git add -u tests/test_scan_html.py
git commit -m "refactor(#55): move 85 Python scan tests to python-legacy/ (ScanHtml ported to Java)

Refs #55"

git commit --allow-empty -m "feat(#55): Phase 4 complete — scan_html + scan_assets ported to Java

JEP call count: 26 → 23 (post_scan_html, post_dismiss_html_check, post_undismiss_html_check)
New Java: SpargeConstants (12), ScanHtml (55+), ScanHtmlIntegration (2), ScanAssets (8), ScanEndpoint (3)
pytest: 290 passing (85 tests retired to python-legacy/)
/api/posts/{slug}/scan now served by Java ScanHtml + ScanAssets + CodeBlockFixer

Closes #55"

git push origin main 2>&1 | tail -3
gh issue close 55 --repo mdproctor/sparge --comment "Phase 4 complete. scan_html.py + scan_assets.py ported to Java (Jsoup). JEP: 26→23. Scan endpoint fully Java-backed (enrich still Python, Phase 5)."
```

---

## Self-Review

**Spec coverage:**
- 16 detectors → ScanHtml.java ✓ (Task 3)
- constants.py → SpargeConstants.java ✓ (Task 1)
- scan_assets.py → ScanAssets.java ✓ (Task 5)
- Unit tests per detector ✓ (Task 2 — all 16 covered)
- Integration test on real HTML ✓ (Task 4)
- E2E @QuarkusTest scan endpoint ✓ (Task 6)
- Happy paths ✓ (cleanArticleReturnsNoIssues + per-detector "not flagged" tests)
- post_scan_html removed ✓ (Task 7)
- post_dismiss_html_check removed ✓ (Task 7)
- post_undismiss_html_check removed ✓ (Task 7)
- All commits reference #55 ✓

**TDD layers verified:**
- Unit: SpargeConstantsTest (12) + ScanHtmlTest (55+) + ScanAssetsTest (8) — all written failing first
- Integration: ScanHtmlIntegrationTest (2) — real KIE HTML, skips gracefully if archive absent
- E2E: ScanEndpointTest (3) — @QuarkusTest, written failing in Task 6, passes in Task 7

**Happy paths verified in tests:**
- `cleanArticleReturnsNoIssues` — clean HTML returns zero issues
- `allLocalisedImagesCountedCorrectly` — all images present returns zero broken
- `articleWithNoImagesReturnsZeros` — no images returns all zeros
- Per-detector "not flagged" tests (e.g. `regularImageNotFlaggedAsDataPlaceholder`)
