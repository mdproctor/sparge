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
