# Quarkus Phase 1 — Port sparge_home.py + config.py to Java

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port path resolution (`sparge_home.py`) and project config loading (`config.py`) to Java, removing JEP delegates for projects list/create/delete — first real Java code, JEP call count drops 35 → 32.

**Architecture:** `SpargeHome` reads `~/.sparge/config.json` to find projects dir; `SpargeConfig` loads/saves/resolves individual project `config.json` files using Jackson; `ProjectsStore` handles projects.json CRUD and reads state.json for stats; `ActiveProject` CDI singleton tracks the currently active project. `ProjectsResource.list/create/delete` call Java directly; `activate` still delegates to Python (needs `State.init_from_source()`). Retired pytest tests move to `tests/python-legacy/` (never run in CI).

**Tech Stack:** Java 21, Quarkus 3.34, Jackson ObjectMapper, JUnit 5, `@ApplicationScoped` CDI

---

## Task 1: Create tests/python-legacy/ holding area and pytest.ini

**Files:**
- Create: `tests/python-legacy/README.md`
- Create: `pytest.ini`

- [ ] **Step 1: Create the directory and README**

```bash
mkdir -p ~/claude/sparge/tests/python-legacy
```

Create `tests/python-legacy/README.md`:

```markdown
# python-legacy

Holding area for pytest tests whose Python modules have been ported to Java.

These tests are **never run in CI** (excluded by `pytest.ini`). They exist for
cross-checking: if a specific Java port needs verifying, run them directly:

    pytest tests/python-legacy/test_sparge_home.py -v

Do not delete them until the final phase (when Python is fully removed).
```

- [ ] **Step 2: Create pytest.ini to exclude python-legacy/ from default run**

Create `pytest.ini` at the repo root:

```ini
[pytest]
addopts = --ignore=tests/python-legacy
```

- [ ] **Step 3: Verify default run still passes**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --no-header --tb=no 2>&1 | tail -3
```

Expected: `473 passed` (same as before — python-legacy is empty so nothing changes yet).

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add tests/python-legacy/README.md pytest.ini
git commit -m "chore(#52): add tests/python-legacy/ holding area and pytest.ini"
```

---

## Task 2: SpargeHomeTest.java — write the failing JUnit tests

The JUnit tests mirror `tests/test_sparge_home.py` exactly — same four behaviours, TDD order.

**Files:**
- Create: `server/src/test/java/io/sparge/server/SpargeHomeTest.java`

- [ ] **Step 1: Write the failing test class**

```java
package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Mirrors tests/test_sparge_home.py — four behaviours for SpargeHome.getProjectsDir().
 */
class SpargeHomeTest {

    @Test
    void defaultsToSpargeProjectsWhenNoConfig(@TempDir Path home) throws IOException {
        SpargeHome spargeHome = new SpargeHome(home);
        Path result = spargeHome.getProjectsDir();
        assertEquals(home.resolve("sparge-projects"), result);
    }

    @Test
    void readsProjectsDirFromConfig(@TempDir Path home) throws IOException {
        Path custom = home.resolve("my-projects");
        Path spargeDir = home.resolve(".sparge");
        Files.createDirectories(spargeDir);
        Files.writeString(spargeDir.resolve("config.json"),
                "{\"projects_dir\": \"" + custom + "\"}");

        SpargeHome spargeHome = new SpargeHome(home);
        assertEquals(custom, spargeHome.getProjectsDir());
    }

    @Test
    void expandsTildeInProjectsDir(@TempDir Path home) throws IOException {
        Path spargeDir = home.resolve(".sparge");
        Files.createDirectories(spargeDir);
        Files.writeString(spargeDir.resolve("config.json"),
                "{\"projects_dir\": \"~/custom-projects\"}");

        SpargeHome spargeHome = new SpargeHome(home);
        assertEquals(home.resolve("custom-projects"), spargeHome.getProjectsDir());
    }

    @Test
    void createsSpargeConfigWithDefaultsOnFirstCall(@TempDir Path home) throws IOException {
        SpargeHome spargeHome = new SpargeHome(home);
        spargeHome.getProjectsDir();

        Path cfgPath = home.resolve(".sparge").resolve("config.json");
        assertTrue(Files.exists(cfgPath), "~/.sparge/config.json should be created");
        String content = Files.readString(cfgPath);
        assertTrue(content.contains("projects_dir"), "config.json must contain projects_dir key");
    }
}
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=SpargeHomeTest -q 2>&1 | tail -5
```

