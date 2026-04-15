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
            String     projectName,
            Path       serveRoot,
            Path       postsDir,
            Path       assetsDir,
            Path       mdDir,
            Path       enrichedDir,
            String     authorFilter,
            String     githubToken,
            ObjectNode raw           // original JSON — needed for save()
    ) {}

    /**
     * Load and resolve a project config.json.
     *
     * @param configPath  path to the project's config.json
     * @param projectDir  the project directory (enrichedDir = projectDir/enriched)
     */
    public static ResolvedConfig load(Path configPath, Path projectDir) throws Exception {
        ObjectNode raw      = (ObjectNode) MAPPER.readTree(configPath.toFile());
        Path serveRoot      = Path.of(raw.get("serve_root").asText());
        Path postsDir       = resolve(serveRoot, raw.path("source").path("posts_dir").asText("legacy/posts"));
        Path assetsDir      = resolve(serveRoot, raw.path("source").path("assets_dir").asText("legacy/assets"));
        Path mdDir          = resolve(serveRoot, raw.path("output").path("md_dir").asText("output/md"));
        Path enrichedDir    = projectDir.resolve("enriched");
        String authorFilter = raw.path("filter").path("author").asText("");
        String githubToken  = raw.path("github_token").asText("");

        return new ResolvedConfig(
                raw.path("project_name").asText(""),
                serveRoot, postsDir, assetsDir, mdDir, enrichedDir,
                authorFilter, githubToken, raw
        );
    }

    /**
     * Save a config back to disk.
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
