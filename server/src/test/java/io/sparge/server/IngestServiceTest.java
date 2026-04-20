package io.sparge.server;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class IngestServiceTest {

    // ── URL normalisation ─────────────────────────────────────────────────────

    @Test
    void normaliseUrl_stripsTrailingSlash() {
        assertEquals("https://example.com", IngestService.normaliseUrl("https://example.com/"));
    }

    @Test
    void normaliseUrl_upgradesHttp() {
        assertEquals("https://example.com", IngestService.normaliseUrl("http://example.com"));
    }

    @Test
    void normaliseUrl_httpsWithPathNoTrailingSlash() {
        assertEquals("https://example.com/blog",
                IngestService.normaliseUrl("https://example.com/blog/"));
    }

    // ── Slug generation ───────────────────────────────────────────────────────

    @Test
    void makeSlug_withDateAndUrl() {
        String slug = IngestService.makeSlug("2024-03-15", "https://blog.example.com/my-great-post/");
        assertTrue(slug.startsWith("2024-03-15-"), "Should start with date");
        assertTrue(slug.contains("my-great-post"), "Should contain URL segment");
    }

    @Test
    void makeSlug_sanitisesSpecialChars() {
        String slug = IngestService.makeSlug("2024-01-01", "https://blog.com/post?id=123&foo=bar");
        assertFalse(slug.contains("?"));
        assertFalse(slug.contains("="));
        assertFalse(slug.contains("&"));
    }

    @Test
    void makeSlug_emptyDate_usesUrlOnly() {
        String slug = IngestService.makeSlug("", "https://blog.com/my-post/");
        assertFalse(slug.isEmpty());
        assertTrue(slug.contains("my-post"));
    }

    // ── isPostUrl ─────────────────────────────────────────────────────────────

    @Test
    void isPostUrl_dateSegment_true() {
        assertTrue(IngestService.isPostUrl("https://blog.com/2024/03/my-post/"));
    }

    @Test
    void isPostUrl_categoryPath_false() {
        assertFalse(IngestService.isPostUrl("https://blog.com/category/drools/"));
    }

    @Test
    void isPostUrl_wpAdmin_false() {
        assertFalse(IngestService.isPostUrl("https://blog.com/wp-admin/edit.php"));
    }

    @Test
    void isPostUrl_nonHttp_false() {
        assertFalse(IngestService.isPostUrl("ftp://blog.com/post"));
    }

    @Test
    void isPostUrl_pathTraversal_false() {
        assertFalse(IngestService.isPostUrl("https://blog.com/../etc/passwd"));
    }

    // ── Sitemap XML parsing ───────────────────────────────────────────────────

    @Test
    void parseSitemapUrls_extractsPostLocs() {
        String xml = "<?xml version=\"1.0\"?><urlset>"
            + "<url><loc>https://blog.com/2024/post-one/</loc></url>"
            + "<url><loc>https://blog.com/category/drools/</loc></url>"
            + "<url><loc>https://blog.com/2023/post-two/</loc></url>"
            + "</urlset>";
        List<String> urls = IngestService.parseSitemapUrls(xml, "https://blog.com");
        assertEquals(2, urls.size(), "Should filter out non-post URLs");
        assertTrue(urls.contains("https://blog.com/2024/post-one/"));
        assertTrue(urls.contains("https://blog.com/2023/post-two/"));
    }

    @Test
    void parseSitemapIndexUrls_extractsChildUrls() {
        String xml = "<?xml version=\"1.0\"?><sitemapindex>"
            + "<sitemap><loc>https://blog.com/post-sitemap.xml</loc></sitemap>"
            + "<sitemap><loc>https://blog.com/page-sitemap.xml</loc></sitemap>"
            + "</sitemapindex>";
        List<String> childUrls = IngestService.parseSitemapIndexUrls(xml);
        assertEquals(2, childUrls.size());
        assertTrue(childUrls.contains("https://blog.com/post-sitemap.xml"));
    }

    @Test
    void parseSitemapIndexUrls_regularSitemap_returnsEmpty() {
        String xml = "<?xml version=\"1.0\"?><urlset>"
            + "<url><loc>https://blog.com/post/</loc></url>"
            + "</urlset>";
        List<String> childUrls = IngestService.parseSitemapIndexUrls(xml);
        assertTrue(childUrls.isEmpty(), "Regular sitemap has no <sitemap> elements");
    }

    // ── RSS/Atom feed parsing ─────────────────────────────────────────────────

    @Test
    void parseFeedLinks_rssItems() {
        String rss = "<?xml version=\"1.0\"?><rss version=\"2.0\"><channel>"
            + "<item><link>https://blog.com/2024/post-a/</link></item>"
            + "<item><link>https://blog.com/2023/post-b/</link></item>"
            + "</channel></rss>";
        List<String> links = IngestService.parseFeedLinks(rss);
        assertEquals(2, links.size());
        assertTrue(links.contains("https://blog.com/2024/post-a/"));
    }

    @Test
    void parseFeedLinks_atomEntries() {
        String atom = "<?xml version=\"1.0\"?><feed xmlns=\"http://www.w3.org/2005/Atom\">"
            + "<entry><link href=\"https://blog.com/2024/post-c/\" rel=\"alternate\"/></entry>"
            + "<entry><link href=\"https://blog.com/2023/post-d/\"/></entry>"
            + "</feed>";
        List<String> links = IngestService.parseFeedLinks(atom);
        assertEquals(2, links.size());
    }

    // ── WordPress REST ────────────────────────────────────────────────────────

    @Test
    void parseWpRestLinks_extractsLinkField() {
        String json = "[{\"link\":\"https://blog.com/2024/post-one/\"},"
            + "{\"link\":\"https://blog.com/2023/post-two/\"}]";
        List<String> urls = IngestService.parseWpRestLinks(json);
        assertEquals(2, urls.size());
        assertTrue(urls.contains("https://blog.com/2024/post-one/"));
    }

    // ── Date normalisation ────────────────────────────────────────────────────

    @Test
    void normaliseDate_iso8601WithTime() {
        assertEquals("2024-03-15", IngestService.normaliseDate("2024-03-15T10:00:00+00:00"));
    }

    @Test
    void normaliseDate_dateOnly_unchanged() {
        assertEquals("2024-03-15", IngestService.normaliseDate("2024-03-15"));
    }

    @Test
    void normaliseDate_empty_returnsEmpty() {
        assertEquals("", IngestService.normaliseDate(""));
    }

    // ── HTML metadata extraction ───────────────────────────────────────────────

    @Test
    void extractMetadata_ogTitle_preferred() {
        String html = "<html><head>"
            + "<meta property=\"og:title\" content=\"My OG Title\"/>"
            + "<title>Fallback</title>"
            + "</head><body></body></html>";
        Map<String, Object> meta = IngestService.extractMetadata(html, "https://example.com/post/");
        assertEquals("My OG Title", meta.get("title"));
    }

    @Test
    void extractMetadata_jsonLd_extractsTitleDateAuthor() {
        String html = "<html><head>"
            + "<script type=\"application/ld+json\">"
            + "{\"@type\":\"BlogPosting\",\"headline\":\"LD Title\","
            + "\"datePublished\":\"2024-03-15\",\"author\":{\"name\":\"Mark\"}}"
            + "</script>"
            + "</head><body></body></html>";
        Map<String, Object> meta = IngestService.extractMetadata(html, "https://example.com/post/");
        assertEquals("LD Title", meta.get("title"));
        assertEquals("2024-03-15", meta.get("date"));
        assertEquals("Mark", meta.get("author"));
    }

    @Test
    void extractMetadata_titleFallback() {
        String html = "<html><head><title>Page Title</title></head><body></body></html>";
        Map<String, Object> meta = IngestService.extractMetadata(html, "https://example.com/post/");
        assertFalse(((String) meta.get("title")).isEmpty());
    }

    // ── Article extraction ────────────────────────────────────────────────────

    @Test
    void extractArticleHtml_usesArticleElement() {
        String html = "<html><body>"
            + "<nav>Navigation</nav>"
            + "<article><p>The real content.</p></article>"
            + "<footer>Footer</footer>"
            + "</body></html>";
        String article = IngestService.extractArticleHtml(html, "https://example.com/");
        assertTrue(article.contains("The real content."));
        assertFalse(article.contains("Navigation"));
        assertFalse(article.contains("Footer"));
    }

    @Test
    void extractArticleHtml_stripsScriptsAndStyles() {
        String html = "<html><body><article>"
            + "<script>alert('xss')</script>"
            + "<style>.foo{color:red}</style>"
            + "<p>Clean content here.</p>"
            + "</article></body></html>";
        String article = IngestService.extractArticleHtml(html, "https://example.com/");
        assertFalse(article.contains("alert"));
        assertFalse(article.contains("color:red"));
        assertTrue(article.contains("Clean content"));
    }

    @Test
    void extractArticleHtml_stripsEventHandlers() {
        String html = "<html><body><article>"
            + "<a onclick=\"evil()\" href=\"https://safe.com\">Link</a>"
            + "<p>Content.</p>"
            + "</article></body></html>";
        String article = IngestService.extractArticleHtml(html, "https://example.com/");
        assertFalse(article.contains("onclick"), "onclick should be stripped");
        assertTrue(article.contains("https://safe.com"), "href should be preserved");
    }
}