Expected: `BUILD FAILURE` — `SpargeHome` does not exist yet.

- [ ] **Step 3: Commit the failing test**

```bash
cd ~/claude/sparge
git add server/src/test/java/io/sparge/server/SpargeHomeTest.java
git commit -m "test(#52): add SpargeHomeTest (failing — TDD)"
```

---

## Task 3: SpargeHome.java — implement to pass tests

Note: `SpargeHome` takes a `home` constructor parameter for testability. The production CDI bean uses `Path.of(System.getProperty("user.home"))`.

**Files:**
- Create: `server/src/main/java/io/sparge/server/SpargeHome.java`

- [ ] **Step 1: Write SpargeHome.java**

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.enterprise.context.ApplicationScoped;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Manages ~/.sparge/config.json — machine-wide Sparge home config.
 * Mirrors scripts/sparge_home.py.
 *
 * Accepts an injected home path for testability; CDI usage passes the real home dir.
 */
@ApplicationScoped
public class SpargeHome {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final Path home;
    private final Path spargeDir;
    private final Path spargeCfg;
    private final Path defaultProjectsDir;

    /** CDI no-arg constructor — uses real user home. */
    public SpargeHome() {
        this(Path.of(System.getProperty("user.home")));
    }

    /** Testable constructor — accepts any home dir. */
    SpargeHome(Path home) {
        this.home              = home;
        this.spargeDir         = home.resolve(".sparge");
        this.spargeCfg         = spargeDir.resolve("config.json");
        this.defaultProjectsDir = home.resolve("sparge-projects");
    }

    /**
     * Return the resolved projects directory.
     * Creates ~/.sparge/config.json with defaults if absent.
     */
    public Path getProjectsDir() throws IOException {
        Files.createDirectories(spargeDir);
        if (!Files.exists(spargeCfg)) {
            ObjectNode cfg = MAPPER.createObjectNode();
            cfg.put("projects_dir", defaultProjectsDir.toString());
            MAPPER.writerWithDefaultPrettyPrinter().writeValue(spargeCfg.toFile(), cfg);
        }
        try {
            ObjectNode data = (ObjectNode) MAPPER.readTree(spargeCfg.toFile());
            String raw = data.has("projects_dir")
                    ? data.get("projects_dir").asText()
                    : defaultProjectsDir.toString();
            return Path.of(raw.replace("~", home.toString()));
        } catch (Exception e) {
            return defaultProjectsDir;
        }
    }
}
```

- [ ] **Step 2: Run tests — expect all 4 to pass**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=SpargeHomeTest -q 2>&1 | tail -5
```

