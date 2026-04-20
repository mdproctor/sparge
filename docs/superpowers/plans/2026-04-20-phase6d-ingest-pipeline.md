# Phase 6d: Ingest Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove 7 JEP bridge calls by porting the ingest pipeline (platform detection, URL discovery, post extraction, async ingestion) to native Java using `java.net.http.HttpClient` and jsoup.

**Architecture:** Two new classes: `IngestJobState` (thread-safe job state POJO) and `IngestService` (@ApplicationScoped CDI bean owning the HttpClient, ExecutorService, and all ingest logic). jsoup (already in pom.xml v1.18.3) handles HTML/XML parsing throughout. `IngestResource` and `ProjectsResource.projectIngestRun()` are updated to delegate to `IngestService` instead of JEP.

**Tech Stack:** Quarkus 3.34, java.net.http.HttpClient (JDK 11+), jsoup 1.18.3 (existing), Jackson, ExecutorService (single-thread daemon), JUnit 5, RestAssured, @QuarkusTest

---

## File Map

| File | Change |
|---|---|
| `server/src/main/java/io/sparge/server/IngestJobState.java` | **NEW** — thread-safe job state POJO |
| `server/src/main/java/io/sparge/server/IngestService.java` | **NEW** — @ApplicationScoped: detect, discover, preview, ingest, cancel, status |
| `server/src/main/java/io/sparge/server/IngestResource.java` | Replace all JEP calls with IngestService delegation |
| `server/src/main/java/io/sparge/server/ProjectsResource.java` | Replace `projectIngestRun` JEP call |
| `server/src/test/java/io/sparge/server/IngestJobStateTest.java` | **NEW** — unit tests, thread safety |
| `server/src/test/java/io/sparge/server/IngestServiceTest.java` | **NEW** — unit tests for parsing logic + guarded integration tests |
| `server/src/test/java/io/sparge/server/IngestResourceTest.java` | **NEW** — @QuarkusTest E2E for status/cancel/detect endpoints |

---

## Background: Python → Java mapping

| Python | Java |
|---|---|
| `requests.Session` | `java.net.http.HttpClient` (static, shared) |
| `BeautifulSoup(html, 'html.parser')` | `Jsoup.parse(html, baseUrl)` |
| `BeautifulSoup(xml, 'xml')` | `Jsoup.parse(xml, "", Parser.xmlParser())` |
| `soup.find('meta', attrs={...})` | `doc.selectFirst("meta[name=...]")` |
| `soup.select(selector)` | `doc.select(selector)` |
| `tag.decompose()` | `element.remove()` |
| `tag.get_text(strip=True)` | `element.text()` |
| `tag.get('href', '')` | `element.attr("href")` |
| `threading.Thread(daemon=True)` | `Executors.newSingleThreadExecutor()` (daemon thread) |
| `threading.Lock()` | `synchronized` methods on IngestJobState |
| `urljoin(base, rel)` | `URI.create(base).resolve(rel).toString()` |

---

### Task 1: IngestJobState + Status/Cancel (Trivial)

**Files:**
- Create: `server/src/main/java/io/sparge/server/IngestJobState.java`
- Create: `server/src/test/java/io/sparge/server/IngestJobStateTest.java`

- [ ] **Step 1: Write IngestJobStateTest.java first**

```java
package io.sparge.server;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import static org.junit.jupiter.api.Assertions.*;

class IngestJobStateTest {

    @Test
    void initialState_notRunning() {
        IngestJobState s = new IngestJobState();
        Map<String, Object> snap = s.snapshot();
        assertFalse((Boolean) snap.get("running"));
        assertEquals(0, snap.get("done"));
        assertEquals(0, snap.get("total"));
        assertEquals("", snap.get("current"));
        assertFalse((Boolean) snap.get("cancelled"));
        assertTrue(((List<?>) snap.get("errors")).isEmpty());
        assertTrue(((List<?>) snap.get("log")).isEmpty());
    }

    @Test
    void reset_setsRunningAndTotal() {
        IngestJobState s = new IngestJobState();
        s.reset(42);
        Map<String, Object> snap = s.snapshot();
        assertTrue((Boolean) snap.get("running"));
        assertEquals(42, snap.get("total"));
        assertEquals(0, snap.get("done"));
    }

    @Test
    void cancel_setsCancelledFlag() {
        IngestJobState s = new IngestJobState();
        s.reset(10);
        assertFalse(s.isCancelled());
        s.cancel();
        assertTrue(s.isCancelled());
        assertTrue((Boolean) s.snapshot().get("cancelled"));
    }

    @Test
    void finish_setsRunningFalse() {
        IngestJobState s = new IngestJobState();
        s.reset(5);
        s.finish();
        assertFalse((Boolean) s.snapshot().get("running"));
    }

    @Test
    void appendLog_recordsEntries() {
        IngestJobState s = new IngestJobState();
        s.reset(2);
        s.appendLog(Map.of("url", "https://a.com", "slug", "a", "ok", true));
        s.appendLog(Map.of("url", "https://b.com", "slug", "b", "ok", false));
        List<?> log = (List<?>) s.snapshot().get("log");
        assertEquals(2, log.size());
    }

    @Test
    void appendError_recordsEntries() {
        IngestJobState s = new IngestJobState();
        s.reset(1);
        s.appendError(Map.of("url", "https://bad.com", "error", "timeout"));
        List<?> errors = (List<?>) s.snapshot().get("errors");
        assertEquals(1, errors.size());
    }

    @Test
    void reset_clearsPreviousState() {
        IngestJobState s = new IngestJobState();
        s.reset(5);
        s.appendLog(Map.of("url", "u", "slug", "sl", "ok", true));
        s.cancel();
        // Reset for a new run
        s.reset(3);
        Map<String, Object> snap = s.snapshot();
        assertTrue(((List<?>) snap.get("log")).isEmpty());
        assertFalse((Boolean) snap.get("cancelled"));
        assertEquals(3, snap.get("total"));
    }

    @Test
    void snapshot_returnsCopies_notLiveReferences() {
        IngestJobState s = new IngestJobState();
        s.reset(1);
        s.appendLog(Map.of("url", "u", "slug", "sl", "ok", true));
        List<?> logSnapshot = (List<?>) s.snapshot().get("log");
        // Add another entry — the snapshot should not change
        s.appendLog(Map.of("url", "v", "slug", "sl2", "ok", true));
        assertEquals(1, logSnapshot.size(), "Snapshot should be independent of further mutations");
    }

    @Test
    void threadSafety_concurrentAppends_noDataLoss() throws Exception {
        IngestJobState s = new IngestJobState();
        s.reset(100);
        int threads = 10;
        CountDownLatch latch = new CountDownLatch(threads);
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        for (int i = 0; i < threads; i++) {
            final int idx = i;
            pool.submit(() -> {
                for (int j = 0; j < 10; j++) {
                    s.appendLog(Map.of("url", "u" + idx + "_" + j, "slug", "s", "ok", true));
                }
                latch.countDown();
            });
        }
        latch.await();
        pool.shutdown();
        List<?> log = (List<?>) s.snapshot().get("log");
        assertEquals(100, log.size(), "All 100 entries should be recorded despite concurrent appends");
    }
}
```

