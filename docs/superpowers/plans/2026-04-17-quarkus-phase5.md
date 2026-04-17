# Quarkus Phase 5 — Port enrich.py to Java (Enricher.java)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `scripts/enrich.py` to `Enricher.java`, replacing the `bridge.post_enrich_only` JEP call with a direct Java invocation in `PostsResource.scan()`.

**Architecture:** `Enricher.java` holds all enrichment operations. Static methods for pure DOM transforms (no HTTP); instance methods for HTTP-dependent operations. `java.net.http.HttpClient` is injected via a package-private constructor so tests can override `fetchUrl()` and `fetchJson()` without Mockito. The orchestrator `enrich()` calls all operations in the same order as Python's `enrich_post`, writes the enriched HTML, and returns stats that `StateStore.markEnriched()` understands.

**Tech Stack:** Java 21, Jsoup 1.18.3 (already on classpath), `java.net.http.HttpClient`, JUnit 5, `@QuarkusTest` + RestAssured.

**TDD layers:**
- **Unit:** `EnricherTest.java` — one test group per method, `MockEnricher` inner class for HTTP
- **Integration:** `EnricherIntegrationTest.java` — enrich a real KIE HTML file, skip when archive absent
- **E2E:** `EnrichEndpointTest.java` — scan a post with no enriched copy via `@QuarkusTest`

**Issues:** Tasks 1–7 commit under `Refs #57`. Task 8 commits under `Refs #58` / `Closes #58`, then closes #57 and epic #56.

---

## File Map

| File | Action |
|---|---|
| `server/src/main/java/io/sparge/server/Enricher.java` | Create |
| `server/src/test/java/io/sparge/server/EnricherTest.java` | Create |
| `server/src/test/java/io/sparge/server/EnricherIntegrationTest.java` | Create |
| `server/src/test/java/io/sparge/server/EnrichEndpointTest.java` | Create |
| `server/src/main/java/io/sparge/server/PostsResource.java` | Modify — replace bridge call at line 226 |
| `scripts/bridge.py` | Modify — remove `post_enrich_only` |
| `tests/test_enrich.py` | Move → `tests/python-legacy/test_enrich.py` |

---

## Task 1: Enricher.java skeleton + normaliseBrToNewlines

**Files:**
- Create: `server/src/test/java/io/sparge/server/EnricherTest.java`
- Create: `server/src/main/java/io/sparge/server/Enricher.java`

- [ ] **Step 1: Write failing tests — EnricherTest.java**

```java
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
```

- [ ] **Step 2: Run tests — expect compile failure (Enricher does not exist)**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherTest -q 2>&1 | tail -10
```

Expected: compilation error — `cannot find symbol: class Enricher`

- [ ] **Step 3: Create Enricher.java with skeleton + normaliseBrToNewlines**

```java
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
            return resp.statusCode() == 200 ? resp.body() : null;
        } catch (Exception e) { return null; }
    }

    // ── Orchestrator (implemented in Task 7) ──────────────────────────────────

    public Map<String, Integer> enrich(Path htmlPath, Path enrichedPath,
                                       Path assetsDir, String githubToken) throws Exception {
        throw new UnsupportedOperationException("implemented in Task 7");
    }
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherTest#brInsidePreReplacedWithNewline+brOutsidePreNotCounted+preWithoutBrNotCounted -q 2>&1 | tail -5
```

Expected: `BUILD SUCCESS`

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge && git add server/src/main/java/io/sparge/server/Enricher.java \
  server/src/test/java/io/sparge/server/EnricherTest.java
git commit -m "feat(#57): Enricher.java skeleton + normaliseBrToNewlines (3 tests)"
```

---

## Task 2: normaliseCodeClasses

**Files:**
- Modify: `server/src/test/java/io/sparge/server/EnricherTest.java`
- Modify: `server/src/main/java/io/sparge/server/Enricher.java`

- [ ] **Step 1: Add tests to EnricherTest.java — after the normaliseBrToNewlines block**

```java
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherTest -q 2>&1 | tail -5
```

Expected: FAIL — `cannot find symbol: method normaliseCodeClasses`

- [ ] **Step 3: Add BRUSH_MAP + normaliseCodeClasses to Enricher.java — after the normaliseBrToNewlines method**

```java
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
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherTest -q 2>&1 | tail -5
```