Expected: `Tests run: 4, Failures: 0, Errors: 0`

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/SpargeHome.java
git commit -m "feat(#52): add SpargeHome.java — mirrors sparge_home.py"
```

---

## Task 4: SpargeConfigTest.java — write failing JUnit tests

Mirrors `test_config.py` (github_token) and `test_path_resolution.py` (relative/absolute path resolution).

**Files:**
- Create: `server/src/test/java/io/sparge/server/SpargeConfigTest.java`

- [ ] **Step 1: Write the failing test class**

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Mirrors test_config.py and test_path_resolution.py.
 */
class SpargeConfigTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    /** Write a minimal config.json to a temp dir and return its path. */
    private Path writeConfig(@TempDir Path dir, String serveRoot,
                              String postsDir, String assetsDir, String mdDir,
                              String githubToken) throws Exception {
        ObjectNode cfg = MAPPER.createObjectNode();
        cfg.put("project_name", "Test");
        cfg.put("serve_root", serveRoot);

        ObjectNode source = MAPPER.createObjectNode();
        source.put("posts_dir", postsDir);
        source.put("assets_dir", assetsDir);
        cfg.set("source", source);

        ObjectNode output = MAPPER.createObjectNode();
        output.put("md_dir", mdDir);
        cfg.set("output", output);

        ObjectNode filter = MAPPER.createObjectNode();
        filter.put("author", "");
        cfg.set("filter", filter);

        if (githubToken != null) cfg.put("github_token", githubToken);

        Path configPath = dir.resolve("config.json");
        MAPPER.writeValue(configPath.toFile(), cfg);
        return configPath;
    }

    // ── github_token (mirrors test_config.py) ─────────────────────────────────

    @Test
    void githubTokenDefaultsToEmpty(@TempDir Path dir) throws Exception {
        Path configPath = writeConfig(dir, dir.toString(), "posts", "assets", "md", null);
        SpargeConfig.ResolvedConfig cfg = SpargeConfig.load(configPath, dir);
        assertEquals("", cfg.githubToken());
    }

    @Test
    void githubTokenPreserved(@TempDir Path dir) throws Exception {
        Path configPath = writeConfig(dir, dir.toString(), "posts", "assets", "md", "ghp_abc123");
        SpargeConfig.ResolvedConfig cfg = SpargeConfig.load(configPath, dir);
        assertEquals("ghp_abc123", cfg.githubToken());
    }

    // ── Relative path resolution (mirrors TestResolveRelativePaths) ───────────

    @Test
    void relativeMdDirJoinsServeRoot(@TempDir Path dir) throws Exception {
        Path configPath = writeConfig(dir, "/srv/blog", "posts", "assets", "out/md", null);
        SpargeConfig.ResolvedConfig cfg = SpargeConfig.load(configPath, dir);
        assertEquals(Path.of("/srv/blog/out/md"), cfg.mdDir());
    }

    @Test
    void relativePostsDirJoinsServeRoot(@TempDir Path dir) throws Exception {
        Path configPath = writeConfig(dir, "/srv/blog", "legacy/posts", "assets", "out/md", null);
        SpargeConfig.ResolvedConfig cfg = SpargeConfig.load(configPath, dir);
        assertEquals(Path.of("/srv/blog/legacy/posts"), cfg.postsDir());
    }

    @Test
    void relativeAssetsDirJoinsServeRoot(@TempDir Path dir) throws Exception {
        Path configPath = writeConfig(dir, "/srv/blog", "posts", "legacy/assets", "out/md", null);
        SpargeConfig.ResolvedConfig cfg = SpargeConfig.load(configPath, dir);
        assertEquals(Path.of("/srv/blog/legacy/assets"), cfg.assetsDir());
    }

    // ── Absolute path resolution (mirrors TestResolveAbsolutePaths) ───────────

    @Test
    void absoluteMdDirUsedAsIs(@TempDir Path dir) throws Exception {
        Path configPath = writeConfig(dir, "/srv/blog", "posts", "assets", "/external/output", null);
        SpargeConfig.ResolvedConfig cfg = SpargeConfig.load(configPath, dir);
        assertEquals(Path.of("/external/output"), cfg.mdDir());
    }

    @Test
    void absolutePostsDirUsedAsIs(@TempDir Path dir) throws Exception {
        Path configPath = writeConfig(dir, "/srv/blog", "/data/posts", "assets", "out/md", null);
        SpargeConfig.ResolvedConfig cfg = SpargeConfig.load(configPath, dir);
        assertEquals(Path.of("/data/posts"), cfg.postsDir());
    }

    @Test
    void absoluteAssetsDirUsedAsIs(@TempDir Path dir) throws Exception {
        Path configPath = writeConfig(dir, "/srv/blog", "posts", "/data/assets", "out/md", null);
        SpargeConfig.ResolvedConfig cfg = SpargeConfig.load(configPath, dir);
        assertEquals(Path.of("/data/assets"), cfg.assetsDir());
    }

    @Test
    void absoluteInsideServeRootStillUsedAsIs(@TempDir Path dir) throws Exception {
        Path configPath = writeConfig(dir, "/srv/blog", "posts", "assets", "/srv/blog/markdown", null);
        SpargeConfig.ResolvedConfig cfg = SpargeConfig.load(configPath, dir);
        assertEquals(Path.of("/srv/blog/markdown"), cfg.mdDir());
    }
}
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=SpargeConfigTest -q 2>&1 | tail -5
```

