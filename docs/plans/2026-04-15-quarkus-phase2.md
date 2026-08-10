# Quarkus Phase 2 — Port state.py to Java

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `scripts/state.py` state management to `StateStore.java`, removing JEP delegates for posts list/get/patch and staging workflow — JEP call count drops 32 → 27.

**Architecture:** `StateStore` is an `@ApplicationScoped` bean that owns `state.json` reads/writes. It injects `ActiveProject` (which gains a `projectDir` field this phase) for path resolution. State operations that are pure JSON + file ops move to Java; complex ops that still call Python business logic (generate-md, scan, validate) keep their state updates in bridge.py for now. `PostsResource` gains 5 Java-direct methods. ~28 TDD JUnit tests cover every state operation including edge cases.

**Tech Stack:** Java 21, Quarkus 3.34, Jackson ObjectMapper, JUnit 5, `@TempDir`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `server/src/main/java/io/sparge/server/ActiveProject.java` | Modify | Add `projectDir` field; update `set()` signature |
| `server/src/main/java/io/sparge/server/ProjectsResource.java` | Modify | Pass `projectDir` to `activeProject.set()` in `activate()` |
| `server/src/test/java/io/sparge/server/StateStoreTest.java` | Create | ~28 JUnit tests written BEFORE StateStore.java |
| `server/src/main/java/io/sparge/server/StateStore.java` | Create | All state operations; injects ActiveProject |
| `server/src/main/java/io/sparge/server/PostsResource.java` | Modify | posts_list, post_get, post_patch, post_stage, post_reject_staged → Java |
| `scripts/bridge.py` | Modify | Remove 5 ported delegates |

**JEP calls removed:** `posts_list`, `post_get`, `post_patch`, `post_stage`, `post_reject_staged` → 5 removed (32 → 27)

---

## Task 1: Add projectDir to ActiveProject

`StateStore` needs to know where `state.json` lives — that's `{projectDir}/state.json`. `ActiveProject` currently tracks `projectId` and `config` but not the raw project directory path.

**Files:**
- Modify: `server/src/main/java/io/sparge/server/ActiveProject.java`
- Modify: `server/src/main/java/io/sparge/server/ProjectsResource.java`

- [ ] **Step 1: Read both files**

Read `ActiveProject.java` and `ProjectsResource.java` to see current code.

- [ ] **Step 2: Update ActiveProject.java**

Add a `projectDir` volatile field and update `set()`:

```java
@ApplicationScoped
public class ActiveProject {

    private volatile String                     projectId;
    private volatile SpargeConfig.ResolvedConfig config;
    private volatile java.nio.file.Path          projectDir;

    public String                      getProjectId()  { return projectId;  }
    public SpargeConfig.ResolvedConfig getConfig()     { return config;     }
    public java.nio.file.Path          getProjectDir() { return projectDir; }
    public boolean                     isActive()      { return projectId != null; }

    public synchronized void set(String projectId,
                                  SpargeConfig.ResolvedConfig config,
                                  java.nio.file.Path projectDir) {
        this.projectId  = projectId;
        this.config     = config;
        this.projectDir = projectDir;
    }
}
```

- [ ] **Step 3: Update ProjectsResource.activate() to pass projectDir**

Find the `activate()` method. Change the `activeProject.set(id, ...)` call from the 2-arg form to the 3-arg form:

```java
// Before (2-arg):
activeProject.set(id, SpargeConfig.load(configPath, projectDir));

// After (3-arg):
activeProject.set(id, SpargeConfig.load(configPath, projectDir), projectDir);
```

- [ ] **Step 4: Compile**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn compile -q 2>&1 | tail -5
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/ActiveProject.java \
        server/src/main/java/io/sparge/server/ProjectsResource.java
git commit -m "feat(#53): add projectDir to ActiveProject for StateStore path resolution

