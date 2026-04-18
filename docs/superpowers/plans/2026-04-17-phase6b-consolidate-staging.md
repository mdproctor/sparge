# Phase 6b: Consolidate + Staging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove 5 JEP bridge calls by porting consolidate.py to native Java and making all staging endpoints fully native.

**Architecture:** `Consolidate.java` (new static utility class) ports hash-based asset deduplication from Python; `ConsolidateResource` wires it in place of JEP. `PostsResource` staging methods (`stagedGet`, `acceptStaged`, `stage`, `rejectStaged`) already have partial native implementations — this completes them by removing JEP fallback paths and making `stagedGet`/`acceptStaged` fully native using existing `StateStore` methods. TDD throughout: all unit tests use `@TempDir`; E2E tests use `@QuarkusTest` + `@EnabledIf("kieArchivePresent")`.

**Tech Stack:** Quarkus 3.34, JAX-RS (Jakarta), Jackson, Java NIO, JUnit 5, RestAssured, @QuarkusTest

---

## File Map

| File | Change |
|---|---|
| `server/src/main/java/io/sparge/server/Consolidate.java` | **NEW** — port of consolidate.py: hash dedup, global/ promotion, index update, HTML rewrite |
| `server/src/main/java/io/sparge/server/ConsolidateResource.java` | Replace JEP delegation with `Consolidate.consolidate()` |
| `server/src/main/java/io/sparge/server/PostsResource.java` | Make `stagedGet()` and `acceptStaged()` native; remove JEP fallback from `stage()` and `rejectStaged()` |
| `server/src/test/java/io/sparge/server/ConsolidateTest.java` | **NEW** — unit tests for Consolidate logic (TempDir, no HTTP) |
| `server/src/test/java/io/sparge/server/ConsolidateResourceTest.java` | **NEW** — E2E @QuarkusTest for POST /api/consolidate |
| `server/src/test/java/io/sparge/server/PostsResourceStagingTest.java` | **NEW** — unit + E2E tests for staging lifecycle |

---

## Background: what consolidate.py does

`consolidate(assets_root, cleaned_dir)`:
1. Walks `assets_root/posts/*/` — collects all post-specific asset files
2. SHA-256 hashes each file; groups by hash
3. If a hash appears in **2+ different post folders**: promotes the first copy to `assets_root/global/`, deletes the duplicates, updates `assets_root/.url-index.json` (url → relative path map)
4. Rewrites HTML in `cleaned_dir/**/*.html` to update `/assets/posts/…` references to `/assets/global/…`
5. Returns `{promoted, updated_html, duplicates}`

The index file `.url-index.json` is a flat JSON object `{"https://example.com/img.png": "posts/post-a/img.png", ...}`.

---

## Background: staging gaps in current PostsResource

| Method | Current state | Target state |
|---|---|---|
| `stagedGet()` | 100% JEP | Native: read `.md.staged` from `mdDir` |
| `stage()` | 50% native (has JEP fallback when cfg==null) | 100% native, no fallback |
| `acceptStaged()` | 100% JEP | Native: call `stateStore.acceptStaged()` |
| `rejectStaged()` | 50% native (has JEP fallback when cfg==null) | 100% native, no fallback |

`StateStore` already has `acceptStaged(slug, mdDir, postsDir)` and `rejectStaged(slug, mdDir)` — just need to wire them.

**Known gap (intentional):** Python's `post_accept_staged` re-validates MD after accepting. Java won't do this yet — md_validator is ported in Phase 6c. Validation on accept is restored then.

---

### Task 1: ConsolidateTest.java — Write Failing Tests

**Files:**
- Create: `server/src/test/java/io/sparge/server/ConsolidateTest.java`

- [ ] **Step 1: Create the test file**