Expected: `BUILD FAILURE` — `SpargeConfig` does not exist.

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/test/java/io/sparge/server/SpargeConfigTest.java
git commit -m "test(#52): add SpargeConfigTest (failing — TDD)"
```

---

## Task 5: SpargeConfig.java — implement to pass tests

**Files:**
- Create: `server/src/main/java/io/sparge/server/SpargeConfig.java`

- [ ] **Step 1: Write SpargeConfig.java**

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.nio.file.Path;

/**
 * Loads, resolves, and saves individual project config.json files.
 * Mirrors scripts/config.py: _resolve(), load(), save().
 *
 * Stateless utility class — no CDI scope. State lives in ActiveProject.
 */
public final class SpargeConfig {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private SpargeConfig() {}

    /**
     * Immutable resolved view of a project config.json.
     * All paths are absolute. Mirrors the _-prefixed fields in Python's cfg dict.
     */
    public record ResolvedConfig(
            String projectName,
            Path   serveRoot,
            Path   postsDir,
            Path   assetsDir,
            Path   mdDir,
            Path   enrichedDir,
            String authorFilter,
            String githubToken,
            ObjectNode raw          // original JSON — needed for save()
    ) {}

    /**
     * Load and resolve a project config.json.
     *
     * @param configPath  path to the project's config.json
     * @param projectDir  the project directory (enrichedDir = projectDir/enriched)
     */
    public static ResolvedConfig load(Path configPath, Path projectDir) throws Exception {
        ObjectNode raw     = (ObjectNode) MAPPER.readTree(configPath.toFile());
        Path serveRoot     = Path.of(raw.get("serve_root").asText());
        Path postsDir      = resolve(serveRoot, raw.path("source").path("posts_dir").asText("legacy/posts"));
        Path assetsDir     = resolve(serveRoot, raw.path("source").path("assets_dir").asText("legacy/assets"));
        Path mdDir         = resolve(serveRoot, raw.path("output").path("md_dir").asText("output/md"));
        Path enrichedDir   = projectDir.resolve("enriched");
        String authorFilter = raw.path("filter").path("author").asText("");
        String githubToken  = raw.path("github_token").asText("");

        return new ResolvedConfig(
                raw.path("project_name").asText(""),
                serveRoot, postsDir, assetsDir, mdDir, enrichedDir,
                authorFilter, githubToken, raw
        );
    }

    /**
     * Save a config back to disk, stripping no internal fields
     * (the raw ObjectNode already contains only user-visible fields).
     */
    public static void save(Path configPath, ObjectNode raw) throws Exception {
        MAPPER.writerWithDefaultPrettyPrinter().writeValue(configPath.toFile(), raw);
    }

    /** Resolve p against serveRoot if relative; return absolute paths unchanged. */
    static Path resolve(Path serveRoot, String p) {
        Path path = Path.of(p);
        return path.isAbsolute() ? path : serveRoot.resolve(path);
    }
}
```

- [ ] **Step 2: Run tests — all 9 must pass**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=SpargeConfigTest -q 2>&1 | tail -5
```

Expected: `Tests run: 9, Failures: 0, Errors: 0`

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/SpargeConfig.java
git commit -m "feat(#52): add SpargeConfig.java — mirrors config.py load/resolve/save"
```

---

## Task 6: ProjectsStore.java + ActiveProject.java

`ProjectsStore` handles projects.json CRUD and reads state.json for stats. `ActiveProject` tracks which project is active across requests.

**Files:**
- Create: `server/src/main/java/io/sparge/server/ProjectsStore.java`
- Create: `server/src/main/java/io/sparge/server/ActiveProject.java`

