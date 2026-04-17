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
        throw new UnsupportedOperationException("implemented in Task 7");
    }
}