- [ ] **Step 2: Run to confirm COMPILATION FAILURE (IngestJobState not found)**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=IngestJobStateTest -q 2>&1 | grep -E "ERROR|cannot find" | head -5
```

- [ ] **Step 3: Create IngestJobState.java**

```java
package io.sparge.server;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * Thread-safe job state for the ingest pipeline.
 * Mirrors the Python _job dict + _job_lock in bridge.py.
 */
public class IngestJobState {

    private volatile boolean running   = false;
    private volatile int     done      = 0;
    private volatile int     total     = 0;
    private volatile String  current   = "";
    private volatile boolean cancelled = false;

    private final List<Map<String, Object>> errors = new ArrayList<>();
    private final List<Map<String, Object>> log    = new ArrayList<>();

    /** Reset for a new ingest run — clears all previous state. */
    public synchronized void reset(int total) {
        this.running   = true;
        this.done      = 0;
        this.total     = total;
        this.current   = "";
        this.cancelled = false;
        this.errors.clear();
        this.log.clear();
    }

    public synchronized void incrementDone(String current) {
        this.done++;
        this.current = current;
    }

    public synchronized void setCurrent(String current) {
        this.current = current;
    }

    public synchronized void appendLog(Map<String, Object> entry) {
        log.add(entry);
    }

    public synchronized void appendError(Map<String, Object> entry) {
        errors.add(entry);
    }

    public synchronized void finish() {
        this.running  = false;
        this.current  = "";
    }

    public void cancel() {
        this.cancelled = true;
    }

    public boolean isCancelled() {
        return cancelled;
    }

    /** Thread-safe snapshot — returns copies of all mutable collections. */
    public synchronized Map<String, Object> snapshot() {
        return Map.of(
            "running",   running,
            "done",      done,
            "total",     total,
            "current",   current,
            "cancelled", cancelled,
            "errors",    List.copyOf(errors),
            "log",       List.copyOf(log)
        );
    }
}
```

- [ ] **Step 4: Run IngestJobStateTest**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=IngestJobStateTest -q 2>&1 | tail -5
```
Expected: 9/9 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/IngestJobState.java \
        server/src/test/java/io/sparge/server/IngestJobStateTest.java
git commit -m "feat(#63): IngestJobState — thread-safe job state (9 unit tests incl. concurrency)

Refs #59

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: IngestService.java — Core + Detect + Discover + Wire Status/Cancel

**Files:**
- Create: `server/src/main/java/io/sparge/server/IngestService.java`
- Create: `server/src/test/java/io/sparge/server/IngestServiceTest.java`
- Modify: `server/src/main/java/io/sparge/server/IngestResource.java`

- [ ] **Step 1: Write IngestServiceTest.java (parsing logic only — no live HTTP needed)**