```java
package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class ConsolidateTest {

    // ── fileHash ──────────────────────────────────────────────────────────────

    @Test
    void fileHash_sameContent_sameHash(@TempDir Path tmp) throws Exception {
        Path a = tmp.resolve("a.png");
        Path b = tmp.resolve("b.png");
        Files.write(a, "shared".getBytes());
        Files.write(b, "shared".getBytes());
        assertEquals(Consolidate.fileHash(a), Consolidate.fileHash(b));
    }

    @Test
    void fileHash_differentContent_differentHash(@TempDir Path tmp) throws Exception {
        Path a = tmp.resolve("a.png");
        Path b = tmp.resolve("b.png");
        Files.writeString(a, "content-a");
        Files.writeString(b, "content-b");
        assertNotEquals(Consolidate.fileHash(a), Consolidate.fileHash(b));
    }

    // ── uniquePath ────────────────────────────────────────────────────────────

    @Test
    void uniquePath_noConflict_returnsCandidate(@TempDir Path tmp) throws Exception {
        Path result = Consolidate.uniquePath(tmp, "logo.png");
        assertEquals(tmp.resolve("logo.png"), result);
    }

    @Test
    void uniquePath_conflict_appendsSuffix(@TempDir Path tmp) throws Exception {
        Files.writeString(tmp.resolve("logo.png"), "x");
        Path result = Consolidate.uniquePath(tmp, "logo.png");
        assertEquals(tmp.resolve("logo_1.png"), result);
    }

    @Test
    void uniquePath_multipleConflicts_incrementsSuffix(@TempDir Path tmp) throws Exception {
        Files.writeString(tmp.resolve("logo.png"),   "x");
        Files.writeString(tmp.resolve("logo_1.png"), "x");
        Path result = Consolidate.uniquePath(tmp, "logo.png");
        assertEquals(tmp.resolve("logo_2.png"), result);
    }

    // ── consolidate — no duplicates ───────────────────────────────────────────

    @Test
    void consolidate_noDuplicates_promotesZero(@TempDir Path tmp) throws Exception {
        Path assets = tmp.resolve("assets");
        Files.createDirectories(assets.resolve("posts/post-a"));
        Files.createDirectories(assets.resolve("posts/post-b"));
        Files.writeString(assets.resolve("posts/post-a/img1.png"), "unique-a");
        Files.writeString(assets.resolve("posts/post-b/img2.png"), "unique-b");

        Consolidate.Result r = Consolidate.consolidate(assets, tmp.resolve("cleaned"));
        assertEquals(0, r.promoted());
        assertEquals(0, r.updatedHtml());
        assertTrue(r.duplicates().isEmpty());
    }

    @Test
    void consolidate_sameFileInSamePost_notConsolidated(@TempDir Path tmp) throws Exception {
        // Two files with same content in ONE post folder — not enough for consolidation (needs 2+ slugs)
        Path assets = tmp.resolve("assets");
        Files.createDirectories(assets.resolve("posts/post-a"));
        Files.writeString(assets.resolve("posts/post-a/img1.png"), "shared");
        Files.writeString(assets.resolve("posts/post-a/img2.png"), "shared");

        Consolidate.Result r = Consolidate.consolidate(assets, tmp.resolve("cleaned"));
        assertEquals(0, r.promoted());
    }

    @Test
    void consolidate_missingPostsDir_returnsZero(@TempDir Path tmp) throws Exception {
        Path assets = tmp.resolve("assets");
        Files.createDirectories(assets); // no posts/ subdirectory

        Consolidate.Result r = Consolidate.consolidate(assets, tmp.resolve("cleaned"));
        assertEquals(0, r.promoted());
        assertEquals(0, r.updatedHtml());
    }

    // ── consolidate — with duplicates ─────────────────────────────────────────

    @Test
    void consolidate_duplicateAcrossPosts_promotesOneAndDeletesDuplicate(@TempDir Path tmp) throws Exception {
        Path assets  = tmp.resolve("assets");
        Path cleaned = tmp.resolve("cleaned");
        Files.createDirectories(assets.resolve("posts/post-a"));
        Files.createDirectories(assets.resolve("posts/post-b"));
        Files.createDirectories(cleaned);

        byte[] shared = "shared-image-bytes".getBytes();
        Files.write(assets.resolve("posts/post-a/logo.png"), shared);
        Files.write(assets.resolve("posts/post-b/logo.png"), shared);

        Consolidate.Result r = Consolidate.consolidate(assets, cleaned);

        assertEquals(1, r.promoted());
        assertEquals(1, r.duplicates().size());
        assertTrue(Files.isDirectory(assets.resolve("global")));
        // Exactly one file in global/
        assertEquals(1, Files.list(assets.resolve("global")).count());
        // One of the two originals was deleted; the primary was moved to global/
        long remaining = (Files.isDirectory(assets.resolve("posts/post-a")) ? Files.list(assets.resolve("posts/post-a")).count() : 0)
                       + (Files.isDirectory(assets.resolve("posts/post-b")) ? Files.list(assets.resolve("posts/post-b")).count() : 0);
        assertEquals(0, remaining);
    }

    @Test
    void consolidate_threePostsSameContent_promotesOneDeletesTwo(@TempDir Path tmp) throws Exception {
        Path assets  = tmp.resolve("assets");
        Files.createDirectories(assets.resolve("posts/post-a"));
        Files.createDirectories(assets.resolve("posts/post-b"));
        Files.createDirectories(assets.resolve("posts/post-c"));

        byte[] shared = "triple-duplicate".getBytes();
        Files.write(assets.resolve("posts/post-a/img.png"), shared);
        Files.write(assets.resolve("posts/post-b/img.png"), shared);
        Files.write(assets.resolve("posts/post-c/img.png"), shared);

        Consolidate.Result r = Consolidate.consolidate(assets, tmp.resolve("cleaned"));
        assertEquals(1, r.promoted());
        // One file in global, two originals deleted
        assertEquals(1, Files.list(assets.resolve("global")).count());
    }

    // ── HTML rewriting ────────────────────────────────────────────────────────

    @Test
    void consolidate_htmlReferencesRewritten(@TempDir Path tmp) throws Exception {
        Path assets  = tmp.resolve("assets");
        Path cleaned = tmp.resolve("cleaned");
        Files.createDirectories(assets.resolve("posts/post-a"));
        Files.createDirectories(assets.resolve("posts/post-b"));
        Files.createDirectories(cleaned);

        byte[] shared = "img-bytes".getBytes();
        Files.write(assets.resolve("posts/post-a/hero.png"), shared);
        Files.write(assets.resolve("posts/post-b/hero.png"), shared);

        Path html = cleaned.resolve("post-a.html");
        Files.writeString(html, "<img src=\"/assets/posts/post-a/hero.png\">");

        Consolidate.consolidate(assets, cleaned);

        String rewritten = Files.readString(html);
        assertTrue(rewritten.contains("/assets/global/"),
                "HTML should reference global/: " + rewritten);
        assertFalse(rewritten.contains("/assets/posts/post-a/hero.png"),
                "Old path should be gone");
    }

    @Test
    void consolidate_htmlNotModifiedWhenNoMatch(@TempDir Path tmp) throws Exception {
        Path assets  = tmp.resolve("assets");
        Path cleaned = tmp.resolve("cleaned");
        Files.createDirectories(assets.resolve("posts/post-a"));
        Files.createDirectories(assets.resolve("posts/post-b"));
        Files.createDirectories(cleaned);

        byte[] shared = "bytes".getBytes();
        Files.write(assets.resolve("posts/post-a/img.png"), shared);
        Files.write(assets.resolve("posts/post-b/img.png"), shared);

        // HTML references a DIFFERENT asset — should not be modified
        Path html = cleaned.resolve("other.html");
        String original = "<img src=\"/assets/posts/post-a/other.png\">";
        Files.writeString(html, original);

        Consolidate.consolidate(assets, cleaned);

        assertEquals(original, Files.readString(html), "Unrelated HTML should be unchanged");
    }

    // ── index file ────────────────────────────────────────────────────────────

    @Test
    void consolidate_indexFileUpdatedAfterPromotion(@TempDir Path tmp) throws Exception {
        Path assets  = tmp.resolve("assets");
        Files.createDirectories(assets.resolve("posts/post-a"));
        Files.createDirectories(assets.resolve("posts/post-b"));

        byte[] shared = "data".getBytes();
        Files.write(assets.resolve("posts/post-a/file.png"), shared);
        Files.write(assets.resolve("posts/post-b/file.png"), shared);

        // Pre-populate index pointing to the original path
        Path indexFile = assets.resolve(".url-index.json");
        Files.writeString(indexFile,
                "{\"https://example.com/file.png\": \"posts/post-a/file.png\"}");

        Consolidate.consolidate(assets, tmp.resolve("cleaned"));

        String indexContent = Files.readString(indexFile);
        assertFalse(indexContent.contains("posts/post-a/file.png"),
                "Index should not point to old path");
        assertTrue(indexContent.contains("global/"),
                "Index should point to global/ path");
    }

    @Test
    void consolidate_noIndexFile_createsOneAfterPromotion(@TempDir Path tmp) throws Exception {
        Path assets  = tmp.resolve("assets");
        Files.createDirectories(assets.resolve("posts/post-a"));
        Files.createDirectories(assets.resolve("posts/post-b"));

        byte[] shared = "data".getBytes();
        Files.write(assets.resolve("posts/post-a/file.png"), shared);
        Files.write(assets.resolve("posts/post-b/file.png"), shared);

        // No .url-index.json — consolidate should still work
        Consolidate.consolidate(assets, tmp.resolve("cleaned"));

        // Index created (may be empty or have entries depending on implementation)
        assertTrue(Files.exists(assets.resolve(".url-index.json")));
    }

    // ── rewriteHtmlReferences standalone ─────────────────────────────────────

    @Test
    void rewriteHtmlReferences_emptyGlobalMap_returnsZero(@TempDir Path tmp) throws Exception {
        int result = Consolidate.rewriteHtmlReferences(tmp, Map.of(), tmp);
        assertEquals(0, result);
    }

    @Test
    void rewriteHtmlReferences_missingCleanedDir_returnsZero(@TempDir Path tmp) throws Exception {
        Path missing = tmp.resolve("does-not-exist");
        int result = Consolidate.rewriteHtmlReferences(missing,
                Map.of(tmp.resolve("old.png"), tmp.resolve("new.png")), tmp);
        assertEquals(0, result);
    }
}
```

