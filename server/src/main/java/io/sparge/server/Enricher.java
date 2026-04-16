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
