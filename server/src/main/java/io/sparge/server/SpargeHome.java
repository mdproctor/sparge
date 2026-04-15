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
        this.home               = home;
        this.spargeDir          = home.resolve(".sparge");
        this.spargeCfg          = spargeDir.resolve("config.json");
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