```java
package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;

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
    void normaliseUrl_addsHttps() {
        assertEquals("https://example.com", IngestService.normaliseUrl("http://example.com"));
    }

    @Test
    void normaliseUrl_httpsUnchanged() {
        assertEquals("https://example.com/blog",
                IngestService.normaliseUrl("https://example.com/blog/"));
    }

    // ── Slug generation ───────────────────────────────────────────────────────

    @Test
    void makeSlug_withDateAndUrl() {
        String slug = IngestService.makeSlug("2024-03-15", "https://blog.example.com/my-great-post/");
        assertTrue(slug.startsWith("2024-03-15-"), "Slug should start with date");
        assertTrue(slug.contains("my-great-post"), "Slug should contain URL path component");
    }

    @Test
    void makeSlug_sanitisesSpecialChars() {
        String slug = IngestService.makeSlug("2024-01-01", "https://blog.com/post?id=123&foo=bar");
        assertFalse(slug.contains("?"), "Slug should not contain query string chars");
        assertFalse(slug.contains("="), "Slug should not contain equals sign");
        assertFalse(slug.contains("&"), "Slug should not contain ampersand");
    }

    @Test
    void makeSlug_emptyDate_usesUrlOnly() {
        String slug = IngestService.makeSlug("", "https://blog.com/my-post/");
        assertFalse(slug.isEmpty(), "Slug should not be empty even without date");
        assertTrue(slug.contains("my-post"), "Should use URL path");
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
    void parseSitemapXml_extractsLocs() {
        String xml = "<?xml version=\"1.0\"?><urlset>"
            + "<url><loc>https://blog.com/2024/post-one/</loc></url>"
            + "<url><loc>https://blog.com/category/drools/</loc></url>"
            + "<url><loc>https://blog.com/2023/post-two/</loc></url>"
            + "</urlset>";
        List<String> urls = IngestService.parseSitemapUrls(xml, "https://blog.com");
        assertEquals(2, urls.size(), "Should filter out category URLs via isPostUrl");
        assertTrue(urls.contains("https://blog.com/2024/post-one/"));
        assertTrue(urls.contains("https://blog.com/2023/post-two/"));
    }

    @Test
    void parseSitemapIndex_extractsChildSitemapUrls() {
        String xml = "<?xml version=\"1.0\"?><sitemapindex>"
            + "<sitemap><loc>https://blog.com/post-sitemap.xml</loc></sitemap>"
            + "<sitemap><loc>https://blog.com/page-sitemap.xml</loc></sitemap>"
            + "</sitemapindex>";
        List<String> childUrls = IngestService.parseSitemapIndexUrls(xml);
        assertEquals(2, childUrls.size());
        assertTrue(childUrls.contains("https://blog.com/post-sitemap.xml"));
    }

    // ── RSS/Atom feed parsing ─────────────────────────────────────────────────

    @Test
    void parseRssFeed_extractsItemLinks() {
        String rss = "<?xml version=\"1.0\"?><rss version=\"2.0\"><channel>"
            + "<item><link>https://blog.com/2024/post-a/</link></item>"
            + "<item><link>https://blog.com/2023/post-b/</link></item>"
            + "</channel></rss>";
        List<String> links = IngestService.parseFeedLinks(rss);
        assertEquals(2, links.size());
        assertTrue(links.contains("https://blog.com/2024/post-a/"));
    }

    @Test
    void parseAtomFeed_extractsEntryHrefs() {
        String atom = "<?xml version=\"1.0\"?><feed xmlns=\"http://www.w3.org/2005/Atom\">"
            + "<entry><link href=\"https://blog.com/2024/post-c/\" rel=\"alternate\"/></entry>"
            + "<entry><link href=\"https://blog.com/2023/post-d/\"/></entry>"
            + "</feed>";
        List<String> links = IngestService.parseFeedLinks(atom);
        assertEquals(2, links.size());
    }

    // ── WordPress REST API URL extraction ─────────────────────────────────────

    @Test
    void parseWpRestResponse_extractsLinks() {
        String json = "[{\"link\":\"https://blog.com/2024/post-one/\"},"
            + "{\"link\":\"https://blog.com/2023/post-two/\"}]";
        List<String> urls = IngestService.parseWpRestLinks(json);
        assertEquals(2, urls.size());
        assertTrue(urls.contains("https://blog.com/2024/post-one/"));
    }

    // ── Date normalisation ────────────────────────────────────────────────────

    @Test
    void normaliseDate_iso8601_extracted() {
        assertEquals("2024-03-15", IngestService.normaliseDate("2024-03-15T10:00:00+00:00"));
    }

    @Test
    void normaliseDate_alreadyShort_unchanged() {
        assertEquals("2024-03-15", IngestService.normaliseDate("2024-03-15"));
    }

    @Test
    void normaliseDate_empty_returnsEmpty() {
        assertEquals("", IngestService.normaliseDate(""));
    }

    // ── HTML metadata extraction ───────────────────────────────────────────────

    @Test
    void extractMetadata_ogTitle_used() {
        String html = "<html><head>"
            + "<meta property=\"og:title\" content=\"My OG Title\"/>"
            + "<title>Fallback Title</title>"
            + "</head><body></body></html>";
        Map<String, Object> meta = IngestService.extractMetadata(html, "https://example.com/post/");
        assertEquals("My OG Title", meta.get("title"));
    }

    @Test
    void extractMetadata_jsonLd_extracted() {
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
    void extractMetadata_titleTag_fallback() {
        String html = "<html><head><title>Page Title - Blog Name</title></head><body></body></html>";
        Map<String, Object> meta = IngestService.extractMetadata(html, "https://example.com/post/");
        assertNotNull(meta.get("title"));
        assertFalse(((String) meta.get("title")).isEmpty());
    }

    // ── Article extraction ────────────────────────────────────────────────────

    @Test
    void findArticle_articleElement_preferred() {
        String html = "<html><body>"
            + "<nav>Navigation</nav>"
            + "<article><p>The real content.</p></article>"
            + "<footer>Footer</footer>"
            + "</body></html>";
        String article = IngestService.extractArticleHtml(html, "https://example.com/");
        assertTrue(article.contains("The real content."), "Should extract article element");
        assertFalse(article.contains("Navigation"),       "Should not include nav");
        assertFalse(article.contains("Footer"),           "Should not include footer");
    }

    @Test
    void junkStripping_scriptsAndStyles_removed() {
        String html = "<html><body><article>"
            + "<script>alert('xss')</script>"
            + "<style>.foo{color:red}</style>"
            + "<p>Clean content here.</p>"
            + "</article></body></html>";
        String article = IngestService.extractArticleHtml(html, "https://example.com/");
        assertFalse(article.contains("alert"),       "Scripts should be removed");
        assertFalse(article.contains("color:red"),   "Styles should be removed");
        assertTrue(article.contains("Clean content"), "Real content preserved");
    }

    // ── Integration tests (live HTTP — guarded) ───────────────────────────────

    @Test
    @EnabledIfSystemProperty(named = "ingest.integration", matches = "true")
    void detectPlatform_wordpress_detected() throws Exception {
        IngestService svc = new IngestService();
        Map<String, Object> result = svc.detectPlatform("https://blog.kie.org");
        assertEquals("wordpress", result.get("platform"));
        assertNotNull(result.get("name"));
    }
}
```