Expected: `BUILD SUCCESS`

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge && git add server/src/main/java/io/sparge/server/Enricher.java \
  server/src/test/java/io/sparge/server/EnricherTest.java
git commit -m "feat(#57): normaliseCodeClasses — brush:X → language-X (6 tests)"
```

---

## Task 3: detectCodeLanguages

**Files:**
- Modify: `server/src/test/java/io/sparge/server/EnricherTest.java`
- Modify: `server/src/main/java/io/sparge/server/Enricher.java`

- [ ] **Step 1: Add tests to EnricherTest.java**

```java
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherTest -q 2>&1 | tail -5
```

- [ ] **Step 3: Add LANG_PATTERNS + detectCodeLanguages to Enricher.java — after normaliseCodeClasses**

```java
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
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherTest -q 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge && git add server/src/main/java/io/sparge/server/Enricher.java \
  server/src/test/java/io/sparge/server/EnricherTest.java
git commit -m "feat(#57): detectCodeLanguages — 8-pattern heuristic detection (6 tests)"
```

---

## Task 4: replaceEmbedFallbacks

**Files:**
- Modify: `server/src/test/java/io/sparge/server/EnricherTest.java`
- Modify: `server/src/main/java/io/sparge/server/Enricher.java`

- [ ] **Step 1: Add tests**

```java
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherTest -q 2>&1 | tail -5
```

- [ ] **Step 3: Add replaceEmbedFallbacks to Enricher.java**

```java
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
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherTest -q 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge && git add server/src/main/java/io/sparge/server/Enricher.java \
  server/src/test/java/io/sparge/server/EnricherTest.java
git commit -m "feat(#57): replaceEmbedFallbacks — wrap remaining iframes/objects/embeds (4 tests)"
```

---

## Task 5: replaceYoutubeEmbeds

**Files:**
- Modify: `server/src/test/java/io/sparge/server/EnricherTest.java`
- Modify: `server/src/main/java/io/sparge/server/Enricher.java`

- [ ] **Step 1: Add tests — MockEnricher already defined in Task 1**

```java
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
        MockEnricher e = new MockEnricher(); // no mocked bytes — fetchUrl returns null
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherTest -q 2>&1 | tail -5
```

- [ ] **Step 3: Add youtubeVideoId + replaceYoutubeEmbeds to Enricher.java**

```java
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
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherTest -q 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge && git add server/src/main/java/io/sparge/server/Enricher.java \
  server/src/test/java/io/sparge/server/EnricherTest.java