- [ ] **Step 2: Run tests — confirm they fail (Consolidate class not found)**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=ConsolidateTest -q 2>&1 | grep -E "ERROR|FAIL|Cannot find" | head -5
```

Expected: COMPILATION ERROR — `Consolidate` not found.

---

### Task 2: Consolidate.java — Implement

**Files:**
- Create: `server/src/main/java/io/sparge/server/Consolidate.java`

- [ ] **Step 1: Create Consolidate.java**

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.*;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Hash-based asset consolidation — port of scripts/consolidate.py.
 *
 * Finds files with identical SHA-256 across different post folders, promotes
 * the first to assets/global/, deletes duplicates, updates .url-index.json,
 * and rewrites HTML references in the cleaned HTML directory.
 */
public final class Consolidate {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private Consolidate() {}

    public record Result(int promoted, int updatedHtml, List<Map<String, Object>> duplicates) {}

    /**
     * Main entry point — mirrors consolidate.py consolidate().
     *
     * @param assetsRoot  the assets/ directory (contains global/ and posts/)
     * @param cleanedDir  directory of HTML files whose asset references get rewritten
     */
    public static Result consolidate(Path assetsRoot, Path cleanedDir) throws Exception {
        Path indexFile = assetsRoot.resolve(".url-index.json");
        Map<String, String> index = loadIndex(indexFile);

        // Build hash → [path] map across all post folders
        Map<String, List<Path>> hashToPaths = new LinkedHashMap<>();
        Path postsDir = assetsRoot.resolve("posts");
        if (Files.isDirectory(postsDir)) {
            try (var slugDirs = Files.newDirectoryStream(postsDir)) {
                for (Path slugDir : slugDirs) {
                    if (!Files.isDirectory(slugDir)) continue;
                    try (var files = Files.newDirectoryStream(slugDir)) {
                        for (Path file : files) {
                            if (Files.isRegularFile(file)) {
                                String hash = fileHash(file);
                                hashToPaths.computeIfAbsent(hash, k -> new ArrayList<>()).add(file);
                            }
                        }
                    }
                }
            }
        }

        int promoted = 0;
        List<Map<String, Object>> duplicates = new ArrayList<>();
        Map<Path, Path> globalMap = new LinkedHashMap<>(); // old → new global path

        for (Map.Entry<String, List<Path>> entry : hashToPaths.entrySet()) {
            String     hash  = entry.getKey();
            List<Path> paths = entry.getValue();

            // Only consolidate if the same content appears in 2+ different post folders
            Set<String> slugs = paths.stream()
                    .map(p -> p.getParent().getFileName().toString())
                    .collect(Collectors.toSet());
            if (slugs.size() < 2) continue;

            // Promote the first file to global/
            Path primary   = paths.get(0);
            Path globalDir = assetsRoot.resolve("global");
            Files.createDirectories(globalDir);
            Path newPath = uniquePath(globalDir, primary.getFileName().toString());
            Files.move(primary, newPath);

            // Update index entries pointing to the old primary path
            String oldPrimaryRel = assetsRoot.relativize(primary).toString().replace('\\', '/');
            String newRel        = assetsRoot.relativize(newPath).toString().replace('\\', '/');
            index.replaceAll((url, rel) -> rel.equals(oldPrimaryRel) ? newRel : rel);

            globalMap.put(primary, newPath);
            promoted++;

            // Remove duplicate copies
            for (Path dup : paths.subList(1, paths.size())) {
                if (Files.exists(dup)) {
                    String dupOldRel = assetsRoot.relativize(dup).toString().replace('\\', '/');
                    index.replaceAll((url, rel) -> rel.equals(dupOldRel) ? newRel : rel);
                    globalMap.put(dup, newPath);
                    Files.delete(dup);
                }
            }

            saveIndex(indexFile, index);

            Map<String, Object> dup = new LinkedHashMap<>();
            dup.put("hash",        hash.substring(0, 12));
            dup.put("files",       paths.stream().map(Path::toString).collect(Collectors.toList()));
            dup.put("global_path", newPath.toString());
            duplicates.add(dup);
        }

        int updatedHtml = rewriteHtmlReferences(cleanedDir, globalMap, assetsRoot);
        return new Result(promoted, updatedHtml, duplicates);
    }

    /** SHA-256 hex of a file — matches Python's file_hash(). */
    static String fileHash(Path file) throws Exception {
        byte[] bytes  = Files.readAllBytes(file);
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder sb = new StringBuilder();
        for (byte b : digest) sb.append(String.format("%02x", b));
        return sb.toString();
    }

    /** Return a path in dir for filename that doesn't yet exist. */
    static Path uniquePath(Path dir, String filename) throws IOException {
        Path candidate = dir.resolve(filename);
        if (!Files.exists(candidate)) return candidate;
        String base = filename.contains(".") ? filename.substring(0, filename.lastIndexOf('.')) : filename;
        String ext  = filename.contains(".") ? filename.substring(filename.lastIndexOf('.'))    : "";
        for (int i = 1; i < 1000; i++) {
            candidate = dir.resolve(base + "_" + i + ext);
            if (!Files.exists(candidate)) return candidate;
        }
        throw new IOException("Could not find unique name for: " + filename);
    }

    /**
     * Rewrite /assets/posts/… references to /assets/global/… in all HTML files.
     * Package-private for unit testing.
     */
    static int rewriteHtmlReferences(Path cleanedDir, Map<Path, Path> globalMap, Path assetsRoot) throws IOException {
        if (!Files.isDirectory(cleanedDir) || globalMap.isEmpty()) return 0;

        // Build old_web_path → new_web_path string map
        Map<String, String> pathRemap = new LinkedHashMap<>();
        for (Map.Entry<Path, Path> entry : globalMap.entrySet()) {
            try {
                String oldRel = "/assets/" + assetsRoot.relativize(entry.getKey()).toString().replace('\\', '/');
                String newRel = "/assets/" + assetsRoot.relativize(entry.getValue()).toString().replace('\\', '/');
                pathRemap.put(oldRel, newRel);
            } catch (IllegalArgumentException ignored) {}
        }
        if (pathRemap.isEmpty()) return 0;

        Pattern regex = Pattern.compile(
                pathRemap.keySet().stream().map(Pattern::quote).collect(Collectors.joining("|")));

        int updated = 0;
        List<Path> htmlFiles;
        try (var stream = Files.walk(cleanedDir)) {
            htmlFiles = stream.filter(p -> p.toString().endsWith(".html"))
                              .collect(Collectors.toList());
        }
        for (Path htmlFile : htmlFiles) {
            String text    = Files.readString(htmlFile);
            String newText = regex.matcher(text).replaceAll(m -> pathRemap.get(m.group(0)));
            if (!newText.equals(text)) {
                Files.writeString(htmlFile, newText);
                updated++;
            }
        }
        return updated;
    }

    private static Map<String, String> loadIndex(Path indexFile) throws IOException {
        if (!Files.exists(indexFile)) return new LinkedHashMap<>();
        ObjectNode node = (ObjectNode) MAPPER.readTree(indexFile.toFile());
        Map<String, String> map = new LinkedHashMap<>();
        node.fields().forEachRemaining(e -> map.put(e.getKey(), e.getValue().asText()));
        return map;
    }

    private static void saveIndex(Path indexFile, Map<String, String> index) throws IOException {
        ObjectNode node = MAPPER.createObjectNode();
        index.forEach(node::put);
        MAPPER.writerWithDefaultPrettyPrinter().writeValue(indexFile.toFile(), node);
    }
}
```