- [ ] **Step 2: Run to confirm compilation fails (IngestService not found)**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=IngestServiceTest -q 2>&1 | grep -E "ERROR|cannot find" | head -5
```

- [ ] **Step 3: Create IngestService.java**

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PreDestroy;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.parser.Parser;
import org.jsoup.select.Elements;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Ingest service — native Java port of scripts/ingest.py.
 *
 * Provides: detect_platform, discover_urls, preview_post, ingest_post (async),
 * cancel, status.  Uses java.net.http.HttpClient for HTTP and jsoup for HTML/XML.
 */
@ApplicationScoped
public class IngestService {

    static final String USER_AGENT =
        "Mozilla/5.0 (compatible; BlogMigrator/1.0; +https://github.com/mdproctor/mdproctor.github.io)";
    private static final int     TIMEOUT_SECS  = 20;
    private static final String[] GENERIC_FEED_PATHS =
        { "/feed/", "/rss.xml", "/atom.xml", "/feed.xml" };

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static final HttpClient HTTP = HttpClient.newBuilder()
        .followRedirects(HttpClient.Redirect.NORMAL)
        .connectTimeout(Duration.ofSeconds(TIMEOUT_SECS))
        .build();

    private final IngestJobState jobState = new IngestJobState();
    private final ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "ingest-worker");
        t.setDaemon(true);
        return t;
    });

    @Inject StateStore    stateStore;
    @Inject ActiveProject activeProject;

    @PreDestroy
    void destroy() { executor.shutdownNow(); }

    // ── Status / cancel ───────────────────────────────────────────────────────

    public Map<String, Object> status()  { return jobState.snapshot(); }
    public Map<String, Object> cancel()  { jobState.cancel(); return Map.of("cancelled", true); }

    // ── Platform detection ────────────────────────────────────────────────────

    public Map<String, Object> detectPlatform(String rawUrl) throws Exception {
        String base = normaliseUrl(rawUrl);

        // 1. WordPress: probe /wp-json/
        try {
            HttpResponse<String> r = get(base + "/wp-json/");
            if (r != null && r.statusCode() == 200) {
                JsonNode data = MAPPER.readTree(r.body());
                String name = data.path("name").asText("");
                if (name.isEmpty()) name = extractSiteName(base);
                return Map.of("platform", "wordpress", "base_url", base, "name", name);
            }
        } catch (Exception ignored) {}

        // 2. Blogger: check domain
        URI parsed = URI.create(base);
        String host = parsed.getHost().toLowerCase();
        if (host.contains("blogger.com") || host.contains("blogspot.com")) {
            return Map.of("platform", "blogger", "base_url", base, "name", extractSiteName(base));
        }

        // 3. Ghost: check meta generator
        try {
            HttpResponse<String> r = get(base);
            if (r != null && r.statusCode() == 200) {
                Document doc = Jsoup.parse(r.body(), base);
                Element gen = doc.selectFirst("meta[name=generator]");
                if (gen != null && gen.attr("content").toLowerCase().contains("ghost")) {
                    return Map.of("platform", "ghost", "base_url", base,
                            "name", extractNameFromDoc(doc, base));
                }
                return Map.of("platform", "generic", "base_url", base,
                        "name", extractNameFromDoc(doc, base));
            }
        } catch (Exception ignored) {}

        return Map.of("platform", "generic", "base_url", base, "name", "");
    }

    // ── URL discovery ─────────────────────────────────────────────────────────

    public Map<String, Object> discoverUrls(String rawUrl, String authorFilter) throws Exception {
        Map<String, Object> platform = detectPlatform(rawUrl);
        String base     = (String) platform.get("base_url");
        String pf       = (String) platform.get("platform");
        List<String> urls = discoverUrlsForPlatform(base, pf, authorFilter);
        return Map.of("platform", pf, "base_url", base,
                "name", platform.get("name"), "urls", urls, "count", urls.size());
    }

    List<String> discoverUrlsForPlatform(String base, String platform, String authorFilter)
            throws Exception {
        List<String> urls = trySitemap(base);
        if (urls.isEmpty() && "wordpress".equals(platform)) urls = tryWpRest(base);
        if (urls.isEmpty()) {
            if ("blogger".equals(platform)) urls = tryBloggerFeed(base);
            if (urls.isEmpty())             urls = tryGenericFeeds(base);
        }
        // Deduplicate preserving order
        List<String> deduped = new ArrayList<>(new LinkedHashSet<>(urls));
        // Author filter (only when small enough)
        if (authorFilter != null && !authorFilter.isBlank() && deduped.size() <= 50) {
            String af = authorFilter.toLowerCase();
            List<String> filtered = new ArrayList<>();
            for (String u : deduped) {
                try {
                    Map<String, Object> meta = fetchPostMeta(u);
                    String author = String.valueOf(meta.getOrDefault("author", "")).toLowerCase();
                    if (author.contains(af)) filtered.add(u);
                } catch (Exception ignored) { filtered.add(u); }
            }
            deduped = filtered;
        }
        return deduped;
    }

    // ── Preview (no disk write) ───────────────────────────────────────────────

    public Map<String, Object> previewPost(String url) throws Exception {
        return fetchAndExtract(url);
    }

    // ── Async ingest run ──────────────────────────────────────────────────────

    public Map<String, Object> startIngest(List<String> urls, String authorFilter) {
        synchronized (jobState) {
            if ((boolean) jobState.snapshot().get("running"))
                return Map.of("error", "ingest already running");
        }
        jobState.reset(urls.size());
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        executor.submit(() -> runWorker(urls, authorFilter, cfg));
        return Map.of("started", true, "total", urls.size());
    }

    private void runWorker(List<String> urls, String authorFilter,
                           SpargeConfig.ResolvedConfig cfg) {
        try {
            for (String url : urls) {
                if (jobState.isCancelled()) break;
                jobState.setCurrent(url);
                try {
                    Map<String, Object> result = ingestPost(url, cfg);
                    jobState.appendLog(Map.of(
                        "url",  url,
                        "slug", result.getOrDefault("slug", ""),
                        "ok",   result.get("error") == null));
                    if (result.get("error") != null)
                        jobState.appendError(Map.of("url", url, "error", result.get("error")));
                } catch (Exception e) {
                    jobState.appendError(Map.of("url", url, "error", e.getMessage()));
                }
                jobState.incrementDone(url);
            }
            // Re-sync StateStore after bulk ingest
            if (cfg != null) stateStore.getAll(); // triggers reload from disk
        } finally {
            jobState.finish();
        }
    }

    // ── Core extraction ───────────────────────────────────────────────────────

    Map<String, Object> fetchAndExtract(String url) throws Exception {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("slug", ""); result.put("title", ""); result.put("date", "");
        result.put("author", ""); result.put("categories", List.of()); result.put("tags", List.of());
        result.put("original_url", url); result.put("html", "");
        result.put("asset_count", 0); result.put("error", null);

        HttpResponse<String> resp;
        try {
            resp = get(url);
        } catch (Exception e) {
            result.put("error", "Fetch error: " + e.getMessage());
            return result;
        }
        if (resp == null || resp.statusCode() != 200) {
            result.put("error", "HTTP " + (resp != null ? resp.statusCode() : "unreachable"));
            return result;
        }

        String html = resp.body();
        Document doc;
        try {
            doc = Jsoup.parse(html, url);
        } catch (Exception e) {
            result.put("error", "Parse error: " + e.getMessage());
            return result;
        }

        Map<String, Object> meta = extractMetadata(html, url);
        result.putAll(meta);

        Element article = findArticle(doc);
        if (article == null) {
            result.put("error", "No article content found");
            return result;
        }
        stripJunk(article);

        // Count assets
        int assetCount = 0;
        for (Element img : article.select("img")) {
            String src = img.attr("src");
            if (!src.startsWith("data:") && !src.isEmpty()) assetCount++;
        }
        result.put("asset_count", assetCount);

        String date = String.valueOf(meta.getOrDefault("date", ""));
        result.put("slug", makeSlug(date, url));
        result.put("html", article.outerHtml());
        return result;
    }

    Map<String, Object> ingestPost(String url, SpargeConfig.ResolvedConfig cfg) throws Exception {
        Map<String, Object> extracted = fetchAndExtract(url);
        if (extracted.get("error") != null) return extracted;
        if (cfg == null) { extracted.put("error", "no active project"); return extracted; }

        String slug = (String) extracted.get("slug");
        String html  = (String) extracted.get("html");

        // Download and localise images
        Document doc = Jsoup.parse("<html><body>" + html + "</body></html>", url);
        Element article = doc.selectFirst("body");
        int localised = 0, failed = 0;
        if (article != null) {
            for (Element img : article.select("img[src]")) {
                String src = img.attr("abs:src");
                if (src.isEmpty() || src.startsWith("data:")) continue;
                try {
                    String localPath = downloadAsset(src, extracted, cfg.serveRoot());
                    if (localPath != null) { img.attr("src", localPath); localised++; }
                    else failed++;
                } catch (Exception ignored) { failed++; }
            }
            html = article.outerHtml();
        }

        // Write to disk
        Path postsDir = cfg.postsDir();
        Files.createDirectories(postsDir);
        Files.writeString(postsDir.resolve(slug + ".html"), html, StandardCharsets.UTF_8);
        String sidecar = MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(
            Map.of("title", extracted.getOrDefault("title", ""),
                   "date",  extracted.getOrDefault("date", ""),
                   "author", extracted.getOrDefault("author", ""),
                   "categories", extracted.getOrDefault("categories", List.of()),
                   "tags", extracted.getOrDefault("tags", List.of()),
                   "original_url", url));
        Files.writeString(postsDir.resolve(slug + ".json"), sidecar, StandardCharsets.UTF_8);

        Map<String, Object> result = new LinkedHashMap<>(extracted);
        result.remove("html");
        result.put("asset_localised", localised);
        result.put("asset_failed",    failed);
        result.put("wrote",           true);
        return result;
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private List<String> trySitemap(String base) {
        try {
            HttpResponse<String> r = get(base + "/sitemap.xml");
            if (r == null || r.statusCode() != 200) return List.of();
            String body = r.body().strip();
            if (!body.startsWith("<")) return List.of();
            // Sitemap index?
            List<String> childUrls = parseSitemapIndexUrls(body);
            if (!childUrls.isEmpty()) {
                List<String> postUrls = new ArrayList<>();
                // Prefer post-sitemap children
                List<String> postSitemaps = childUrls.stream()
                    .filter(u -> u.toLowerCase().contains("post")).collect(Collectors.toList());
                List<String> toFetch = postSitemaps.isEmpty() ? childUrls : postSitemaps;
                for (String sm : toFetch) {
                    HttpResponse<String> cr = get(sm);
                    if (cr != null && cr.statusCode() == 200)
                        postUrls.addAll(parseSitemapUrls(cr.body(), base));
                }
                return postUrls;
            }
            return parseSitemapUrls(body, base);
        } catch (Exception ignored) { return List.of(); }
    }

    private List<String> tryWpRest(String base) {
        List<String> urls = new ArrayList<>();
        int page = 1;
        while (true) {
            try {
                String apiUrl = base + "/wp-json/wp/v2/posts?per_page=100&page=" + page + "&_fields=link";
                HttpResponse<String> r = get(apiUrl);
                if (r == null || r.statusCode() != 200) break;
                List<String> batch = parseWpRestLinks(r.body());
                urls.addAll(batch);
                if (batch.size() < 100) break;
                page++;
            } catch (Exception ignored) { break; }
        }
        return urls;
    }

    private List<String> tryBloggerFeed(String base) {
        try {
            String feedUrl = base + "/feeds/posts/default?max-results=500&alt=rss";
            HttpResponse<String> r = get(feedUrl);
            if (r == null || r.statusCode() != 200) return List.of();
            return parseFeedLinks(r.body());
        } catch (Exception ignored) { return List.of(); }
    }

    private List<String> tryGenericFeeds(String base) {
        for (String path : GENERIC_FEED_PATHS) {
            try {
                HttpResponse<String> r = get(base + path);
                if (r == null || r.statusCode() != 200) continue;
                String body = r.body().strip();
                if (!body.startsWith("<")) continue;
                List<String> links = parseFeedLinks(body);
                if (!links.isEmpty()) return links;
            } catch (Exception ignored) {}
        }
        return List.of();
    }

    private Map<String, Object> fetchPostMeta(String url) throws Exception {
        HttpResponse<String> r = get(url);
        if (r == null || r.statusCode() != 200) return Map.of();
        return extractMetadata(r.body(), url);
    }

    private String extractSiteName(String base) {
        try {
            HttpResponse<String> r = get(base);
            if (r != null && r.statusCode() == 200) {
                Document doc = Jsoup.parse(r.body(), base);
                return extractNameFromDoc(doc, base);
            }
        } catch (Exception ignored) {}
        return "";
    }

    private static String extractNameFromDoc(Document doc, String base) {
        Element og = doc.selectFirst("meta[property=og:site_name]");
        if (og != null && !og.attr("content").isBlank()) return og.attr("content").strip();
        Element title = doc.selectFirst("title");
        if (title != null) return title.text().strip();
        return URI.create(base).getHost();
    }

    private String downloadAsset(String src, Map<String, Object> meta, Path serveRoot) {
        try {
            URI uri = URI.create(src);
            String path = uri.getPath();
            String ext  = path.contains(".") ? path.substring(path.lastIndexOf('.')) : "";
            String date = String.valueOf(meta.getOrDefault("date", "unknown"));
            String hash = Integer.toHexString(src.hashCode());
            Path   local = serveRoot.resolve("legacy/assets/images/" + date + "/" + hash + ext);
            Files.createDirectories(local.getParent());
            if (Files.exists(local)) return "/legacy/assets/images/" + date + "/" + hash + ext;
            HttpRequest req = HttpRequest.newBuilder(uri)
                .header("User-Agent", USER_AGENT)
                .timeout(Duration.ofSeconds(TIMEOUT_SECS))
                .build();
            HTTP.send(req, HttpResponse.BodyHandlers.ofFile(local));
            return "/legacy/assets/images/" + date + "/" + hash + ext;
        } catch (Exception ignored) { return null; }
    }

    HttpResponse<String> get(String url) throws Exception {
        HttpRequest req = HttpRequest.newBuilder(URI.create(url))
            .header("User-Agent", USER_AGENT)
            .timeout(Duration.ofSeconds(TIMEOUT_SECS))
            .GET()
            .build();
        return HTTP.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
    }

    // ── Static parsing helpers (package-private for unit testing) ─────────────

    static String normaliseUrl(String url) {
        url = url.trim();
        if (url.startsWith("http://")) url = "https://" + url.substring(7);
        return url.replaceAll("/+$", "");
    }

    static String makeSlug(String date, String url) {
        String path = URI.create(url).getPath();
        // Take last meaningful path segment
        String[] parts = path.split("/");
        String slug = "";
        for (int i = parts.length - 1; i >= 0; i--) {
            if (!parts[i].isBlank()) { slug = parts[i]; break; }
        }
        slug = slug.replaceAll("[^a-z0-9-]", "-").replaceAll("-+", "-").replaceAll("^-|-$", "");
        if (slug.isBlank()) slug = Integer.toHexString(url.hashCode());
        return (date.isBlank() ? "" : date + "-") + slug;
    }

    static boolean isPostUrl(String url) {
        if (!url.startsWith("http://") && !url.startsWith("https://")) return false;
        try {
            URI u = URI.create(url);
            String path = u.getPath().toLowerCase();
            if (path.contains("..")) return false;
            Set<String> exclude = Set.of("category", "tag", "author", "page", "feed",
                "wp-content", "wp-includes", "wp-admin", "comment-page", "attachment");
            List<String> segments = Arrays.stream(path.split("/"))
                .filter(s -> !s.isBlank()).collect(Collectors.toList());
            if (segments.stream().anyMatch(exclude::contains)) return false;
            if (path.matches(".*/\\d{4}/.*")) return true;
            return !segments.isEmpty();
        } catch (Exception ignored) { return false; }
    }

    static List<String> parseSitemapUrls(String xml, String base) {
        try {
            Document doc = Jsoup.parse(xml, base, Parser.xmlParser());
            return doc.select("url > loc, loc").stream()
                .map(e -> e.text().strip())
                .filter(IngestService::isPostUrl)
                .collect(Collectors.toList());
        } catch (Exception ignored) { return List.of(); }
    }

    static List<String> parseSitemapIndexUrls(String xml) {
        try {
            Document doc = Jsoup.parse(xml, "", Parser.xmlParser());
            if (doc.select("sitemap").isEmpty()) return List.of();
            return doc.select("sitemap > loc").stream()
                .map(e -> e.text().strip())
                .collect(Collectors.toList());
        } catch (Exception ignored) { return List.of(); }
    }

    static List<String> parseFeedLinks(String xml) {
        try {
            Document doc = Jsoup.parse(xml, "", Parser.xmlParser());
            List<String> links = new ArrayList<>();
            // RSS <item><link>
            for (Element item : doc.select("item")) {
                Element link = item.selectFirst("link");
                if (link != null && !link.text().isBlank()) links.add(link.text().strip());
            }
            // Atom <entry><link href="...">
            for (Element entry : doc.select("entry")) {
                Element link = entry.selectFirst("link[href]");
                if (link != null) links.add(link.attr("href").strip());
            }
            return links;
        } catch (Exception ignored) { return List.of(); }
    }

    static List<String> parseWpRestLinks(String json) {
        try {
            JsonNode arr = MAPPER.readTree(json);
            List<String> links = new ArrayList<>();
            if (arr.isArray()) {
                for (JsonNode item : arr) {
                    String link = item.path("link").asText("");
                    if (!link.isBlank()) links.add(link);
                }
            }
            return links;
        } catch (Exception ignored) { return List.of(); }
    }

    static String normaliseDate(String raw) {
        if (raw == null || raw.isBlank()) return "";
        // ISO 8601 with time → date only
        if (raw.length() >= 10 && raw.charAt(4) == '-' && raw.charAt(7) == '-')
            return raw.substring(0, 10);
        return raw.strip();
    }

    static Map<String, Object> extractMetadata(String html, String url) {
        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("title", ""); meta.put("date", ""); meta.put("author", "");
        meta.put("categories", new ArrayList<String>()); meta.put("tags", new ArrayList<String>());
        meta.put("original_url", url);

        Document doc = Jsoup.parse(html, url);

        // 1. JSON-LD
        for (Element script : doc.select("script[type=application/ld+json]")) {
            try {
                JsonNode ld = MAPPER.readTree(script.html());
                // Handle @graph wrapper
                if (ld.has("@graph")) {
                    for (JsonNode node : ld.get("@graph")) {
                        if (extractFromLd(node, meta)) break;
                    }
                } else {
                    extractFromLd(ld, meta);
                }
            } catch (Exception ignored) {}
        }

        // 2. OpenGraph / meta tags (fill gaps)
        if (meta.get("title").toString().isEmpty()) {
            Element og = doc.selectFirst("meta[property=og:title]");
            if (og != null) meta.put("title", og.attr("content").strip());
        }
        if (meta.get("date").toString().isEmpty()) {
            for (String sel : List.of("meta[property=article:published_time]",
                    "meta[name=date]", "meta[name=pubdate]", "time[datetime]")) {
                Element e = doc.selectFirst(sel);
                if (e != null) {
                    String d = e.hasAttr("datetime") ? e.attr("datetime") : e.attr("content");
                    if (!d.isBlank()) { meta.put("date", normaliseDate(d)); break; }
                }
            }
        }
        if (meta.get("author").toString().isEmpty()) {
            Element au = doc.selectFirst("meta[name=author]");
            if (au != null) meta.put("author", au.attr("content").strip());
        }

        // 3. Title tag fallback
        if (meta.get("title").toString().isEmpty()) {
            Element t = doc.selectFirst("title");
            if (t != null) meta.put("title", t.text().strip());
        }

        return meta;
    }

    private static boolean extractFromLd(JsonNode ld, Map<String, Object> meta) {
        String type = ld.path("@type").asText("");
        if (!type.contains("BlogPosting") && !type.contains("Article") && !type.contains("Post"))
            return false;
        if (!ld.path("headline").asText("").isEmpty())
            meta.put("title", ld.path("headline").asText("").strip());
        if (!ld.path("datePublished").asText("").isEmpty())
            meta.put("date", normaliseDate(ld.path("datePublished").asText("")));
        JsonNode author = ld.path("author");
        if (!author.isMissingNode()) {
            String name = author.isTextual() ? author.asText()
                : author.path("name").asText("");
            if (!name.isEmpty()) meta.put("author", name.strip());
        }
        return true;
    }

    static String extractArticleHtml(String html, String baseUrl) {
        Document doc = Jsoup.parse(html, baseUrl);
        Element article = findArticle(doc);
        if (article == null) return "";
        stripJunk(article);
        return article.outerHtml();
    }

    private static final String[] ARTICLE_SELECTORS = {
        "article", ".entry-content", ".post-content", "#content",
        "main", ".content", "[role=main]"
    };

    static Element findArticle(Document doc) {
        for (String sel : ARTICLE_SELECTORS) {
            Element e = doc.selectFirst(sel);
            if (e != null && !e.text().isBlank()) return e;
        }
        return doc.selectFirst("body");
    }

    private static final String[] JUNK_SELECTORS_INGEST = {
        "script", "style", "nav", "header", "footer",
        ".sidebar", "#comments", ".comments-area",
        ".author-box", ".author-description", ".author-info",
        ".sharedaddy", ".addtoany_share_save_container",
        "[class*=wpDiscuz]", "[class*=addtoany]",
        ".jp-relatedposts", ".post-navigation",
        ".wpdiscuz-form-container", ".entry-header", ".entry-meta"
    };

    static void stripJunk(Element article) {
        for (String sel : JUNK_SELECTORS_INGEST) {
            try { article.select(sel).remove(); } catch (Exception ignored) {}
        }
        // Remove event handlers
        for (Element el : article.getAllElements()) {
            el.attributes().removeAll(el.attributes().asList().stream()
                .filter(a -> a.getKey().startsWith("on"))
                .map(org.jsoup.nodes.Attribute::getKey)
                .collect(Collectors.toList()));
        }
    }
}
```

