package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/config")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class ConfigResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject ActiveProject activeProject;

    @GET
    public Response get() {
        if (!activeProject.isActive()) {
            return error(400, "no active project");
        }
        return ok(activeProject.getConfig().raw().toString());
    }

    @POST
    public Response post(String body) {
        if (!activeProject.isActive()) {
            return error(400, "no active project");
        }
        if (body == null || body.isBlank()) body = "{}";
        try {
            ObjectNode patch = (ObjectNode) MAPPER.readTree(body);
            ObjectNode raw   = activeProject.getConfig().raw();
            patch.fields().forEachRemaining(e -> raw.set(e.getKey(), e.getValue()));
            java.nio.file.Path configPath = activeProject.getProjectDir().resolve("config.json");
            SpargeConfig.save(configPath, raw);
            SpargeConfig.ResolvedConfig updated =
                    SpargeConfig.load(configPath, activeProject.getProjectDir());
            activeProject.set(activeProject.getProjectId(), updated, activeProject.getProjectDir());
            return ok("{\"saved\":true}");
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            return error(400, "invalid JSON");
        } catch (Exception e) {
            String msg = e.getMessage() != null ? e.getMessage().replace("\"", "'") : "unknown";
            return error(500, msg);
        }
    }

    private static Response ok(String json) {
        return Response.ok(json)
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }

    private static Response error(int status, String msg) {
        return Response.status(status)
                .entity("{\"error\":\"" + msg + "\"}")
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }
}
