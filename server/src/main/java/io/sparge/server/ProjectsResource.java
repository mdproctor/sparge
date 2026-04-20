package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.nio.file.Files;
import java.time.Instant;
import java.util.List;
import java.util.regex.Pattern;

@Path("/api/projects")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class ProjectsResource {

    private static final ObjectMapper MAPPER  = new ObjectMapper();
    private static final Pattern      SLUG_STRIP = Pattern.compile("[^a-z0-9]+");

    @Inject PythonBridge  bridge;
    @Inject ProjectsStore store;
    @Inject ActiveProject activeProject;
    @Inject SpargeHome    spargeHome;
    @Inject IngestService ingestService;

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
            ObjectNode data = (body != null && !body.isBlank())
                    ? (ObjectNode) MAPPER.readTree(body)
                    : MAPPER.createObjectNode();

            String name = data.path("name").asText("").strip();
            if (name.isEmpty()) return Response.status(400)
                    .header("Content-Type", "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .entity("{\"error\":\"name required\"}").build();

            String rawId = SLUG_STRIP.matcher(name.toLowerCase())
                    .replaceAll("-").replaceAll("^-+|-+$", "");
            final String projectId = rawId.length() > 40 ? rawId.substring(0, 40) : rawId;

            java.nio.file.Path projectDir = store.getProjectDir(projectId);
            Files.createDirectories(projectDir);

            // Build project config.json — mirrors bridge.py projects_create
            ObjectNode cfg = MAPPER.createObjectNode();
            cfg.put("project_name", name);
            cfg.put("serve_root",   data.path("serve_root").asText(System.getProperty("user.home")));

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

    @POST
    @Path("{id}/activate")
    public Response activate(@PathParam("id") String id) {
        try {
            java.nio.file.Path projectDir = store.getProjectDir(id);
            java.nio.file.Path configPath = projectDir.resolve("config.json");
            if (!Files.exists(configPath)) return err("project not found: " + id);
            activeProject.set(id, SpargeConfig.load(configPath, projectDir), projectDir);
        } catch (Exception e) {
            return err("activation failed: " + e.getMessage());
        }
        // All endpoints are now native Java — no Python bridge call needed
        return ok("{\"active\":\"" + id + "\",\"name\":\""
                + activeProject.getConfig().projectName() + "\"}");
    }

    @POST
    @Path("{id}/ingest/run")
    public Response projectIngestRun(@PathParam("id") String id, String body) {
        // Activate the project in Java, then start ingest
        try {
            java.nio.file.Path projectDir = store.getProjectDir(id);
            java.nio.file.Path configPath = projectDir.resolve("config.json");
            if (!java.nio.file.Files.exists(configPath)) return err("project not found: " + id);
            activeProject.set(id, SpargeConfig.load(configPath, projectDir), projectDir);
        } catch (Exception e) { return err("failed to activate project: " + e.getMessage()); }
        try {
            var data = MAPPER.readTree(body == null ? "{}" : body);
            java.util.List<String> urls = new java.util.ArrayList<>();
            for (var u : data.path("urls")) urls.add(u.asText());
            String author = data.path("author_filter").asText(null);
            if (urls.isEmpty()) return Response.status(400)
                    .entity("{\"error\":\"urls required\"}")
                    .header("Content-Type",                "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*").build();
            return ok(MAPPER.writeValueAsString(ingestService.startIngest(urls, author)));
        } catch (Exception e) { return err(e.getMessage()); }
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