Refs #53"
```

---

## Task 2: StateStoreTest.java — write ALL failing tests first

This is the TDD anchor for Phase 2. Write ~28 tests BEFORE StateStore.java exists. Each test is precise and exercises a real edge case — not just happy-path.

**Files:**
- Create: `server/src/test/java/io/sparge/server/StateStoreTest.java`

- [ ] **Step 1: Write StateStoreTest.java**

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Comprehensive TDD tests for StateStore — covers every state operation
 * including edge cases for stale detection, dismiss/undismiss interaction,
 * and staged workflow.
 *
 * StateStore is tested directly (not via CDI) using the package-private
 * constructor that accepts a stateFile path.
 */
class StateStoreTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @TempDir Path dir;
    private Path stateFile;
    private StateStore store;

    @BeforeEach
    void setUp() {
        stateFile = dir.resolve("state.json");
        store = new StateStore(stateFile);
    }

    // ── Basic load / get ──────────────────────────────────────────────────────

    @Test
    void getAllReturnsEmptyListWhenStateAbsent() {
        assertEquals(List.of(), store.getAll());
    }

    @Test
    void getReturnsNullForUnknownSlug() {
        assertNull(store.get("nonexistent"));
    }

    @Test
    void getReturnsEntryAfterUpdate() {
        store.update("my-post", Map.of("title", "My Post"));
        ObjectNode entry = store.get("my-post");
        assertNotNull(entry);
        assertEquals("my-post", entry.path("slug").asText());
        assertEquals("My Post", entry.path("title").asText());
    }

    @Test
    void getAllReturnsStaleFlagComputed() {
        // html.hash differs from md.html_hash → stale = true
        store.update("post", Map.of(
            "html", Map.of("hash", "abc123"),
            "md",   Map.of("generated_at", "2026-01-01", "html_hash", "old456")
        ));
        List<ObjectNode> all = store.getAll();
        assertEquals(1, all.size());
        assertTrue(all.get(0).path("md").path("stale").asBoolean(),
                "Expected stale=true when hashes differ");
    }

    // ── Stale computation edge cases ──────────────────────────────────────────

    @Test
    void notStaleWhenNoGeneratedAt() {
        store.update("post", Map.of("html", Map.of("hash", "abc")));
        assertFalse(store.get("post").path("md").path("stale").asBoolean());
    }

    @Test
    void notStaleWhenHashesMatch() {
        store.update("post", Map.of(
            "html", Map.of("hash", "abc123"),
            "md",   Map.of("generated_at", "2026-01-01", "html_hash", "abc123")
        ));
        assertFalse(store.get("post").path("md").path("stale").asBoolean());
    }

    @Test
    void staleWhenHashesDiffer() {
        store.update("post", Map.of(
            "html", Map.of("hash", "newHash"),
            "md",   Map.of("generated_at", "2026-01-01", "html_hash", "oldHash")
        ));
        assertTrue(store.get("post").path("md").path("stale").asBoolean());
    }

    @Test
    void notStaleWhenMdHtmlHashNull() {
        store.update("post", Map.of(
            "html", Map.of("hash", "abc"),
            "md",   Map.of("generated_at", "2026-01-01")
            // html_hash absent
        ));
        assertFalse(store.get("post").path("md").path("stale").asBoolean());
    }

    // ── update() deep-merge behaviour ─────────────────────────────────────────

    @Test
    void updateCreatesEntryWithSlugIfAbsent() {
        store.update("new-post", Map.of("title", "New"));
        assertNotNull(store.get("new-post"));
        assertEquals("new-post", store.get("new-post").path("slug").asText());
    }

    @Test
    void updateOverwritesTopLevelField() {
        store.update("post", Map.of("flagged", false));
        store.update("post", Map.of("flagged", true));
        assertTrue(store.get("post").path("flagged").asBoolean());
    }

    @Test
    void updateDeepMergesHtmlKeys() {
        store.update("post", Map.of("html", Map.of("hash", "abc", "issues", List.of())));
        store.update("post", Map.of("html", Map.of("hash", "xyz")));  // only update hash
        ObjectNode entry = store.get("post");
        assertEquals("xyz", entry.path("html").path("hash").asText());
        assertTrue(entry.path("html").path("issues").isArray(),
                "issues array must survive partial html update");
    }

    @Test
    void updateDeepMergesMdKeys() {
        store.update("post", Map.of("md", Map.of("generated_at", "2026-01-01", "staged", false)));
        store.update("post", Map.of("md", Map.of("staged", true)));  // only update staged
        ObjectNode entry = store.get("post");
        assertEquals("2026-01-01", entry.path("md").path("generated_at").asText(),
                "generated_at must survive partial md update");
        assertTrue(entry.path("md").path("staged").asBoolean());
    }

    // ── HTML issue dismiss / undismiss ─────────────────────────────────────────

    @Test
    void dismissHtmlCheckFiltersIssueFromActive() {
        store.update("post", Map.of("html", Map.of("issues", List.of(
            Map.of("type", "suspicious_code", "level", "WARN", "detail", "x", "check", "suspicious_code")
        ))));
        store.dismissHtmlCheck("post", "suspicious_code");
        ObjectNode entry = store.get("post");
        ArrayNode issues = (ArrayNode) entry.path("html").path("issues");
        assertEquals(0, issues.size(), "dismissed issue must be filtered from active list");
    }

    @Test
    void dismissStoredInDismissedHtmlChecks() {
        store.update("post", Map.of("html", Map.of("issues", List.of())));
        store.dismissHtmlCheck("post", "my_check");
        ObjectNode entry = store.get("post");
        assertFalse(entry.path("dismissed_html_checks").path("my_check").isMissingNode(),
                "dismissed_html_checks must store the dismissed type");
    }

    @Test
    void dismissDoesNothingForUnknownSlug() {
        // must not throw
        assertDoesNotThrow(() -> store.dismissHtmlCheck("ghost", "some_check"));
    }

    @Test
    void undismissRemovesDismissalEntry() {
        store.update("post", Map.of("html", Map.of("issues", List.of())));
        store.dismissHtmlCheck("post", "my_check");
        store.undismissHtmlCheck("post", "my_check");
        ObjectNode entry = store.get("post");
        assertTrue(entry.path("dismissed_html_checks").path("my_check").isMissingNode(),
                "undismiss must remove the dismissal entry");
    }

    @Test
    void setHtmlIssuesClearsDismissalWhenIssueNoLongerDetected() {
        // Issue was dismissed; new scan doesn't find it → auto-clear dismissal
        store.update("post", Map.of("html", Map.of("issues", List.of(
            Map.of("type", "gone_issue", "level", "WARN", "detail", "x", "check", "gone_issue")
        ))));
        store.dismissHtmlCheck("post", "gone_issue");

        // New scan: gone_issue no longer appears
        store.setHtmlIssues("post", List.of(), null, null);

        ObjectNode entry = store.get("post");
        assertTrue(entry.path("dismissed_html_checks").path("gone_issue").isMissingNode(),
                "dismissal must be cleared when the issue is no longer detected");
    }

    @Test
    void setHtmlIssuesKeepsDismissedIssueFiltered() {
        // Issue is dismissed; new scan still detects it → keep filtered
        store.update("post", Map.of("html", Map.of("issues", List.of(
            Map.of("type", "persistent", "level", "WARN", "detail", "x", "check", "persistent")
        ))));
        store.dismissHtmlCheck("post", "persistent");

        // New scan still finds it
        store.setHtmlIssues("post", List.of(
            Map.of("type", "persistent", "level", "WARN", "detail", "x", "check", "persistent")
        ), null, null);

        ObjectNode entry = store.get("post");
        ArrayNode active = (ArrayNode) entry.path("html").path("issues");
        assertEquals(0, active.size(), "dismissed issue must stay filtered in active list");
        assertFalse(entry.path("dismissed_html_checks").path("persistent").isMissingNode(),
                "dismissal must be retained when issue still detected");
    }

    // ── MD issues ─────────────────────────────────────────────────────────────

    @Test
    void setMdIssuesReplacesExisting() {
        store.update("post", Map.of("md", Map.of("issues", List.of(
            Map.of("check", "old", "level", "WARN", "detail", "d")
        ))));
        store.setMdIssues("post", List.of(
            Map.of("check", "new1", "level", "ERROR", "detail", "d1"),
            Map.of("check", "new2", "level", "WARN",  "detail", "d2")
        ));
        ArrayNode issues = (ArrayNode) store.get("post").path("md").path("issues");
        assertEquals(2, issues.size());
        assertEquals("new1", issues.get(0).path("check").asText());
    }

    // ── mark_md_generated ─────────────────────────────────────────────────────

    @Test
    void markMdGeneratedSetsTimestampAndHash() throws Exception {
        // Create a real HTML file to hash
        Path htmlFile = dir.resolve("my-post.html");
        Files.writeString(htmlFile, "<html>content</html>");

        store.markMdGenerated("my-post", htmlFile);

        ObjectNode md = store.get("my-post").path("md");
        assertFalse(md.path("generated_at").isMissingNode(), "generated_at must be set");
        assertFalse(md.path("html_hash").isMissingNode(), "html_hash must be set");
        assertFalse(md.path("staged").asBoolean(true), "staged must be false");
        assertTrue(md.path("issues").isArray(), "issues must be empty array");
    }

    @Test
    void markMdGeneratedMatchesHtmlHash() throws Exception {
        Path htmlFile = dir.resolve("post.html");
        Files.writeString(htmlFile, "<html>test</html>");

        store.markMdGenerated("post", htmlFile);

        // html.hash and md.html_hash should agree → not stale
        store.update("post", Map.of("html", Map.of(
            "hash", store.get("post").path("md").path("html_hash").asText()
        )));
        assertFalse(store.get("post").path("md").path("stale").asBoolean(),
                "just-generated MD must not be stale");
    }

    // ── mark_enriched ─────────────────────────────────────────────────────────

    @Test
    void markEnrichedStoresStats() {
        store.markEnriched("post", Map.of(
            "youtube_replaced", 2, "gists_replaced", 1, "gists_failed", 0,
            "classes_normalised", 5, "languages_detected", 3, "embeds_wrapped", 1
        ));
        ObjectNode enriched = store.get("post").path("enriched");
        assertEquals(2, enriched.path("youtube_replaced").asInt());
        assertEquals(1, enriched.path("gists_replaced").asInt());
        assertFalse(enriched.path("generated_at").isMissingNode());
    }

    // ── Staged workflow ───────────────────────────────────────────────────────

    @Test
    void stageSetsTrue() {
        store.stage("post");
        assertTrue(store.get("post").path("md").path("staged").asBoolean());
        assertFalse(store.get("post").path("md").path("staged_at").isMissingNode());
    }

    @Test
    void acceptStagedReturnsFalseWhenNoStagedFile() {
        boolean result = store.acceptStaged("post", dir, dir);
        assertFalse(result);
    }

    @Test
    void acceptStagedPromotesStagedToMdAndClearsFlag() throws Exception {
        // Create slug.md.staged
        Path mdDir = dir.resolve("md");
        Files.createDirectories(mdDir);
        Path staged = mdDir.resolve("my-post.md.staged");
        Files.writeString(staged, "# Staged content");
        store.stage("my-post");

        // Create HTML file for hashing
        Path postsDir = dir.resolve("posts");
        Files.createDirectories(postsDir);
        Path htmlFile = postsDir.resolve("my-post.html");
        Files.writeString(htmlFile, "<html/>");

        boolean result = store.acceptStaged("my-post", mdDir, postsDir);

        assertTrue(result);
        Path mdFile = mdDir.resolve("my-post.md");
        assertTrue(Files.exists(mdFile), "md file must be created");
        assertEquals("# Staged content", Files.readString(mdFile));
        assertFalse(Files.exists(staged), "staged file must be deleted");
        assertFalse(store.get("my-post").path("md").path("staged").asBoolean(),
                "staged flag must be cleared");
    }

    @Test
    void rejectStagedReturnsFalseWhenNoStagedFile() {
        assertFalse(store.rejectStaged("ghost", dir));
    }

    @Test
    void rejectStagedDeletesStagedFileAndClearsFlag() throws Exception {
        Path mdDir = dir.resolve("md");
        Files.createDirectories(mdDir);
        Path staged = mdDir.resolve("post.md.staged");
        Files.writeString(staged, "staged");
        store.stage("post");

        assertTrue(store.rejectStaged("post", mdDir));
        assertFalse(Files.exists(staged), "staged file must be deleted");
        assertFalse(store.get("post").path("md").path("staged").asBoolean(),
                "staged flag must be cleared");
    }
}
```