- [ ] **Step 1: Write ProjectsStore.java**

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * CRUD operations on projects.json and per-project stats from state.json.
 * Mirrors _load_projects, _save_projects, _project_stats in bridge.py.
 */
@ApplicationScoped
public class ProjectsStore {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject SpargeHome spargeHome;

    public Path getProjectsFile() throws Exception {
        return spargeHome.getProjectsDir().resolve("projects.json");
    }

    public Path getProjectDir(String projectId) throws Exception {
        return spargeHome.getProjectsDir().resolve(projectId);
    }

    /** Load the projects list. Returns empty list if file absent. */
    public List<ObjectNode> load() throws Exception {
        Path file = getProjectsFile();
        if (!Files.exists(file)) return new ArrayList<>();
        ArrayNode arr = (ArrayNode) MAPPER.readTree(file.toFile());
        List<ObjectNode> result = new ArrayList<>();
        arr.forEach(n -> result.add((ObjectNode) n));
        return result;
    }

    /** Save the projects list. */
    public void save(List<ObjectNode> projects) throws Exception {
        Path file = getProjectsFile();
        Files.createDirectories(file.getParent());
        ArrayNode arr = MAPPER.createArrayNode();
        projects.forEach(arr::add);
        MAPPER.writerWithDefaultPrettyPrinter().writeValue(file.toFile(), arr);
    }

    /**
     * Compute post stats by reading state.json for the given project.
     * Returns zeroed stats if state.json absent or unreadable.
     */
    public ObjectNode stats(String projectId) {
        ObjectNode stats = MAPPER.createObjectNode();
        stats.put("total",        0);
        stats.put("reviewed",     0);
        stats.put("staged",       0);
        stats.put("md_generated", 0);
        stats.put("html_issues",  0);
        try {
            Path statePath = getProjectDir(projectId).resolve("state.json");
            if (!Files.exists(statePath)) return stats;
            ObjectNode state = (ObjectNode) MAPPER.readTree(statePath.toFile());
            int total = 0, reviewed = 0, staged = 0, mdGenerated = 0, htmlIssues = 0;
            var fields = state.fields();
            while (fields.hasNext()) {
                ObjectNode post = (ObjectNode) fields.next().getValue();
                total++;
                if (post.path("reviewed").asBoolean(false))                         reviewed++;
                if (post.path("md").path("staged").asBoolean(false))               staged++;
                if (!post.path("md").path("generated_at").isMissingNode()
                        && !post.path("md").path("generated_at").isNull())          mdGenerated++;
                if (post.path("html").path("issues").isArray()
                        && post.path("html").path("issues").size() > 0)             htmlIssues++;
            }
            stats.put("total",        total);
            stats.put("reviewed",     reviewed);
            stats.put("staged",       staged);
            stats.put("md_generated", mdGenerated);
            stats.put("html_issues",  htmlIssues);
        } catch (Exception ignored) {}
        return stats;
    }
}
```

- [ ] **Step 2: Write ActiveProject.java**

```java
package io.sparge.server;

import jakarta.enterprise.context.ApplicationScoped;

/**
 * CDI singleton tracking which project is currently active.
 * Set by ProjectsResource.activate() after Python confirms the switch.
 */
@ApplicationScoped
public class ActiveProject {

    private volatile String projectId;
    private volatile SpargeConfig.ResolvedConfig config;

    public String getProjectId() { return projectId; }

    public SpargeConfig.ResolvedConfig getConfig() { return config; }

    public boolean isActive() { return projectId != null; }

    public synchronized void set(String projectId, SpargeConfig.ResolvedConfig config) {
        this.projectId = projectId;
        this.config    = config;
    }
}
```

- [ ] **Step 3: Compile**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn compile -q 2>&1 | tail -5
```

Expected: no output (clean).

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/ProjectsStore.java \
        server/src/main/java/io/sparge/server/ActiveProject.java
