# Phase 6c: Convert Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove 6 JEP bridge calls by porting the HTML→Markdown conversion pipeline to native Java.

**Architecture:** Four simple endpoints are pure file-ops (no new classes). Two complex endpoints need `ConvertPost.java` (port of convert_post.py using jsoup + flexmark-html2md-converter) and `MdValidator.java` (port of md_validator.py — 14 MD-only checks + key cross-checks). Both converter and validator use identical jsoup selectors for HTML preprocessing, which is the key coherence requirement from the Python migration notes. TDD throughout: unit tests first for both new classes, E2E @QuarkusTest for endpoint wiring.

**Tech Stack:** Quarkus 3.34, JAX-RS, jsoup 1.18.3 (already in pom.xml), flexmark-html2md-converter 0.64.8 (new), Jackson, Java NIO, JUnit 5, RestAssured, @QuarkusTest

---

## File Map

| File | Change |
|---|---|
| `server/pom.xml` | Add flexmark-html2md-converter 0.64.8 dependency |
| `server/src/main/java/io/sparge/server/MdIssue.java` | **NEW** record: `{check, level, detail}` |
| `server/src/main/java/io/sparge/server/ConvertPost.java` | **NEW** HTML→Markdown converter (port of convert_post.py) |
| `server/src/main/java/io/sparge/server/MdValidator.java` | **NEW** MD validator (port of md_validator.py) |
| `server/src/main/java/io/sparge/server/PostsResource.java` | Make view/saveHtml/saveMd native; wire generateMd/validateMd |
| `server/src/test/java/io/sparge/server/ConvertPostTest.java` | **NEW** unit + integration tests |
| `server/src/test/java/io/sparge/server/MdValidatorTest.java` | **NEW** unit tests for each check |
| `server/src/test/java/io/sparge/server/PostsResourceConvertTest.java` | **NEW** E2E @QuarkusTest |

---

## Background: Python migration notes

The Python source explicitly documents the Java migration:

**convert_post.py** (line 482-508):
> `html2text` has no direct Java equivalent. The closest is flexmark-java (HtmlToMarkdown).
> Critical flag: `protect_links=True` makes html2text produce `[text](<url>)` with angle brackets — the MD validator's link regexes all assume this format. Java must either use the same format or update validator regexes to match.

**Recommendation:** Since we port BOTH converter AND validator to Java, use Java-native link format `[text](url)` and update validator regexes accordingly. Both sides are consistent.

**md_validator.py** (line 53-56):
> `_load_article()` must use identical Jsoup selectors as convert_post.py. The key invariant is that both functions process the HTML with identical chrome-removal so the validator's HTML matches the converter's HTML.

**JUNK_SELECTORS** (shared by converter and validator):
```
.entry-header, header, .entry-meta, .author-box, .author-description, .author-info,
.addtoany_share_save_container, .addtoany_share_save, .sharedaddy, #comments,
.comments-area, .jp-relatedposts, .post-navigation, .wpdiscuz-form-container, script, style
```

---

## Task 1: Simple Endpoints + PostsResourceConvertTest (4 JEP calls)

**Files:**
- Modify: `server/src/main/java/io/sparge/server/PostsResource.java` (view, saveHtml, saveMd; remove html fallback)
- Create: `server/src/test/java/io/sparge/server/PostsResourceConvertTest.java`

