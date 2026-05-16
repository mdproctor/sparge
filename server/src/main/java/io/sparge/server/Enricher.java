package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.nodes.TextNode;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

public class Enricher {

    private final HttpClient http;

    public Enricher() {
        this.http = HttpClient.newHttpClient();
    }

    // Package-private: allows tests to subclass and override fetchUrl/fetchJson
    Enricher(HttpClient http) {
        this.http = http;
    }

    // ── normaliseBrToNewlines ─────────────────────────────────────────────────

    static int normaliseBrToNewlines(Element article) {
        int count = 0;
        for (Element pre : article.select("pre")) {
            var brs = pre.select("br");
            if (!brs.isEmpty()) {
                for (Element br : brs) br.replaceWith(new TextNode("\n"));
                count++;
            }
        }
        return count;
    }

    // ── normaliseCodeClasses ──────────────────────────────────────────────────

    private static final Pattern BRUSH_RE =
            Pattern.compile("\\bbrush\\s*:\\s*(\\w+)\\b", Pattern.CASE_INSENSITIVE);

    private static final Map<String, String> BRUSH_MAP;
    static {
        Map<String, String> m = new LinkedHashMap<>();
        m.put("jscript", "javascript"); m.put("js", "javascript");
        m.put("csharp",  "csharp");     m.put("c#", "csharp");
        m.put("c++",     "cpp");        m.put("cplusplus", "cpp");
        m.put("plain",   "plaintext");  m.put("text", "plaintext");
        m.put("shell",   "bash");       m.put("sh",  "bash");
        m.put("drl",     "drl");
        BRUSH_MAP = Collections.unmodifiableMap(m);
    }

    static int normaliseCodeClasses(Element article) {
        int count = 0;
        for (Element pre : article.select("pre")) {
            String classAttr = String.join(" ", pre.classNames());
            Matcher m = BRUSH_RE.matcher(classAttr);
            if (!m.find()) continue;

            String langToken = m.group(1).toLowerCase();
            String lang = BRUSH_MAP.getOrDefault(langToken, langToken);

            Set<String> newClasses = pre.classNames().stream()
                    .filter(c -> !BRUSH_RE.matcher(c).find())
                    .filter(c -> !c.toLowerCase().startsWith("brush"))
                    .filter(c -> !BRUSH_MAP.containsKey(c.toLowerCase()))
                    .filter(c -> !c.toLowerCase().equals(langToken))
                    .collect(Collectors.toCollection(LinkedHashSet::new));
            newClasses.add("language-" + lang);
            pre.classNames(newClasses);

            Element code = pre.selectFirst("code");
            if (code != null) {
                Set<String> codeClasses = code.classNames().stream()
                        .filter(c -> !c.startsWith("language-"))
                        .collect(Collectors.toCollection(LinkedHashSet::new));
                codeClasses.add("language-" + lang);
                code.classNames(codeClasses);
            }
            count++;
        }
        return count;
    }

    // ── detectCodeLanguages ───────────────────────────────────────────────────

    private static final List<Map.Entry<String, List<String>>> LANG_PATTERNS = List.of(
        Map.entry("java",       List.of("\\bpublic\\s+class\\b",
                                        "\\bpublic\\s+static\\s+void\\s+main\\b",
                                        "\\bimport\\s+java\\.")),
        Map.entry("xml",        List.of("<\\?xml\\s", "xmlns=")),
        Map.entry("html",       List.of("<!DOCTYPE\\s+html", "<html[\\s>]")),
        Map.entry("sql",        List.of("\\bSELECT\\b.+\\bFROM\\b",
                                        "\\bCREATE\\s+TABLE\\b",
                                        "\\bINSERT\\s+INTO\\b")),
        Map.entry("python",     List.of("\\bdef\\s+\\w+\\s*\\(",
                                        "\\bimport\\s+\\w+",
                                        "\\bprint\\s*\\(")),
        Map.entry("javascript", List.of("\\bfunction\\s+\\w+\\s*\\(",
                                        "\\bconst\\s+\\w+\\s*=",
                                        "=>")),
        Map.entry("bash",       List.of("^#!.*\\bsh\\b", "\\$\\{?\\w+\\}?")),
        Map.entry("drl",        List.of("\\brule\\s+\"", "\\bwhen\\b.*\\bthen\\b", "\\bend\\b")));

    static int detectCodeLanguages(Element article) {
        int count = 0;
        for (Element pre : article.select("pre")) {
            Element code = pre.selectFirst("code");
            if (code == null) continue;
            boolean hasLang = code.classNames().stream().anyMatch(c -> c.startsWith("language-"))
                           || pre.classNames().stream().anyMatch(c -> c.startsWith("language-"));
            if (hasLang) continue;

            String text = code.wholeText();
            String detected = null;
            outer:
            for (Map.Entry<String, List<String>> entry : LANG_PATTERNS) {
                for (String pattern : entry.getValue()) {
                    if (Pattern.compile(pattern, Pattern.MULTILINE | Pattern.CASE_INSENSITIVE)
                               .matcher(text).find()) {
                        detected = entry.getKey();
                        break outer;
                    }
                }
            }
            if (detected != null) {
                Set<String> classes = new LinkedHashSet<>(code.classNames());
                classes.add("language-" + detected);
                code.classNames(classes);
                count++;
            }
        }
        return count;
    }