git commit -m "feat(#57): replaceYoutubeEmbeds — thumbnail download + figure replacement (5 tests)"
```

---

## Task 6: replaceGistEmbeds

**Files:**
- Modify: `server/src/test/java/io/sparge/server/EnricherTest.java`
- Modify: `server/src/main/java/io/sparge/server/Enricher.java`

- [ ] **Step 1: Add tests**

```java
    // ── replaceGistEmbeds ─────────────────────────────────────────────────────

    @Test
    void gistScriptReplacedWithCodeFigure() throws Exception {
        MockEnricher e = new MockEnricher();
        e.mockJson("https://api.github.com/gists/abc123",
                   "{\"files\":{\"Foo.java\":{\"content\":\"System.out.println();\",\"language\":\"Java\"}}}");

        Element a = article("<script src=\"https://gist.github.com/user/abc123.js\"></script>");
        int[] stats = e.replaceGistEmbeds(a, "");

        assertEquals(1, stats[0], "replaced count");
        assertEquals(0, stats[1], "failed count");
        assertNull(a.selectFirst("script"), "script replaced");
        Element fig = a.selectFirst("figure.gist-embed");
        assertNotNull(fig);
        assertTrue(fig.selectFirst("code").hasClass("language-java"));
        assertTrue(fig.selectFirst("code").text().contains("System.out.println"));
    }

    @Test
    void gistApiFailureProducesArchiveNoteFigure() throws Exception {
        MockEnricher e = new MockEnricher(); // fetchJson returns null
        Element a = article("<script src=\"https://gist.github.com/user/fail123.js\"></script>");
        int[] stats = e.replaceGistEmbeds(a, "");

        assertEquals(0, stats[0]);
        assertEquals(1, stats[1], "failed count");
        Element fig = a.selectFirst("figure.gist-embed");
        assertNotNull(fig);
        assertTrue(fig.text().contains("could not be retrieved"), "archive note on failure");
    }

    @Test
    void nonGistScriptNotReplaced() throws Exception {
        MockEnricher e = new MockEnricher();
        Element a = article("<script src=\"https://example.com/script.js\"></script>");
        e.replaceGistEmbeds(a, "");
        assertNotNull(a.selectFirst("script"), "non-gist script untouched");
    }

    @Test
    void gistWithoutUserParsedCorrectly() throws Exception {
        MockEnricher e = new MockEnricher();
        e.mockJson("https://api.github.com/gists/nouserid",
                   "{\"files\":{\"a.txt\":{\"content\":\"hello\",\"language\":\"Text\"}}}");
        Element a = article("<script src=\"https://gist.github.com/nouserid.js\"></script>");
        int[] stats = e.replaceGistEmbeds(a, "");
        assertEquals(1, stats[0]);
        assertTrue(a.selectFirst("figure.gist-embed").selectFirst("a").attr("href")
                    .contains("nouserid"), "link uses gist id");
    }
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherTest -q 2>&1 | tail -5
```

- [ ] **Step 3: Add gistIdFromSrc + replaceGistEmbeds to Enricher.java**

```java
    // ── replaceGistEmbeds ─────────────────────────────────────────────────────

    // Returns [user, gistId] or null if not a gist URL; user may be null.
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
                return fig.appendChild(cap).parent().appendChild(pre).parent();
            }
        } catch (Exception ignored) {}
        // Fallback figure if JSON parse fails
        Element fig = new Element("figure").addClass("gist-embed");
        fig.appendChild(new Element("p").addClass("archive-note")
                .text("Gist embed could not be retrieved."));
        return fig;
    }
```

> **Note on imports:** `buildGistFigure` uses `com.fasterxml.jackson.databind.ObjectMapper` which is already on the Quarkus classpath (quarkus-rest-jackson dependency).

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherTest -q 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge && git add server/src/main/java/io/sparge/server/Enricher.java \
  server/src/test/java/io/sparge/server/EnricherTest.java
git commit -m "feat(#57): replaceGistEmbeds — GitHub API inlining + fallback figure (4 tests)"
```

---

## Task 7: enrich() orchestrator + EnricherIntegrationTest

**Files:**
- Modify: `server/src/main/java/io/sparge/server/Enricher.java`
- Create: `server/src/test/java/io/sparge/server/EnricherIntegrationTest.java`

- [ ] **Step 1: Create EnricherIntegrationTest.java**

```java
package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration test: enrich a real KIE HTML file.
 * Skipped when the KIE archive is not present.
 */
class EnricherIntegrationTest {

    private static final Path KIE_POSTS = Paths.get(
            System.getProperty("user.home"),
            "mdproctor.github.io/legacy/posts/mark-proctor");

    private static final Path KIE_ASSETS = Paths.get(
            System.getProperty("user.home"),
            "mdproctor.github.io/legacy/assets");

    static boolean kieArchivePresent() {
        return Files.isDirectory(KIE_POSTS);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void enrichWritesEnrichedFile(@TempDir Path tempDir) throws Exception {
        Path htmlPath     = Files.list(KIE_POSTS)
                .filter(p -> p.toString().endsWith(".html"))
                .findFirst()
                .orElseThrow(() -> new RuntimeException("No HTML in KIE archive"));
        Path enrichedPath = tempDir.resolve("enriched.html");
        Path assetsDir    = Files.isDirectory(KIE_ASSETS) ? KIE_ASSETS : tempDir.resolve("assets");
        Files.createDirectories(assetsDir);

        Map<String, Integer> stats = new Enricher().enrich(htmlPath, enrichedPath, assetsDir, "");

        assertTrue(Files.exists(enrichedPath), "enriched file written");
        assertTrue(Files.size(enrichedPath) > 0, "enriched file not empty");
        assertNotNull(stats);
        assertTrue(stats.containsKey("youtube_replaced"), "stats has youtube_replaced key");
        assertTrue(stats.containsKey("gists_replaced"),   "stats has gists_replaced key");
        assertTrue(stats.containsKey("embeds_wrapped"),   "stats has embeds_wrapped key");
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void enrichTenPostsAllSucceed(@TempDir Path tempDir) throws Exception {
        Path assetsDir = Files.createDirectories(tempDir.resolve("assets"));
        Enricher enricher = new Enricher();
        long count = Files.list(KIE_POSTS)
                .filter(p -> p.toString().endsWith(".html"))
                .limit(10)
                .peek(p -> {
                    try {
                        Path out = tempDir.resolve(p.getFileName());
                        enricher.enrich(p, out, assetsDir, "");
                        assertTrue(Files.exists(out), "output written for " + p.getFileName());
                    } catch (Exception e) {
                        throw new RuntimeException("enrich failed for " + p.getFileName(), e);
                    }
                }).count();
        assertTrue(count > 0, "at least one post enriched");
    }
}
```