- [ ] **Step 2: Run ConsolidateTest**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=ConsolidateTest -q 2>&1 | tail -10
```

Expected: All tests pass, BUILD SUCCESS.

- [ ] **Step 3: Run full suite to confirm no regressions**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dquarkus.http.test-port=8888 -q 2>&1 | grep -E "Tests run:|BUILD" | tail -5
```

Expected: BUILD SUCCESS, 0 failures.

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/Consolidate.java \
        server/src/test/java/io/sparge/server/ConsolidateTest.java
git commit -m "feat(#61): Consolidate.java — native Java port of consolidate.py (hash dedup, index, HTML rewrite)

Refs #59

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: ConsolidateResource + ConsolidateResourceTest

**Files:**
- Modify: `server/src/main/java/io/sparge/server/ConsolidateResource.java`
- Create: `server/src/test/java/io/sparge/server/ConsolidateResourceTest.java`

- [ ] **Step 1: Write ConsolidateResourceTest first**

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
import static org.junit.jupiter.api.Assertions.assertEquals;

@QuarkusTest
class ConsolidateResourceTest {

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

    @Test
    @EnabledIf("kieArchivePresent")
    void consolidateReturns200WithPromotedCount() {
        given()
                .when().post("/api/consolidate")
                .then()
                .statusCode(200)
                .body("promoted",     notNullValue())
                .body("updated_html", notNullValue())
                .body("duplicates",   notNullValue());
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void consolidateIsIdempotent() {
        // Running consolidate twice should promote 0 on the second run
        // (already consolidated, no new duplicates)
        given().when().post("/api/consolidate").then().statusCode(200);

        int promoted = given()
                .when().post("/api/consolidate")
                .then().statusCode(200)
                .extract().jsonPath().getInt("promoted");
        assertEquals(0, promoted,
                "Second consolidation run should find no new duplicates");
    }
}
```

- [ ] **Step 2: Replace ConsolidateResource with native implementation**

Full file replacement:

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.inject.Inject;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.util.List;
import java.util.Map;

@Path("/api/consolidate")
@Produces(MediaType.APPLICATION_JSON)
public class ConsolidateResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject ActiveProject activeProject;

    @POST
    public Response consolidate() {
        if (!activeProject.isActive()) {
            return err(400, "no active project");
        }
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        java.nio.file.Path assetsDir = cfg.assetsDir();
        java.nio.file.Path postsDir  = cfg.postsDir();
        if (assetsDir == null || postsDir == null) {
            return err(400, "project paths not configured");
        }
        try {
            Consolidate.Result result = Consolidate.consolidate(assetsDir, postsDir);
            String body = MAPPER.writeValueAsString(Map.of(
                    "promoted",     result.promoted(),
                    "updated_html", result.updatedHtml(),
                    "duplicates",   result.duplicates()
            ));
            return ok(body);
        } catch (Exception e) {
            String msg = e.getMessage() != null ? e.getMessage().replace("\"", "'") : "unknown";
            return err(500, msg);
        }
    }

    private static Response ok(String json) {
        return Response.ok(json)
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }

    private static Response err(int status, String msg) {
        return Response.status(status)
                .entity("{\"error\":\"" + msg + "\"}")
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }
}
```

- [ ] **Step 3: Run ConsolidateResourceTest**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dtest=ConsolidateResourceTest -Dquarkus.http.test-port=8888 -q 2>&1 | tail -10
```

Expected: Tests pass or skip. BUILD SUCCESS.

- [ ] **Step 4: Run full suite**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dquarkus.http.test-port=8888 -q 2>&1 | grep -E "Tests run:|BUILD" | tail -5
```

Expected: BUILD SUCCESS, 0 failures.

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/ConsolidateResource.java \
        server/src/test/java/io/sparge/server/ConsolidateResourceTest.java
git commit -m "feat(#61): native Java ConsolidateResource — remove consolidate JEP call

Refs #59

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: PostsResourceStagingTest — Write Failing Tests

**Files:**
- Create: `server/src/test/java/io/sparge/server/PostsResourceStagingTest.java`

- [ ] **Step 1: Create the test file**

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
class PostsResourceStagingTest {

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

