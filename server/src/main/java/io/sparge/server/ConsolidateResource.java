package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.inject.Inject;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.util.Map;

@Path("/api/consolidate")
@Produces(MediaType.APPLICATION_JSON)
public class ConsolidateResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject ActiveProject activeProject;

    @POST
    public Response consolidate() {
        if (!activeProject.isActive()) {
            return err(400, "no active project");
        }
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        java.nio.file.Path assetsDir = cfg.assetsDir();
        java.nio.file.Path postsDir  = cfg.postsDir();
        if (assetsDir == null || postsDir == null) {
            return err(400, "project paths not configured");
        }
        try {
            Consolidate.Result result = Consolidate.consolidate(assetsDir, postsDir);
            String body = MAPPER.writeValueAsString(Map.of(
                    "promoted",     result.promoted(),
                    "updated_html", result.updatedHtml(),
                    "duplicates",   result.duplicates()
            ));
            return ok(body);
        } catch (Exception e) {
            String msg = e.getMessage() != null ? e.getMessage().replace("\"", "'") : "unknown";
            return err(500, msg);
        }
    }

    private static Response ok(String json) {
        return Response.ok(json)
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }

    private static Response err(int status, String msg) {
        return Response.status(status)
                .entity("{\"error\":\"" + msg + "\"}")
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }
}
