package io.sparge.server;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.core.Response;

import java.io.IOException;
import java.net.URI;
import java.net.URLConnection;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Serves three categories:
 *   GET /               → redirect to /ui/projects.html
 *   GET /ui/{path}      → ../ui/{path} on disk
 *   GET /{anything}     → blog asset from SERVE_ROOT (via bridge.static_resolve)
 */
@jakarta.ws.rs.Path("/")
public class StaticResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject PythonBridge bridge;

    private final Path uiDir;

    public StaticResource() {
        // server/ is CWD when Quarkus runs; ui/ is a sibling directory
        Path serverDir = Paths.get(System.getProperty("user.dir")).toAbsolutePath();
        this.uiDir = serverDir.getParent().resolve("ui");
    }

    @GET
    public Response root() {
        return Response.temporaryRedirect(URI.create("/ui/projects.html")).build();
    }

    @GET
    @jakarta.ws.rs.Path("ui/{path:.*}")
    public Response serveUi(@PathParam("path") String path) {
        String rel = (path == null || path.isEmpty()) ? "projects.html" : path;
        return serveFile(uiDir.resolve(rel));
    }

    @GET
    @jakarta.ws.rs.Path("{path:.*}")
    public Response serveStatic(@PathParam("path") String path) {
        String json = bridge.call("bridge.static_resolve", "/" + path);
        try {
            JsonNode node = MAPPER.readTree(json);
            if (node.get("status").asInt() != 200) {
                return Response.status(404).build();
            }
            return serveFile(Paths.get(node.get("file_path").asText()));
        } catch (Exception e) {
            return Response.serverError().build();
        }
    }

    private Response serveFile(Path file) {
        try {
            byte[] data = Files.readAllBytes(file);
            String mime = URLConnection.guessContentTypeFromName(file.toString());
            if (mime == null) mime = "application/octet-stream";
            return Response.ok(data)
                .header("Content-Type",                mime)
                .header("Access-Control-Allow-Origin", "*")
                .build();
        } catch (NoSuchFileException e) {
            return Response.status(404).build();
        } catch (IOException e) {
            return Response.serverError().build();
        }
    }
}