    // ── Helper ────────────────────────────────────────────────────────────────

    private String firstSlug() {
        return given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");
    }

    // ── stagedGet ─────────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void stagedGet_noStagedFile_returns404() {
        String slug = firstSlug();
        // Ensure no staged file exists
        given().when().post("/api/posts/{slug}/reject-staged", slug);

        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then()
                .statusCode(404);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void stagedGet_unknownSlug_returns404() {
        given()
                .when().get("/api/posts/this-slug-does-not-exist-xyz/staged")
                .then()
                .statusCode(404);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void stagedGet_afterStage_returnsContent() {
        String slug = firstSlug();
        String content = "# Staged heading\n\nStaged body text.";

        given()
                .contentType("text/plain")
                .body(content)
                .when().post("/api/posts/{slug}/stage", slug)
                .then().statusCode(200);

        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then()
                .statusCode(200)
                .body(containsString("Staged heading"));

        // Cleanup
        given().when().post("/api/posts/{slug}/reject-staged", slug).then().statusCode(200);
    }

    // ── stage ─────────────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void stage_writesFileAndSetsStateStagedTrue() {
        String slug = firstSlug();

        given()
                .contentType("text/plain")
                .body("# Staged content")
                .when().post("/api/posts/{slug}/stage", slug)
                .then()
                .statusCode(200)
                .body("md.staged", equalTo(true))
                .body("slug", equalTo(slug));

        // Cleanup
        given().when().post("/api/posts/{slug}/reject-staged", slug).then().statusCode(200);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void stage_unknownSlug_stillSucceeds() {
        // stage() creates the .md.staged file even for unknown slugs —
        // the file is written to mdDir regardless; state.get() may return null.
        // This is consistent with Python behaviour.
        given()
                .contentType("text/plain")
                .body("# Content")
                .when().post("/api/posts/nonexistent-slug-xyz/stage")
                .then()
                .statusCode(200);
    }

    // ── rejectStaged ──────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void rejectStaged_removesFileAndSetsStagedFalse() {
        String slug = firstSlug();

        // Stage first
        given()
                .contentType("text/plain")
                .body("# Content to reject")
                .when().post("/api/posts/{slug}/stage", slug)
                .then().statusCode(200);

        // Reject
        given()
                .when().post("/api/posts/{slug}/reject-staged", slug)
                .then()
                .statusCode(200)
                .body("md.staged", equalTo(false));

        // Staged file should now be gone
        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then()
                .statusCode(404);
    }

