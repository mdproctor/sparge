# Phase 6a: config + search + static_resolve Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove 4 JEP bridge calls by implementing config, search, and static file resolution as native Java in their respective Quarkus resources.

**Architecture:** Three resource classes updated in isolation. ConfigResource reads/writes SpargeConfig via ActiveProject. SearchResource filters StateStore.getAll() using Java string matching and MD file reads. StaticResource resolves paths directly with java.nio. JEP bridge field removed from all three. TDD throughout — tests first, then implementation, then commit.

**Tech Stack:** Quarkus 3.34, JAX-RS (Jakarta), Jackson, Java NIO, JUnit 5, RestAssured, @QuarkusTest

---

## File Map

| File | Change |
|---|---|
| `server/src/main/java/io/sparge/server/ConfigResource.java` | Replace JEP with SpargeConfig + ActiveProject |
| `server/src/main/java/io/sparge/server/SearchResource.java` | Replace JEP with StateStore + NIO file reads |
| `server/src/main/java/io/sparge/server/StaticResource.java` | Replace JEP static_resolve with direct Path.resolve() |
| `server/src/test/java/io/sparge/server/ConfigResourceTest.java` | New — E2E @QuarkusTest |
| `server/src/test/java/io/sparge/server/SearchResourceTest.java` | New — unit tests + E2E @QuarkusTest |
| `server/src/test/java/io/sparge/server/StaticResourceTest.java` | New — E2E @QuarkusTest |

---

### Task 1: Create GitHub Epic and Issue 6a

**Files:** none (GitHub only)

- [ ] **Step 1: Create the Phase 6 epic**

```bash
gh issue create \
  --repo mdproctor/sparge \
  --title "Phase 6: Complete JEP elimination (22 calls)" \
  --body "Port all remaining 22 JEP bridge calls to native Java. When done, bridge.py is dead code and JEP can be removed from pom.xml.

## Child issues (in order)
- [ ] 6a: config + search + static_resolve (4 calls)
- [ ] 6b: consolidate + staging (3–5 calls)
- [ ] 6c: convert pipeline (6 calls)
- [ ] 6d: ingest pipeline (7 calls)

## Spec
docs/superpowers/specs/2026-04-17-phase6-design.md"
```

Note the epic issue number — referred to as **#EPIC** throughout this plan.

- [ ] **Step 2: Create issue 6a**

Replace `#EPIC` with the actual number from Step 1.

```bash
gh issue create \
  --repo mdproctor/sparge \
  --title "6a: Port config + search + static_resolve to native Java (4 JEP calls)" \
  --body "Remove 4 JEP bridge calls by implementing config, search, and static resolution natively.

Part of epic #EPIC

## JEP calls removed
- config_get, config_post → ConfigResource reads/writes SpargeConfig via ActiveProject
- search → SearchResource filters StateStore with Java string matching + MD file reads
- static_resolve → StaticResource resolves paths with java.nio, traversal-guarded

## Done when
- [ ] ConfigResourceTest passing (E2E @QuarkusTest)
- [ ] SearchResourceTest passing (unit + E2E @QuarkusTest)
- [ ] StaticResourceTest passing (E2E @QuarkusTest)
- [ ] PythonBridge removed from all 3 resources
- [ ] Python bridge tests for these 4 calls retired to tests/python-legacy/
- [ ] 270 pytest + ≥180 JUnit passing, 0 failures"
```

Note the issue number — referred to as **#6A** throughout this plan.

---

### Task 2: ConfigResource — Write Failing Tests

