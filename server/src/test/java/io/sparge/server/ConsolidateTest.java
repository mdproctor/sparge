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
        Files.createDirectories(assets);

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
        assertEquals(1, Files.list(assets.resolve("global")).count());
        long remaining = (Files.isDirectory(assets.resolve("posts/post-a")) ? Files.list(assets.resolve("posts/post-a")).count() : 0)
                       + (Files.isDirectory(assets.resolve("posts/post-b")) ? Files.list(assets.resolve("posts/post-b")).count() : 0);
        assertEquals(0, remaining);
    }

    @Test
    void consolidate_threePostsSameContent_promotesOneDeletesTwo(@TempDir Path tmp) throws Exception {
        Path assets = tmp.resolve("assets");
        Files.createDirectories(assets.resolve("posts/post-a"));
        Files.createDirectories(assets.resolve("posts/post-b"));
        Files.createDirectories(assets.resolve("posts/post-c"));

        byte[] shared = "triple-duplicate".getBytes();
        Files.write(assets.resolve("posts/post-a/img.png"), shared);
        Files.write(assets.resolve("posts/post-b/img.png"), shared);
        Files.write(assets.resolve("posts/post-c/img.png"), shared);

        Consolidate.Result r = Consolidate.consolidate(assets, tmp.resolve("cleaned"));
        assertEquals(1, r.promoted());
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

        Path html = cleaned.resolve("other.html");
        String original = "<img src=\"/assets/posts/post-a/other.png\">";
        Files.writeString(html, original);

        Consolidate.consolidate(assets, cleaned);

        assertEquals(original, Files.readString(html), "Unrelated HTML should be unchanged");
    }

    // ── index file ────────────────────────────────────────────────────────────

    @Test
    void consolidate_indexFileUpdatedAfterPromotion(@TempDir Path tmp) throws Exception {
        Path assets = tmp.resolve("assets");
        Files.createDirectories(assets.resolve("posts/post-a"));
        Files.createDirectories(assets.resolve("posts/post-b"));

        byte[] shared = "data".getBytes();
        Files.write(assets.resolve("posts/post-a/file.png"), shared);
        Files.write(assets.resolve("posts/post-b/file.png"), shared);

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
    void consolidate_noIndexFile_runsSuccessfully(@TempDir Path tmp) throws Exception {
        Path assets = tmp.resolve("assets");
        Files.createDirectories(assets.resolve("posts/post-a"));
        Files.createDirectories(assets.resolve("posts/post-b"));

        byte[] shared = "data".getBytes();
        Files.write(assets.resolve("posts/post-a/file.png"), shared);
        Files.write(assets.resolve("posts/post-b/file.png"), shared);

        // No .url-index.json — should still work
        Consolidate.Result r = Consolidate.consolidate(assets, tmp.resolve("cleaned"));
        assertEquals(1, r.promoted());
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