- [ ] **Step 4: Run IngestServiceTest**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=IngestServiceTest -q 2>&1 | tail -15
```

Expected: All non-integration tests pass. Fix any failures before continuing.

- [ ] **Step 5: Wire status and cancel in IngestResource.java**

Read the current file first:
```bash
cat ~/claude/sparge/server/src/main/java/io/sparge/server/IngestResource.java
```

Replace with a version that handles status and cancel natively, leaving detect/discover/preview/run as JEP for now:

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.util.List;
import java.util.Map;

@Path("/api/ingest")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class IngestResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject PythonBridge  bridge;
    @Inject IngestService ingestService;

    @GET
    @Path("status")
    public Response status() {
        return ok(ingestService.status());
    }

    @POST
    @Path("detect")
    public Response detect(String body) {
        try {
            String url = MAPPER.readTree(body == null ? "{}" : body).path("url").asText("");
            if (url.isBlank()) return err(400, "url required");
            return ok(ingestService.detectPlatform(url));
        } catch (Exception e) { return err(e.getMessage()); }
    }

    @POST
    @Path("discover")
    public Response discover(String body) {
        try {
            var data = MAPPER.readTree(body == null ? "{}" : body);
            String url    = data.path("url").asText("");
            String author = data.path("author_filter").asText(null);
            if (url.isBlank()) return err(400, "url required");
            return ok(ingestService.discoverUrls(url, author));
        } catch (Exception e) { return err(e.getMessage()); }
    }

    @POST
    @Path("preview")
    public Response preview(String body) {
        try {
            String url = MAPPER.readTree(body == null ? "{}" : body).path("url").asText("");
            if (url.isBlank()) return err(400, "url required");
            return ok(ingestService.previewPost(url));
        } catch (Exception e) { return err(e.getMessage()); }
    }

    @POST
    @Path("run")
    public Response run(String body) {
        try {
            var data = MAPPER.readTree(body == null ? "{}" : body);
            List<String> urls = new java.util.ArrayList<>();
            for (var u : data.path("urls")) urls.add(u.asText());
            String author = data.path("author_filter").asText(null);
            if (urls.isEmpty()) return err(400, "urls required");
            return ok(ingestService.startIngest(urls, author));
        } catch (Exception e) { return err(e.getMessage()); }
    }

    @POST
    @Path("cancel")
    public Response cancel() {
        return ok(ingestService.cancel());
    }

    private Response ok(Object obj) {
        try {
            return Response.ok(MAPPER.writeValueAsString(obj))
                    .header("Content-Type",                "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .build();
        } catch (Exception e) { return err(e.getMessage()); }
    }

    private Response err(String msg) {
        return err(500, msg);
    }

    private Response err(int status, String msg) {
        String escaped = msg == null ? "error" : msg.replace("\\", "\\\\").replace("\"", "\\\"");
        return Response.status(status)
                .entity("{\"error\":\"" + escaped + "\"}")
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }
}
```