- [ ] **Step 2: Run integration tests — expect failure (enrich() throws UnsupportedOperationException)**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnricherIntegrationTest -q 2>&1 | tail -10
```

- [ ] **Step 3: Replace the UnsupportedOperationException stub in Enricher.java with full enrich() implementation**

Replace the `enrich()` stub entirely:

```java
    public Map<String, Integer> enrich(Path htmlPath, Path enrichedPath,
                                       Path assetsDir, String githubToken) throws Exception {
        org.jsoup.nodes.Document soup = Jsoup.parse(htmlPath.toFile(), "UTF-8");
        Element article = soup.selectFirst("article");
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
```

- [ ] **Step 4: Run all Enricher tests — expect PASS**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest="EnricherTest,EnricherIntegrationTest" -q 2>&1 | tail -10
```

- [ ] **Step 5: Run full test suite — no regressions**

```bash
cd ~/claude/sparge/server && mvn test -q 2>&1 | tail -10
```

Expected: `BUILD SUCCESS`

- [ ] **Step 6: Commit**

```bash
cd ~/claude/sparge && git add server/src/main/java/io/sparge/server/Enricher.java \
  server/src/test/java/io/sparge/server/EnricherIntegrationTest.java
git commit -m "feat(#57): enrich() orchestrator + integration test — Enricher.java complete"
```

---

## Task 8: Wire PostsResource + remove bridge call + E2E test + retire Python test (Issue #58)

**Files:**
- Create: `server/src/test/java/io/sparge/server/EnrichEndpointTest.java`
- Modify: `server/src/main/java/io/sparge/server/PostsResource.java`
- Modify: `scripts/bridge.py`
- Move: `tests/test_enrich.py` → `tests/python-legacy/test_enrich.py`

- [ ] **Step 1: Create EnrichEndpointTest.java**

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

/**
 * E2E test: scanning a post triggers Java enrichment when no enriched copy exists.
 * Skipped when the KIE archive is not present.
 */
@QuarkusTest
class EnrichEndpointTest {

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
            System.err.println("Warning: could not activate project: " + e.getMessage());
        }
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanWithNoEnrichedCopySucceeds() {
        // Pick a slug that may or may not have an enriched copy — scan should succeed either way
        String slug = given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");

        given().contentType("application/json")
                .when().post("/api/posts/" + slug + "/scan")
                .then()
                .statusCode(200)
                .body("slug", equalTo(slug))
                .body("html",   notNullValue())
                .body("assets", notNullValue());
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanReturnsJsonWithNoErrors() {
        String slug = given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");

        given().contentType("application/json")
                .when().post("/api/posts/" + slug + "/scan")
                .then()
                .statusCode(200)
                .contentType(containsString("application/json"));
    }
}
```

- [ ] **Step 2: Run E2E test — expect PASS (scan already works, this just confirms the endpoint)**

```bash
cd ~/claude/sparge/server && mvn test -pl . -Dtest=EnrichEndpointTest -q 2>&1 | tail -10
```

- [ ] **Step 3: Replace bridge call in PostsResource.java**

Find this block (around line 222–227):

```java
            // Enrich if not yet enriched — still Python (enrich.py ported in Phase 5)
            if (!java.nio.file.Files.exists(enrichedPath)) {
                bridge.call("bridge.post_enrich_only", slug);
            }
```

Replace with:

```java
            // Enrich if not yet enriched (Java — Enricher.java, Phase 5)
            if (!java.nio.file.Files.exists(enrichedPath)) {
                try {
                    Map<String, Integer> enrichStats = new Enricher().enrich(
                            htmlPath, enrichedPath, cfg.assetsDir(), cfg.githubToken());
                    stateStore.markEnriched(slug, new java.util.HashMap<>(enrichStats));
                } catch (Exception enrichEx) {
                    System.err.println("Warning: enrichment failed for " + slug + ": " + enrichEx.getMessage());
                }
            }
```

- [ ] **Step 4: Add `import java.util.Map;` if not already present at top of PostsResource.java**

Check top of file — `import java.util.Map;` should already be there (it is, from existing code).

- [ ] **Step 5: Run full test suite — no regressions**

```bash
cd ~/claude/sparge/server && mvn test -q 2>&1 | tail -10
```

Expected: `BUILD SUCCESS`

- [ ] **Step 6: Remove post_enrich_only from bridge.py**

Find and delete this entire function (lines ~248–262 in bridge.py):

```python
def post_enrich_only(slug: str) -> str:
    """Enrich a post — called by Java PostsResource.scan() when enriched copy absent."""
    if not _can_enrich:
        return _ok({'enriched': False, 'reason': 'enrich not available'})
    ...
    except Exception as ex:
        return _err(500, str(ex))
```

Also remove these lines from `bridge_init()` (if they reference enrich loading):

```python
    global _can_enrich, _enrich_post
    ...
        from scripts.enrich import enrich_post as _ep
        _enrich_post = _ep; _can_enrich = True
```

And remove the module-level declarations:
```python
_can_enrich       = False; _enrich_post  = None
```

- [ ] **Step 7: Run Python tests — no regressions**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --ignore=tests/python-legacy 2>&1 | tail -10
```

Expected: same pass/skip counts as before (290 passing, N skipped, 0 failing).

- [ ] **Step 8: Move Python enrich tests to python-legacy**

```bash
cd ~/claude/sparge && mv tests/test_enrich.py tests/python-legacy/test_enrich.py
```

- [ ] **Step 9: Run Python tests again — confirm count unchanged (tests/python-legacy is not collected)**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --ignore=tests/python-legacy 2>&1 | tail -5
```

- [ ] **Step 10: Commit and close issues**

```bash
cd ~/claude/sparge && git add \
  server/src/main/java/io/sparge/server/PostsResource.java \
  server/src/test/java/io/sparge/server/EnrichEndpointTest.java \
  scripts/bridge.py \
  tests/python-legacy/test_enrich.py
git commit -m "feat(#58): wire PostsResource.scan() to Java Enricher — remove post_enrich_only bridge call

Closes #58, Closes #57, Closes #56"
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Task |
|---|---|
| `normaliseBrToNewlines` | Task 1 |
| `normaliseCodeClasses` with brush map | Task 2 |
| `detectCodeLanguages` with 8 patterns | Task 3 |
| `replaceEmbedFallbacks` | Task 4 |
| `replaceYoutubeEmbeds` — thumbnail download, figure, fallback | Task 5 |
| `replaceGistEmbeds` — GitHub API, fallback figure | Task 6 |
| `enrich()` orchestrator — correct order, write file, return stats | Task 7 |
| Integration test on real KIE files | Task 7 |
| `StateStore.markEnriched()` called after enrich | Task 8 |
| `bridge.post_enrich_only` removed | Task 8 |
| E2E `@QuarkusTest` for scan-with-enrich path | Task 8 |
| `tests/test_enrich.py` retired to python-legacy | Task 8 |

**Type/method consistency:**
- `Enricher.normaliseBrToNewlines(Element)` — used in Task 1, Task 7 ✓
- `Enricher.normaliseCodeClasses(Element)` — Task 2, Task 7 ✓
- `Enricher.detectCodeLanguages(Element)` — Task 3, Task 7 ✓
- `Enricher.replaceEmbedFallbacks(Element)` — Task 4, Task 7 ✓
- `enricher.replaceYoutubeEmbeds(Element, Path)` — Task 5, Task 7 ✓
- `enricher.replaceGistEmbeds(Element, String)` returns `int[]` — Task 6, Task 7 ✓
- `enricher.enrich(Path, Path, Path, String)` returns `Map<String,Integer>` — Task 7, Task 8 ✓
- `stateStore.markEnriched(slug, Map<String,Object>)` — Task 8, matches StateStore.java signature ✓