    // ── replaceEmbedFallbacks ─────────────────────────────────────────────────

    static int replaceEmbedFallbacks(Element article) {
        int count = 0;
        for (Element tag : article.select("iframe, object, embed")) {
            String src = tag.attr("src");
            if (src.isEmpty()) src = tag.attr("data");

            Element fig = new Element("figure").addClass("live-embed");
            Element p   = new Element("p").addClass("archive-note");
            p.appendText("This embed could not be captured in the archive. Original source: ");
            if (!src.isEmpty()) {
                p.appendChild(new Element("a")
                        .attr("href", src).attr("target", "_blank").attr("rel", "noopener")
                        .text(src));
            } else {
                p.appendText("unknown source");
            }
            fig.appendChild(p);
            tag.replaceWith(fig);
            count++;
        }
        return count;
    }

    // ── replaceYoutubeEmbeds ──────────────────────────────────────────────────

    private static String youtubeVideoId(String url) {
        if (url == null || url.isEmpty()) return null;
        try {
            URI uri = URI.create(url);
            String host = uri.getHost() != null
                    ? uri.getHost().toLowerCase().replace("www.", "") : "";
            String path = uri.getPath() != null ? uri.getPath() : "";
            if ("youtu.be".equals(host)) {
                String id = path.replaceFirst("^/+", "").split("/")[0];
                return id.isEmpty() ? null : id;
            }
            if ("youtube.com".equals(host) || "youtube-nocookie.com".equals(host)) {
                if (path.contains("/embed/")) {
                    String[] parts = path.split("/embed/");
                    if (parts.length > 1) {
                        String id = parts[1].split("/")[0].split("\\?")[0];
                        return id.isEmpty() ? null : id;
                    }
                }
                String query = uri.getRawQuery();
                if (query != null) {
                    for (String param : query.split("&")) {
                        if (param.startsWith("v=")) {
                            String id = param.substring(2);
                            return id.isEmpty() ? null : id;
                        }
                    }
                }
            }
        } catch (Exception ignored) {}
        return null;
    }

    int replaceYoutubeEmbeds(Element article, Path assetsDir) throws Exception {
        int replaced = 0;
        for (Element iframe : article.select("iframe")) {
            String src = iframe.attr("src");
            String videoId = youtubeVideoId(src);
            if (videoId == null) continue;

            String thumbName = downloadThumbnail(videoId, assetsDir);
            String watchUrl  = "https://www.youtube.com/watch?v=" + videoId;

            Element fig = new Element("figure").addClass("video-embed");
            Element a   = new Element("a")
                    .attr("href", watchUrl).attr("target", "_blank").attr("rel", "noopener");
            a.appendChild(new Element("img")
                    .attr("src", thumbName != null ? thumbName : "")
                    .attr("alt", "YouTube video")
                    .attr("style", "max-width:100%"));
            a.appendChild(new Element("figcaption").text("\u25B6 Watch on YouTube"));
            fig.appendChild(a);
            iframe.replaceWith(fig);
            replaced++;
        }
        return replaced;
    }

    private String downloadThumbnail(String videoId, Path assetsDir) {
        Path dest = assetsDir.resolve("yt_" + videoId + ".jpg");
        if (Files.exists(dest)) return dest.getFileName().toString();
        for (String quality : new String[]{"maxresdefault", "hqdefault"}) {
            String url = "https://img.youtube.com/vi/" + videoId + "/" + quality + ".jpg";
            byte[] body = fetchUrl(url);
            if (body != null && body.length > 0) {
                try {
                    Files.createDirectories(assetsDir);
                    Files.write(dest, body);
                    return dest.getFileName().toString();
                } catch (Exception ignored) {}
            }
        }
        return null;
    }

    // ── replaceGistEmbeds ─────────────────────────────────────────────────────

    // Returns [user, gistId] or null if not a valid gist script URL; user may be null.
    private static String[] gistIdFromSrc(String src) {
        try {
            URI uri = URI.create(src);
            String host = uri.getHost();
            if (host == null || !host.contains("gist.github.com")) return null;
            String path = uri.getPath().replaceAll("^/+", "").replaceAll("/+$", "");
            if (path.isEmpty()) return null;
            String[] parts = path.split("/");
            if (parts.length >= 2) {
                String gid = parts[1].endsWith(".js")
                        ? parts[1].substring(0, parts[1].length() - 3) : parts[1];
                return gid.isEmpty() ? null : new String[]{parts[0], gid};
            }
            String gid = parts[0].endsWith(".js")
                    ? parts[0].substring(0, parts[0].length() - 3) : parts[0];
            return gid.isEmpty() ? null : new String[]{null, gid};
        } catch (Exception e) { return null; }
    }

