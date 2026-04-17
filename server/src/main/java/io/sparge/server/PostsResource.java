package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.util.List;
import java.util.Map;

@Path("/api/posts")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class PostsResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject PythonBridge  bridge;
    @Inject StateStore    stateStore;
    @Inject ActiveProject activeProject;

    // ── CRUD ──────────────────────────────────────────────────────────────────

    @GET
    public Response list(@QueryParam("author") String author) {
        try {
            List<ObjectNode> posts = stateStore.getAll();
            String effectiveAuthor = (author != null) ? author : "";
            if (!effectiveAuthor.isEmpty()) {
                posts = posts.stream()
                        .filter(p -> effectiveAuthor.equals(p.path("author").asText("")))
                        .collect(java.util.stream.Collectors.toList());
            }
            posts.sort(java.util.Comparator
                    .comparing((ObjectNode p) -> p.path("date").asText(""))
                    .thenComparing(p -> p.path("slug").asText("")));
            ArrayNode result = MAPPER.createArrayNode();
            posts.forEach(result::add);
            return ok(result.toString());
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    @GET
    @Path("{slug}")
    public Response get(@PathParam("slug") String slug) {
        ObjectNode post = stateStore.get(slug);
        if (post == null) return Response.status(404)
                .header("Content-Type", "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .entity("{\"error\":\"unknown slug: " + slug + "\"}").build();
        return ok(post.toString());
    }

    @PATCH
    @Path("{slug}")
    public Response patch(@PathParam("slug") String slug, String body) {
        try {
            ObjectNode patch = (body != null && !body.isBlank())
                    ? (ObjectNode) MAPPER.readTree(body)
                    : MAPPER.createObjectNode();
            Map<String, Object> safe = new java.util.LinkedHashMap<>();
            if (patch.has("flagged"))   safe.put("flagged",   patch.get("flagged").asBoolean());
            if (patch.has("reviewed"))  safe.put("reviewed",  patch.get("reviewed").asBoolean());
            if (patch.has("user_note")) safe.put("user_note", patch.get("user_note").asText());
            stateStore.update(slug, safe);
            ObjectNode updated = stateStore.get(slug);
            return ok(updated != null ? updated.toString() : "{}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    // ── HTML ──────────────────────────────────────────────────────────────────

    @GET
    @Path("{slug}/html")
    @Produces(MediaType.TEXT_PLAIN)
    public Response html(@PathParam("slug") String slug) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) {
            // No active project — fall back to bridge
            return BridgeResponse.of(bridge.call("bridge.post_html", slug));
        }
        try {
            java.nio.file.Path enriched = cfg.enrichedDir().resolve(slug + ".html");
            java.nio.file.Path original  = cfg.postsDir().resolve(slug + ".html");
            java.nio.file.Path htmlPath  = java.nio.file.Files.exists(enriched) ? enriched : original;

            if (!java.nio.file.Files.exists(htmlPath)) {
                return Response.status(404)
                        .header("Content-Type",                "application/json; charset=utf-8")
                        .header("Access-Control-Allow-Origin", "*")
                        .entity("{\"error\":\"HTML not found: " + slug + "\"}")
                        .build();
            }

            String raw     = java.nio.file.Files.readString(htmlPath);
            String content = HtmlUtils.prettifyHtml(raw);

            return Response.ok(content)
                    .header("Content-Type",                "text/plain; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .build();
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    @GET
    @Path("{slug}/view")
    @Produces(MediaType.TEXT_HTML)
    public Response view(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_view", slug));
    }

    @POST
    @Path("{slug}/save-html")
    @Consumes({MediaType.TEXT_PLAIN, MediaType.TEXT_HTML, MediaType.WILDCARD})
    public Response saveHtml(@PathParam("slug") String slug, String body) {
        return BridgeResponse.of(bridge.call("bridge.post_save_html", slug,
                                             body == null ? "" : body));
    }

    // ── Markdown ──────────────────────────────────────────────────────────────

    @POST
    @Path("{slug}/generate-md")
    public Response generateMd(@PathParam("slug") String slug,
                                @QueryParam("dry") @DefaultValue("") String dryParam) {
        // Accept ?dry=1 (Python server convention) and ?dry=true (JAX-RS convention)
        boolean dry = "1".equals(dryParam) || "true".equalsIgnoreCase(dryParam);
        return BridgeResponse.of(bridge.call("bridge.post_generate_md", slug, dry));
    }

    @POST
    @Path("{slug}/validate-md")
    public Response validateMd(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_validate_md", slug));
    }

    @POST
    @Path("{slug}/save-md")
    @Consumes(MediaType.TEXT_PLAIN)
    public Response saveMd(@PathParam("slug") String slug, String body) {
        return BridgeResponse.of(bridge.call("bridge.post_save_md", slug,
                                             body == null ? "" : body));
    }

    // ── Staged workflow ───────────────────────────────────────────────────────

    @GET
    @Path("{slug}/staged")
    @Produces(MediaType.TEXT_PLAIN)
    public Response stagedGet(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_staged_get", slug));
    }

    @POST
    @Path("{slug}/stage")
    @Consumes(MediaType.TEXT_PLAIN)
    public Response stage(@PathParam("slug") String slug, String body) {
        try {
            SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
            if (cfg == null) return BridgeResponse.of(bridge.call("bridge.post_stage", slug,
                    body == null ? "" : body));
            java.nio.file.Files.writeString(cfg.mdDir().resolve(slug + ".md.staged"),
                    body == null ? "" : body);
            stateStore.stage(slug);
            ObjectNode post = stateStore.get(slug);
            return ok(post != null ? post.toString() : "{}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    @POST
    @Path("{slug}/accept-staged")
    public Response acceptStaged(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_accept_staged", slug));
    }

    @POST
    @Path("{slug}/reject-staged")
    public Response rejectStaged(@PathParam("slug") String slug) {
        try {
            SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
            if (cfg == null) return BridgeResponse.of(bridge.call("bridge.post_reject_staged", slug));
            stateStore.rejectStaged(slug, cfg.mdDir());
            ObjectNode post = stateStore.get(slug);
            return ok(post != null ? post.toString() : "{}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    // ── Scan ─────────────────────────────────────────────────────────────────

    @POST
    @Path("{slug}/scan")
    public Response scan(@PathParam("slug") String slug) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) {
            return BridgeResponse.of(bridge.call("bridge.post_scan_html", slug));
        }
        try {
            java.nio.file.Path postsDir    = cfg.postsDir();
            java.nio.file.Path enrichedDir = cfg.enrichedDir();
            java.nio.file.Path htmlPath    = postsDir.resolve(slug + ".html");

            if (!java.nio.file.Files.exists(htmlPath)) {
                return Response.status(404)
                        .header("Content-Type",                "application/json; charset=utf-8")
                        .header("Access-Control-Allow-Origin", "*")
                        .entity("{\"error\":\"HTML not found: " + slug + "\"}").build();
            }

            java.nio.file.Path enrichedPath = enrichedDir.resolve(slug + ".html");

            // Enrich if not yet enriched (Java — Enricher.java, Phase 5)
            if (!java.nio.file.Files.exists(enrichedPath)) {
                try {
                    Map<String, Integer> enrichStats = new Enricher().enrich(
                            htmlPath, enrichedPath, cfg.assetsDir(), cfg.githubToken());
                    stateStore.markEnriched(slug, new java.util.HashMap<>(enrichStats));
                } catch (Exception enrichEx) {
                    System.err.println("Warning: enrichment failed for " + slug + ": " + enrichEx.getMessage());
                }
            }

            // Apply code block fixes to enriched copy (Java)
            java.nio.file.Path scanPath = java.nio.file.Files.exists(enrichedPath) ? enrichedPath : htmlPath;
            if (java.nio.file.Files.exists(enrichedPath)) {
                try {
                    org.jsoup.nodes.Document soup = org.jsoup.Jsoup.parse(
                            java.nio.file.Files.readString(enrichedPath));
                    if (CodeBlockFixer.apply(soup)) {
                        java.nio.file.Files.writeString(enrichedPath, soup.outerHtml());
                    }
                } catch (Exception ignored) {}
            }

            // Scan HTML issues (Java)
            java.util.List<ScanHtml.Issue> rawIssues = ScanHtml.scanPost(scanPath, postsDir);
            java.util.List<java.util.Map<String, Object>> issues = rawIssues.stream().map(i ->
                    java.util.Map.<String, Object>of(
                            "type",     i.type(),
                            "level",    i.level(),
                            "check",    i.type(),
                            "detail",   i.detail(),
                            "selector", i.selector() != null ? i.selector() : ""
                    )).collect(java.util.stream.Collectors.toList());
            stateStore.setHtmlIssues(slug, issues, null, null);

            // Scan assets (Java)
            try {
                ScanAssets.Result assets = ScanAssets.scan(scanPath, htmlPath, cfg.serveRoot());
                stateStore.update(slug, java.util.Map.of("assets", java.util.Map.of(
                        "total",      assets.total(),
                        "localised",  assets.localised(),
                        "broken",     assets.broken(),
                        "checked_at", java.time.Instant.now().toString().substring(0, 19)
                )));
            } catch (Exception ignored) {}

            ObjectNode post = stateStore.get(slug);
            return ok(post != null ? post.toString() : "{}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    // ── Dismiss ───────────────────────────────────────────────────────────────

    @POST
    @Path("{slug}/dismiss-html-check")
    public Response dismiss(@PathParam("slug") String slug, String body) {
        try {
            ObjectNode patch = (body != null && !body.isBlank())
                    ? (ObjectNode) MAPPER.readTree(body)
                    : MAPPER.createObjectNode();
            String issueType = patch.path("type").asText("");
            if (issueType.isEmpty()) return Response.status(400)
                    .header("Content-Type",                "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .entity("{\"error\":\"type required\"}").build();
            stateStore.dismissHtmlCheck(slug, issueType);
            ObjectNode post = stateStore.get(slug);
            return ok(post != null ? post.toString() : "{}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    @DELETE
    @Path("{slug}/dismiss-html-check/{type}")
    public Response undismiss(@PathParam("slug") String slug,
                               @PathParam("type") String type) {
        stateStore.undismissHtmlCheck(slug, type);
        return scan(slug);  // re-scan immediately so the issue reappears
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