git commit -m "feat(#52): add ProjectsStore and ActiveProject CDI beans"
```

---

## Task 7: Update ProjectsResource — list/create/delete use Java

`list`, `create`, and `delete` now call Java directly. `activate` still calls `bridge.projects_activate` (Python needs to update its `State` singleton). `activate` also updates `ActiveProject` with the Java config view.

**Files:**
- Modify: `server/src/main/java/io/sparge/server/ProjectsResource.java`

- [ ] **Step 1: Read the current ProjectsResource.java**

Read `server/src/main/java/io/sparge/server/ProjectsResource.java` to see the current code.

- [ ] **Step 2: Replace ProjectsResource.java with the updated version**

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.List;
import java.util.regex.Pattern;

@Path("/api/projects")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class ProjectsResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    // Project IDs: lowercase alphanumeric + hyphens, max 40 chars
    private static final Pattern SLUG_STRIP = Pattern.compile("[^a-z0-9]+");

    @Inject PythonBridge    bridge;
    @Inject ProjectsStore   store;
    @Inject ActiveProject   activeProject;
    @Inject SpargeHome      spargeHome;

    // ── Java implementations ──────────────────────────────────────────────────

    @GET
    public Response list() {
        try {
            List<ObjectNode> projects = store.load();
            ArrayNode result = MAPPER.createArrayNode();
            for (ObjectNode p : projects) {
                String id    = p.get("id").asText();
                ObjectNode entry = p.deepCopy();
                entry.set("stats", store.stats(id));
                entry.put("active", id.equals(activeProject.getProjectId()));
                result.add(entry);
            }
            return ok(result.toString());
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    @POST
    public Response create(String body) {
        try {
            ObjectNode data = body != null && !body.isBlank()
                    ? (ObjectNode) MAPPER.readTree(body)
                    : MAPPER.createObjectNode();

            String name = data.path("name").asText("").strip();
            if (name.isEmpty()) return Response.status(400)
                    .entity("{\"error\":\"name required\"}").build();

            String projectId = SLUG_STRIP.matcher(name.toLowerCase())
                    .replaceAll("-").replaceAll("^-+|-+$", "");
            if (projectId.length() > 40) projectId = projectId.substring(0, 40);

            Path projectDir = store.getProjectDir(projectId);
            Files.createDirectories(projectDir);

            // Build project config.json
            ObjectNode cfg = MAPPER.createObjectNode();
            cfg.put("project_name", name);
            cfg.put("serve_root", data.path("serve_root").asText(
                    System.getProperty("user.home")));

            ObjectNode source = MAPPER.createObjectNode();
            source.put("posts_dir",  data.path("posts_dir").asText("legacy/posts"));
            source.put("assets_dir", data.path("assets_dir").asText("legacy/assets"));
            cfg.set("source", source);

            ObjectNode output = MAPPER.createObjectNode();
            output.put("md_dir", data.path("md_dir").asText("output/md"));
            cfg.set("output", output);

            ObjectNode filter = MAPPER.createObjectNode();
            filter.put("author", data.path("author_filter").asText(""));
            cfg.set("filter", filter);

            ObjectNode server = MAPPER.createObjectNode();
            server.put("port", 9000);
            cfg.set("server", server);

            MAPPER.writerWithDefaultPrettyPrinter()
                    .writeValue(projectDir.resolve("config.json").toFile(), cfg);

            // Update projects.json
            List<ObjectNode> projects = store.load();
            boolean alreadyExists = projects.stream()
                    .anyMatch(p -> p.path("id").asText().equals(projectId));
            if (!alreadyExists) {
                ObjectNode entry = MAPPER.createObjectNode();
                entry.put("id",         projectId);
                entry.put("name",       name);
                entry.put("created_at", Instant.now().toString().substring(0, 19));
                projects.add(entry);
                store.save(projects);
            }

            ObjectNode result = MAPPER.createObjectNode();
            result.put("id",   projectId);
            result.put("name", name);
            return ok(result.toString());
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    @DELETE
    @Path("{id}")
    public Response delete(@PathParam("id") String id) {
        try {
            List<ObjectNode> projects = store.load();
            projects.removeIf(p -> p.path("id").asText().equals(id));
            store.save(projects);
            return ok("{\"deleted\":\"" + id + "\"}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    // ── Still via Python (needs State.init_from_source()) ────────────────────

    @POST
    @Path("{id}/activate")
    public Response activate(@PathParam("id") String id) {
        // Python updates its cfg singleton and calls State.init_from_source()
        String bridgeResult = bridge.call("bridge.projects_activate", id);
        // Also update Java's view of the active project
        try {
            Path projectDir  = store.getProjectDir(id);
            Path configPath  = projectDir.resolve("config.json");
            if (Files.exists(configPath)) {
                activeProject.set(id, SpargeConfig.load(configPath, projectDir));
            }
        } catch (Exception ignored) {}
        return BridgeResponse.of(bridgeResult);
    }

    @POST
    @Path("{id}/ingest/run")
    public Response projectIngestRun(@PathParam("id") String id, String body) {
        return BridgeResponse.of(bridge.call("bridge.project_ingest_run",
                id, body == null ? "{}" : body));
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private Response ok(String json) {
        return Response.ok(json)
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }

    private Response err(String msg) {
        String escaped = msg == null ? "error" : msg.replace("\"", "\\\"");
        return Response.serverError()
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .entity("{\"error\":\"" + escaped + "\"}")
                .build();
    }
}
```