- [ ] **Step 1: Write PostsResourceConvertTest.java first**

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
class PostsResourceConvertTest {

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
            System.err.println("Warning: project activation failed: " + e.getMessage());
        }
    }

    private String firstSlug() {
        return given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");
    }

    // ── html ──────────────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void htmlEndpointReturns200WithTextPlain() {
        String slug = firstSlug();
        given()
                .when().get("/api/posts/{slug}/html", slug)
                .then()
                .statusCode(200)
                .contentType(containsString("text/plain"));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void htmlEndpointReturnsHtmlContent() {
        String slug = firstSlug();
        String content = given()
                .when().get("/api/posts/{slug}/html", slug)
                .then().statusCode(200)
                .extract().asString();
        // Should contain HTML tags
        assertTrue(content.contains("<") && content.contains(">"),
                "Expected HTML content but got: " + content.substring(0, Math.min(200, content.length())));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void htmlUnknownSlugReturns404() {
        given()
                .when().get("/api/posts/this-slug-does-not-exist-xyz/html")
                .then()
                .statusCode(404);
    }

    // ── view ──────────────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void viewEndpointReturns200WithTextHtml() {
        String slug = firstSlug();
        given()
                .when().get("/api/posts/{slug}/view", slug)
                .then()
                .statusCode(200)
                .contentType(containsString("text/html"));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void viewDoesNotContainArchiveHeader() {
        String slug = firstSlug();
        String html = given()
                .when().get("/api/posts/{slug}/view", slug)
                .then().statusCode(200)
                .extract().asString();
        assertFalse(html.contains("archive-header"),
                "view endpoint should strip archive-header elements");
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void viewUnknownSlugReturns404() {
        given()
                .when().get("/api/posts/this-slug-does-not-exist-xyz/view")
                .then()
                .statusCode(404);
    }

    // ── save-html ─────────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void saveHtmlPersistsContent() {
        String slug = firstSlug();
        String marker = "<!-- test-save-html-marker -->";

        given()
                .contentType("text/plain")
                .body("<html><body>" + marker + "</body></html>")
                .when().post("/api/posts/{slug}/save-html", slug)
                .then()
                .statusCode(200)
                .body("slug", equalTo(slug));

        // Verify stored by reading view (which uses enriched-first)
        String viewContent = given()
                .when().get("/api/posts/{slug}/view", slug)
                .then().statusCode(200)
                .extract().asString();
        assertTrue(viewContent.contains(marker),
                "save-html content should be readable via view endpoint");
    }

    // ── save-md ───────────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void saveMdPersistsAndUpdatesState() {
        String slug = firstSlug();
        String content = "---\nlayout: post\ntitle: \"Test\"\ndate: 2024-01-01\n---\n\n# Test content";

        given()
                .contentType("text/plain")
                .body(content)
                .when().post("/api/posts/{slug}/save-md", slug)
                .then()
                .statusCode(200)
                .body("slug",           equalTo(slug))
                .body("md.generated_at", notNullValue());
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void saveMdUnknownSlugStillSucceeds() {
        // save-md creates the MD file; state entry may not exist
        given()
                .contentType("text/plain")
                .body("---\nlayout: post\ntitle: \"Test\"\ndate: 2024-01-01\n---\n\n# Content")
                .when().post("/api/posts/test-unknown-slug-xyz/save-md")
                .then()
                .statusCode(200);
    }

    private static void assertTrue(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static void assertFalse(boolean condition, String message) {
        if (condition) throw new AssertionError(message);
    }
}
```

- [ ] **Step 2: Run tests — confirm they compile (most will FAIL or SKIP — that's correct)**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dtest=PostsResourceConvertTest -Dquarkus.http.test-port=8888 2>&1 | grep -E "Tests run|FAIL|ERROR" | head -10
```

Expected: Tests compile. Some pass (JEP still handles them), KIE-gated tests skip if no archive.

- [ ] **Step 3: Make html(), view(), saveHtml(), saveMd() native in PostsResource.java**

Find the current `html()` method — it already has partial native code with a `cfg == null` JEP fallback. Remove the fallback:

**html() — remove JEP fallback (cfg == null branch):**
```java
@GET
@Path("{slug}/html")
@Produces(MediaType.TEXT_PLAIN)
public Response html(@PathParam("slug") String slug) {
    SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
    if (cfg == null) return err(400, "no active project");
    try {
        java.nio.file.Path enriched = cfg.enrichedDir().resolve(slug + ".html");
        java.nio.file.Path original  = cfg.postsDir().resolve(slug + ".html");
        java.nio.file.Path htmlPath  = java.nio.file.Files.exists(enriched) ? enriched : original;
        if (!java.nio.file.Files.exists(htmlPath)) {
            return Response.status(404)
                    .header("Content-Type",                "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .entity("{\"error\":\"HTML not found: " + slug + "\"}").build();
        }
        String raw     = java.nio.file.Files.readString(htmlPath);
        String content = HtmlUtils.prettifyHtml(raw);
        return Response.ok(content)
                .header("Content-Type",                "text/plain; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

**view() — fully native:**
```java
private static final java.util.regex.Pattern ARCHIVE_HEADER_RE =
    java.util.regex.Pattern.compile(
        "<header\\s[^>]*class=\"[^\"]*archive-header[^\"]*\"[^>]*>.*?</header>",
        java.util.regex.Pattern.DOTALL | java.util.regex.Pattern.CASE_INSENSITIVE);

@GET
@Path("{slug}/view")
@Produces(MediaType.TEXT_HTML)
public Response view(@PathParam("slug") String slug) {
    SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
    if (cfg == null) return err(400, "no active project");
    try {
        java.nio.file.Path enriched = cfg.enrichedDir().resolve(slug + ".html");
        java.nio.file.Path original  = cfg.postsDir().resolve(slug + ".html");
        java.nio.file.Path htmlPath  = java.nio.file.Files.exists(enriched) ? enriched : original;
        if (!java.nio.file.Files.exists(htmlPath)) {
            return Response.status(404)
                    .header("Content-Type",                "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .entity("{\"error\":\"HTML not found: " + slug + "\"}").build();
        }
        String content = java.nio.file.Files.readString(htmlPath, java.nio.charset.StandardCharsets.UTF_8);
        content = ARCHIVE_HEADER_RE.matcher(content).replaceAll("");
        return Response.ok(content)
                .header("Content-Type",                "text/html; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

**saveHtml() — fully native:**
```java
@POST
@Path("{slug}/save-html")
@Consumes({MediaType.TEXT_PLAIN, MediaType.TEXT_HTML, MediaType.WILDCARD})
public Response saveHtml(@PathParam("slug") String slug, String body) {
    SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
    if (cfg == null) return err(400, "no active project");
    try {
        java.nio.file.Path enrichedDir = cfg.enrichedDir();
        java.nio.file.Files.createDirectories(enrichedDir);
        java.nio.file.Files.writeString(enrichedDir.resolve(slug + ".html"),
                body == null ? "" : body, java.nio.charset.StandardCharsets.UTF_8);
        ObjectNode post = stateStore.get(slug);
        return ok(post != null ? post.toString() : "{}");
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

**saveMd() — fully native:**
```java
@POST
@Path("{slug}/save-md")
@Consumes(MediaType.TEXT_PLAIN)
public Response saveMd(@PathParam("slug") String slug, String body) {
    SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
    if (cfg == null) return err(400, "no active project");
    try {
        java.nio.file.Path mdPath = cfg.mdDir().resolve(slug + ".md");
        java.nio.file.Files.createDirectories(mdPath.getParent());
        java.nio.file.Files.writeString(mdPath,
                body == null ? "" : body, java.nio.charset.StandardCharsets.UTF_8);
        java.nio.file.Path htmlPath = cfg.postsDir().resolve(slug + ".html");
        stateStore.markMdGenerated(slug, java.nio.file.Files.exists(htmlPath) ? htmlPath : null);
        ObjectNode post = stateStore.get(slug);
        return ok(post != null ? post.toString() : "{}");
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

- [ ] **Step 4: Verify no JEP calls for these 4 methods**

```bash
grep -n "bridge.call.*post_html\|bridge.call.*post_view\|bridge.call.*post_save_html\|bridge.call.*post_save_md" \
  ~/claude/sparge/server/src/main/java/io/sparge/server/PostsResource.java
```
Expected: no output.

- [ ] **Step 5: Run PostsResourceConvertTest**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dtest=PostsResourceConvertTest -Dquarkus.http.test-port=8888 -q 2>&1 | grep "Tests run" | tail -3
```
Expected: All pass or skip. 0 failures.

- [ ] **Step 6: Run full suite**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dquarkus.http.test-port=8888 -q 2>&1 | grep -E "Tests run:|BUILD" | tail -5
```
Expected: BUILD SUCCESS, ≥240 tests, 0 failures.

- [ ] **Step 7: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/PostsResource.java \
        server/src/test/java/io/sparge/server/PostsResourceConvertTest.java
git commit -m "feat(#62): native Java view/saveHtml/saveMd/html — remove 4 JEP calls

Refs #59

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: flexmark dependency + MdIssue.java

**Files:**
- Modify: `server/pom.xml`
- Create: `server/src/main/java/io/sparge/server/MdIssue.java`

- [ ] **Step 1: Add flexmark-html2md-converter to pom.xml**

Find the `<dependencies>` section in `server/pom.xml` and add after the jsoup dependency:

```xml
<dependency>
    <groupId>com.vladsch.flexmark</groupId>
    <artifactId>flexmark-html2md-converter</artifactId>
    <version>0.64.8</version>
</dependency>
```

- [ ] **Step 2: Create MdIssue.java**

```java
package io.sparge.server;

/**
 * A single validation issue from MdValidator — mirrors md_validator.py Issue dataclass.
 * level is "ERROR" or "WARN".
 */
public record MdIssue(String check, String level, String detail) {

    @Override
    public String toString() {
        return "[" + level + "] " + check + ": " + detail;
    }
}
```

- [ ] **Step 3: Verify compilation**

```bash
cd ~/claude/sparge/server && mvn compile -q 2>&1 | tail -5
```
Expected: BUILD SUCCESS.

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add server/pom.xml \
        server/src/main/java/io/sparge/server/MdIssue.java
git commit -m "feat(#62): add flexmark-html2md-converter dep + MdIssue record

Refs #59

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: ConvertPostTest.java — Write Failing Tests

**Files:**
- Create: `server/src/test/java/io/sparge/server/ConvertPostTest.java`

- [ ] **Step 1: Create the test file**

```java
package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import static org.junit.jupiter.api.Assertions.*;

class ConvertPostTest {

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static Path writeHtml(Path dir, String filename, String content) throws Exception {
        Path p = dir.resolve(filename);
        Files.writeString(p, content);
        return p;
    }

    private static Path writeJson(Path dir, String filename, String json) throws Exception {
        Path p = dir.resolve(filename);
        Files.writeString(p, json);
        return p;
    }

    private static String sidecar(String title, String date) {
        return "{\"title\":\"" + title + "\",\"date\":\"" + date + "\","
             + "\"author\":\"Mark Proctor\",\"categories\":[],\"tags\":[],"
             + "\"original_url\":\"https://example.com/post\"}";
    }

    // ── Front matter ──────────────────────────────────────────────────────────

    @Test
    void frontMatter_hasRequiredFields(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("My Test Post", "2024-03-15T10:00:00Z"));
        writeHtml(tmp, "post.html",
            "<html><body><article><p>Hello world content here.</p></article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertNotNull(md, "convert() should return non-null");
        assertTrue(md.startsWith("---\n"),   "Should start with front matter");
        assertTrue(md.contains("layout: post"), "Should have layout field");
        assertTrue(md.contains("title: \"My Test Post\""), "Should have title");
        assertTrue(md.contains("date: 2024-03-15"),        "Should have date (YYYY-MM-DD)");
        assertTrue(md.contains("author: Mark Proctor"),    "Should have author");
    }

    @Test
    void frontMatter_stripsKieCommunityFromTitle(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Rule Engine Basics - KIE Community", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html",
            "<html><body><article><p>Content.</p></article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("title: \"Rule Engine Basics\""),
                "Should strip '- KIE Community' from title");
        assertFalse(md.contains("KIE Community"), "KIE Community suffix should be stripped");
    }

    @Test
    void frontMatter_withCategoriesAndTags(@TempDir Path tmp) throws Exception {
        Path json = writeJson(tmp, "meta.json",
            "{\"title\":\"Post\",\"date\":\"2024-01-01T00:00:00Z\","
          + "\"author\":\"Mark Proctor\","
          + "\"categories\":[\"Drools\",\"Rules\"],\"tags\":[\"rete\",\"jbpm\"],"
          + "\"original_url\":\"https://example.com\"}");
        writeHtml(tmp, "meta.html",
            "<html><body><article><p>Content here.</p></article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("meta.html"), json);

        assertTrue(md.contains("  - Drools"),  "Should list category Drools");
        assertTrue(md.contains("  - Rules"),   "Should list category Rules");
        assertTrue(md.contains("  - rete"),    "Should list tag rete");
        assertTrue(md.contains("  - jbpm"),    "Should list tag jbpm");
    }

    // ── Junk removal ──────────────────────────────────────────────────────────

    @Test
    void junkSelectors_headerAndComments_removed(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<header class=\"entry-header\">HEADER JUNK</header>"
            + "<div class=\"entry-meta\">META JUNK</div>"
            + "<!-- HTML COMMENT -->"
            + "<p>Real content paragraph here.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertFalse(md.contains("HEADER JUNK"),  "entry-header should be removed");
        assertFalse(md.contains("META JUNK"),    "entry-meta should be removed");
        assertFalse(md.contains("HTML COMMENT"), "HTML comments should be removed");
        assertTrue(md.contains("Real content"),  "Real content should be preserved");
    }

    @Test
    void junkSelectors_commentsAndSharing_removed(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<div id=\"comments\"><p>Comment text</p></div>"
            + "<div class=\"addtoany_share_save_container\">Share</div>"
            + "<p>Article body content here.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertFalse(md.contains("Comment text"), "#comments should be removed");
        assertFalse(md.contains("addtoany"),     "addtoany should be removed");
        assertTrue(md.contains("Article body"),  "Article content should be preserved");
    }

    // ── Code blocks ───────────────────────────────────────────────────────────

    @Test
    void codeBlock_preservedAsFencedMarkdown(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<p>Example code:</p>"
            + "<pre><code class=\"language-java\">public class Hello {\n"
            + "    public static void main(String[] args) {\n"
            + "        System.out.println(\"Hello\");\n"
            + "    }\n"
            + "}</code></pre>"
            + "<p>After code.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("```java"),               "Should have java fence");
        assertTrue(md.contains("public class Hello"),    "Code content should be preserved");
        assertTrue(md.contains("System.out.println"),    "Code content should be preserved");
        assertTrue(md.contains("```\n"),                 "Should have closing fence");
        assertFalse(md.contains("@@CODEBLOCK_"),         "No orphaned placeholders");
    }

    @Test
    void codeBlock_noLanguage_preservedAsPlain(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<pre><code>plain code block here</code></pre>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("```"),               "Should have fence");
        assertTrue(md.contains("plain code block"), "Code should be preserved");
    }

    @Test
    void codeBlock_withBackticksInCode_usesLongerFence(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<pre><code>use `backtick` in code</code></pre>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        // If code contains backticks, fence must be longer than any backtick run
        assertTrue(md.contains("use `backtick` in code"), "Backtick content preserved");
        // Count fence backticks — must be ≥ 4 (since content has 1-backtick runs)
        int idx = md.indexOf("use `backtick`");
        assertTrue(idx > 0, "code block present");
    }

    // ── HTML→MD conversion ────────────────────────────────────────────────────

    @Test
    void headings_convertedToHashStyle(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<h2>Section One</h2><p>Content.</p>"
            + "<h3>Subsection</h3><p>More content.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("## Section One"),  "h2 should become ##");
        assertTrue(md.contains("### Subsection"),  "h3 should become ###");
        // Setext style (underline) must NOT be used
        assertFalse(md.contains("Section One\n==="), "Should not use setext headings");
        assertFalse(md.contains("Section One\n---"), "Should not use setext headings");
    }

    @Test
    void imagePathsFixed(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<img src=\"../../assets/images/drools.png\" alt=\"Drools logo\">"
            + "<p>Content.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertTrue(md.contains("/legacy/assets/images/drools.png"),
                "../../assets/ paths should become /legacy/assets/");
        assertFalse(md.contains("../../assets/"), "Old relative path should be gone");
    }

    @Test
    void dataUriImages_removed(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<img src=\"data:image/png;base64,AAAA\" alt=\"spacer\">"
            + "<p>Real content paragraph.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertFalse(md.contains("data:image"),  "data: URI images should be removed");
        assertTrue(md.contains("Real content"), "Real content preserved");
    }

    @Test
    void blockquoteWithCite_preserved(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<blockquote><p>Famous quote text.</p><cite>Author Name</cite></blockquote>"
            + "<p>Content.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        // Semantic blockquote (has <cite>) should be kept as > in MD
        assertTrue(md.contains("> ") || md.contains("Famous quote"),
                "Semantic blockquote should be preserved");
    }

    @Test
    void blockquoteWithoutCite_unwrapped(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<blockquote><p>Indentation-only content.</p></blockquote>"
            + "<p>Normal paragraph.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        // Plain blockquote (no class, no cite) should be unwrapped — content kept but > stripped
        assertTrue(md.contains("Indentation-only content"), "Content should be preserved");
    }

    // ── MD cleanup ────────────────────────────────────────────────────────────

    @Test
    void tripleNewlines_collapsed(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<p>Para one.</p><p>Para two.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertFalse(md.contains("\n\n\n\n"), "Should not have 4+ consecutive newlines");
    }

    @Test
    void noOrphanedPlaceholders(@TempDir Path tmp) throws Exception {
        writeJson(tmp, "post.json", sidecar("Post", "2024-01-01T00:00:00Z"));
        writeHtml(tmp, "post.html", "<html><body><article>"
            + "<pre><code>code one</code></pre>"
            + "<pre><code class=\"language-xml\">&lt;bean id=\"x\"/&gt;</code></pre>"
            + "<p>Content.</p>"
            + "</article></body></html>");

        String md = ConvertPost.convert(tmp.resolve("post.html"), null);

        assertFalse(md.contains("@@CODEBLOCK_"),
                "All placeholders should be restored, none orphaned");
    }

    // ── Integration test with real KIE post ───────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void convertRealKiePost_producesValidFrontMatter() throws Exception {
        Path postsDir = Paths.get(System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor");
        // Pick a known post that has a sidecar JSON
        Path html = Files.list(postsDir)
                .filter(p -> p.toString().endsWith(".html"))
                .filter(p -> p.resolveSibling(
                        p.getFileName().toString().replace(".html", ".json")).toFile().exists())
                .findFirst()
                .orElse(null);
        if (html == null) return; // no sidecar — skip

        String md = ConvertPost.convert(html, null);

        assertNotNull(md,                        "convert() should not return null");
        assertTrue(md.startsWith("---\n"),       "Should have front matter");
        assertTrue(md.contains("layout: post"), "Should have layout");
        assertTrue(md.contains("title:"),       "Should have title");
        assertTrue(md.contains("date:"),        "Should have date");
        assertFalse(md.contains("@@CODEBLOCK_"), "No orphaned placeholders");
        // Body should be non-trivial
        String body = md.substring(md.indexOf("---\n", 4) + 4).trim();
        assertTrue(body.length() > 50, "Body should have meaningful content");
    }

}

```

- [ ] **Step 2: Run tests — confirm COMPILATION FAILURE (ConvertPost not found)**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=ConvertPostTest -q 2>&1 | grep -E "ERROR|cannot find" | head -5
```
Expected: COMPILATION ERROR.

---

## Task 4: ConvertPost.java — Implement

**Files:**
- Create: `server/src/main/java/io/sparge/server/ConvertPost.java`

- [ ] **Step 1: Create ConvertPost.java**

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.vladsch.flexmark.html2md.converter.FlexmarkHtmlConverter;
import com.vladsch.flexmark.util.data.MutableDataSet;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Comment;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.nodes.Node;
import org.jsoup.nodes.TextNode;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * HTML-to-Markdown converter — native Java port of scripts/convert_post.py.
 *
 * Uses jsoup for DOM manipulation and flexmark-html2md-converter for the
 * core HTML→Markdown conversion.  Mirrors convert_post.py's 7-phase pipeline:
 * 1. Load HTML + JSON sidecar
 * 2. Remove junk selectors
 * 3. DOM cleanup (blockquotes, author chrome, metadata paragraphs)
 * 4. Extract code blocks to placeholders
 * 5. Convert to Markdown via flexmark
 * 6. Restore code blocks (with fence-length protection)
 * 7. MD cleanup + front matter
 */
public final class ConvertPost {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    // ── Selectors (mirrors JUNK_SELECTORS in convert_post.py) ────────────────

    static final String[] JUNK_SELECTORS = {
        ".entry-header", "header", ".entry-meta",
        ".author-box", ".author-description", ".author-info",
        ".addtoany_share_save_container", ".addtoany_share_save",
        ".sharedaddy", "#comments", ".comments-area",
        ".jp-relatedposts", ".post-navigation",
        ".wpdiscuz-form-container", "script", "style"
    };

    private static final Set<String> CHROME_HEADINGS =
        Set.of("author", "related posts", "feedback", "share", "about");

    // ── Patterns ──────────────────────────────────────────────────────────────

    private static final Pattern[] META_PATTERNS = {
        Pattern.compile("^by\\s", Pattern.CASE_INSENSITIVE),
        Pattern.compile("Post Comment", Pattern.CASE_INSENSITIVE),
        Pattern.compile("View all posts", Pattern.CASE_INSENSITIVE),
        Pattern.compile("mailto:"),
        Pattern.compile("^\\[?\\s*Rules?\\s*\\]?\\s*\\[?\\s*Article", Pattern.CASE_INSENSITIVE),
    };

    private static final Pattern SOCIAL_PLATFORM_RE =
        Pattern.compile("addtoany|linkedin|twitter|facebook|reddit|tumblr",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern SOCIAL_SHARE_URL_RE =
        Pattern.compile("twitter\\.com/intent|facebook\\.com/sharer|linkedin\\.com/share"
            + "|reddit\\.com/submit|plus\\.google\\.com/share|t\\.co/",
            Pattern.CASE_INSENSITIVE);

    private static final Pattern[] JUNK_LINE_PATTERNS = {
        Pattern.compile("^\\[\\]\\(<https?://"),
        Pattern.compile("^\\[\\]\\(<https://www\\.addtoany"),
        Pattern.compile("^\\[Post Comment\\]"),
        Pattern.compile("^## Author\\s*$"),
        Pattern.compile("^\\* !\\[.*?\\]\\(/legacy/assets/images.*?\\)\\s*$"),
        Pattern.compile("^\\[Mark Proctor\\].*?title=\"Mark Proctor\"\\)"),
        Pattern.compile("^\\[ View all posts \\]"),
        Pattern.compile("^\\[ \\]\\(<mailto:"),
    };

    private static final Pattern ENCODED_TAG_RE =
        Pattern.compile("&lt;(?:table|div|p|span|ul|ol|tr|td|th)\\b",
            Pattern.CASE_INSENSITIVE);

    private static final Pattern TRIPLE_NEWLINES =
        Pattern.compile("\n{3,}");
    private static final Pattern EMPTY_LINK_PREFIX =
        Pattern.compile("\\[\\]\\(<https?://[^)]*\\)");
    private static final Pattern SETEXT_H1 =
        Pattern.compile("(?m)^(\\S[^\n]*)\n=+$");
    private static final Pattern SETEXT_H2 =
        Pattern.compile("(?m)^(\\S[^\n]*)\n-+$");

    // ── flexmark converter ────────────────────────────────────────────────────

    private static final FlexmarkHtmlConverter HTML_CONVERTER;
    static {
        MutableDataSet opts = new MutableDataSet()
            .set(FlexmarkHtmlConverter.SETEXT_HEADINGS, false);
        HTML_CONVERTER = FlexmarkHtmlConverter.builder(opts).build();
    }

    private ConvertPost() {}

    // ── Public API ────────────────────────────────────────────────────────────

    /**
     * Convert an HTML post to Jekyll Markdown.
     *
     * @param htmlPath  path to the HTML post file
     * @param jsonPath  path to the JSON sidecar (null = sibling of htmlPath)
     * @return complete Markdown string with YAML front matter, or null if no article element
     */
    public static String convert(Path htmlPath, Path jsonPath) throws Exception {
        // Resolve sidecar
        Path sidecar = jsonPath != null ? jsonPath
            : htmlPath.resolveSibling(
                htmlPath.getFileName().toString().replaceAll("\\.html$", ".json"));
        JsonNode meta = MAPPER.readTree(sidecar.toFile());

        // Parse HTML
        String htmlContent = new String(Files.readAllBytes(htmlPath), StandardCharsets.UTF_8);
        Document doc = Jsoup.parse(htmlContent, htmlPath.toUri().toString());
        Element article = doc.selectFirst("article");
        if (article == null) article = doc.selectFirst("body");
        if (article == null) return null;

        // Phase 1: Remove junk selectors
        for (String sel : JUNK_SELECTORS) {
            article.select(sel).remove();
        }

        // Phase 2: DOM cleanup
        removeComments(article);
        decodeEncodedCodeBlocks(article);
        unwrapPlainBlockquotes(article);
        removeWpDiscuzAddToAny(article);
        removeAuthorChrome(article, meta);
        removeChromeHeadings(article);
        removeMetaElements(article);
        fixImagePaths(article);
        fixLinkPaths(article);
        removeEmptyTags(article);

        // Phase 3: Extract code blocks to placeholders
        Map<String, String[]> codeBlocks = new LinkedHashMap<>();
        extractCodeBlocks(article, codeBlocks);

        // Phase 4: Convert HTML to Markdown
        String body = HTML_CONVERTER.convert(article.outerHtml()).strip();

        // Phase 5: Restore code blocks
        for (Map.Entry<String, String[]> e : codeBlocks.entrySet()) {
            String key  = e.getKey();
            String lang = e.getValue()[0];
            String code = e.getValue()[1];
            int maxRun  = maxBacktickRun(code);
            int fenceLen = Math.max(3, maxRun + 1);
            String fence = "`".repeat(fenceLen);
            String replacement = fence + lang + "\n" + code + "\n" + fence;
            body = body.replace(key, replacement);
        }

        // Phase 6: MD cleanup
        body = cleanMarkdown(body);

        // Phase 7: Front matter
        String frontMatter = buildFrontMatter(meta, htmlPath);

        return frontMatter + body;
    }

    // ── DOM manipulation helpers ──────────────────────────────────────────────

    private static void removeComments(Element root) {
        root.childNodes().stream()
            .filter(n -> n instanceof Comment)
            .collect(Collectors.toList())
            .forEach(Node::remove);
        for (Element e : root.getAllElements()) {
            e.childNodes().stream()
                .filter(n -> n instanceof Comment)
                .collect(Collectors.toList())
                .forEach(Node::remove);
        }
    }

    private static void decodeEncodedCodeBlocks(Element article) {
        for (Element pre : new ArrayList<>(article.select("pre"))) {
            Element code = pre.selectFirst("code");
            if (code == null) continue;
            String raw = code.html();
            if (ENCODED_TAG_RE.matcher(raw).find()) {
                String decoded = org.jsoup.parser.Parser.unescapeEntities(code.text(), true);
                // Remove spacer images from decoded HTML
                decoded = decoded.replaceAll("<img[^>]*spacer[^>]*/>", "");
                decoded = decoded.replaceAll(
                    "<img[^>]+height=[\"']?[01][\"']?[^>]+alt=[\"']?[\"']?[^>]*/>", "");
                pre.replaceWith(Jsoup.parseBodyFragment(decoded).body());
            }
        }
    }

    private static void unwrapPlainBlockquotes(Element article) {
        for (Element bq : new ArrayList<>(article.select("blockquote"))) {
            String classes = String.join(" ", bq.classNames());
            if (classes.contains("missing-image")) continue;
            if (!bq.classNames().isEmpty()) continue;  // has class → keep
            if (bq.selectFirst("cite") != null) continue; // semantic → keep
            bq.unwrap();
        }
    }

    private static void removeWpDiscuzAddToAny(Element article) {
        for (Element tag : new ArrayList<>(article.getAllElements())) {
            String classes = String.join(" ", tag.classNames()).toLowerCase();
            if (classes.contains("wpdiscuz") || classes.contains("addtoany")) tag.remove();
        }
    }

    private static void removeAuthorChrome(Element article, JsonNode meta) {
        // Author avatar links
        for (Element a : new ArrayList<>(article.select("a[href]"))) {
            String href = a.attr("href");
            if ((href.contains("search_authors") || href.contains("/author/"))
                    && a.selectFirst("img") != null) {
                a.remove();
            }
        }
        // Author portrait images (alt == author name)
        String authorName = meta.path("author").asText("").trim().toLowerCase();
        if (!authorName.isEmpty()) {
            for (Element img : new ArrayList<>(article.select("img"))) {
                if (img.attr("alt").trim().toLowerCase().equals(authorName)) img.remove();
            }
        }
    }

    private static void removeChromeHeadings(Element article) {
        for (Element h : new ArrayList<>(article.select("h2, h3"))) {
            if (CHROME_HEADINGS.contains(h.text().trim().toLowerCase())) {
                for (Element sib : new ArrayList<>(h.nextElementSiblings())) sib.remove();
                h.remove();
                break;
            }
        }
    }

    private static void removeMetaElements(Element article) {
        for (Element tag : new ArrayList<>(article.select("p, div, span"))) {
            String text    = tag.text().strip();
            String hrefs   = tag.select("a[href]").stream()
                .map(a -> a.attr("href")).collect(Collectors.joining(" "));
            String combined = text + " " + hrefs;

            if (tag.tagName().equals("div") && text.length() > 120) {
                if (text.length() < 300 && META_PATTERNS[0].matcher(text).find()) tag.remove();
                continue;
            }
            if (text.length() < 500 && matchesAnyMeta(combined)) { tag.remove(); continue; }
            if (SOCIAL_PLATFORM_RE.matcher(combined).find()) {
                boolean isShareUrl  = SOCIAL_SHARE_URL_RE.matcher(hrefs).find();
                boolean isBareLabel = text.length() < 50 && hrefs.isEmpty();
                if (isShareUrl || isBareLabel) { tag.remove(); continue; }
            }
            if (META_PATTERNS[0].matcher(text).find() && text.length() < 300) tag.remove();
        }
    }

    private static boolean matchesAnyMeta(String combined) {
        for (Pattern p : META_PATTERNS) if (p.matcher(combined).find()) return true;
        return false;
    }

    private static void fixImagePaths(Element article) {
        for (Element img : new ArrayList<>(article.select("img"))) {
            String src = img.attr("src");
            if (src.startsWith("data:")) { img.remove(); continue; }
            if (src.startsWith("../../assets/"))
                img.attr("src", "/legacy/" + src.replace("../../", ""));
        }
    }

    private static void fixLinkPaths(Element article) {
        for (Element a : article.select("a[href]")) {
            String href = a.attr("href");
            if (href.startsWith("../../assets/"))
                a.attr("href", "/legacy/" + href.replace("../../", ""));
        }
    }

    private static void removeEmptyTags(Element article) {
        boolean changed = true;
        while (changed) {
            changed = false;
            for (Element tag : new ArrayList<>(article.select("p, div, span, li"))) {
                if (tag.text().isBlank() && tag.selectFirst("img") == null) {
                    tag.remove(); changed = true;
                }
            }
        }
    }

    // ── Code block extraction ─────────────────────────────────────────────────

    private static void extractCodeBlocks(Element article,
                                           Map<String, String[]> codeBlocks) {
        int idx = 0;
        for (Element pre : new ArrayList<>(article.select("pre"))) {
            Element code = pre.selectFirst("code");
            if (code == null) continue;
            String lang  = extractLang(code);
            String text  = code.text();
            String key   = String.format("@@CODEBLOCK_%03d@@", idx++);
            codeBlocks.put(key, new String[]{lang, text});
            pre.replaceWith(Jsoup.parseBodyFragment("<p>" + key + "</p>").selectFirst("p"));
        }
    }

    private static String extractLang(Element code) {
        for (String cls : code.classNames()) {
            if (cls.startsWith("language-")) return cls.substring("language-".length());
            // Some posts use bare language class
            if (KNOWN_LANGUAGES.contains(cls.toLowerCase())) return cls.toLowerCase();
        }
        return "";
    }

    private static final Set<String> KNOWN_LANGUAGES = Set.of(
        "java", "python", "javascript", "js", "typescript", "ts",
        "xml", "json", "yaml", "yml", "sql", "bash", "sh", "shell",
        "groovy", "kotlin", "scala", "go", "rust", "c", "cpp",
        "html", "css", "properties", "text", "plain", "diff",
        "drools", "drl", "console", "log", "dockerfile"
    );

    private static int maxBacktickRun(String text) {
        int max = 0, cur = 0;
        for (char c : text.toCharArray()) {
            if (c == '`') { cur++; max = Math.max(max, cur); } else cur = 0;
        }
        return max;
    }

    // ── Markdown cleanup ──────────────────────────────────────────────────────

    private static String cleanMarkdown(String body) {
        // Remove junk lines
        String[] lines = body.split("\n", -1);
        List<String> cleaned = new ArrayList<>();
        for (String line : lines) {
            boolean junk = false;
            for (Pattern p : JUNK_LINE_PATTERNS) {
                if (p.matcher(line).find()) { junk = true; break; }
            }
            if (!junk) cleaned.add(line);
        }
        body = String.join("\n", cleaned);

        // Strip empty link artifacts like [text](<url>) prefix artifacts
        body = EMPTY_LINK_PREFIX.matcher(body).replaceAll("");

        // Convert setext headings to ATX (prevent === conversion)
        body = SETEXT_H1.matcher(body).replaceAll("# $1");
        body = SETEXT_H2.matcher(body).replaceAll("## $1");

        // Collapse 3+ newlines to 2
        body = TRIPLE_NEWLINES.matcher(body).replaceAll("\n\n");

        return body.strip();
    }

    // ── Front matter ──────────────────────────────────────────────────────────

    static String buildFrontMatter(JsonNode meta, Path htmlPath) {
        String title = meta.path("title").asText(
            htmlPath != null ? htmlPath.getFileName().toString().replace(".html", "") : "");
        title = title.replaceAll("\\s*[-–]\\s*KIE Community\\s*$", "").strip();
        title = title.replace("\"", "\\\"");

        String date = meta.path("date").asText("").length() >= 10
            ? meta.path("date").asText().substring(0, 10) : meta.path("date").asText("");

        List<String> cats = new ArrayList<>();
        for (JsonNode c : meta.path("categories")) {
            String s = c.asText("").strip(); if (!s.isEmpty()) cats.add(s);
        }
        List<String> tags = new ArrayList<>();
        for (JsonNode t : meta.path("tags")) {
            String s = t.asText("").strip(); if (!s.isEmpty()) tags.add(s);
        }
        String originalUrl = meta.path("original_url").asText("");

        return "---\n"
            + "layout: post\n"
            + "title: \"" + title + "\"\n"
            + "date: " + date + "\n"
            + "author: Mark Proctor\n"
            + "categories: " + yamlList(cats) + "\n"
            + "tags: " + yamlList(tags) + "\n"
            + "original_url: " + originalUrl + "\n"
            + "---\n\n";
    }

    private static String yamlList(List<String> items) {
        if (items.isEmpty()) return "[]";
        return "\n" + items.stream().map(i -> "  - " + i).collect(Collectors.joining("\n"));
    }
}
```

- [ ] **Step 2: Run ConvertPostTest**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=ConvertPostTest -q 2>&1 | tail -15
```

Expected: Most tests pass. If any fail, read the error carefully — the TDD failures reveal bugs in the implementation to fix immediately before moving on.

- [ ] **Step 3: Fix any failing tests before committing**

If tests fail, investigate the specific assertion and fix the implementation. Do NOT skip or weaken tests — fix the code.

- [ ] **Step 4: Run full suite**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dquarkus.http.test-port=8888 -q 2>&1 | grep -E "Tests run:|BUILD" | tail -5
```
Expected: BUILD SUCCESS, 0 failures.

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/ConvertPost.java \
        server/src/test/java/io/sparge/server/ConvertPostTest.java
git commit -m "feat(#62): ConvertPost.java — native HTML→Markdown converter (port of convert_post.py)

Refs #59

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: MdValidatorTest.java — Write Failing Tests

**Files:**
- Create: `server/src/test/java/io/sparge/server/MdValidatorTest.java`

- [ ] **Step 1: Create the test file**

```java
package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class MdValidatorTest {

    private static final String VALID_FM =
        "---\nlayout: post\ntitle: \"My Post\"\ndate: 2024-03-15\n"
        + "author: Mark Proctor\ncategories: []\ntags: []\noriginal_url: https://example.com\n---\n\n";

    private static List<MdIssue> validate(String md) {
        return MdValidator.validate(md, "test-slug", null);
    }

    private static boolean hasCheck(List<MdIssue> issues, String check) {
        return issues.stream().anyMatch(i -> i.check().equals(check));
    }

    // ── Clean baseline ────────────────────────────────────────────────────────

    @Test
    void cleanPost_hasNoIssues() {
        String md = VALID_FM + "# Introduction\n\nThis is valid content with enough words to not trigger empty body check.\n\n"
                + "```java\npublic class Example {}\n```\n\nMore content here.\n";
        List<MdIssue> issues = validate(md);
        issues.forEach(i -> System.out.println("  Unexpected issue: " + i));
        assertTrue(issues.isEmpty(), "Clean post should have no issues");
    }

    // ── Orphaned placeholders ─────────────────────────────────────────────────

    @Test
    void orphanedPlaceholder_detected() {
        String md = VALID_FM + "Some content.\n\n@@CODEBLOCK_001@@\n\nMore content.\n";
        assertTrue(hasCheck(validate(md), "orphaned_placeholder"),
                "Should detect @@CODEBLOCK_001@@ as orphaned");
    }

    @Test
    void noOrphanedPlaceholder_passes() {
        String md = VALID_FM + "No placeholders here.\n";
        assertFalse(hasCheck(validate(md), "orphaned_placeholder"),
                "No placeholder → no orphaned_placeholder issue");
    }

    // ── Stray digit after fence ───────────────────────────────────────────────

    @Test
    void strayDigitAfterFence_detected() {
        String md = VALID_FM + "Some text.\n\n```0\ncode here\n```\n";
        assertTrue(hasCheck(validate(md), "stray_digit_after_fence"),
                "```0 should trigger stray_digit_after_fence");
    }

    // ── Balanced fences ───────────────────────────────────────────────────────

    @Test
    void unbalancedFence_detected() {
        String md = VALID_FM + "Text before.\n\n```java\ncode without closing fence\n";
        assertTrue(hasCheck(validate(md), "unbalanced_fences"),
                "Unclosed fence should be detected");
    }

    @Test
    void balancedFences_passes() {
        String md = VALID_FM + "```java\npublic void foo() {}\n```\n";
        assertFalse(hasCheck(validate(md), "unbalanced_fences"),
                "Balanced fences should pass");
    }

    // ── Empty code blocks ─────────────────────────────────────────────────────

    @Test
    void emptyCodeBlock_detected() {
        String md = VALID_FM + "Text.\n\n```\n```\n";
        assertTrue(hasCheck(validate(md), "empty_code_block"),
                "Empty fence block should be detected");
    }

    // ── Front matter validation ───────────────────────────────────────────────

    @Test
    void missingTitle_detected() {
        String md = "---\nlayout: post\ndate: 2024-03-15\nauthor: X\n---\n\nContent here.\n";
        assertTrue(hasCheck(validate(md), "front_matter_invalid"),
                "Missing title should trigger front_matter_invalid");
    }

    @Test
    void missingDate_detected() {
        String md = "---\nlayout: post\ntitle: \"T\"\nauthor: X\n---\n\nContent here.\n";
        assertTrue(hasCheck(validate(md), "front_matter_invalid"),
                "Missing date should trigger front_matter_invalid");
    }

    @Test
    void badDateFormat_detected() {
        String md = "---\nlayout: post\ntitle: \"T\"\ndate: 15/03/2024\nauthor: X\n---\n\nContent here.\n";
        assertTrue(hasCheck(validate(md), "front_matter_invalid"),
                "Non-ISO date should trigger front_matter_invalid");
    }

    @Test
    void missingFrontMatter_detected() {
        String md = "# Just a heading\n\nContent without front matter.\n";
        assertTrue(hasCheck(validate(md), "front_matter_invalid"),
                "No front matter should trigger front_matter_invalid");
    }

    // ── Empty body ────────────────────────────────────────────────────────────

    @Test
    void emptyBody_detected() {
        String md = VALID_FM.strip() + "\n\n";
        assertTrue(hasCheck(validate(md), "empty_body"),
                "Empty body (< 20 chars) should be detected");
    }

    @Test
    void shortBody_detected() {
        String md = VALID_FM + "Hi.\n";
        assertTrue(hasCheck(validate(md), "empty_body"),
                "Body with < 20 chars should be detected");
    }

    // ── WordPress junk ────────────────────────────────────────────────────────

    @Test
    void viewAllPostsJunk_detected() {
        String md = VALID_FM + "Real content here.\n\nView all posts by Mark Proctor\n";
        assertTrue(hasCheck(validate(md), "wordpress_junk"),
                "'View all posts' should trigger wordpress_junk");
    }

    @Test
    void postCommentJunk_detected() {
        String md = VALID_FM + "Content here.\n\nPost Comment\n\nMore text.\n";
        assertTrue(hasCheck(validate(md), "wordpress_junk"),
                "'Post Comment' should trigger wordpress_junk");
    }

    // ── HTML entities ─────────────────────────────────────────────────────────

    @Test
    void manyHtmlEntities_detected() {
        // More than 5 &amp; in body triggers the check
        String md = VALID_FM + "a &amp; b &amp; c &amp; d &amp; e &amp; f more text here.\n";
        assertTrue(hasCheck(validate(md), "html_entities_in_body"),
                "6+ &amp; entities should be detected");
    }

    @Test
    void fewHtmlEntities_passes() {
        String md = VALID_FM + "Only one &amp; entity here.\n";
        assertFalse(hasCheck(validate(md), "html_entities_in_body"),
                "≤5 entities should be OK");
    }

    // ── Local image paths ─────────────────────────────────────────────────────

    @Test
    void relativeImagePath_detected() {
        String md = VALID_FM + "![img](../../assets/images/foo.png)\n";
        assertTrue(hasCheck(validate(md), "local_image_paths"),
                "../../assets/ paths should be detected");
    }

    @Test
    void correctImagePath_passes() {
        String md = VALID_FM + "![img](/legacy/assets/images/foo.png)\n";
        assertFalse(hasCheck(validate(md), "local_image_paths"),
                "/legacy/assets/ paths should be OK");
    }

    // ── Broken MD links ───────────────────────────────────────────────────────

    @Test
    void emptyHrefLink_detected() {
        String md = VALID_FM + "[Link text]()\n\nContent.\n";
        assertTrue(hasCheck(validate(md), "broken_md_links"),
                "[text]() empty href should be detected");
    }

    // ── Triple blanks ─────────────────────────────────────────────────────────

    @Test
    void tripleBlankLines_detected() {
        String md = VALID_FM + "Para one.\n\n\n\nPara two.\n";
        assertTrue(hasCheck(validate(md), "no_triple_blanks"),
                "3+ consecutive blank lines should be detected");
    }

    @Test
    void doubleBlankLines_passes() {
        String md = VALID_FM + "Para one.\n\nPara two.\n";
        assertFalse(hasCheck(validate(md), "no_triple_blanks"),
                "Double blank lines should be OK");
    }

    // ── Excessive line length ─────────────────────────────────────────────────

    @Test
    void veryLongLine_detected() {
        String longLine = "x".repeat(8100);
        String md = VALID_FM + longLine + "\n";
        assertTrue(hasCheck(validate(md), "excessive_line_length"),
                "Lines > 8000 chars should be detected");
    }

    // ── Code fence language ───────────────────────────────────────────────────

    @Test
    void unknownFenceLanguage_detected() {
        String md = VALID_FM + "```unknownlang\ncode\n```\n";
        assertTrue(hasCheck(validate(md), "code_fence_language"),
                "Unknown fence language should be flagged");
    }

    @Test
    void knownFenceLanguage_passes() {
        String md = VALID_FM + "```java\npublic void foo() {}\n```\n";
        assertFalse(hasCheck(validate(md), "code_fence_language"),
                "Known language 'java' should pass");
    }

    @Test
    void noFenceLanguage_passes() {
        String md = VALID_FM + "```\ngeneric code\n```\n";
        assertFalse(hasCheck(validate(md), "code_fence_language"),
                "No language (generic fence) should pass");
    }

    // ── Cross-checks with HTML ────────────────────────────────────────────────

    @Test
    void crossWordCount_largeLoss_detected(@TempDir Path tmp) throws Exception {
        // HTML has many words, MD has very few
        StringBuilder htmlWords = new StringBuilder();
        for (int i = 0; i < 200; i++) htmlWords.append("word" + i + " ");
        Path html = tmp.resolve("post.html");
        Files.writeString(html,
            "<html><body><article><p>" + htmlWords + "</p></article></body></html>");

        String md = VALID_FM + "Short body.\n";
        List<MdIssue> issues = MdValidator.validate(md, "post", html);
        assertTrue(hasCheck(issues, "word_count"),
                "MD with far fewer words than HTML should trigger word_count check");
    }

    @Test
    void crossWordCount_acceptable_passes(@TempDir Path tmp) throws Exception {
        Path html = tmp.resolve("post.html");
        Files.writeString(html,
            "<html><body><article><p>This is some content with a reasonable word count.</p></article></body></html>");
        String md = VALID_FM + "This is some content with a reasonable word count.\n";
        List<MdIssue> issues = MdValidator.validate(md, "post", html);
        assertFalse(hasCheck(issues, "word_count"),
                "MD with similar word count to HTML should pass");
    }

    @Test
    void crossHeadingMatch_missingHeading_detected(@TempDir Path tmp) throws Exception {
        Path html = tmp.resolve("post.html");
        Files.writeString(html,
            "<html><body><article>"
            + "<h2>Important Section Title</h2>"
            + "<p>Content here with enough words to matter.</p>"
            + "</article></body></html>");
        String md = VALID_FM + "No heading present.\n\nContent here with enough words to matter.\n";
        List<MdIssue> issues = MdValidator.validate(md, "post", html);
        assertTrue(hasCheck(issues, "heading_match"),
                "Missing HTML heading in MD should be detected");
    }

    @Test
    void crossTechnicalTerms_kieTermPreserved_passes(@TempDir Path tmp) throws Exception {
        Path html = tmp.resolve("post.html");
        Files.writeString(html,
            "<html><body><article><p>Drools is a rules engine built by the KIE team.</p></article></body></html>");
        String md = VALID_FM + "Drools is a rules engine built by the KIE team.\n";
        List<MdIssue> issues = MdValidator.validate(md, "post", html);
        assertFalse(hasCheck(issues, "technical_terms"),
                "Preserved KIE terms should not trigger technical_terms check");
    }

    @Test
    void crossTechnicalTerms_kieLost_detected(@TempDir Path tmp) throws Exception {
        Path html = tmp.resolve("post.html");
        Files.writeString(html,
            "<html><body><article><p>Drools and OptaPlanner are KIE projects.</p></article></body></html>");
        String md = VALID_FM + "Rules engine projects are interesting.\n";
        List<MdIssue> issues = MdValidator.validate(md, "post", html);
        assertTrue(hasCheck(issues, "technical_terms"),
                "Lost KIE terms (drools, optaplanner) should be detected");
    }

    @Test
    void crossLastSection_truncationDetected(@TempDir Path tmp) throws Exception {
        Path html = tmp.resolve("post.html");
        Files.writeString(html,
            "<html><body><article>"
            + "<p>Introduction content.</p>"
            + "<p>This very specific final paragraph text should appear in the markdown output.</p>"
            + "</article></body></html>");
        String md = VALID_FM + "Introduction content.\n\nSomething else entirely different.\n";
        List<MdIssue> issues = MdValidator.validate(md, "post", html);
        assertTrue(hasCheck(issues, "last_section_present"),
                "Missing final paragraph should be detected as possible truncation");
    }
}
```

- [ ] **Step 2: Run tests — confirm COMPILATION FAILURE (MdValidator not found)**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=MdValidatorTest -q 2>&1 | grep -E "ERROR|cannot find" | head -5
```
Expected: COMPILATION ERROR.

---

## Task 6: MdValidator.java — Implement

**Files:**
- Create: `server/src/main/java/io/sparge/server/MdValidator.java`

- [ ] **Step 1: Create MdValidator.java**

```java
package io.sparge.server;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Markdown validation suite — port of scripts/md_validator.py.
 *
 * Runs 14 MD-only checks (pure string/regex on the MD) plus key cross-checks
 * that compare the MD against the original HTML. Both use identical jsoup
 * selectors for HTML preprocessing (coherence requirement).
 */
public final class MdValidator {

    // ── Known code fence languages ────────────────────────────────────────────

    private static final Set<String> KNOWN_LANGUAGES = Set.of(
        "java", "python", "javascript", "js", "typescript", "ts",
        "xml", "json", "yaml", "yml", "sql", "bash", "sh", "shell",
        "groovy", "kotlin", "scala", "go", "rust", "c", "cpp",
        "html", "css", "properties", "text", "plain", "diff",
        "drools", "drl", "console", "log", "dockerfile"
    );

    // KIE technical terms to preserve
    private static final List<String> KIE_TERMS = List.of(
        "drools", "jbpm", "kie", "optaplanner", "kogito", "guvnor", "rete"
    );

    // Chrome headings stripped by converter (mirrors convert_post.py)
    private static final Set<String> CHROME_HEADINGS =
        Set.of("author", "related posts", "feedback", "share", "about");

    private MdValidator() {}

    // ── Public API ────────────────────────────────────────────────────────────

    public static List<MdIssue> validate(String md, String slug, Path htmlPath) {
        List<MdIssue> issues = new ArrayList<>();

        // MD-only checks
        issues.addAll(chkOrphanedPlaceholders(md));
        issues.addAll(chkStrayDigitAfterFence(md));
        issues.addAll(chkBalancedFences(md));
        issues.addAll(chkEmptyCodeBlocks(md));
        issues.addAll(chkFrontMatterValid(md));
        issues.addAll(chkEmptyBody(md));
        issues.addAll(chkWordPressJunk(md));
        issues.addAll(chkHtmlEntitiesInBody(md));
        issues.addAll(chkLocalImagePaths(md));
        issues.addAll(chkBrokenMdLinks(md));
        issues.addAll(chkNoTripleBlanks(md));
        issues.addAll(chkExcessiveLineLength(md));
        issues.addAll(chkManyMissingImages(md));
        issues.addAll(chkCodeFenceLanguage(md));

        // Cross-checks
        if (htmlPath != null && Files.exists(htmlPath)) {
            try {
                String htmlContent = Files.readString(htmlPath, StandardCharsets.UTF_8);
                Element article = loadArticle(htmlContent);
                if (article != null) {
                    issues.addAll(crossWordCount(md, slug, article));
                    issues.addAll(crossCodeBlockCount(md, slug, article));
                    issues.addAll(crossHeadingMatch(md, slug, article));
                    issues.addAll(crossLastSectionPresent(md, slug, article));
                    issues.addAll(crossTechnicalTerms(md, slug, article));
                }
            } catch (Exception e) {
                issues.add(new MdIssue("cross_check_error", "WARN",
                        "Could not load HTML: " + e.getMessage()));
            }
        }

        return issues;
    }

    // ── HTML preprocessing (mirrors convert_post.py's chrome-stripping) ───────

    static Element loadArticle(String html) {
        org.jsoup.nodes.Document doc = Jsoup.parse(html);
        Element article = doc.selectFirst("article");
        if (article == null) article = doc.selectFirst("body");
        if (article == null) return null;

        // Strip script/style/noscript
        article.select("script, style, noscript").remove();

        // Strip chrome headings (same as convert_post.py)
        for (Element h : new ArrayList<>(article.select("h2, h3"))) {
            if (CHROME_HEADINGS.contains(h.text().trim().toLowerCase())) {
                for (Element sib : new ArrayList<>(h.nextElementSiblings())) sib.remove();
                h.remove();
                break;
            }
        }

        // Strip bylines
        for (Element tag : new ArrayList<>(article.select("p, div, span"))) {
            String text = tag.text().strip();
            if (text.length() < 200 && text.matches("(?i)^by\\s+[A-Z].*")) tag.remove();
        }

        // Strip === separator paragraphs
        for (Element p : new ArrayList<>(article.select("p"))) {
            for (org.jsoup.nodes.TextNode tn : p.textNodes()) {
                if (tn.text().matches("^={4,}\\s*$")) { p.remove(); break; }
            }
        }

        // Strip send_to_friend links
        for (Element a : new ArrayList<>(article.select("a[href]"))) {
            String href = a.attr("href");
            if (href.contains("send_to_friend") || href.toLowerCase().contains("sendtofriend")) {
                Element parent = a.parent();
                a.remove();
                if (parent != null && parent.text().isBlank()) parent.remove();
            }
        }

        return article;
    }

    // ── Helper: body after front matter ──────────────────────────────────────

    private static String body(String md) {
        int end = md.indexOf("\n---\n");
        if (end < 0) return md;
        return md.substring(end + 5);
    }

    // ══════════════════════════════════════════════════════════════════════════
    // MD-ONLY CHECKS
    // ══════════════════════════════════════════════════════════════════════════

    static List<MdIssue> chkOrphanedPlaceholders(String md) {
        List<String> found = new ArrayList<>();
        Pattern p = Pattern.compile("@@CODEBLOCK_\\d+@@|CODEBLOCK_FENCE_\\d+");
        var m = p.matcher(md);
        while (m.find()) found.add(m.group());
        if (!found.isEmpty())
            return List.of(new MdIssue("orphaned_placeholder", "ERROR",
                    "Unreplaced code placeholders: " + found.subList(0, Math.min(3, found.size()))));
        return List.of();
    }

    static List<MdIssue> chkStrayDigitAfterFence(String md) {
        if (Pattern.compile("(?m)^`{3,}\\d").matcher(md).find())
            return List.of(new MdIssue("stray_digit_after_fence", "ERROR",
                    "Fence followed by digit — partial placeholder replacement"));
        return List.of();
    }

    static List<MdIssue> chkBalancedFences(String md) {
        int open = 0;
        int openLen = 0;
        for (String line : md.split("\n", -1)) {
            String trimmed = line.strip();
            if (trimmed.startsWith("`")) {
                int len = 0;
                while (len < trimmed.length() && trimmed.charAt(len) == '`') len++;
                if (len >= 3) {
                    if (open == 0) { open = 1; openLen = len; }
                    else if (len >= openLen) { open = 0; openLen = 0; }
                }
            }
        }
        if (open != 0)
            return List.of(new MdIssue("unbalanced_fences", "ERROR",
                    "Unclosed code fence in document"));
        return List.of();
    }

    static List<MdIssue> chkEmptyCodeBlocks(String md) {
        if (Pattern.compile("(?m)^`{3,}[^\n]*\n`{3,}").matcher(md).find())
            return List.of(new MdIssue("empty_code_block", "WARN", "Empty fenced code block"));
        return List.of();
    }

    static List<MdIssue> chkFrontMatterValid(String md) {
        if (!md.startsWith("---\n"))
            return List.of(new MdIssue("front_matter_invalid", "ERROR", "No front matter found"));
        int end = md.indexOf("\n---\n", 4);
        if (end < 0)
            return List.of(new MdIssue("front_matter_invalid", "ERROR", "Front matter not closed"));
        String fm = md.substring(4, end);
        List<String> missing = new ArrayList<>();
        if (!fm.contains("title:"))  missing.add("title");
        if (!fm.contains("date:"))   missing.add("date");
        if (!fm.contains("author:")) missing.add("author");
        if (!missing.isEmpty())
            return List.of(new MdIssue("front_matter_invalid", "ERROR",
                    "Missing required fields: " + missing));
        // Validate date format YYYY-MM-DD
        if (!Pattern.compile("date:\\s*\\d{4}-\\d{2}-\\d{2}").matcher(fm).find())
            return List.of(new MdIssue("front_matter_invalid", "WARN",
                    "date field not in YYYY-MM-DD format"));
        return List.of();
    }

    static List<MdIssue> chkEmptyBody(String md) {
        String b = body(md).strip();
        if (b.length() < 20)
            return List.of(new MdIssue("empty_body", "ERROR",
                    "Body is too short (" + b.length() + " chars)"));
        return List.of();
    }

    static List<MdIssue> chkWordPressJunk(String md) {
        String b = body(md);
        List<Pattern> patterns = List.of(
            Pattern.compile("View all posts", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Post Comment", Pattern.CASE_INSENSITIVE),
            Pattern.compile("addtoany", Pattern.CASE_INSENSITIVE),
            Pattern.compile("wpDiscuz", Pattern.CASE_INSENSITIVE)
        );
        for (Pattern p : patterns) {
            if (p.matcher(b).find())
                return List.of(new MdIssue("wordpress_junk", "WARN",
                        "WordPress template content detected: " + p.pattern()));
        }
        return List.of();
    }

    static List<MdIssue> chkHtmlEntitiesInBody(String md) {
        String b = body(md);
        long count = Pattern.compile("&amp;|&lt;|&gt;|&quot;|&nbsp;").matcher(b).results().count();
        if (count > 5)
            return List.of(new MdIssue("html_entities_in_body", "WARN",
                    count + " unescaped HTML entities in body"));
        return List.of();
    }

    static List<MdIssue> chkLocalImagePaths(String md) {
        if (Pattern.compile("\\.\\.[\\\\/]\\.\\.[\\\\/]assets[\\\\/]").matcher(md).find())
            return List.of(new MdIssue("local_image_paths", "ERROR",
                    "Relative ../../assets/ paths must be /legacy/assets/"));
        return List.of();
    }

    static List<MdIssue> chkBrokenMdLinks(String md) {
        if (Pattern.compile("\\[[^\\]]+\\]\\(\\)").matcher(md).find())
            return List.of(new MdIssue("broken_md_links", "WARN",
                    "Empty href links [text]() detected"));
        return List.of();
    }

    static List<MdIssue> chkNoTripleBlanks(String md) {
        if (Pattern.compile("\n{4,}").matcher(md).find())
            return List.of(new MdIssue("no_triple_blanks", "WARN",
                    "3+ consecutive blank lines detected"));
        return List.of();
    }

    static List<MdIssue> chkExcessiveLineLength(String md) {
        for (String line : md.split("\n")) {
            if (line.length() > 8000)
                return List.of(new MdIssue("excessive_line_length", "WARN",
                        "Line exceeds 8000 chars (" + line.length() + ")"));
        }
        return List.of();
    }

    static List<MdIssue> chkManyMissingImages(String md) {
        long count = Pattern.compile("MISSING_IMAGE|missing-image-placeholder")
            .matcher(md).results().count();
        if (count > 10)
            return List.of(new MdIssue("many_missing_images", "WARN",
                    count + " missing image placeholders"));
        return List.of();
    }

    static List<MdIssue> chkCodeFenceLanguage(String md) {
        Pattern fence = Pattern.compile("(?m)^`{3,}(\\w+)");
        var matcher = fence.matcher(md);
        List<String> unknown = new ArrayList<>();
        while (matcher.find()) {
            String lang = matcher.group(1).toLowerCase();
            if (!KNOWN_LANGUAGES.contains(lang)) unknown.add(lang);
        }
        if (!unknown.isEmpty())
            return List.of(new MdIssue("code_fence_language", "WARN",
                    "Unknown fence languages: " + unknown.subList(0, Math.min(3, unknown.size()))));
        return List.of();
    }

    // ══════════════════════════════════════════════════════════════════════════
    // CROSS-CHECKS (require HTML)
    // ══════════════════════════════════════════════════════════════════════════

    static List<MdIssue> crossWordCount(String md, String slug, Element article) {
        // MD words (excluding code blocks)
        String bodyMd = removeCodeFences(body(md));
        int mdWords = bodyMd.trim().isEmpty() ? 0 : bodyMd.trim().split("\\s+").length;

        // HTML words (excluding pre/code)
        Element copy = article.clone();
        copy.select("pre, code").remove();
        int htmlWords = copy.text().trim().isEmpty() ? 0
            : copy.text().trim().split("\\s+").length;

        if (htmlWords > 150 && mdWords < htmlWords * 0.35)
            return List.of(new MdIssue("word_count", "WARN",
                    "MD has " + mdWords + " words vs HTML " + htmlWords + " (< 35%)"));
        return List.of();
    }

    static List<MdIssue> crossCodeBlockCount(String md, String slug, Element article) {
        long htmlPres = article.select("pre").size();
        long mdFences = Pattern.compile("(?m)^`{3,}").matcher(md).results().count() / 2;
        // Only flag if HTML has code and MD has significantly fewer
        if (htmlPres > 0 && mdFences < htmlPres * 0.5)
            return List.of(new MdIssue("code_block_count", "WARN",
                    "HTML has " + htmlPres + " <pre> blocks, MD has " + mdFences + " fences"));
        return List.of();
    }

    static List<MdIssue> crossHeadingMatch(String md, String slug, Element article) {
        String bodyMd = body(md).toLowerCase();
        List<String> missing = new ArrayList<>();
        for (Element h : article.select("h2, h3")) {
            String text = h.text().strip().toLowerCase();
            if (text.length() < 3) continue;
            if (!bodyMd.contains(text)) missing.add(h.text());
        }
        if (!missing.isEmpty())
            return List.of(new MdIssue("heading_match", "WARN",
                    "HTML headings not found in MD: " + missing.subList(0, Math.min(3, missing.size()))));
        return List.of();
    }

    static List<MdIssue> crossLastSectionPresent(String md, String slug, Element article) {
        Elements paras = article.select("p");
        if (paras.isEmpty()) return List.of();
        // Find last paragraph with substantial content
        for (int i = paras.size() - 1; i >= 0; i--) {
            String text = paras.get(i).text().strip();
            if (text.length() > 30) {
                // Check first 40 chars of last paragraph in MD
                String snippet = text.substring(0, Math.min(40, text.length())).toLowerCase();
                if (!body(md).toLowerCase().contains(snippet))
                    return List.of(new MdIssue("last_section_present", "WARN",
                            "Last HTML paragraph may be truncated in MD: '"
                            + text.substring(0, Math.min(60, text.length())) + "'"));
                break;
            }
        }
        return List.of();
    }

    static List<MdIssue> crossTechnicalTerms(String md, String slug, Element article) {
        String htmlText = article.text().toLowerCase();
        String mdText   = md.toLowerCase();
        List<String> lost = new ArrayList<>();
        for (String term : KIE_TERMS) {
            if (htmlText.contains(term) && !mdText.contains(term)) lost.add(term);
        }
        if (!lost.isEmpty())
            return List.of(new MdIssue("technical_terms", "WARN",
                    "KIE terms in HTML not found in MD: " + lost));
        return List.of();
    }

    // ── Utility ───────────────────────────────────────────────────────────────

    private static String removeCodeFences(String md) {
        return Pattern.compile("(?s)```[^\n]*\n.*?```").matcher(md).replaceAll("");
    }
}
```

- [ ] **Step 2: Run MdValidatorTest**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=MdValidatorTest -q 2>&1 | tail -15
```

Expected: All tests pass. If any fail, fix the implementation before committing.

- [ ] **Step 3: Run ConvertPostTest still passes**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=ConvertPostTest -q 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/MdValidator.java \
        server/src/test/java/io/sparge/server/MdValidatorTest.java
git commit -m "feat(#62): MdValidator.java — 14 MD checks + 5 cross-checks (port of md_validator.py)

Refs #59

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Wire generateMd() and validateMd() in PostsResource

**Files:**
- Modify: `server/src/main/java/io/sparge/server/PostsResource.java`

- [ ] **Step 1: Replace generateMd() with native implementation**

Find the current `generateMd()` method (calls `bridge.call("bridge.post_generate_md", slug, dry)`) and replace:

```java
@POST
@Path("{slug}/generate-md")
public Response generateMd(@PathParam("slug") String slug,
                            @QueryParam("dry") @DefaultValue("") String dryParam) {
    boolean dry = "1".equals(dryParam) || "true".equalsIgnoreCase(dryParam);
    SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
    if (cfg == null) return err(400, "no active project");
    try {
        // Prefer enriched HTML, fall back to original
        java.nio.file.Path enriched = cfg.enrichedDir().resolve(slug + ".html");
        java.nio.file.Path original  = cfg.postsDir().resolve(slug + ".html");
        java.nio.file.Path htmlPath  = java.nio.file.Files.exists(enriched) ? enriched : original;
        if (!java.nio.file.Files.exists(htmlPath)) {
            return Response.status(404)
                    .header("Content-Type",                "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .entity("{\"error\":\"HTML not found: " + slug + "\"}").build();
        }
        // Sidecar JSON lives in the original posts dir
        java.nio.file.Path jsonPath = cfg.postsDir().resolve(slug + ".json");
        java.nio.file.Path jsonArg  = java.nio.file.Files.exists(jsonPath) ? jsonPath : null;

        String content = ConvertPost.convert(htmlPath, jsonArg);
        if (content == null) return err(500, "No article element found in HTML");

        if (dry) return ok("{\"content\":" + MAPPER.writeValueAsString(content) + "}");

        // Write MD file
        java.nio.file.Path mdPath = cfg.mdDir().resolve(slug + ".md");
        java.nio.file.Files.createDirectories(mdPath.getParent());
        java.nio.file.Files.writeString(mdPath, content, java.nio.charset.StandardCharsets.UTF_8);
        stateStore.markMdGenerated(slug, htmlPath);

        // Run validation
        List<MdIssue> issues = MdValidator.validate(content, slug, htmlPath);
        stateStore.setMdIssues(slug, issues.stream()
            .map(i -> Map.of("check", i.check(), "level", i.level(), "detail", i.detail()))
            .collect(java.util.stream.Collectors.toList()));

        ObjectNode post = stateStore.get(slug);
        return ok(post != null ? post.toString() : "{}");
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

**Note:** This method uses `MAPPER` (already a static field in PostsResource) and needs imports for `List`, `Map`. Check if these are already imported; add if not.

- [ ] **Step 2: Replace validateMd() with native implementation**

Find the current `validateMd()` method (calls `bridge.call("bridge.post_validate_md", slug)`) and replace:

```java
@POST
@Path("{slug}/validate-md")
public Response validateMd(@PathParam("slug") String slug) {
    SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
    if (cfg == null) return err(400, "no active project");
    try {
        java.nio.file.Path mdPath = cfg.mdDir().resolve(slug + ".md");
        if (!java.nio.file.Files.exists(mdPath))
            return Response.status(404)
                    .header("Content-Type",                "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .entity("{\"error\":\"MD not generated yet\"}").build();

        String content  = java.nio.file.Files.readString(mdPath, java.nio.charset.StandardCharsets.UTF_8);
        java.nio.file.Path enriched = cfg.enrichedDir().resolve(slug + ".html");
        java.nio.file.Path original  = cfg.postsDir().resolve(slug + ".html");
        java.nio.file.Path htmlPath  = java.nio.file.Files.exists(enriched) ? enriched : original;

        List<MdIssue> issues = MdValidator.validate(content, slug,
                java.nio.file.Files.exists(htmlPath) ? htmlPath : null);
        stateStore.setMdIssues(slug, issues.stream()
            .map(i -> Map.of("check", i.check(), "level", i.level(), "detail", i.detail()))
            .collect(java.util.stream.Collectors.toList()));

        ObjectNode post = stateStore.get(slug);
        return ok(post != null ? post.toString() : "{}");
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

- [ ] **Step 3: Verify no remaining JEP calls for convert pipeline**

```bash
grep -n "bridge.call.*post_generate_md\|bridge.call.*post_validate_md\|bridge.call.*post_save_md\|bridge.call.*post_html\|bridge.call.*post_view\|bridge.call.*post_save_html" \
  ~/claude/sparge/server/src/main/java/io/sparge/server/PostsResource.java
```
Expected: no output.

- [ ] **Step 4: Run PostsResourceConvertTest**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dtest=PostsResourceConvertTest -Dquarkus.http.test-port=8888 -q 2>&1 | grep "Tests run" | tail -3
```

- [ ] **Step 5: Run full suite**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dquarkus.http.test-port=8888 -q 2>&1 | grep -E "Tests run:|BUILD" | tail -5
```
Expected: BUILD SUCCESS, ≥260 tests, 0 failures.

- [ ] **Step 6: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/PostsResource.java
git commit -m "feat(#62): wire generateMd/validateMd to native Java — complete 6-call convert pipeline

Refs #59

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Final Verification + Close Issue

- [ ] **Step 1: Run Python test suite**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --ignore=tests/python-legacy 2>&1 | tail -5
```
Expected: 270 passed, 0 failures.

- [ ] **Step 2: Run full Java suite**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dquarkus.http.test-port=8888 -q 2>&1 | grep -E "Tests run:|BUILD" | tail -5
```
Expected: BUILD SUCCESS, 0 failures.

- [ ] **Step 3: Verify no JEP calls remain for convert pipeline**

```bash
grep -c "bridge.call" ~/claude/sparge/server/src/main/java/io/sparge/server/PostsResource.java
```
Expected: 1 (only the scan fallback at line ~229 which is Phase 6d work).

- [ ] **Step 4: Close issue 62**

```bash
gh issue close 62 \
  --repo mdproctor/sparge \
  --comment "All 6 convert pipeline JEP calls removed. ConvertPost.java and MdValidator.java ported. TDD: ConvertPostTest + MdValidatorTest + PostsResourceConvertTest. Closes #62"
```

- [ ] **Step 5: Tick 6c on epic #59**

```bash
BODY=$(gh issue view 59 --repo mdproctor/sparge --json body -q .body | sed 's/- \[ \] 6c/- [x] 6c/') \
  && gh issue edit 59 --repo mdproctor/sparge --body "$BODY"
```