    // Returns [replaced, failed]
    int[] replaceGistEmbeds(Element article, String githubToken) throws Exception {
        int replaced = 0, failed = 0;
        for (Element script : article.select("script")) {
            String src   = script.attr("src");
            String[] ids = gistIdFromSrc(src);
            if (ids == null) continue;

            String user   = ids[0];
            String gistId = ids[1];
            String gistUrl = user != null
                    ? "https://gist.github.com/" + user + "/" + gistId
                    : "https://gist.github.com/" + gistId;

            String json = fetchJson("https://api.github.com/gists/" + gistId, githubToken);
            Element fig;
            if (json == null) {
                fig = new Element("figure").addClass("gist-embed");
                Element p = new Element("p").addClass("archive-note");
                p.appendText("Gist embed could not be retrieved. ");
                p.appendChild(new Element("a").attr("href", gistUrl)
                        .attr("target", "_blank").attr("rel", "noopener")
                        .text("View original on GitHub Gist"));
                p.appendText(".");
                fig.appendChild(p);
                failed++;
            } else {
                fig = buildGistFigure(gistUrl, json);
                replaced++;
            }
            script.replaceWith(fig);
        }
        return new int[]{replaced, failed};
    }

    private static Element buildGistFigure(String gistUrl, String json) {
        try {
            com.fasterxml.jackson.databind.JsonNode root =
                    new com.fasterxml.jackson.databind.ObjectMapper().readTree(json);
            com.fasterxml.jackson.databind.JsonNode files = root.path("files");
            if (!files.isMissingNode() && files.fields().hasNext()) {
                Map.Entry<String, com.fasterxml.jackson.databind.JsonNode> first =
                        files.fields().next();
                String filename = first.getKey();
                String content  = first.getValue().path("content").asText("");
                String language = first.getValue().path("language").asText("text").toLowerCase();

                Element fig = new Element("figure").addClass("gist-embed");
                Element cap = new Element("figcaption");
                cap.appendChild(new Element("a").attr("href", gistUrl)
                        .attr("target", "_blank").attr("rel", "noopener")
                        .text("View on GitHub Gist: " + filename));
                Element pre  = new Element("pre");
                Element code = new Element("code").addClass("language-" + language).text(content);
                pre.appendChild(code);
                fig.appendChild(cap);
                fig.appendChild(pre);
                return fig;
            }
        } catch (Exception ignored) {}
        // Fallback figure if JSON parse fails
        Element fig = new Element("figure").addClass("gist-embed");
        fig.appendChild(new Element("p").addClass("archive-note")
                .text("Gist embed could not be retrieved."));
        return fig;
    }

    // ── HTTP helpers (package-private — overridden in MockEnricher) ───────────

    byte[] fetchUrl(String url) {
        try {
            HttpRequest req = HttpRequest.newBuilder(URI.create(url)).build();
            HttpResponse<byte[]> resp = http.send(req, HttpResponse.BodyHandlers.ofByteArray());
            return resp.statusCode() == 200 && resp.body().length > 0 ? resp.body() : null;
        } catch (Exception e) { return null; }
    }

    String fetchJson(String url, String token) {
        try {
            HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(url))
                    .header("Accept", "application/vnd.github+json");
            if (token != null && !token.isEmpty())
                b.header("Authorization", "Bearer " + token);
            HttpResponse<String> resp = http.send(b.build(), HttpResponse.BodyHandlers.ofString());
            String body = resp.body();
            return resp.statusCode() == 200 && !body.isEmpty() ? body : null;
        } catch (Exception e) { return null; }
    }

    // ── Orchestrator (implemented in Task 7) ──────────────────────────────────

    public Map<String, Integer> enrich(Path htmlPath, Path enrichedPath,
                                       Path assetsDir, String githubToken) throws Exception {
        org.jsoup.nodes.Document soup = Jsoup.parse(htmlPath.toFile(), "UTF-8");
        Element article = soup.selectFirst("article");
        // If the article element exists but is blank, fall back to body — same
        // logic as IngestService.findArticle(). An empty <article> is not usable
        // as enrichment input and causes corrupt output on re-serialisation.
        if (article != null && article.text().isBlank()) article = null;
        if (article == null) article = soup.body();
        if (article == null) article = soup.root();

        Map<String, Integer> stats = new LinkedHashMap<>();
        stats.put("youtube_replaced", replaceYoutubeEmbeds(article, assetsDir));
        int[] gistStats = replaceGistEmbeds(article, githubToken);
        stats.put("gists_replaced",    gistStats[0]);
        stats.put("gists_failed",      gistStats[1]);
        stats.put("pre_br_normalised", normaliseBrToNewlines(article));
        stats.put("classes_normalised",normaliseCodeClasses(article));
        stats.put("languages_detected",detectCodeLanguages(article));
        stats.put("embeds_wrapped",    replaceEmbedFallbacks(article));

        Files.createDirectories(enrichedPath.getParent());
        Files.writeString(enrichedPath, soup.outerHtml());
        return stats;
    }
}