    // ── acceptStaged ──────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void acceptStaged_noStagedFile_returns404() {
        String slug = firstSlug();
        // Ensure clean state
        given().when().post("/api/posts/{slug}/reject-staged", slug);

        given()
                .when().post("/api/posts/{slug}/accept-staged", slug)
                .then()
                .statusCode(404);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void acceptStaged_unknownSlug_returns404() {
        given()
                .when().post("/api/posts/this-slug-does-not-exist-xyz/accept-staged")
                .then()
                .statusCode(404);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void acceptStaged_withStagedFile_acceptsAndStagedFalse() {
        String slug = firstSlug();
        String content = "# Accepted content\n\nReady to publish.";

        // Stage
        given()
                .contentType("text/plain")
                .body(content)
                .when().post("/api/posts/{slug}/stage", slug)
                .then().statusCode(200);

        // Accept
        given()
                .when().post("/api/posts/{slug}/accept-staged", slug)
                .then()
                .statusCode(200)
                .body("md.staged",      equalTo(false))
                .body("md.generated_at", notNullValue());

        // Staged file gone
        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then()
                .statusCode(404);
    }

    // ── full lifecycle ────────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void fullStagingLifecycle_stageGetAccept() {
        String slug    = firstSlug();
        String content = "# Full lifecycle test\n\nStage → get → accept.";

        // 1. Stage
        given()
                .contentType("text/plain")
                .body(content)
                .when().post("/api/posts/{slug}/stage", slug)
                .then().statusCode(200).body("md.staged", equalTo(true));

        // 2. Get staged content
        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then().statusCode(200).body(containsString("Full lifecycle"));

        // 3. Accept
        given()
                .when().post("/api/posts/{slug}/accept-staged", slug)
                .then().statusCode(200).body("md.staged", equalTo(false));

        // 4. Staged file gone
        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then().statusCode(404);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void fullStagingLifecycle_stageGetReject() {
        String slug    = firstSlug();
        String content = "# Reject lifecycle\n\nStage → get → reject.";

        // 1. Stage
        given()
                .contentType("text/plain")
                .body(content)
                .when().post("/api/posts/{slug}/stage", slug)
                .then().statusCode(200).body("md.staged", equalTo(true));

        // 2. Get
        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then().statusCode(200).body(containsString("Reject lifecycle"));

        // 3. Reject
        given()
                .when().post("/api/posts/{slug}/reject-staged", slug)
                .then().statusCode(200).body("md.staged", equalTo(false));

        // 4. Staged file gone
        given()
                .when().get("/api/posts/{slug}/staged", slug)
                .then().statusCode(404);
    }
}
```

- [ ] **Step 2: Run tests — confirm stagedGet and acceptStaged tests fail (still JEP)**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dtest=PostsResourceStagingTest -Dquarkus.http.test-port=8888 2>&1 | grep -E "Tests run|ERROR|FAIL" | head -10
```

Expected: Tests for `stagedGet` and `acceptStaged` fail or time out (JEP). Tests for `stage` and `rejectStaged` may pass (already native).

---

### Task 5: PostsResource — Make Staging Native

**Files:**
- Modify: `server/src/main/java/io/sparge/server/PostsResource.java`

First, read the current file to understand the exact line numbers and structure before editing:

```bash
grep -n "staged\|accept-staged\|reject-staged\|stagedGet\|acceptStaged\|rejectStaged\|post_staged\|post_accept" \
  ~/claude/sparge/server/src/main/java/io/sparge/server/PostsResource.java
```

- [ ] **Step 1: Replace stagedGet() with native implementation**

Find the current `stagedGet()` method (the one that calls `bridge.call("bridge.post_staged_get", slug)`) and replace its body:

**Before:**
```java
@GET
@Path("{slug}/staged")
@Produces(MediaType.TEXT_PLAIN)
public Response stagedGet(@PathParam("slug") String slug) {
    return BridgeResponse.of(bridge.call("bridge.post_staged_get", slug));
}
```

**After:**
```java
@GET
@Path("{slug}/staged")
@Produces(MediaType.TEXT_PLAIN)
public Response stagedGet(@PathParam("slug") String slug) {
    SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
    if (cfg == null) return err(404, "no active project");
    java.nio.file.Path staged = cfg.mdDir().resolve(slug + ".md.staged");
    if (!java.nio.file.Files.exists(staged)) return err(404, "no staged version");
    try {
        return Response.ok(java.nio.file.Files.readString(staged))
                .header("Content-Type",                "text/plain; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

- [ ] **Step 2: Replace acceptStaged() with native implementation**

Find the current `acceptStaged()` method (calls `bridge.call("bridge.post_accept_staged", slug)`) and replace its body:

**Before:**
```java
@POST
@Path("{slug}/accept-staged")
public Response acceptStaged(@PathParam("slug") String slug) {
    return BridgeResponse.of(bridge.call("bridge.post_accept_staged", slug));
}
```

**After:**
```java
@POST
@Path("{slug}/accept-staged")
public Response acceptStaged(@PathParam("slug") String slug) {
    SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
    if (cfg == null) return err(404, "no active project");
    boolean ok = stateStore.acceptStaged(slug, cfg.mdDir(), cfg.postsDir());
    if (!ok) return Response.status(404)
            .entity("{\"error\":\"no staged version to accept\"}")
            .header("Content-Type",                "application/json; charset=utf-8")
            .header("Access-Control-Allow-Origin", "*")
            .build();
    ObjectNode post = stateStore.get(slug);
    return ok(post != null ? post.toString() : "{}");
}
```

- [ ] **Step 3: Remove JEP fallback from stage()**

Find the current `stage()` method which has a JEP fallback (`if (cfg == null) return BridgeResponse.of(...)`). Replace the entire method:

**After (no JEP fallback):**
```java
@POST
@Path("{slug}/stage")
@Consumes(MediaType.TEXT_PLAIN)
public Response stage(@PathParam("slug") String slug, String body) {
    SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
    if (cfg == null) return err(400, "no active project");
    try {
        java.nio.file.Files.writeString(cfg.mdDir().resolve(slug + ".md.staged"),
                body == null ? "" : body);
        stateStore.stage(slug);
        ObjectNode post = stateStore.get(slug);
        return ok(post != null ? post.toString() : "{}");
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

- [ ] **Step 4: Remove JEP fallback from rejectStaged()**

Find the current `rejectStaged()` method which has a JEP fallback. Replace with:

**After (no JEP fallback):**
```java
@POST
@Path("{slug}/reject-staged")
public Response rejectStaged(@PathParam("slug") String slug) {
    SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
    if (cfg == null) return err(400, "no active project");
    try {
        stateStore.rejectStaged(slug, cfg.mdDir());
        ObjectNode post = stateStore.get(slug);
        return ok(post != null ? post.toString() : "{}");
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

- [ ] **Step 5: Run staging tests**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dtest=PostsResourceStagingTest -Dquarkus.http.test-port=8888 -q 2>&1 | tail -10
```

Expected: All tests pass or skip. 0 failures.

- [ ] **Step 6: Run full suite**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dquarkus.http.test-port=8888 -q 2>&1 | grep -E "Tests run:|BUILD" | tail -5
```

Expected: BUILD SUCCESS, ≥225 tests, 0 failures.

- [ ] **Step 7: Verify PythonBridge not called for staging in PostsResource**

```bash
grep -n "bridge.call.*staged\|bridge.call.*accept\|post_staged_get\|post_accept_staged\|post_stage\b\|post_reject_staged" \
  ~/claude/sparge/server/src/main/java/io/sparge/server/PostsResource.java
```

Expected: no output.

- [ ] **Step 8: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/PostsResource.java \
        server/src/test/java/io/sparge/server/PostsResourceStagingTest.java
git commit -m "feat(#61): native Java staging endpoints — remove post_staged_get/post_accept_staged JEP calls, drop fallbacks

Refs #59

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Final Verification + Close Issue

- [ ] **Step 1: Verify PythonBridge removed from ConsolidateResource**

```bash
grep -n "PythonBridge\|bridge.call" \
  ~/claude/sparge/server/src/main/java/io/sparge/server/ConsolidateResource.java
```

Expected: no output.

- [ ] **Step 2: Run Python test suite**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --ignore=tests/python-legacy 2>&1 | tail -5
```

Expected: 270 passing, 0 failures.

- [ ] **Step 3: Run full Java suite (final)**

```bash
lsof -ti :8081 :8888 | xargs kill -9 2>/dev/null; sleep 2
cd ~/claude/sparge/server && mvn test -Dquarkus.http.test-port=8888 -q 2>&1 | grep -E "Tests run:|BUILD" | tail -5
```

Expected: BUILD SUCCESS, ≥225 tests, 0 failures.

- [ ] **Step 4: Close issue 61**

```bash
gh issue close 61 \
  --repo mdproctor/sparge \
  --comment "All 5 JEP calls removed: consolidate, post_staged_get, post_accept_staged, post_stage fallback, post_reject_staged fallback. Consolidate.java ported, all staging endpoints native Java. Tests passing. Closes #61"
```

- [ ] **Step 5: Update epic #59 — tick 6b**

```bash
# View current body to confirm the checkbox text
gh issue view 59 --repo mdproctor/sparge --json body -q .body | grep "6b"
# Then edit epic to tick 6b:
# Find the line "- [ ] 6b:" and change to "- [x] 6b:"
# Use gh issue edit --body "..." with the updated full body
```
