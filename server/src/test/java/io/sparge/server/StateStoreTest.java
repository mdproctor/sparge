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
        store.update("post", Map.of("html", Map.of("hash", "xyz")));
        ObjectNode entry = store.get("post");
        assertEquals("xyz", entry.path("html").path("hash").asText());
        assertTrue(entry.path("html").path("issues").isArray(),
                "issues array must survive partial html update");
    }

    @Test
    void updateDeepMergesMdKeys() {
        store.update("post", Map.of("md", Map.of("generated_at", "2026-01-01", "staged", false)));
        store.update("post", Map.of("md", Map.of("staged", true)));
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
        ArrayNode issues = (ArrayNode) store.get("post").path("html").path("issues");
        assertEquals(0, issues.size(), "dismissed issue must be filtered from active list");
    }

    @Test
    void dismissStoredInDismissedHtmlChecks() {
        store.update("post", Map.of("html", Map.of("issues", List.of())));
        store.dismissHtmlCheck("post", "my_check");
        assertFalse(store.get("post").path("dismissed_html_checks").path("my_check").isMissingNode(),
                "dismissed_html_checks must store the dismissed type");
    }

    @Test
    void dismissDoesNothingForUnknownSlug() {
        assertDoesNotThrow(() -> store.dismissHtmlCheck("ghost", "some_check"));
    }

    @Test
    void undismissRemovesDismissalEntry() {
        store.update("post", Map.of("html", Map.of("issues", List.of())));
        store.dismissHtmlCheck("post", "my_check");
        store.undismissHtmlCheck("post", "my_check");
        assertTrue(store.get("post").path("dismissed_html_checks").path("my_check").isMissingNode(),
                "undismiss must remove the dismissal entry");
    }

    @Test
    void setHtmlIssuesClearsDismissalWhenIssueNoLongerDetected() {
        store.update("post", Map.of("html", Map.of("issues", List.of(
            Map.of("type", "gone_issue", "level", "WARN", "detail", "x", "check", "gone_issue")
        ))));
        store.dismissHtmlCheck("post", "gone_issue");
        store.setHtmlIssues("post", List.of(), null, null);
        assertTrue(store.get("post").path("dismissed_html_checks").path("gone_issue").isMissingNode(),
                "dismissal must be cleared when the issue is no longer detected");
    }

    @Test
    void setHtmlIssuesKeepsDismissedIssueFiltered() {
        store.update("post", Map.of("html", Map.of("issues", List.of(
            Map.of("type", "persistent", "level", "WARN", "detail", "x", "check", "persistent")
        ))));
        store.dismissHtmlCheck("post", "persistent");
        store.setHtmlIssues("post", List.of(
            Map.of("type", "persistent", "level", "WARN", "detail", "x", "check", "persistent")
        ), null, null);
        ArrayNode active = (ArrayNode) store.get("post").path("html").path("issues");
        assertEquals(0, active.size(), "dismissed issue must stay filtered in active list");
        assertFalse(store.get("post").path("dismissed_html_checks").path("persistent").isMissingNode(),
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
        Path htmlFile = dir.resolve("my-post.html");
        Files.writeString(htmlFile, "<html>content</html>");
        store.markMdGenerated("my-post", htmlFile);
        ObjectNode md = (ObjectNode) store.get("my-post").path("md");
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
        String mdHtmlHash = store.get("post").path("md").path("html_hash").asText();
        store.update("post", Map.of("html", Map.of("hash", mdHtmlHash)));
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
        ObjectNode enriched = (ObjectNode) store.get("post").path("enriched");
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
        assertFalse(store.acceptStaged("post", dir, dir));
    }

    @Test
    void acceptStagedPromotesStagedToMdAndClearsFlag() throws Exception {
        Path mdDir = dir.resolve("md");
        Files.createDirectories(mdDir);
        Files.writeString(mdDir.resolve("my-post.md.staged"), "# Staged content");
        store.stage("my-post");

        Path postsDir = dir.resolve("posts");
        Files.createDirectories(postsDir);
        Files.writeString(postsDir.resolve("my-post.html"), "<html/>");

        boolean result = store.acceptStaged("my-post", mdDir, postsDir);

        assertTrue(result);
        assertTrue(Files.exists(mdDir.resolve("my-post.md")), "md file must be created");
        assertEquals("# Staged content", Files.readString(mdDir.resolve("my-post.md")));
        assertFalse(Files.exists(mdDir.resolve("my-post.md.staged")), "staged file must be deleted");
        assertFalse(store.get("my-post").path("md").path("staged").asBoolean());
    }

    @Test
    void acceptStaged_enrichedDirFirst_usesEnrichedHtmlForHash(@TempDir Path tmp) throws Exception {
        Path mdDir       = tmp.resolve("md");
        Path postsDir    = tmp.resolve("posts");
        Path enrichedDir = tmp.resolve("enriched");
        Files.createDirectories(mdDir);
        Files.createDirectories(postsDir);
        Files.createDirectories(enrichedDir);

        // Write a staged file
        Files.writeString(mdDir.resolve("my-post.md.staged"), "# Accepted");

        // Both original and enriched HTML exist with different content
        Files.writeString(postsDir.resolve("my-post.html"),    "<html>original</html>");
        Files.writeString(enrichedDir.resolve("my-post.html"), "<html>enriched</html>");

        StateStore store = new StateStore(tmp.resolve("state.json"));
        store.acceptStaged("my-post", mdDir, postsDir, enrichedDir);

        // The html_hash should match the ENRICHED file, not the original
        String enrichedHash = StateStore.hash(enrichedDir.resolve("my-post.html"));
        String originalHash = StateStore.hash(postsDir.resolve("my-post.html"));

        ObjectNode post = store.get("my-post");
        String storedHash = post.path("md").path("html_hash").asText();
        assertEquals(enrichedHash, storedHash,
                "Should use enriched HTML for hash, not original");
        assertNotEquals(originalHash, storedHash,
                "Should not use original HTML when enriched exists");
    }

    @Test
    void rejectStagedReturnsFalseWhenNoStagedFile() {
        assertFalse(store.rejectStaged("ghost", dir));
    }

    @Test
    void rejectStagedDeletesStagedFileAndClearsFlag() throws Exception {
        Path mdDir = dir.resolve("md");
        Files.createDirectories(mdDir);
        Files.writeString(mdDir.resolve("post.md.staged"), "staged");
        store.stage("post");

        assertTrue(store.rejectStaged("post", mdDir));
        assertFalse(Files.exists(mdDir.resolve("post.md.staged")));
        assertFalse(store.get("post").path("md").path("staged").asBoolean());
    }

    // ── Refinement state ──────────────────────────────────────────────────────

    @Test
    void setMdSuggestions_stores_in_md_sub_dict() {
        store.update("post", Map.of("title", "My Post"));
        var suggestions = List.of(Map.<String, Object>of(
            "check", "language_tag_missing", "level", "WARN", "detail", "2 fences"));
        store.setMdSuggestions("post", suggestions);
        ObjectNode md = (ObjectNode) store.get("post").path("md");
        assertFalse(md.path("suggestions").isMissingNode(), "suggestions must be stored in md sub-dict");
        assertTrue(md.path("suggestions").isArray(), "suggestions must be an array");
        assertEquals(1, md.path("suggestions").size());
        assertEquals("language_tag_missing", md.path("suggestions").get(0).path("check").asText());
        assertFalse(md.path("suggestions_at").isMissingNode(), "suggestions_at timestamp must be set");
    }

    @Test
    void setMdSuggestions_preserves_existing_md_keys() {
        store.update("post", Map.of("md", Map.of("generated_at", "2026-01-01", "staged", false)));
        store.setMdSuggestions("post", List.of());
        assertEquals("2026-01-01", store.get("post").path("md").path("generated_at").asText(),
            "existing md keys must survive setMdSuggestions");
    }

    @Test
    void setRefinement_stores_accepted_and_conflicts() {
        store.update("post", Map.of("title", "My Post"));
        var accepted = List.of(Map.<String, Object>of("fix", "add_language_tag", "slug", "post"));
        var conflicts = List.of("conflict-slug-1");
        store.setRefinement("post", accepted, conflicts);
        ObjectNode refinement = (ObjectNode) store.get("post").path("refinement");
        assertFalse(refinement.isMissingNode(), "refinement sub-dict must exist");
        assertTrue(refinement.path("accepted").isArray());
        assertEquals(1, refinement.path("accepted").size());
        assertEquals("add_language_tag", refinement.path("accepted").get(0).path("fix").asText());
        assertTrue(refinement.path("replay_conflicts").isArray());
        assertEquals(1, refinement.path("replay_conflicts").size());
        assertEquals("conflict-slug-1", refinement.path("replay_conflicts").get(0).asText());
        assertFalse(refinement.path("refined_at").isMissingNode(), "refined_at timestamp must be set");
    }

    @Test
    void setRefinement_deep_merges_with_existing_refinement_keys() {
        store.update("post", Map.of("refinement", Map.of("extra_key", "keep_me")));
        store.setRefinement("post", List.of(), List.of());
        assertEquals("keep_me", store.get("post").path("refinement").path("extra_key").asText(),
            "existing refinement keys must survive setRefinement deep-merge");
    }

    @Test
    void clearRefinement_resets_to_empty() {
        var accepted = List.of(Map.<String, Object>of("fix", "something"));
        store.setRefinement("post", accepted, List.of("c1"));
        store.clearRefinement("post");
        ObjectNode refinement = (ObjectNode) store.get("post").path("refinement");
        assertEquals(0, refinement.path("accepted").size(), "accepted must be empty after clear");
        assertEquals(0, refinement.path("replay_conflicts").size(), "replay_conflicts must be empty after clear");
        assertEquals("", refinement.path("refined_at").asText(), "refined_at must be empty string after clear");
    }
}
