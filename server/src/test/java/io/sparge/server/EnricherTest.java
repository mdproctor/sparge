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
}