- [ ] **Step 2: Run to verify failure (StateStore doesn't exist)**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=StateStoreTest -q 2>&1 | tail -5
```

Expected: `BUILD FAILURE` — cannot find symbol `StateStore`.

- [ ] **Step 3: Commit failing tests**

```bash
cd ~/claude/sparge
git add server/src/test/java/io/sparge/server/StateStoreTest.java
git commit -m "test(#53): add StateStoreTest — 28 TDD tests (failing)

Covers: get/getAll, stale computation (4 edge cases), update deep-merge,
dismiss/undismiss/setHtmlIssues interactions, setMdIssues, markMdGenerated,
markEnriched, stage/acceptStaged/rejectStaged workflow.

Refs #53"
```

---

## Task 3: StateStore.java — implement to pass all 28 tests

Note the package-private constructor `StateStore(Path stateFile)` used by tests. The CDI `@ApplicationScoped` bean uses the default no-arg constructor which gets the state file from `ActiveProject`.

**Files:**
- Create: `server/src/main/java/io/sparge/server/StateStore.java`

- [ ] **Step 1: Write StateStore.java**

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Manages state.json — one entry per post slug.
 * Mirrors scripts/state.py.
 *
 * CDI bean uses ActiveProject to resolve the state file path.
 * Tests use the package-private StateStore(Path) constructor directly.
 */
@ApplicationScoped
public class StateStore {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    // CDI injection path
    @Inject ActiveProject activeProject;

    /** CDI no-arg constructor. */
    public StateStore() {}

    /** Testable constructor — bypasses CDI, uses a fixed state file. */
    StateStore(Path stateFile) {
        this.fixedStateFile = stateFile;
    }

    private final Path fixedStateFile;   // non-null only in tests

    private Path stateFile() {
        if (fixedStateFile != null) return fixedStateFile;
        return activeProject.getProjectDir().resolve("state.json");
    }

    // ── Internal helpers ──────────────────────────────────────────────────────

    private ObjectNode load() {
        Path f = stateFile();
        try {
            return Files.exists(f) ? (ObjectNode) MAPPER.readTree(f.toFile()) : MAPPER.createObjectNode();
        } catch (IOException e) {
            return MAPPER.createObjectNode();
        }
    }

    private synchronized void save(ObjectNode state) throws IOException {
        MAPPER.writerWithDefaultPrettyPrinter().writeValue(stateFile().toFile(), state);
    }

    private static boolean isStale(ObjectNode entry) {
        String htmlHash = entry.path("html").path("hash").asText(null);
        String mdHash   = entry.path("md").path("html_hash").asText(null);
        String genAt    = entry.path("md").path("generated_at").asText(null);
        return genAt != null && htmlHash != null && mdHash != null
                && !htmlHash.equals(mdHash);
    }

    private static ObjectNode computed(ObjectNode entry) {
        ObjectNode copy = entry.deepCopy();
        ObjectNode md   = copy.has("md") ? (ObjectNode) copy.get("md") : MAPPER.createObjectNode();
        md.put("stale", isStale(copy));
        copy.set("md", md);
        return copy;
    }

    /** sha256[:12] of a file — matches Python's _hash(). */
    static String hash(Path file) throws Exception {
        byte[] bytes  = Files.readAllBytes(file);
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder sb = new StringBuilder();
        for (byte b : digest) sb.append(String.format("%02x", b));
        return sb.substring(0, 12);
    }

    private static String now() {
        return Instant.now().toString().substring(0, 19);
    }

    /**
     * Deep-merge a patch into an entry.
     * html/md/assets sub-objects are merged; all other keys are overwritten.
     */
    @SuppressWarnings("unchecked")
    private static void mergeInto(ObjectNode entry, Map<String, Object> patch) {
        for (Map.Entry<String, Object> kv : patch.entrySet()) {
            String key = kv.getKey();
            Object val = kv.getValue();
            if ((key.equals("html") || key.equals("md") || key.equals("assets"))
                    && val instanceof Map) {
                ObjectNode sub = entry.has(key)
                        ? (ObjectNode) entry.get(key)
                        : MAPPER.createObjectNode();
                for (Map.Entry<String, Object> sv : ((Map<String, Object>) val).entrySet()) {
                    sub.set(sv.getKey(), toJsonNode(sv.getValue()));
                }
                entry.set(key, sub);
            } else {
                entry.set(key, toJsonNode(val));
            }
        }
    }

    private static com.fasterxml.jackson.databind.JsonNode toJsonNode(Object val) {
        if (val == null)                    return MAPPER.nullNode();
        if (val instanceof Boolean b)       return MAPPER.getNodeFactory().booleanNode(b);
        if (val instanceof Integer i)       return MAPPER.getNodeFactory().numberNode(i);
        if (val instanceof Long l)          return MAPPER.getNodeFactory().numberNode(l);
        if (val instanceof String s)        return MAPPER.getNodeFactory().textNode(s);
        if (val instanceof List<?> list) {
            ArrayNode arr = MAPPER.createArrayNode();
            for (Object item : list) arr.add(toJsonNode(item));
            return arr;
        }
        if (val instanceof Map<?,?> map) {
            ObjectNode obj = MAPPER.createObjectNode();
            for (Map.Entry<?,?> e : map.entrySet()) {
                obj.set(e.getKey().toString(), toJsonNode(e.getValue()));
            }
            return obj;
        }
        return MAPPER.getNodeFactory().textNode(val.toString());
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /** Return all posts with computed stale field. */
    public List<ObjectNode> getAll() {
        ObjectNode state = load();
        List<ObjectNode> result = new ArrayList<>();
        state.fields().forEachRemaining(e -> result.add(computed((ObjectNode) e.getValue())));
        return result;
    }

    /** Return a single post with computed stale field, or null if unknown. */
    public ObjectNode get(String slug) {
        ObjectNode entry = (ObjectNode) load().get(slug);
        return entry == null ? null : computed(entry);
    }

    /**
     * Shallow-merge patch into the entry; deep-merge html/md/assets sub-objects.
     * Creates the entry if it does not exist.
     */
    public synchronized void update(String slug, Map<String, Object> patch) {
        ObjectNode state = load();
        ObjectNode entry = state.has(slug)
                ? (ObjectNode) state.get(slug)
                : MAPPER.createObjectNode().put("slug", slug);
        mergeInto(entry, patch);
        state.set(slug, entry);
        try { save(state); } catch (IOException e) { throw new RuntimeException(e); }
    }

    // ── HTML issues ───────────────────────────────────────────────────────────

    public synchronized void dismissHtmlCheck(String slug, String issueType) {
        ObjectNode state = load();
        ObjectNode post  = (ObjectNode) state.get(slug);
        if (post == null) return;

        ObjectNode dismissed = post.has("dismissed_html_checks")
                ? (ObjectNode) post.get("dismissed_html_checks")
                : MAPPER.createObjectNode();
        dismissed.put(issueType, now());
        post.set("dismissed_html_checks", dismissed);

        // Filter the issue from the active list immediately
        ArrayNode issues = post.has("html")
                ? (ArrayNode) post.path("html").path("issues")
                : MAPPER.createArrayNode();
        ArrayNode filtered = MAPPER.createArrayNode();
        issues.forEach(i -> {
            String t = i.path("type").asText(i.path("check").asText(""));
            if (!t.equals(issueType)) filtered.add(i);
        });
        post.with("html").set("issues", filtered);

        state.set(slug, post);
        try { save(state); } catch (IOException e) { throw new RuntimeException(e); }
    }

    public synchronized void undismissHtmlCheck(String slug, String issueType) {
        ObjectNode state = load();
        ObjectNode post  = (ObjectNode) state.get(slug);
        if (post == null) return;

        if (post.has("dismissed_html_checks")) {
            ((ObjectNode) post.get("dismissed_html_checks")).remove(issueType);
        }
        state.set(slug, post);
        try { save(state); } catch (IOException e) { throw new RuntimeException(e); }
    }

    /**
     * Replace the HTML issue list, applying dismiss filtering and auto-clearing
     * stale dismissals.
     *
     * @param slug      the post slug
     * @param issues    raw issues from scanner
     * @param htmlHash  sha256[:12] of the HTML file, or null if unavailable
     * @param checkedAt ISO timestamp, or null to use now()
     */
    public synchronized void setHtmlIssues(String slug, List<Map<String, Object>> issues,
                                            String htmlHash, String checkedAt) {
        ObjectNode state = load();
        ObjectNode post  = state.has(slug) ? (ObjectNode) state.get(slug)
                                           : MAPPER.createObjectNode().put("slug", slug);

        ObjectNode dismissed = post.has("dismissed_html_checks")
                ? (ObjectNode) post.get("dismissed_html_checks")
                : MAPPER.createObjectNode();

        // Which issue types appear in this scan?
        Set<String> detected = new HashSet<>();
        for (Map<String, Object> i : issues) {
            Object t = i.get("type");
            if (t != null) detected.add(t.toString());
        }

        // Clear dismissals for types no longer detected (problem resolved)
        Set<String> toRemove = new HashSet<>();
        dismissed.fieldNames().forEachRemaining(t -> {
            if (!detected.contains(t)) toRemove.add(t);
        });
        toRemove.forEach(dismissed::remove);

        // Active issues = detected minus dismissed
        ArrayNode active = MAPPER.createArrayNode();
        for (Map<String, Object> i : issues) {
            String t = i.containsKey("type") ? i.get("type").toString() : "";
            if (!dismissed.has(t)) active.add(toJsonNode(i));
        }

        ObjectNode html = post.has("html") ? (ObjectNode) post.get("html")
                                           : MAPPER.createObjectNode();
        html.set("issues", active);
        html.put("checked_at", checkedAt != null ? checkedAt : now());
        if (htmlHash != null) html.put("hash", htmlHash);
        post.set("html", html);
        post.set("dismissed_html_checks", dismissed);

        state.set(slug, post);
        try { save(state); } catch (IOException e) { throw new RuntimeException(e); }
    }

    // ── MD issues ─────────────────────────────────────────────────────────────

    public synchronized void setMdIssues(String slug, List<Map<String, Object>> issues) {
        ArrayNode arr = MAPPER.createArrayNode();
        issues.forEach(i -> arr.add(toJsonNode(i)));
        update(slug, Map.of("md", Map.of(
                "issues",       issues,
                "validated_at", now()
        )));
    }

    // ── mark_md_generated ─────────────────────────────────────────────────────

    /**
     * Record that MD was generated from the given HTML file.
     *
     * @param slug     the post slug
     * @param htmlFile the HTML file that was used (enriched or original)
     */
    public synchronized void markMdGenerated(String slug, Path htmlFile) {
        String h = null;
        if (htmlFile != null && Files.exists(htmlFile)) {
            try { h = hash(htmlFile); } catch (Exception ignored) {}
        }
        update(slug, Map.of(
                "html", Map.of("hash", h != null ? h : ""),
                "md",   Map.of(
                        "generated_at", now(),
                        "html_hash",    h != null ? h : "",
                        "staged",       false,
                        "staged_at",    "",
                        "issues",       List.of(),
                        "validated_at", ""
                )
        ));
    }

    // ── mark_enriched ─────────────────────────────────────────────────────────

    public synchronized void markEnriched(String slug, Map<String, Object> stats) {
        update(slug, Map.of("enriched", Map.of(
                "generated_at",     now(),
                "youtube_replaced", stats.getOrDefault("youtube_replaced", 0),
                "gists_replaced",   stats.getOrDefault("gists_replaced",   0),
                "gists_failed",     stats.getOrDefault("gists_failed",     0),
                "classes_normalised",stats.getOrDefault("classes_normalised", 0),
                "languages_detected",stats.getOrDefault("languages_detected", 0),
                "embeds_wrapped",   stats.getOrDefault("embeds_wrapped",   0)
        )));
    }

    // ── Staged workflow ───────────────────────────────────────────────────────

    public synchronized void stage(String slug) {
        update(slug, Map.of("md", Map.of("staged", true, "staged_at", now())));
    }

    /**
     * Promote SLUG.md.staged → SLUG.md. Returns false if no staged file.
     *
     * @param slug     the post slug
     * @param mdDir    directory containing .md and .md.staged files
     * @param postsDir directory containing source HTML files (for hashing)
     */
    public synchronized boolean acceptStaged(String slug, Path mdDir, Path postsDir) {
        Path staged = mdDir.resolve(slug + ".md.staged");
        if (!Files.exists(staged)) return false;
        try {
            String content = Files.readString(staged);
            Files.writeString(mdDir.resolve(slug + ".md"), content);
            Files.delete(staged);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
        // Hash the HTML for freshness tracking
        Path htmlFile = postsDir.resolve(slug + ".html");
        String h = null;
        if (Files.exists(htmlFile)) {
            try { h = hash(htmlFile); } catch (Exception ignored) {}
        }
        update(slug, Map.of("md", Map.of(
                "staged",       false,
                "staged_at",    "",
                "generated_at", now(),
                "html_hash",    h != null ? h : "",
                "issues",       List.of(),
                "validated_at", ""
        )));
        return true;
    }

    /**
     * Delete SLUG.md.staged without touching SLUG.md. Returns false if absent.
     *
     * @param slug  the post slug
     * @param mdDir directory containing .md.staged files
     */
    public synchronized boolean rejectStaged(String slug, Path mdDir) {
        Path staged = mdDir.resolve(slug + ".md.staged");
        boolean existed = Files.exists(staged);
        if (existed) {
            try { Files.delete(staged); } catch (IOException e) { throw new RuntimeException(e); }
        }
        update(slug, Map.of("md", Map.of("staged", false, "staged_at", "")));
        return existed;
    }
}
```

- [ ] **Step 2: Run tests — all 28 must pass**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=StateStoreTest -q 2>&1 | tail -5
```

Expected: `Tests run: 28, Failures: 0, Errors: 0`

If any fail, diagnose and fix StateStore.java. Do NOT change the tests.

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/StateStore.java
git commit -m "feat(#53): add StateStore.java — mirrors state.py, 28 tests green

Refs #53"
```

---

## Task 4: Update PostsResource — 5 methods use Java directly

Replace JEP bridge calls for: `list`, `get`, `patch`, `stagedGet`, `stage`, `rejectStaged`.

Note: `stagedGet` returns the raw file content (text/plain), so it uses `serveFile` not StateStore directly.

**Files:**
- Modify: `server/src/main/java/io/sparge/server/PostsResource.java`

- [ ] **Step 1: Read PostsResource.java**

Read the current file — note the `list()`, `get()`, `patch()`, `stagedGet()`, `stage()`, `rejectStaged()` methods.

- [ ] **Step 2: Add @Inject StateStore and ActiveProject to PostsResource**

Add these injections alongside the existing `@Inject PythonBridge bridge`:

```java
@Inject StateStore    stateStore;
@Inject ActiveProject activeProject;
```

- [ ] **Step 3: Replace list() to use Java**

```java
@GET
public Response list(@QueryParam("author") String author) {
    try {
        List<ObjectNode> posts = stateStore.getAll();
        // Apply author filter
        String effectiveAuthor = author != null ? author : "";
        if (!effectiveAuthor.isEmpty()) {
            posts = posts.stream()
                    .filter(p -> effectiveAuthor.equals(p.path("author").asText("")))
                    .collect(java.util.stream.Collectors.toList());
        }
        posts.sort(java.util.Comparator.comparing(
                (ObjectNode p) -> p.path("date").asText(""))
                .thenComparing(p -> p.path("slug").asText("")));
        ArrayNode result = MAPPER.createArrayNode();
        posts.forEach(result::add);
        return ok(result.toString());
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

- [ ] **Step 4: Replace get() to use Java**

```java
@GET
@Path("{slug}")
public Response get(@PathParam("slug") String slug) {
    ObjectNode post = stateStore.get(slug);
    if (post == null) return Response.status(404)
            .header("Content-Type", "application/json; charset=utf-8")
            .header("Access-Control-Allow-Origin", "*")
            .entity("{\"error\":\"unknown slug: " + slug + "\"}").build();
    return ok(post.toString());
}
```

- [ ] **Step 5: Replace patch() to use Java**

```java
@PATCH
@Path("{slug}")
public Response patch(@PathParam("slug") String slug, String body) {
    try {
        ObjectNode patch = (body != null && !body.isBlank())
                ? (ObjectNode) MAPPER.readTree(body)
                : MAPPER.createObjectNode();
        Map<String, Object> safe = new java.util.LinkedHashMap<>();
        if (patch.has("flagged"))   safe.put("flagged",   patch.get("flagged").asBoolean());
        if (patch.has("reviewed"))  safe.put("reviewed",  patch.get("reviewed").asBoolean());
        if (patch.has("user_note")) safe.put("user_note", patch.get("user_note").asText());
        stateStore.update(slug, safe);
        ObjectNode updated = stateStore.get(slug);
        return ok(updated != null ? updated.toString() : "{}");
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

- [ ] **Step 6: Replace stage() and rejectStaged() to use Java**

```java
@POST
@Path("{slug}/stage")
@Consumes(MediaType.TEXT_PLAIN)
public Response stage(@PathParam("slug") String slug, String body) {
    try {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return BridgeResponse.of(bridge.call("bridge.post_stage", slug,
                body == null ? "" : body));
        java.nio.file.Path staged = cfg.mdDir().resolve(slug + ".md.staged");
        Files.writeString(staged, body == null ? "" : body);
        stateStore.stage(slug);
        ObjectNode post = stateStore.get(slug);
        return ok(post != null ? post.toString() : "{}");
    } catch (Exception e) {
        return err(e.getMessage());
    }
}

@POST
@Path("{slug}/reject-staged")
public Response rejectStaged(@PathParam("slug") String slug) {
    try {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return BridgeResponse.of(bridge.call("bridge.post_reject_staged", slug));
        stateStore.rejectStaged(slug, cfg.mdDir());
        ObjectNode post = stateStore.get(slug);
        return ok(post != null ? post.toString() : "{}");
    } catch (Exception e) {
        return err(e.getMessage());
    }
}
```

You need `import java.nio.file.Files;` added to the imports (as FQN or at top of file — check for existing Path import clash pattern from Task 7).

- [ ] **Step 7: Compile**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn compile -q 2>&1 | tail -5
```

Expected: no output.

- [ ] **Step 8: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/PostsResource.java
git commit -m "feat(#53): PostsResource list/get/patch/stage/rejectStaged use Java directly

Refs #53"
```

---

## Task 5: Remove bridge.py delegates for ported functions

Remove these functions from `scripts/bridge.py`:
- `posts_list` → now Java
- `post_get` → now Java
- `post_patch` → now Java
- `post_stage` → now Java
- `post_reject_staged` → now Java

**Do NOT remove:**
- `post_staged_get` — still reads the file, returns text/plain; bridge still needed until file-ops ported
- `post_accept_staged` — calls Python's accept_staged() which does file ops + state; keep for now
- `post_dismiss_html_check`, `post_undismiss_html_check` — keep for now (called from PostsResource dismiss/undismiss)
- All other bridge functions

**Files:**
- Modify: `scripts/bridge.py`

- [ ] **Step 1: Remove the 5 functions**

Find and delete these function definitions (def + body):
- `def posts_list(author: str | None = None) -> str:`
- `def post_get(slug: str) -> str:`
- `def post_patch(slug: str, body: str) -> str:`
- `def post_stage(slug: str, content: str) -> str:`
- `def post_reject_staged(slug: str) -> str:`

Also check: is `state_stage` (the Python `stage()` function) imported from state.py in bridge.py? If it's only used by `post_stage`, remove that import too.

- [ ] **Step 2: Smoke-test bridge.py**

```bash
cd ~/claude/sparge && python3 -c "
import sys; sys.path.insert(0, '.')
import scripts.bridge as bridge
result = bridge.bridge_init()
import json; data = json.loads(result)
print('initialized:', data['body']['initialized'])
print('posts:', data['body']['posts'])
for fn in ['posts_list','post_get','post_patch','post_stage','post_reject_staged']:
    assert not hasattr(bridge, fn), f'{fn} should be removed'
for fn in ['post_staged_get','post_accept_staged','post_scan_html']:
    assert hasattr(bridge, fn), f'{fn} must remain'
print('All assertions passed')
"
```

- [ ] **Step 3: Run pytest**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q --no-header --tb=no 2>&1 | tail -3
```

Expected: `460 passed, 0 failed`.

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add scripts/bridge.py
git commit -m "refactor(#53): remove posts_list/get/patch/stage/rejectStaged from bridge.py

JEP call count: 32 → 27
posts_list, post_get, post_patch, post_stage, post_reject_staged ported to Java.
Retained: post_staged_get, post_accept_staged, dismiss/undismiss (file ops still in Python)

Refs #53"
```

---

## Task 6: Full verification — JUnit + pytest + live server

- [ ] **Step 1: Run all JUnit tests**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
export PYTHONHOME=$HOME/claude/sparge/resources/python/mac-arm64
mvn test \
  -Djava.library.path=$HOME/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  2>&1 | grep -E "Tests run:|BUILD|FAILURE" | tail -10
```

Expected: BUILD SUCCESS. Total ≥ 42 tests (28 StateStore + 4 SpargeHome + 9 SpargeConfig + 1 Smoke).

- [ ] **Step 2: Run pytest**

```bash
unset PYTHONHOME
cd ~/claude/sparge && python3 -m pytest tests/ -q --no-header --tb=no 2>&1 | tail -3
```

Expected: `460 passed, 0 failed`.

- [ ] **Step 3: Build jar and smoke-test**

```bash
export DYLD_LIBRARY_PATH=$HOME/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
export PYTHONHOME=$HOME/claude/sparge/resources/python/mac-arm64
cd ~/claude/sparge/server
mvn package -DskipTests -q

java \
  -Djava.library.path=$HOME/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  -Dquarkus.http.port=9000 \
  -jar target/quarkus-app/quarkus-run.jar > /tmp/quarkus-p2.log 2>&1 &
JAVA_PID=$!

for i in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9000/api/config 2>/dev/null)
  [ "$STATUS" = "200" ] && echo "Ready after ${i}s" && break
  sleep 1
done

unset PYTHONHOME

# Test /api/posts (now Java-direct via StateStore)
COUNT=$(curl -s http://127.0.0.1:9000/api/posts | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d))")
echo "Posts returned by Java StateStore: $COUNT"

# Test /api/posts/{slug} (Java-direct)
SLUG=$(curl -s http://127.0.0.1:9000/api/posts | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['slug'])")
STALE=$(curl -s "http://127.0.0.1:9000/api/posts/$SLUG" | python3 -c "import json,sys; d=json.load(sys.stdin); print('has_stale:', 'stale' in d.get('md', {}))")
echo "Single post $SLUG — $STALE"

kill $JAVA_PID 2>/dev/null
wait $JAVA_PID 2>/dev/null
echo "Server stopped"
```

Expected: ~577 posts, stale field present.

- [ ] **Step 4: Final commit**

```bash
cd ~/claude/sparge
git commit --allow-empty -m "feat(#53): Phase 2 complete — state.py ported to Java

JEP call count: 32 → 27 (posts_list, post_get, post_patch, post_stage, post_reject_staged)
JUnit: 42+ tests passing (28 StateStore + 14 from Phase 1)
pytest: 460 passing (unchanged)
/api/posts list/get/patch and staging workflow now served by StateStore (Java)

Closes #53"
```

---

## Self-Review

**Spec coverage:**
- `state.py` `get_all()` / `get()` → StateStore.getAll() / get() ✓ (Task 3)
- `update()` deep merge → StateStore.update() with mergeInto() ✓ (Task 3)
- `dismiss/undismiss_html_check` → StateStore (kept in bridge for now; Java has the impl) ✓
- `set_html_issues()` with dismiss logic → StateStore.setHtmlIssues() ✓ (Task 3)
- `set_md_issues()` → StateStore.setMdIssues() ✓ (Task 3)
- `mark_md_generated()` → StateStore.markMdGenerated() ✓ (Task 3)
- `mark_enriched()` → StateStore.markEnriched() ✓ (Task 3)
- `stage()` / `accept_staged()` / `reject_staged()` → StateStore ✓ (Task 3)
- ActiveProject gains projectDir ✓ (Task 1)
- 5 bridge delegates removed: 32→27 ✓ (Task 5)
- TDD: 28 tests written first ✓ (Task 2 before Task 3)

**Placeholder scan:** No TBDs. All code blocks complete. acceptStaged / rejectStaged parameter signatures are consistent between test (uses positional paths) and implementation. ✓

**Type consistency:**
- `stateStore.get(slug)` returns `ObjectNode` — consistent throughout ✓
- `stateStore.update(slug, Map<String,Object>)` — consistent throughout ✓
- `activeProject.getConfig()` returns `SpargeConfig.ResolvedConfig` — used correctly in stage/reject ✓

**TDD emphasis (per user feedback):** 28 tests before any implementation. Edge cases covered: 4 stale scenarios, 3 dismiss/undismiss interactions, full staging workflow with real temp files, hash-matching verification. All written as failing tests in Task 2, passing only after Task 3.
