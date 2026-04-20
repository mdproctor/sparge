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
 * Provides detect_platform, discover_urls, preview_post, ingest_post (async), cancel, status.
 */
@ApplicationScoped
public class IngestService {

    static final String USER_AGENT =
        "Mozilla/5.0 (compatible; BlogMigrator/1.0; +https://github.com/mdproctor/mdproctor.github.io)";
    private static final int TIMEOUT_SECS = 20;
    private static final String[] GENERIC_FEED_PATHS = {"/feed/", "/rss.xml", "/atom.xml", "/feed.xml"};
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
            var r = get(base + "/wp-json/");
            if (r != null && r.statusCode() == 200) {
                JsonNode data = MAPPER.readTree(r.body());
                String name = data.path("name").asText("");
                if (name.isEmpty()) name = extractSiteName(base);
                return Map.of("platform", "wordpress", "base_url", base, "name", name);
            }
        } catch (Exception ignored) {}

        // 2. Blogger: check domain
        String host = URI.create(base).getHost().toLowerCase();
        if (host.contains("blogger.com") || host.contains("blogspot.com"))
            return Map.of("platform", "blogger", "base_url", base, "name", extractSiteName(base));

        // 3. Ghost: check meta[name=generator]
        try {
            var r = get(base);
            if (r != null && r.statusCode() == 200) {
                Document doc = Jsoup.parse(r.body(), base);
                Element gen = doc.selectFirst("meta[name=generator]");
                if (gen != null && gen.attr("content").toLowerCase().contains("ghost"))
                    return Map.of("platform", "ghost", "base_url", base, "name", extractNameFromDoc(doc, base));
                return Map.of("platform", "generic", "base_url", base, "name", extractNameFromDoc(doc, base));
            }
        } catch (Exception ignored) {}

        return Map.of("platform", "generic", "base_url", base, "name", "");
    }

    // ── URL discovery ─────────────────────────────────────────────────────────

    public Map<String, Object> discoverUrls(String rawUrl, String authorFilter) throws Exception {
        Map<String, Object> platform = detectPlatform(rawUrl);
        String base = (String) platform.get("base_url");
        String pf   = (String) platform.get("platform");
        List<String> urls = discoverUrlsInternal(base, pf, authorFilter);
        return Map.of("platform", pf, "base_url", base,
                "name", platform.get("name"), "urls", urls, "count", urls.size());
    }

    List<String> discoverUrlsInternal(String base, String platform, String authorFilter) throws Exception {
        List<String> urls = trySitemap(base);
        if (urls.isEmpty() && "wordpress".equals(platform)) urls = tryWpRest(base);
        if (urls.isEmpty()) {
            if ("blogger".equals(platform)) urls = tryBloggerFeed(base);
            if (urls.isEmpty())             urls = tryGenericFeeds(base);
        }
        List<String> deduped = new ArrayList<>(new LinkedHashSet<>(urls));
        if (authorFilter != null && !authorFilter.isBlank() && deduped.size() <= 50) {
            String af = authorFilter.toLowerCase();
            List<String> filtered = new ArrayList<>();
            for (String u : deduped) {
                try {
                    Map<String, Object> meta = fetchPostMeta(u);
                    if (String.valueOf(meta.getOrDefault("author", "")).toLowerCase().contains(af))
                        filtered.add(u);
                } catch (Exception ignored) { filtered.add(u); }
            }
            deduped = filtered;
        }
        return deduped;
    }

    // ── Preview ───────────────────────────────────────────────────────────────

    public Map<String, Object> previewPost(String url) throws Exception {
        return fetchAndExtract(url);
    }

    // ── Async ingest ──────────────────────────────────────────────────────────

    public Map<String, Object> startIngest(List<String> urls, String authorFilter) {
        synchronized (jobState) {
            if ((boolean) jobState.snapshot().get("running"))
                return Map.of("error", "ingest already running");
        }
        jobState.reset(urls.size());
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        executor.submit(() -> runWorker(urls, cfg));
        return Map.of("started", true, "total", urls.size());
    }

    private void runWorker(List<String> urls, SpargeConfig.ResolvedConfig cfg) {
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
                    jobState.appendError(Map.of("url", url, "error", String.valueOf(e.getMessage())));
                }
                jobState.incrementDone(url);
            }
        } finally {
            jobState.finish();
        }
    }

    // ── Core extraction ───────────────────────────────────────────────────────

    Map<String, Object> fetchAndExtract(String url) throws Exception {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("slug", ""); result.put("title", ""); result.put("date", "");
        result.put("author", ""); result.put("categories", List.of()); result.put("tags", List.of());
        result.put("original_url", url); result.put("html", ""); result.put("asset_count", 0); result.put("error", null);

        HttpResponse<String> resp;
        try { resp = get(url); }
        catch (Exception e) { result.put("error", "Fetch error: " + e.getMessage()); return result; }
        if (resp == null || resp.statusCode() != 200) {
            result.put("error", "HTTP " + (resp != null ? resp.statusCode() : "unreachable")); return result;
        }

        String html = resp.body();
        Document doc;
        try { doc = Jsoup.parse(html, url); }
        catch (Exception e) { result.put("error", "Parse error: " + e.getMessage()); return result; }

        result.putAll(extractMetadata(html, url));
        Element article = findArticle(doc);
        if (article == null) { result.put("error", "No article content found"); return result; }
        stripJunk(article);

        int assetCount = 0;
        for (Element img : article.select("img")) {
            String src = img.attr("src");
            if (!src.startsWith("data:") && !src.isEmpty()) assetCount++;
        }
        result.put("asset_count", assetCount);
        result.put("slug", makeSlug(String.valueOf(result.getOrDefault("date", "")), url));
        result.put("html", article.outerHtml());
        return result;
    }

    Map<String, Object> ingestPost(String url, SpargeConfig.ResolvedConfig cfg) throws Exception {
        Map<String, Object> extracted = fetchAndExtract(url);
        if (extracted.get("error") != null) return extracted;
        if (cfg == null) { extracted.put("error", "no active project"); return extracted; }

        String slug = (String) extracted.get("slug");
        String html  = (String) extracted.get("html");

        // Localise images
        Document doc = Jsoup.parse("<html><body>" + html + "</body></html>", url);
        Element body = doc.selectFirst("body");
        int localised = 0, failed = 0;
        if (body != null) {
            for (Element img : body.select("img[src]")) {
                String src = img.attr("abs:src");
                if (src.isEmpty() || src.startsWith("data:")) continue;
                try {
                    String local = downloadAsset(src, extracted, cfg.serveRoot());
                    if (local != null) { img.attr("src", local); localised++; }
                    else failed++;
                } catch (Exception ignored) { failed++; }
            }
            html = body.outerHtml();
        }

        // Write to disk
        Path postsDir = cfg.postsDir();
        Files.createDirectories(postsDir);
        Files.writeString(postsDir.resolve(slug + ".html"), html, StandardCharsets.UTF_8);
        Files.writeString(postsDir.resolve(slug + ".json"),
            MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(Map.of(
                "title",        extracted.getOrDefault("title", ""),
                "date",         extracted.getOrDefault("date", ""),
                "author",       extracted.getOrDefault("author", ""),
                "categories",   extracted.getOrDefault("categories", List.of()),
                "tags",         extracted.getOrDefault("tags", List.of()),
                "original_url", url)),
            StandardCharsets.UTF_8);

        Map<String, Object> r = new LinkedHashMap<>(extracted);
        r.remove("html");
        r.put("asset_localised", localised);
        r.put("asset_failed",    failed);
        r.put("wrote",           true);
        return r;
    }

    // ── Discovery helpers ─────────────────────────────────────────────────────

    private List<String> trySitemap(String base) {
        try {
            var r = get(base + "/sitemap.xml");
            if (r == null || r.statusCode() != 200 || !r.body().strip().startsWith("<")) return List.of();
            List<String> childUrls = parseSitemapIndexUrls(r.body());
            if (!childUrls.isEmpty()) {
                List<String> postUrls = new ArrayList<>();
                List<String> toFetch = childUrls.stream().filter(u -> u.toLowerCase().contains("post"))
                    .collect(Collectors.toList());
                if (toFetch.isEmpty()) toFetch = childUrls;
                for (String sm : toFetch) {
                    var cr = get(sm);
                    if (cr != null && cr.statusCode() == 200) postUrls.addAll(parseSitemapUrls(cr.body(), base));
                }
                return postUrls;
            }
            return parseSitemapUrls(r.body(), base);
        } catch (Exception ignored) { return List.of(); }
    }

    private List<String> tryWpRest(String base) {
        List<String> urls = new ArrayList<>();
        int page = 1;
        while (true) {
            try {
                var r = get(base + "/wp-json/wp/v2/posts?per_page=100&page=" + page + "&_fields=link");
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
            var r = get(base + "/feeds/posts/default?max-results=500&alt=rss");
            return (r != null && r.statusCode() == 200) ? parseFeedLinks(r.body()) : List.of();
        } catch (Exception ignored) { return List.of(); }
    }

    private List<String> tryGenericFeeds(String base) {
        for (String path : GENERIC_FEED_PATHS) {
            try {
                var r = get(base + path);
                if (r == null || r.statusCode() != 200 || !r.body().strip().startsWith("<")) continue;
                List<String> links = parseFeedLinks(r.body());
                if (!links.isEmpty()) return links;
            } catch (Exception ignored) {}
        }
        return List.of();
    }

    private Map<String, Object> fetchPostMeta(String url) throws Exception {
        var r = get(url);
        return (r != null && r.statusCode() == 200) ? extractMetadata(r.body(), url) : Map.of();
    }

    private String extractSiteName(String base) {
        try {
            var r = get(base);
            if (r != null && r.statusCode() == 200)
                return extractNameFromDoc(Jsoup.parse(r.body(), base), base);
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
            if (ext.length() > 6) ext = ""; // ignore suspicious extensions
            String date = String.valueOf(meta.getOrDefault("date", "unknown"));
            String hash = Integer.toHexString(src.hashCode());
            Path local  = serveRoot.resolve("legacy/assets/images/" + date + "/" + hash + ext);
            Files.createDirectories(local.getParent());
            if (Files.exists(local)) return "/legacy/assets/images/" + date + "/" + hash + ext;
            var req = HttpRequest.newBuilder(uri).header("User-Agent", USER_AGENT)
                .timeout(Duration.ofSeconds(TIMEOUT_SECS)).GET().build();
            HTTP.send(req, HttpResponse.BodyHandlers.ofFile(local));
            return "/legacy/assets/images/" + date + "/" + hash + ext;
        } catch (Exception ignored) { return null; }
    }

    HttpResponse<String> get(String url) throws Exception {
        var req = HttpRequest.newBuilder(URI.create(url))
            .header("User-Agent", USER_AGENT)
            .timeout(Duration.ofSeconds(TIMEOUT_SECS))
            .GET().build();
        return HTTP.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
    }

    // ── Static helpers (package-private for unit tests) ───────────────────────

    static String normaliseUrl(String url) {
        url = url.trim();
        if (url.startsWith("http://")) url = "https://" + url.substring(7);
        return url.replaceAll("/+$", "");
    }

    static String makeSlug(String date, String url) {
        String path = "";
        try { path = URI.create(url).getPath(); } catch (Exception ignored) {}
        String[] parts = path.split("/");
        String slug = "";
        for (int i = parts.length - 1; i >= 0; i--)
            if (!parts[i].isBlank()) { slug = parts[i]; break; }
        slug = slug.toLowerCase().replaceAll("[^a-z0-9-]", "-").replaceAll("-+", "-").replaceAll("^-|-$", "");
        if (slug.isBlank()) slug = Integer.toHexString(url.hashCode());
        return (date == null || date.isBlank() ? "" : date + "-") + slug;
    }

    static boolean isPostUrl(String url) {
        if (!url.startsWith("http://") && !url.startsWith("https://")) return false;
        try {
            String path = URI.create(url).getPath().toLowerCase();
            if (path.contains("..")) return false;
            Set<String> exclude = Set.of("category","tag","author","page","feed",
                "wp-content","wp-includes","wp-admin","comment-page","attachment");
            List<String> segs = Arrays.stream(path.split("/"))
                .filter(s -> !s.isBlank()).collect(Collectors.toList());
            if (segs.stream().anyMatch(exclude::contains)) return false;
            if (path.matches(".*/\\d{4}/.*")) return true;
            return !segs.isEmpty();
        } catch (Exception ignored) { return false; }
    }

    static List<String> parseSitemapUrls(String xml, String base) {
        try {
            Document doc = Jsoup.parse(xml, base, Parser.xmlParser());
            return doc.select("url > loc, urlset loc").stream()
                .map(e -> e.text().strip())
                .filter(IngestService::isPostUrl)
                .collect(Collectors.toList());
        } catch (Exception ignored) { return List.of(); }
    }

    static List<String> parseSitemapIndexUrls(String xml) {
        try {
            Document doc = Jsoup.parse(xml, "", Parser.xmlParser());
            if (doc.select("sitemap").isEmpty()) return List.of();
            return doc.select("sitemap > loc").stream().map(e -> e.text().strip()).collect(Collectors.toList());
        } catch (Exception ignored) { return List.of(); }
    }

    static List<String> parseFeedLinks(String xml) {
        try {
            Document doc = Jsoup.parse(xml, "", Parser.xmlParser());
            List<String> links = new ArrayList<>();
            for (Element item : doc.select("item")) {
                Element link = item.selectFirst("link");
                if (link != null && !link.text().isBlank()) links.add(link.text().strip());
            }
            for (Element entry : doc.select("entry")) {
                Element link = entry.selectFirst("link[href]");
                if (link != null && !link.attr("href").isBlank()) links.add(link.attr("href").strip());
            }
            return links;
        } catch (Exception ignored) { return List.of(); }
    }

    static List<String> parseWpRestLinks(String json) {
        try {
            JsonNode arr = MAPPER.readTree(json);
            List<String> links = new ArrayList<>();
            if (arr.isArray()) for (JsonNode item : arr) {
                String link = item.path("link").asText("");
                if (!link.isBlank()) links.add(link);
            }
            return links;
        } catch (Exception ignored) { return List.of(); }
    }

    static String normaliseDate(String raw) {
        if (raw == null || raw.isBlank()) return "";
        if (raw.length() >= 10 && raw.charAt(4) == '-' && raw.charAt(7) == '-') return raw.substring(0, 10);
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
                if (ld.has("@graph")) {
                    for (JsonNode n : ld.get("@graph")) if (extractFromLd(n, meta)) break;
                } else extractFromLd(ld, meta);
            } catch (Exception ignored) {}
        }

        // 2. OG/meta tags (fill gaps)
        if (meta.get("title").toString().isEmpty()) {
            Element og = doc.selectFirst("meta[property=og:title]");
            if (og != null) meta.put("title", og.attr("content").strip());
        }
        if (meta.get("date").toString().isEmpty()) {
            for (String sel : List.of("meta[property=article:published_time]",
                    "meta[name=date]","meta[name=pubdate]","time[datetime]")) {
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

        // 3. Title fallback
        if (meta.get("title").toString().isEmpty()) {
            Element t = doc.selectFirst("title");
            if (t != null) meta.put("title", t.text().strip());
        }
        return meta;
    }

    private static boolean extractFromLd(JsonNode ld, Map<String, Object> meta) {
        String type = ld.path("@type").asText("");
        if (!type.contains("BlogPosting") && !type.contains("Article") && !type.contains("Post")) return false;
        if (!ld.path("headline").asText("").isEmpty()) meta.put("title", ld.path("headline").asText("").strip());
        if (!ld.path("datePublished").asText("").isEmpty()) meta.put("date", normaliseDate(ld.path("datePublished").asText("")));
        JsonNode au = ld.path("author");
        if (!au.isMissingNode()) {
            String name = au.isTextual() ? au.asText() : au.path("name").asText("");
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
        "article",".entry-content",".post-content","#content","main",".content","[role=main]"
    };

    static Element findArticle(Document doc) {
        for (String sel : ARTICLE_SELECTORS) {
            Element e = doc.selectFirst(sel);
            if (e != null && !e.text().isBlank()) return e;
        }
        return doc.selectFirst("body");
    }

    private static final String[] JUNK_SELECTORS_INGEST = {
        "script","style","nav","header","footer",
        ".sidebar","#comments",".comments-area",
        ".author-box",".author-description",".author-info",
        ".sharedaddy",".addtoany_share_save_container",
        "[class*=wpDiscuz]","[class*=addtoany]",
        ".jp-relatedposts",".post-navigation",
        ".wpdiscuz-form-container",".entry-header",".entry-meta"
    };

    static void stripJunk(Element article) {
        for (String sel : JUNK_SELECTORS_INGEST) try { article.select(sel).remove(); } catch (Exception ignored) {}
        // Strip event handlers (XSS prevention)
        for (Element el : article.getAllElements()) {
            List<String> toRemove = el.attributes().asList().stream()
                .filter(a -> a.getKey().startsWith("on"))
                .map(org.jsoup.nodes.Attribute::getKey)
                .collect(Collectors.toList());
            toRemove.forEach(k -> el.removeAttr(k));
        }
    }
}
