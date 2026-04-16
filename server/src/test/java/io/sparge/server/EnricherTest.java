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
}
