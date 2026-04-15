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