- [ ] **Step 6: Run full suite**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dquarkus.http.test-port=8888 -q 2>&1 | grep -E "Tests run:|BUILD" | tail -5
```
Expected: BUILD SUCCESS, 0 failures.

- [ ] **Step 7: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/IngestService.java \
        server/src/main/java/io/sparge/server/IngestResource.java \
        server/src/test/java/io/sparge/server/IngestServiceTest.java
git commit -m "feat(#63): IngestService — detect/discover/preview/run/cancel/status (port of ingest.py)

Refs #59

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: IngestResourceTest + projectIngestRun + Final Verify

**Files:**
- Create: `server/src/test/java/io/sparge/server/IngestResourceTest.java`
- Modify: `server/src/main/java/io/sparge/server/ProjectsResource.java`

- [ ] **Step 1: Write IngestResourceTest.java**

```java
package io.sparge.server;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;

import java.nio.file.Files;
import java.nio.file.Paths;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@QuarkusTest
class IngestResourceTest {

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    @BeforeEach
    void activateProject() {
        if (!kieArchivePresent()) return;
        try {
            String id = given()
                    .when().get("/api/projects")
                    .then().statusCode(200)
                    .extract().jsonPath().getString("[0].id");
            if (id != null && !id.isEmpty()) {
                given().contentType("application/json")
                        .when().post("/api/projects/{id}/activate", id)
                        .then().statusCode(200);
            }
        } catch (Exception e) {
            System.err.println("Warning: " + e.getMessage());
        }
    }

