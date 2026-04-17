package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class EnricherTest {

    static Element article(String html) {
        Document doc = Jsoup.parse("<article>" + html + "</article>");
        return doc.selectFirst("article");
    }

    // ── MockEnricher — overrides HTTP hooks for testing ───────────────────────

    static class MockEnricher extends Enricher {
        final Map<String, byte[]> urlBytes = new HashMap<>();
        final Map<String, String> urlJson  = new HashMap<>();
        int fetchCallCount = 0;

        void mockBytes(String url, byte[] bytes) { urlBytes.put(url, bytes); }
        void mockJson(String url, String json)   { urlJson.put(url, json); }

        @Override byte[] fetchUrl(String url)                { fetchCallCount++; return urlBytes.get(url); }
        @Override String fetchJson(String url, String token) { return urlJson.get(url); }
    }

    // ── normaliseBrToNewlines ─────────────────────────────────────────────────

    @Test
    void brInsidePreReplacedWithNewline() {
        Element a = article("<pre>line1<br/>line2<br/>line3</pre>");
        int count = Enricher.normaliseBrToNewlines(a);
        assertEquals(1, count);
        assertFalse(a.selectFirst("pre").html().contains("<br"), "br tags replaced");
        assertTrue(a.selectFirst("pre").html().contains("line1"), "content preserved");
    }

    @Test
    void brOutsidePreNotCounted() {
        Element a = article("<p>para<br/>line</p>");
        assertEquals(0, Enricher.normaliseBrToNewlines(a));
    }

    @Test
    void preWithoutBrNotCounted() {
        assertEquals(0, Enricher.normaliseBrToNewlines(article("<pre>no brs here</pre>")));
    }

    // ── normaliseCodeClasses ──────────────────────────────────────────────────

    @Test
    void brushJavaConvertedToLanguageJava() {
        Element a = article("<pre class=\"brush:java\"><code>public class Foo {}</code></pre>");
        int count = Enricher.normaliseCodeClasses(a);
        assertEquals(1, count);
        assertTrue(a.selectFirst("pre").hasClass("language-java"));
        assertFalse(a.selectFirst("pre").classNames().stream().anyMatch(c -> c.startsWith("brush")));
    }

    @Test
    void brushJscriptConvertedToJavascript() {
        Element a = article("<pre class=\"brush:jscript\"></pre>");
        Enricher.normaliseCodeClasses(a);
        assertTrue(a.selectFirst("pre").hasClass("language-javascript"));
    }

    @Test
    void brushShConvertedToBash() {
        Element a = article("<pre class=\"brush:sh\"></pre>");
        Enricher.normaliseCodeClasses(a);
        assertTrue(a.selectFirst("pre").hasClass("language-bash"));
    }

    @Test
    void brushCppConvertedToCpp() {
        Element a = article("<pre class=\"brush:cplusplus\"></pre>");
        Enricher.normaliseCodeClasses(a);
        assertTrue(a.selectFirst("pre").hasClass("language-cpp"));
    }

    @Test
    void brushClassPropagatedToChildCode() {
        Element a = article("<pre class=\"brush:java\"><code>foo</code></pre>");
        Enricher.normaliseCodeClasses(a);
        assertTrue(a.selectFirst("code").hasClass("language-java"));
    }

    @Test
    void preWithoutBrushClassNotTouched() {
        Element a = article("<pre class=\"someclass\"><code>text</code></pre>");
        assertEquals(0, Enricher.normaliseCodeClasses(a));
        assertTrue(a.selectFirst("pre").hasClass("someclass"));
    }

    // ── detectCodeLanguages ───────────────────────────────────────────────────

    @Test
    void javaPublicClassDetected() {
        Element a = article("<pre><code>public class Foo { }</code></pre>");
        assertEquals(1, Enricher.detectCodeLanguages(a));
        assertTrue(a.selectFirst("code").hasClass("language-java"));
    }

    @Test
    void drlRuleDetected() {
        Element a = article("<pre><code>rule \"test\" when Foo() then end</code></pre>");
        assertEquals(1, Enricher.detectCodeLanguages(a));
        assertTrue(a.selectFirst("code").hasClass("language-drl"));
    }

    @Test
    void xmlDeclarationDetected() {
        Element a = article("<pre><code>&lt;?xml version=\"1.0\"?&gt;</code></pre>");
        assertEquals(1, Enricher.detectCodeLanguages(a));
        assertTrue(a.selectFirst("code").hasClass("language-xml"));
    }

    @Test
    void alreadyLabelledCodeNotRelabelled() {
        Element a = article("<pre><code class=\"language-python\">public class Foo {}</code></pre>");
        assertEquals(0, Enricher.detectCodeLanguages(a));
        assertFalse(a.selectFirst("code").hasClass("language-java"), "python label not replaced by java");
    }

    @Test
    void preWithoutCodeElementSkipped() {
        assertEquals(0, Enricher.detectCodeLanguages(article("<pre>no code element</pre>")));
    }

    @Test
    void unrecognisedCodeHasNoLangAdded() {
        Element a = article("<pre><code>¯\\_(ツ)_/¯</code></pre>");
        assertEquals(0, Enricher.detectCodeLanguages(a));
        assertTrue(a.selectFirst("code").classNames().isEmpty());
    }

    // ── replaceEmbedFallbacks ─────────────────────────────────────────────────

    @Test
    void iframeWrappedInLiveEmbedFigure() {
        Element a = article("<iframe src=\"https://example.com/embed\"></iframe>");
        int count = Enricher.replaceEmbedFallbacks(a);
        assertEquals(1, count);
        assertNull(a.selectFirst("iframe"), "iframe replaced");
        Element fig = a.selectFirst("figure.live-embed");
        assertNotNull(fig, "live-embed figure present");
        assertTrue(fig.text().contains("example.com"), "link references original source");
    }

    @Test
    void objectTagWrapped() {
        Element a = article("<object data=\"https://example.com/thing\"></object>");
        assertEquals(1, Enricher.replaceEmbedFallbacks(a));
        assertNotNull(a.selectFirst("figure.live-embed"));
    }

    @Test
    void iframeWithNoSrcShowsUnknownSource() {
        Element a = article("<iframe></iframe>");
        Enricher.replaceEmbedFallbacks(a);
        assertTrue(a.selectFirst("figure.live-embed").text().contains("unknown source"));
    }

    @Test
    void noEmbedsReturnsZero() {
        assertEquals(0, Enricher.replaceEmbedFallbacks(article("<p>Clean content</p>")));
    }

    // ── replaceYoutubeEmbeds ──────────────────────────────────────────────────

    @Test
    void youtubeEmbedIframeReplacedWithFigure(@TempDir Path tempDir) throws Exception {
        MockEnricher e = new MockEnricher();
        e.mockBytes("https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
                    new byte[]{1, 2, 3});
        Path assets = Files.createDirectories(tempDir.resolve("assets"));

        Element a = article("<iframe src=\"https://www.youtube.com/embed/dQw4w9WgXcQ\"></iframe>");
        int count = e.replaceYoutubeEmbeds(a, assets);

        assertEquals(1, count);
        assertNull(a.selectFirst("iframe"), "iframe replaced");
        Element fig = a.selectFirst("figure.video-embed");
        assertNotNull(fig);
        assertEquals("https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                     fig.selectFirst("a").attr("href"));
        assertEquals("yt_dQw4w9WgXcQ.jpg", fig.selectFirst("img").attr("src"));
        assertTrue(Files.exists(assets.resolve("yt_dQw4w9WgXcQ.jpg")), "thumbnail file saved");
    }

    @Test
    void youtubeDownloadFailureResultsInEmptySrc(@TempDir Path tempDir) throws Exception {
        MockEnricher e = new MockEnricher(); // fetchUrl returns null
        Path assets = Files.createDirectories(tempDir.resolve("assets"));

        Element a = article("<iframe src=\"https://www.youtube.com/embed/abc123\"></iframe>");
        e.replaceYoutubeEmbeds(a, assets);

        Element img = a.selectFirst("img");
        assertNotNull(img);
        assertEquals("", img.attr("src"), "empty src when thumbnail download fails");
    }

    @Test
    void existingThumbnailNotReDownloaded(@TempDir Path tempDir) throws Exception {
        MockEnricher e = new MockEnricher();
        Path assets = Files.createDirectories(tempDir.resolve("assets"));
        Files.write(assets.resolve("yt_existing.jpg"), new byte[]{9, 8, 7});

        Element a = article("<iframe src=\"https://www.youtube.com/embed/existing\"></iframe>");
        int count = e.replaceYoutubeEmbeds(a, assets);

        assertEquals(1, count);
        assertEquals(0, e.fetchCallCount, "should not re-download existing thumbnail");
        assertEquals("yt_existing.jpg", a.selectFirst("img").attr("src"));
    }

    @Test
    void nonYoutubeIframeNotReplaced(@TempDir Path tempDir) throws Exception {
        MockEnricher e = new MockEnricher();
        Element a = article("<iframe src=\"https://example.com/embed\"></iframe>");
        assertEquals(0, e.replaceYoutubeEmbeds(a, tempDir));
        assertNotNull(a.selectFirst("iframe"), "non-youtube iframe untouched");
    }

    @Test
    void youtuBeShortLinkParsed(@TempDir Path tempDir) throws Exception {
        MockEnricher e = new MockEnricher();
        e.mockBytes("https://img.youtube.com/vi/abc/maxresdefault.jpg", new byte[]{1});
        Path assets = Files.createDirectories(tempDir.resolve("assets"));
        Element a = article("<iframe src=\"https://youtu.be/abc\"></iframe>");
        assertEquals(1, e.replaceYoutubeEmbeds(a, assets));
        assertEquals("https://www.youtube.com/watch?v=abc", a.selectFirst("a").attr("href"));
    }
}
