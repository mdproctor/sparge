package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.util.ArrayList;
import java.util.List;

@Path("/api/ingest")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class IngestResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject IngestService ingestService;

    @GET
    @Path("status")
    public Response status() { return ok(ingestService.status()); }

    @POST
    @Path("cancel")
    @Consumes(MediaType.WILDCARD)
    public Response cancel() { return ok(ingestService.cancel()); }

    @POST
    @Path("detect")
    public Response detect(String body) {
        try {
            String url = MAPPER.readTree(body == null ? "{}" : body).path("url").asText("");
            if (url.isBlank()) return err(400, "url required");
            return ok(ingestService.detectPlatform(url));
        } catch (Exception e) { return err(e.getMessage()); }
    }

    @POST
    @Path("discover")
    public Response discover(String body) {
        try {
            var data   = MAPPER.readTree(body == null ? "{}" : body);
            String url = data.path("url").asText("");
            String author = data.path("author_filter").asText(null);
            if (url.isBlank()) return err(400, "url required");
            return ok(ingestService.discoverUrls(url, author));
        } catch (Exception e) { return err(e.getMessage()); }
    }

    @POST
    @Path("preview")
    public Response preview(String body) {
        try {
            String url = MAPPER.readTree(body == null ? "{}" : body).path("url").asText("");
            if (url.isBlank()) return err(400, "url required");
            return ok(ingestService.previewPost(url));
        } catch (Exception e) { return err(e.getMessage()); }
    }

    @POST
    @Path("run")
    public Response run(String body) {
        try {
            var data = MAPPER.readTree(body == null ? "{}" : body);
            List<String> urls = new ArrayList<>();
            for (var u : data.path("urls")) urls.add(u.asText());
            String author = data.path("author_filter").asText(null);
            if (urls.isEmpty()) return err(400, "urls required");
            return ok(ingestService.startIngest(urls, author));
        } catch (Exception e) { return err(e.getMessage()); }
    }

    private Response ok(Object obj) {
        try {
            return Response.ok(MAPPER.writeValueAsString(obj))
                    .header("Content-Type",                "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .build();
        } catch (Exception e) { return err(e.getMessage()); }
    }

    private Response err(String msg) { return err(500, msg); }

    private Response err(int status, String msg) {
        String esc = msg == null ? "error" : msg.replace("\\","\\\\").replace("\"","\\\"");
        return Response.status(status)
                .entity("{\"error\":\"" + esc + "\"}")
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }
}