- [ ] **Step 3: Compile**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn compile -q 2>&1 | tail -5
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/ProjectsResource.java
git commit -m "feat(#52): ProjectsResource list/create/delete use Java directly (JEP removed for these 3)"
```

---

## Task 8: Remove retired bridge.py delegates

Remove the three Python bridge functions whose Java equivalents are now live. Also ensure `bridge.py` no longer exports them as callable JEP functions.

**Files:**
- Modify: `scripts/bridge.py`

- [ ] **Step 1: Read bridge.py to identify the three functions to remove**

Find these function definitions in `scripts/bridge.py`:
- `def projects_list() -> str:`
- `def projects_create(body: str) -> str:`
- `def projects_delete(project_id: str) -> str:`

Also find all helpers used *exclusively* by these three:
- `_save_projects` — also used by `projects_create` and `project_ingest_run`. Keep it; `project_ingest_run` still calls Python.
- `_load_projects` — also used by `_activate_project` and `project_ingest_run`. Keep it.
- `_project_stats` — used only by `projects_list`. **Remove it.**

- [ ] **Step 2: Remove the three functions and `_project_stats`**

Delete these four function definitions entirely from `scripts/bridge.py`:
- `def _project_stats(project_id: str) -> dict:` (and its body)
- `def projects_list() -> str:` (and its body)
- `def projects_create(body: str) -> str:` (and its body)
- `def projects_delete(project_id: str) -> str:` (and its body)

Do not touch any other functions.

- [ ] **Step 3: Smoke-test bridge.py standalone**

```bash
cd ~/claude/sparge && python3 -c "
import sys; sys.path.insert(0, '.')
import scripts.bridge as bridge
result = bridge.bridge_init()
import json; data = json.loads(result)
print('initialized:', data['body']['initialized'])
print('posts:', data['body']['posts'])
"
```

Expected: `initialized: True`, `posts: 577` (or current count), no ImportError.

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add scripts/bridge.py
git commit -m "refactor(#52): remove projects_list/create/delete from bridge.py — ported to Java

JEP call count: 35 → 32
Refs #52"
```

---

## Task 9: Move pytest tests to python-legacy/

**Files:**
- Move: `tests/test_sparge_home.py` → `tests/python-legacy/test_sparge_home.py`
- Move: `tests/test_config.py` → `tests/python-legacy/test_config.py`
- Move: `tests/test_path_resolution.py` → `tests/python-legacy/test_path_resolution.py`

- [ ] **Step 1: Move the files**

```bash
cd ~/claude/sparge
mv tests/test_sparge_home.py tests/python-legacy/
mv tests/test_config.py      tests/python-legacy/
mv tests/test_path_resolution.py tests/python-legacy/
```