**Files:**
- Create: `server/src/test/java/io/sparge/server/ConfigResourceTest.java`

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
class ConfigResourceTest {

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    @BeforeEach
    void activateProject() {
        if (!kieArchivePresent()) return;
        String id = given()
                .when().get("/api/projects")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].id");
        if (id != null && !id.isEmpty()) {
            given().contentType("application/json")
                    .when().post("/api/projects/{id}/activate", id)
                    .then().statusCode(200);
        }
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void getConfigReturns200WithProjectName() {
        given()
                .when().get("/api/config")
                .then()
                .statusCode(200)
                .body("project_name", notNullValue());
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void getConfigDoesNotExposeInternalUnderscoreKeys() {
        given()
                .when().get("/api/config")
                .then()
                .statusCode(200)
                .body("_posts_dir", nullValue())
                .body("_md_dir",    nullValue());
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void postConfigSavesAndReturnsSavedTrue() {
        // Read current config, POST it back unchanged — a safe no-op
        String current = given()
                .when().get("/api/config")
                .then().statusCode(200)
                .extract().response().asString();

        given()
                .contentType("application/json")
                .body(current)
                .when().post("/api/config")
                .then()
                .statusCode(200)
                .body("saved", equalTo(true));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void postConfigInvalidJsonReturns400() {
        given()
                .contentType("application/json")
                .body("not valid json }{")
                .when().post("/api/config")
                .then()
                .statusCode(400);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void getAfterPostReflectsUpdate() {
        // Post a harmless synthetic field, then read it back
        given()
                .contentType("application/json")
                .body("{\"_test_roundtrip\": \"phase6a\"}")
                .when().post("/api/config")
                .then().statusCode(200);

        given()
                .when().get("/api/config")
                .then()
                .statusCode(200)
                .body("_test_roundtrip", equalTo("phase6a"));
    }
}
```

- [ ] **Step 2: Run tests — verify they compile and describe the expected behaviour**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=ConfigResourceTest -q 2>&1 | tail -20
```

Expected: Tests compile. With KIE archive present: tests PASS against existing JEP implementation (confirming the assertions are correct). Without KIE archive: tests SKIP.

---

### Task 3: ConfigResource — Implement Native Java

**Files:**
- Modify: `server/src/main/java/io/sparge/server/ConfigResource.java`

- [ ] **Step 1: Replace ConfigResource with native implementation**

Full file replacement:

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.nio.file.Path;

@Path("/api/config")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class ConfigResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject ActiveProject activeProject;

    @GET
    public Response get() {
        if (!activeProject.isActive()) {
            return error(400, "no active project");
        }
        return ok(activeProject.getConfig().raw().toString());
    }

    @POST
    public Response post(String body) {
        if (!activeProject.isActive()) {
            return error(400, "no active project");
        }
        if (body == null || body.isBlank()) body = "{}";
        try {
            ObjectNode patch = (ObjectNode) MAPPER.readTree(body);
            ObjectNode raw   = activeProject.getConfig().raw();
            patch.fields().forEachRemaining(e -> raw.set(e.getKey(), e.getValue()));
            Path configPath = activeProject.getProjectDir().resolve("config.json");
            SpargeConfig.save(configPath, raw);
            SpargeConfig.ResolvedConfig updated =
                    SpargeConfig.load(configPath, activeProject.getProjectDir());
            activeProject.set(activeProject.getProjectId(), updated, activeProject.getProjectDir());
            return ok("{\"saved\":true}");
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            return error(400, "invalid JSON");
        } catch (Exception e) {
            String msg = e.getMessage() != null ? e.getMessage().replace("\"", "'") : "unknown";
            return error(500, msg);
        }
    }

    private static Response ok(String json) {
        return Response.ok(json)
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }

    private static Response error(int status, String msg) {
        return Response.status(status)
                .entity("{\"error\":\"" + msg + "\"}")
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }
}
```

- [ ] **Step 2: Run ConfigResource tests**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=ConfigResourceTest -q 2>&1 | tail -20
```

Expected: All enabled tests PASS (or SKIP without KIE archive).

- [ ] **Step 3: Run full Java suite — confirm no regressions**

```bash
cd ~/claude/sparge/server && mvn test -q 2>&1 | tail -10
```

Expected: `BUILD SUCCESS`, 0 failures.

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/ConfigResource.java \
        server/src/test/java/io/sparge/server/ConfigResourceTest.java
git commit -m "feat(#6A): native Java ConfigResource — remove config_get/config_post JEP calls

Refs #EPIC

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: SearchResource — Write Failing Tests

**Files:**
- Create: `server/src/test/java/io/sparge/server/SearchResourceTest.java`

- [ ] **Step 1: Create the test file**

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;
import static org.junit.jupiter.api.Assertions.*;

@QuarkusTest
class SearchResourceTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    @BeforeEach
    void activateProject() {
        if (!kieArchivePresent()) return;
        String id = given()
                .when().get("/api/projects")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].id");
        if (id != null && !id.isEmpty()) {
            given().contentType("application/json")
                    .when().post("/api/projects/{id}/activate", id)
                    .then().statusCode(200);
        }
    }

    // ── Unit tests — filterSlugs (no HTTP, no KIE archive needed) ─────────────

    private static ObjectNode post(String slug, String title) {
        ObjectNode n = MAPPER.createObjectNode();
        n.put("slug", slug);
        n.put("title", title);
        return n;
    }

    @Test
    void filterSlugs_emptyQuery_returnsAllSlugs() {
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("alpha", "Alpha Post"), post("beta", "Beta Post"));
        List<String> result = r.filterSlugs(posts, "", "both", null);
        assertEquals(List.of("alpha", "beta"), result);
    }

