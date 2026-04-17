package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.inject.Inject;
import jakarta.ws.rs.DefaultValue;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@jakarta.ws.rs.Path("/api/search")
@Produces(MediaType.APPLICATION_JSON)
public class SearchResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject StateStore stateStore;
    @Inject ActiveProject activeProject;

    @GET
    public Response search(@QueryParam("q")     @DefaultValue("") String q,
                           @QueryParam("scope") @DefaultValue("both") String scope) {
        String query = q.strip().toLowerCase();
        Path mdDir = activeProject.isActive() ? activeProject.getConfig().mdDir() : null;
        List<String> slugs = filterSlugs(stateStore.getAll(), query, scope, mdDir);
        try {
            return ok(MAPPER.writeValueAsString(Map.of("slugs", slugs)));
        } catch (Exception e) {
            return Response.status(500)
                    .header("Content-Type",                "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .entity("{\"error\":\"internal error\"}")
                    .build();
        }
    }

    /**
     * Package-private for unit testing.
     * Empty query returns all slugs. Non-empty filters by title and/or MD body content.
     * Mirrors bridge.py search() logic exactly.
     */
    List<String> filterSlugs(List<ObjectNode> posts, String query, String scope, Path mdDir) {
        List<String> results = new ArrayList<>();
        for (ObjectNode p : posts) {
            String slug = p.path("slug").asText("");
            if (query.isEmpty()) { results.add(slug); continue; }

            String  title   = p.path("title").asText("").toLowerCase();
            boolean inTitle = (scope.equals("title") || scope.equals("both")) && title.contains(query);
            boolean inBody  = false;

            if (!inTitle && mdDir != null && (scope.equals("body") || scope.equals("both"))) {
                Path mdPath = mdDir.resolve(slug + ".md");
                if (Files.exists(mdPath)) {
                    try {
                        inBody = Files.readString(mdPath).toLowerCase().contains(query);
                    } catch (Exception ignored) {}
                }
            }
            if (inTitle || inBody) results.add(slug);
        }
        return results;
    }

    private static Response ok(String json) {
        return Response.ok(json)
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }
}
