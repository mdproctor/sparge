package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

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