    @Test
    void filterSlugs_titleScope_matchesCaseInsensitive() {
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("java-guide", "Java Guide"), post("python-tips", "Python Tips"));
        List<String> result = r.filterSlugs(posts, "java", "title", null);
        assertEquals(List.of("java-guide"), result);
    }

    @Test
    void filterSlugs_titleScope_doesNotMatchBody() {
        SearchResource r = new SearchResource();
        // title doesn't contain "quarkus" — body not read when scope=title
        List<ObjectNode> posts = List.of(post("a", "Unrelated Title"));
        List<String> result = r.filterSlugs(posts, "quarkus", "title", null);
        assertTrue(result.isEmpty());
    }

    @Test
    void filterSlugs_noMatch_returnsEmpty() {
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("a", "Alpha"), post("b", "Beta"));
        List<String> result = r.filterSlugs(posts, "zzznomatch", "both", null);
        assertTrue(result.isEmpty());
    }

    @Test
    void filterSlugs_bodyScope_readsMarkdownFile(@TempDir Path tmp) throws Exception {
        Files.writeString(tmp.resolve("a.md"), "# Hello Quarkus native world");
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("a", "Unrelated Title"));
        List<String> result = r.filterSlugs(posts, "quarkus", "body", tmp);
        assertEquals(List.of("a"), result);
    }

    @Test
    void filterSlugs_bodyScope_missingMdFile_skipsPost(@TempDir Path tmp) {
        // No .md file in tmp for slug "a"
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("a", "Unrelated Title"));
        List<String> result = r.filterSlugs(posts, "quarkus", "body", tmp);
        assertTrue(result.isEmpty());
    }

    @Test
    void filterSlugs_bothScope_matchesTitle_doesNotReadBody(@TempDir Path tmp) throws Exception {
        // Title matches — body file contains opposite — title match should win without reading body
        Files.writeString(tmp.resolve("a.md"), "nothing relevant here");
        SearchResource r = new SearchResource();
        List<ObjectNode> posts = List.of(post("a", "Java Guide"));
        List<String> result = r.filterSlugs(posts, "java", "both", tmp);
        assertEquals(List.of("a"), result);
    }

    // ── E2E @QuarkusTest ───────────────────────────────────────────────────────

    @Test
    @EnabledIf("kieArchivePresent")
    void emptyQueryReturnsAllSlugs() {
        given()
                .queryParam("q",     "")
                .queryParam("scope", "both")
                .when().get("/api/search")
                .then()
                .statusCode(200)
                .body("slugs",        notNullValue())
                .body("slugs.size()", greaterThan(0));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void defaultScopeParameterWorks() {
        // No scope param — defaults to "both"
        given()
                .queryParam("q", "")
                .when().get("/api/search")
                .then()
                .statusCode(200)
                .body("slugs.size()", greaterThan(0));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void unmatchedQueryReturnsEmptySlugs() {
        given()
                .queryParam("q",     "xyzzy-this-cannot-match-any-kie-title-99zz")
                .queryParam("scope", "title")
                .when().get("/api/search")
                .then()
                .statusCode(200)
                .body("slugs", hasSize(0));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void titleSearchFindsKnownKeyword() {
        // "java" appears in KIE archive post titles
        List<String> slugs = given()
                .queryParam("q",     "java")
                .queryParam("scope", "title")
                .when().get("/api/search")
                .then()
                .statusCode(200)
                .extract().jsonPath().getList("slugs", String.class);
        assertFalse(slugs.isEmpty(), "Expected at least one Java-titled post in the KIE archive");
    }
}
```

- [ ] **Step 2: Run tests — confirm compilation fails (filterSlugs not defined yet)**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=SearchResourceTest -q 2>&1 | grep -E "ERROR|FAIL|filterSlugs" | head -10
```

Expected: COMPILATION ERROR — `filterSlugs` not found on `SearchResource`.

---

### Task 5: SearchResource — Implement Native Java

**Files:**
- Modify: `server/src/main/java/io/sparge/server/SearchResource.java`

- [ ] **Step 1: Replace SearchResource with native implementation**

Full file replacement:

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Path("/api/search")
@Produces(MediaType.APPLICATION_JSON)
public class SearchResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject StateStore stateStore;
    @Inject ActiveProject activeProject;

    public SearchResource() {}

    @GET
    public Response search(@QueryParam("q")     @DefaultValue("") String q,
                           @QueryParam("scope") @DefaultValue("both") String scope) {
        String query  = q.strip().toLowerCase();
        Path   mdDir  = activeProject.isActive() ? activeProject.getConfig().mdDir() : null;
        List<String> slugs = filterSlugs(stateStore.getAll(), query, scope, mdDir);
        try {
            return ok(MAPPER.writeValueAsString(Map.of("slugs", slugs)));
        } catch (Exception e) {
            return Response.serverError().build();
        }
    }

    /**
     * Package-private for unit testing.
     * Empty query returns all slugs. Non-empty filters by title and/or MD body content.
     */
    List<String> filterSlugs(List<ObjectNode> posts, String query, String scope, Path mdDir) {
        List<String> results = new ArrayList<>();
        for (ObjectNode p : posts) {
            String slug = p.path("slug").asText("");
            if (query.isEmpty()) { results.add(slug); continue; }

            String  title   = p.path("title").asText("").toLowerCase();
            boolean inTitle = (scope.equals("title") || scope.equals("both")) && title.contains(query);
            boolean inBody  = false;

            if (!inTitle && mdDir != null && (scope.equals("body") || scope.equals("both"))) {
                Path mdPath = mdDir.resolve(slug + ".md");
                if (Files.exists(mdPath)) {
                    try {
                        inBody = Files.readString(mdPath).toLowerCase().contains(query);
                    } catch (Exception ignored) {}
                }
            }
            if (inTitle || inBody) results.add(slug);
        }
        return results;
    }

    private static Response ok(String json) {
        return Response.ok(json)
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }
}
```

- [ ] **Step 2: Run SearchResource tests**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=SearchResourceTest -q 2>&1 | tail -20
```

Expected: All unit tests PASS. E2E tests PASS or SKIP.

- [ ] **Step 3: Run full Java suite**

```bash
cd ~/claude/sparge/server && mvn test -q 2>&1 | tail -10
```

Expected: `BUILD SUCCESS`, 0 failures.

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/SearchResource.java \
        server/src/test/java/io/sparge/server/SearchResourceTest.java
git commit -m "feat(#6A): native Java SearchResource — remove search JEP call

Refs #EPIC

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: StaticResource — Write Failing Tests

**Files:**
- Create: `server/src/test/java/io/sparge/server/StaticResourceTest.java`

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
class StaticResourceTest {

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    @BeforeEach
    void activateProject() {
        if (!kieArchivePresent()) return;
        String id = given()
                .when().get("/api/projects")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].id");
        if (id != null && !id.isEmpty()) {
            given().contentType("application/json")
                    .when().post("/api/projects/{id}/activate", id)
                    .then().statusCode(200);
        }
    }

    @Test
    void rootRedirectsToProjectsHtml() {
        given()
                .redirects().follow(false)
                .when().get("/")
                .then()
                .statusCode(anyOf(is(301), is(302), is(307), is(308)))
                .header("Location", containsString("projects.html"));
    }

    @Test
    void uiProjectsHtmlIsServed() {
        given()
                .when().get("/ui/projects.html")
                .then()
                .statusCode(200)
                .contentType(containsString("text/html"));
    }

    @Test
    void unknownStaticPathReturns404() {
        given()
                .when().get("/xyzzy-this-path-does-not-exist/file.txt")
                .then()
                .statusCode(404);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void pathTraversalAttemptReturns403OrNot200() {
        // Traversal attempts must not serve files outside serve root
        given()
                .when().get("/../../etc/passwd")
                .then()
                .statusCode(not(equalTo(200)));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void knownLegacyAssetIsServed() {
        // A real HTML post file known to exist in the KIE archive
        String slug = given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");

        given()
                .when().get("/legacy/posts/mark-proctor/" + slug + ".html")
                .then()
                .statusCode(200)
                .contentType(containsString("text/html"));
    }
}
```

- [ ] **Step 2: Run tests — confirm the two non-KIE tests already pass with current JEP code**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=StaticResourceTest -q 2>&1 | tail -20
```

Expected: `rootRedirectsToProjectsHtml` and `uiProjectsHtmlIsServed` PASS (these don't involve JEP). `unknownStaticPathReturns404` may fail since JEP is still in use — that's expected. KIE tests SKIP or run.

---

### Task 7: StaticResource — Implement Native Java

**Files:**
- Modify: `server/src/main/java/io/sparge/server/StaticResource.java`

- [ ] **Step 1: Replace StaticResource with native path resolution**

Full file replacement (removes JEP bridge, ObjectMapper; adds ActiveProject):

```java
package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.core.Response;

import java.io.IOException;
import java.net.URI;
import java.net.URLConnection;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Serves three categories:
 *   GET /               → redirect to /ui/projects.html
 *   GET /ui/{path}      → ../ui/{path} on disk
 *   GET /{anything}     → blog asset from SERVE_ROOT via native path resolution
 */
@jakarta.ws.rs.Path("/")
public class StaticResource {

    @Inject ActiveProject activeProject;

    private final Path uiDir;

    public StaticResource() {
        Path serverDir = Paths.get(System.getProperty("user.dir")).toAbsolutePath();
        this.uiDir = serverDir.getParent().resolve("ui");
    }

    @GET
    public Response root() {
        return Response.temporaryRedirect(URI.create("/ui/projects.html")).build();
    }

    @GET
    @jakarta.ws.rs.Path("ui/{path:.*}")
    public Response serveUi(@PathParam("path") String path) {
        String rel = (path == null || path.isEmpty()) ? "projects.html" : path;
        return serveFile(uiDir.resolve(rel));
    }

    @GET
    @jakarta.ws.rs.Path("{path:.*}")
    public Response serveStatic(@PathParam("path") String path) {
        if (!activeProject.isActive()) {
            return Response.status(404).build();
        }
        Path serveRoot = activeProject.getConfig().serveRoot().toAbsolutePath().normalize();
        String decoded = URLDecoder.decode(path == null ? "" : path, StandardCharsets.UTF_8);
        String rel     = decoded.startsWith("/") ? decoded.substring(1) : decoded;
        Path   file    = serveRoot.resolve(rel).normalize();
        if (!file.startsWith(serveRoot)) {
            return Response.status(403).build();
        }
        return serveFile(file);
    }

    private Response serveFile(Path file) {
        try {
            byte[] data = Files.readAllBytes(file);
            String mime = URLConnection.guessContentTypeFromName(file.toString());
            if (mime == null) mime = "application/octet-stream";
            return Response.ok(data)
                    .header("Content-Type",                mime)
                    .header("Access-Control-Allow-Origin", "*")
                    .build();
        } catch (NoSuchFileException e) {
            return Response.status(404).build();
        } catch (IOException e) {
            return Response.serverError().build();
        }
    }
}
```

- [ ] **Step 2: Run StaticResource tests**

```bash
cd ~/claude/sparge/server && mvn test -Dtest=StaticResourceTest -q 2>&1 | tail -20
```

Expected: All tests PASS or SKIP.

- [ ] **Step 3: Run full Java suite**

```bash
cd ~/claude/sparge/server && mvn test -q 2>&1 | tail -10
```

Expected: `BUILD SUCCESS`, 0 failures.

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/StaticResource.java \
        server/src/test/java/io/sparge/server/StaticResourceTest.java
git commit -m "feat(#6A): native Java StaticResource — remove static_resolve JEP call

Refs #EPIC

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Retire Python Bridge Tests + Final Verification

**Files:**
- `tests/` — find and retire bridge tests for config/search/static_resolve

- [ ] **Step 1: Find Python tests that cover these bridge calls**

```bash
grep -r "config_get\|config_post\|bridge\.search\|static_resolve" \
  ~/claude/sparge/tests/ --include="*.py" -l
```

- [ ] **Step 2: Retire each matching test file**

For each file found, move it to `tests/python-legacy/` and add a header comment:

```bash
# Example — adjust for each file found by Step 1:
mv ~/claude/sparge/tests/<test_file>.py ~/claude/sparge/tests/python-legacy/
```

Then open each moved file and add at the top:

```python
# Retired — Phase 6a. Replaced by ConfigResourceTest.java / SearchResourceTest.java /
# StaticResourceTest.java in server/src/test/java/io/sparge/server/
```

If matching tests live in a shared file alongside non-retired tests, copy only the relevant functions to a new `tests/python-legacy/test_bridge_6a.py` file rather than moving the whole file.

- [ ] **Step 3: Confirm Python suite still passes**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --ignore=tests/python-legacy 2>&1 | tail -5
```

Expected: 270 (or fewer if bridge tests were moved) passing, 0 failures.

- [ ] **Step 4: Confirm Java suite still passes**

```bash
cd ~/claude/sparge/server && mvn test -q 2>&1 | tail -10
```

Expected: `BUILD SUCCESS`, 0 failures.

- [ ] **Step 5: Verify PythonBridge is gone from all 3 resources**

```bash
grep -n "PythonBridge\|bridge\.call\|@Inject.*bridge" \
  ~/claude/sparge/server/src/main/java/io/sparge/server/ConfigResource.java \
  ~/claude/sparge/server/src/main/java/io/sparge/server/SearchResource.java \
  ~/claude/sparge/server/src/main/java/io/sparge/server/StaticResource.java
```

Expected: no output (no matches).

- [ ] **Step 6: Commit retired tests**

```bash
cd ~/claude/sparge
git add tests/python-legacy/ tests/
git commit -m "chore(#6A): retire Python bridge tests for config/search/static_resolve

Refs #EPIC

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 7: Close issue 6a**

```bash
gh issue close #6A \
  --repo mdproctor/sparge \
  --comment "All 4 JEP calls removed (config_get, config_post, search, static_resolve). ConfigResource, SearchResource, StaticResource fully native Java. Tests passing. Python bridge tests retired to python-legacy/. Closes #6A"
```

- [ ] **Step 8: Mark 6a done on the epic (manual)**

Open the epic issue (#EPIC) on GitHub and tick the `6a` checkbox in the body.