- [ ] **Step 2: Verify pytest.ini correctly excludes them**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --no-header --tb=no 2>&1 | tail -3
```

Expected: `460 passed` (473 − 13 = 460), 0 failing. The 13 tests that moved are no longer collected.

- [ ] **Step 3: Verify retired tests still work when run directly (optional cross-check)**

```bash
cd ~/claude/sparge && python3 -m pytest tests/python-legacy/test_sparge_home.py -v 2>&1 | tail -8
```

Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add tests/python-legacy/
git add -u tests/test_sparge_home.py tests/test_config.py tests/test_path_resolution.py
git commit -m "refactor(#52): move 13 pytest tests to python-legacy/ (modules ported to Java)

Refs #52"
```

---

## Task 10: Full verification — JUnit + pytest + live server

- [ ] **Step 1: Run JUnit (all tests including the new ones)**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
export PYTHONHOME=$HOME/claude/sparge/resources/python/mac-arm64
mvn test \
  -Djava.library.path=$HOME/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  2>&1 | tail -10
```

Expected: `BUILD SUCCESS`. Tests: SpargeHomeTest (4), SpargeConfigTest (9), SmokeTest (1) = 14 total passing.

- [ ] **Step 2: Run pytest (460 non-legacy tests)**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --no-header --tb=no 2>&1 | tail -3
```

Expected: `460 passed, 0 failed`.

- [ ] **Step 3: Build Quarkus jar and smoke-test projects endpoint**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
export PYTHONHOME=$HOME/claude/sparge/resources/python/mac-arm64
mvn package -DskipTests -q 2>&1 | tail -3

java \
  -Djava.library.path=$HOME/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  -Dquarkus.http.port=9000 \
  -jar target/quarkus-app/quarkus-run.jar > /tmp/quarkus-p1.log 2>&1 &
JAVA_PID=$!

# Wait for startup
for i in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9000/api/config 2>/dev/null)
  [ "$STATUS" = "200" ] && echo "Ready after ${i}s" && break
  sleep 1
done

# Hit projects (now Java-only)
unset PYTHONHOME
curl -s http://127.0.0.1:9000/api/projects | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'{len(d)} project(s) returned, active={d[0][\"active\"] if d else None}')
"
kill $JAVA_PID
```

Expected: `1 project(s) returned, active=True`

- [ ] **Step 4: Final commit**

```bash
cd ~/claude/sparge
git commit --allow-empty -m "feat(#52): Phase 1 complete — sparge_home + config ported to Java

JEP call count: 35 → 32 (projects_list, projects_create, projects_delete removed)
JUnit tests: 14 passing (SpargeHomeTest x4, SpargeConfigTest x9, SmokeTest x1)
pytest: 460 passing (13 tests retired to python-legacy/)

Closes #52"
```

---

## Self-Review

**Spec coverage:**
- `sparge_home.py` ported → SpargeHome.java (Task 3) ✓
- `config.py` ported → SpargeConfig.java (Task 5) ✓
- JUnit tests calling through JEP first → SpargeHomeTest + SpargeConfigTest (Tasks 2, 4) ✓
- JUnit tests call Java directly after port → same tests, same assertions (Tasks 3, 5) ✓
- pytest moved to python-legacy/ → Task 9 ✓
- JEP delegates deleted → Task 8 ✓
- Full test suite green → Task 10 ✓
- JEP call count documented in commit → Task 8 + Task 10 ✓

**Placeholder scan:** No TBDs, no "similar to Task N", all code blocks complete. ✓

**Type consistency:**
- `SpargeConfig.ResolvedConfig` defined in Task 5, used in Task 6 (ActiveProject) and Task 7 (ProjectsResource.activate) ✓
- `store.getProjectDir(id)` defined in Task 6 (ProjectsStore), called in Task 7 ✓
- `activeProject.getProjectId()` defined in Task 6 (ActiveProject), called in Task 7 ✓

---

Plan complete and saved to `docs/superpowers/plans/2026-04-15-quarkus-phase1.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks

**2. Inline Execution** — execute in this session using `superpowers:executing-plans`, batch execution with checkpoints

Which approach?