    // ── Status ────────────────────────────────────────────────────────────────

    @Test
    void statusReturns200WithJobFields() {
        given()
                .when().get("/api/ingest/status")
                .then()
                .statusCode(200)
                .body("running",   notNullValue())
                .body("done",      notNullValue())
                .body("total",     notNullValue())
                .body("cancelled", notNullValue())
                .body("errors",    notNullValue())
                .body("log",       notNullValue());
    }

    @Test
    void statusInitiallyNotRunning() {
        given()
                .when().get("/api/ingest/status")
                .then()
                .statusCode(200)
                .body("running", equalTo(false));
    }

    // ── Cancel ────────────────────────────────────────────────────────────────

    @Test
    void cancelReturns200WithCancelledTrue() {
        given()
                .contentType("application/json")
                .when().post("/api/ingest/cancel")
                .then()
                .statusCode(200)
                .body("cancelled", equalTo(true));
    }

    @Test
    void cancelThenStatus_showsCancelled() {
        given().when().post("/api/ingest/cancel");
        given()
                .when().get("/api/ingest/status")
                .then()
                .statusCode(200)
                .body("cancelled", equalTo(true));
    }

    // ── Detect ────────────────────────────────────────────────────────────────

    @Test
    void detectMissingUrl_returns400() {
        given()
                .contentType("application/json")
                .body("{}")
                .when().post("/api/ingest/detect")
                .then()
                .statusCode(400);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void detectWordPress_returns200WithPlatform() {
        // blog.kie.org is a known WordPress blog
        given()
                .contentType("application/json")
                .body("{\"url\":\"https://blog.kie.org\"}")
                .when().post("/api/ingest/detect")
                .then()
                .statusCode(200)
                .body("platform", notNullValue())
                .body("base_url", notNullValue());
    }

    // ── Discover ──────────────────────────────────────────────────────────────

    @Test
    void discoverMissingUrl_returns400() {
        given()
                .contentType("application/json")
                .body("{}")
                .when().post("/api/ingest/discover")
                .then()
                .statusCode(400);
    }

    // ── Preview ───────────────────────────────────────────────────────────────

    @Test
    void previewMissingUrl_returns400() {
        given()
                .contentType("application/json")
                .body("{}")
                .when().post("/api/ingest/preview")
                .then()
                .statusCode(400);
    }

    // ── Run ───────────────────────────────────────────────────────────────────

    @Test
    void runMissingUrls_returns400() {
        given()
                .contentType("application/json")
                .body("{\"urls\":[]}")
                .when().post("/api/ingest/run")
                .then()
                .statusCode(400);
    }
}
```

- [ ] **Step 2: Wire projectIngestRun in ProjectsResource.java**

Find the current `projectIngestRun` method (calls `bridge.project_ingest_run`):

```java
@POST
@Path("{id}/ingest/run")
public Response projectIngestRun(@PathParam("id") String id, String body) {
    return BridgeResponse.of(bridge.call("bridge.project_ingest_run",
            id, body == null ? "{}" : body));
}
```

Replace with native Java:

```java
@POST
@Path("{id}/ingest/run")
public Response projectIngestRun(@PathParam("id") String id, String body) {
    // Activate the project first, then delegate to IngestService
    java.nio.file.Path projectDir = store.getProjectDir(id);
    java.nio.file.Path configPath = projectDir.resolve("config.json");
    try {
        if (!java.nio.file.Files.exists(configPath)) {
            return err("project not found: " + id);
        }
        activeProject.set(id, SpargeConfig.load(configPath, projectDir), projectDir);
    } catch (Exception e) {
        return err("failed to activate project: " + e.getMessage());
    }
    // Delegate to ingest run
    try {
        var data = new com.fasterxml.jackson.databind.ObjectMapper()
            .readTree(body == null ? "{}" : body);
        java.util.List<String> urls = new java.util.ArrayList<>();
        for (var u : data.path("urls")) urls.add(u.asText());
        String author = data.path("author_filter").asText(null);
        if (urls.isEmpty()) return Response.status(400)
                .entity("{\"error\":\"urls required\"}")
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
        return ok(new com.fasterxml.jackson.databind.ObjectMapper()
            .writeValueAsString(ingestService.startIngest(urls, author)));
    } catch (Exception e) { return err(e.getMessage()); }
}
```

Also add `@Inject IngestService ingestService;` to ProjectsResource if not already present.

- [ ] **Step 3: Verify no JEP calls remain for all 7 ingest calls**

```bash
grep -n "bridge.call.*ingest\|bridge.call.*project_ingest" \
  ~/claude/sparge/server/src/main/java/io/sparge/server/IngestResource.java \
  ~/claude/sparge/server/src/main/java/io/sparge/server/ProjectsResource.java
```
Expected: no output.

- [ ] **Step 4: Run IngestResourceTest**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dtest=IngestResourceTest -Dquarkus.http.test-port=8888 -q 2>&1 | grep "Tests run" | tail -3
```

- [ ] **Step 5: Run full suite**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dquarkus.http.test-port=8888 -q 2>&1 | grep -E "Tests run:|BUILD" | tail -5
```
Expected: BUILD SUCCESS, ≥310 tests, 0 failures.

- [ ] **Step 6: Run Python test suite**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --ignore=tests/python-legacy 2>&1 | tail -5
```
Expected: 270 passed, 0 failures.

- [ ] **Step 7: Commit all**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/ProjectsResource.java \
        server/src/test/java/io/sparge/server/IngestResourceTest.java
git commit -m "feat(#63): wire IngestResource + projectIngestRun to native Java — all 7 JEP calls removed

Refs #59

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 8: Close issue 63 and tick 6d on epic**

```bash
gh issue close 63 \
  --repo mdproctor/sparge \
  --comment "All 7 ingest JEP calls removed. IngestJobState (9 thread-safety tests) + IngestService (20+ unit tests) + IngestResourceTest (E2E). Closes #63"

BODY=$(gh issue view 59 --repo mdproctor/sparge --json body -q .body | sed 's/- \[ \] 6d/- [x] 6d/') \
  && gh issue edit 59 --repo mdproctor/sparge --body "$BODY"
```
