package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.core.Response;

import java.io.IOException;
import java.net.URI;
import java.net.URLConnection;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Serves three categories:
 *   GET /               → redirect to /ui/projects.html
 *   GET /ui/{path}      → ../ui/{path} on disk
 *   GET /{anything}     → blog asset from SERVE_ROOT via native path resolution
 */
@jakarta.ws.rs.Path("/")
public class StaticResource {

    @Inject ActiveProject activeProject;

    private final Path uiDir;

    public StaticResource() {
        String uiProp = System.getProperty("sparge.ui.dir");
        if (uiProp != null) {
            this.uiDir = Paths.get(uiProp).toAbsolutePath();
        } else {
            // fallback: direct java -jar from server/ directory
            Path serverDir = Paths.get(System.getProperty("user.dir")).toAbsolutePath();
            this.uiDir = serverDir.getParent().resolve("ui");
        }
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
        // RESTEasy Reactive may route GET / here with path="" when {path:.*} wins over the
        // bare @GET root() method — redirect to the projects page in that case.
        if (path == null || path.isEmpty()) {
            return root();
        }
        if (!activeProject.isActive()) {
            return Response.status(404).build();
        }
        Path serveRoot = activeProject.getConfig().serveRoot().toAbsolutePath().normalize();
        String decoded = URLDecoder.decode(path, StandardCharsets.UTF_8);
        if (decoded.contains("..")) {
            return Response.status(403).build();
        }
        String rel  = decoded.startsWith("/") ? decoded.substring(1) : decoded;
        Path   file = serveRoot.resolve(rel).normalize();
        if (!file.startsWith(serveRoot)) {
            return Response.status(403).build();
        }
        return serveFile(file);
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
